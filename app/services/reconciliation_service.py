from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from typing import Sequence, Dict, List, Set, Tuple, Optional
import difflib

from app.schemas.invoice import Invoice, InvoiceSource
from app.schemas.reconciliation import (
    DifferenceField,
    Difference,
    ReconciliationResult,
    MismatchStats,
    ReconciliationSummary
)
from app.domain.reconciliation_status import ReconciliationStatus
from app.domain.reconciliation_constants import STATUS_PRIORITY
from app.domain.normalized_invoice import NormalizedInvoice, normalize_and_group_invoices
from app.domain.invoice_type import InvoiceType
from app.services.normalization import normalize_partner_name, normalize_pin


def check_pin_matches(sap_pin_raw: Invoice | str | None, kra_pin_raw: Invoice | str | None) -> bool:
    """
    PIN matches are advisory. If either PIN is missing, we consider it a 'match' 
    so the UI does not highlight it as a difference.
    """
    sap_str = sap_pin_raw.pin if isinstance(sap_pin_raw, Invoice) else sap_pin_raw
    kra_str = kra_pin_raw.pin if isinstance(kra_pin_raw, Invoice) else kra_pin_raw

    sap_pin = normalize_pin(sap_str)
    kra_pin = normalize_pin(kra_str)
    if not sap_pin or not kra_pin:
        return True
    return sap_pin == kra_pin


def check_partner_name_matches(sap_name_raw: Invoice | str | None, kra_name_raw: Invoice | str | None) -> bool:
    """
    Partner Name matches are advisory. If either is missing, they do not match.
    """
    sap_str = sap_name_raw.partner_name if isinstance(sap_name_raw, Invoice) else sap_name_raw
    kra_str = kra_name_raw.partner_name if isinstance(kra_name_raw, Invoice) else kra_name_raw

    if not sap_str or not kra_str:
        return False
        
    sap_norm = normalize_partner_name(sap_str)
    kra_norm = normalize_partner_name(kra_str)
    
    if sap_norm == kra_norm:
        return True
        
    ratio = difflib.SequenceMatcher(None, sap_norm, kra_norm).ratio()
    return ratio >= 0.85


def validate_tax_breakdowns(
    sap_breakdown: Dict[str, Decimal],
    kra_breakdown: Dict[str, Decimal],
    tolerance: Decimal
) -> bool:
    """
    Always-on tax breakdown validation comparing category-by-category allocations.
    Returns True if tax distributions match for all tax rates, False otherwise.
    """
    all_keys = set(sap_breakdown.keys()) | set(kra_breakdown.keys())
    for key in all_keys:
        sap_val = sap_breakdown.get(key, Decimal("0.00"))
        kra_val = kra_breakdown.get(key, Decimal("0.00"))
        if abs(sap_val - kra_val) > tolerance:
            return False
    return True


def _format_vat_breakdown_str(breakdown: Dict[str, Decimal]) -> str:
    """Formats VAT breakdown dictionary into readable string."""
    if len(breakdown) == 1:
        return list(breakdown.keys())[0]
    return str(dict(breakdown))


def reconcile_invoices(
    sap: list[Invoice],
    kra: list[Invoice],
    amount_tolerance: Decimal = None
) -> tuple[ReconciliationSummary, list[ReconciliationResult]]:
    """
    Executes the 7-stage modular reconciliation pipeline:
    Stage 1: Preprocess Source Invoices
    Stage 2: Inspect Invoice Integrity (Classify missing CU numbers without discarding)
    Stage 3: Symmetric Normalization (Group by CU & build tax_breakdown with source_rows)
    Stage 4: Document Pairing by CU Number
    Stage 5: Document Validation (Amount, PIN, Date, Partner Name)
    Stage 6: Always-On Tax Breakdown Validation (Category breakdown comparison)
    Stage 7: Result Generation & Status Classification
    """
    if amount_tolerance is None:
        from app.core.config import get_settings
        amount_tolerance = get_settings().amount_tolerance

    results: list[ReconciliationResult] = []

    # Stage 1 & 2 & 3: Validate & Symmetrically Normalize ERP and KRA Data
    sap_norm_list, sap_missing_cu = normalize_and_group_invoices(sap)
    kra_norm_list, kra_missing_cu = normalize_and_group_invoices(kra)

    # Report rows with missing CU numbers (Data Preservation Principle)
    for inv, idx in sap_missing_cu:
        results.append(ReconciliationResult(
            cu_number="",
            sap=inv,
            kra=None,
            status=ReconciliationStatus.MISSING_CU_NUMBER,
            amount_match=False,
            vat_match=False,
            date_match=True,
            partner_name_matches=False,
            pin_matches=False,
            differences=[
                Difference(
                    field=DifferenceField.BASE_AMOUNT,
                    match=False,
                    sap_value="Missing CU Number",
                    kra_value="None"
                )
            ],
            sap_source_index=idx,
            kra_source_index=None
        ))

    for inv, idx in kra_missing_cu:
        results.append(ReconciliationResult(
            cu_number="",
            sap=None,
            kra=inv,
            status=ReconciliationStatus.MISSING_CU_NUMBER,
            amount_match=False,
            vat_match=False,
            date_match=True,
            partner_name_matches=False,
            pin_matches=False,
            differences=[
                Difference(
                    field=DifferenceField.BASE_AMOUNT,
                    match=False,
                    sap_value="None",
                    kra_value="Missing CU Number"
                )
            ],
            sap_source_index=None,
            kra_source_index=idx
        ))

    # Stage 4: Document Pairing (by CU Number & Fallback Heuristic)
    sap_map: Dict[str, NormalizedInvoice] = {norm.cu_number: norm for norm in sap_norm_list}
    kra_map: Dict[str, NormalizedInvoice] = {norm.cu_number: norm for norm in kra_norm_list}

    common_cus = set(sap_map.keys()) & set(kra_map.keys())
    sap_only_cus = set(sap_map.keys()) - set(kra_map.keys())
    kra_only_cus = set(kra_map.keys()) - set(sap_map.keys())

    # Stage 4b: Fallback Pairing for Minor CU Typos / OCR mismatches
    paired_tuples: List[Tuple[str, NormalizedInvoice, NormalizedInvoice]] = []
    for cu in common_cus:
        paired_tuples.append((cu, sap_map[cu], kra_map[cu]))

    fallback_matched_sap: Set[str] = set()
    fallback_matched_kra: Set[str] = set()

    for s_cu in sorted(sap_only_cus):
        s_norm = sap_map[s_cu]
        for k_cu in sorted(kra_only_cus):
            if k_cu in fallback_matched_kra:
                continue
            k_norm = kra_map[k_cu]

            # Matching base amount within tolerance AND matching partner PIN or Name
            if (s_norm.total_base * k_norm.total_base >= 0) and abs(s_norm.total_base - k_norm.total_base) <= amount_tolerance:
                p_match = check_partner_name_matches(s_norm.partner_name, k_norm.partner_name) or check_pin_matches(s_norm.pin, k_norm.pin)
                if p_match:
                    fallback_matched_sap.add(s_cu)
                    fallback_matched_kra.add(k_cu)
                    paired_tuples.append((s_cu, s_norm, k_norm))
                    break

    sap_only_cus -= fallback_matched_sap
    kra_only_cus -= fallback_matched_kra

    # Process Paired Documents (Stage 5, 6, 7)
    for cu, sap_norm, kra_norm in paired_tuples:

        # Stage 5: Document Validation Checks
        amount_match = (
            (sap_norm.total_base * kra_norm.total_base >= 0)
            and abs(sap_norm.total_base - kra_norm.total_base) <= amount_tolerance
        )
        pin_matches = check_pin_matches(sap_norm.pin, kra_norm.pin)
        partner_name_matches = check_partner_name_matches(sap_norm.partner_name, kra_norm.partner_name)
        date_match = True

        # Stage 6: Always-On Tax Breakdown Validation
        vat_breakdown_match = validate_tax_breakdowns(
            sap_norm.tax_breakdown, kra_norm.tax_breakdown, amount_tolerance
        )

        cu_match = (sap_norm.cu_number == kra_norm.cu_number)

        differences: list[Difference] = []
        if not cu_match:
            differences.append(Difference(
                field=DifferenceField.CU_NUMBER,
                match=False,
                sap_value=sap_norm.cu_number,
                kra_value=kra_norm.cu_number
            ))

        if not amount_match:
            differences.append(Difference(
                field=DifferenceField.BASE_AMOUNT,
                match=False,
                sap_value=f"{sap_norm.total_base:.2f}",
                kra_value=f"{kra_norm.total_base:.2f}"
            ))
        elif not vat_breakdown_match:
            differences.append(Difference(
                field=DifferenceField.VAT_GROUP,
                match=False,
                sap_value=_format_vat_breakdown_str(sap_norm.tax_breakdown),
                kra_value=_format_vat_breakdown_str(kra_norm.tax_breakdown)
            ))

        # Stage 7: Status Classification
        if len(differences) > 1:
            status = ReconciliationStatus.MULTIPLE_MISMATCHES
        elif not amount_match:
            status = ReconciliationStatus.AMOUNT_MISMATCH
        elif not vat_breakdown_match:
            status = ReconciliationStatus.VAT_MISMATCH
        elif not cu_match:
            status = ReconciliationStatus.VAT_MISMATCH  # route to 02 Exceptions.xlsx for CU review
        else:
            status = ReconciliationStatus.MATCH

        is_mixed = sap_norm.is_mixed_tax or kra_norm.is_mixed_tax
        inv_type = InvoiceType.MIXED_TAX if is_mixed else InvoiceType.SINGLE_TAX

        results.append(ReconciliationResult(
            cu_number=cu,
            sap=sap_norm.representative_invoice,
            kra=kra_norm.representative_invoice,
            status=status,
            invoice_type=inv_type,
            amount_match=amount_match,
            vat_match=vat_breakdown_match,
            date_match=date_match,
            partner_name_matches=partner_name_matches,
            pin_matches=pin_matches,
            differences=differences,
            sap_source_index=sap_norm.first_source_index,
            kra_source_index=kra_norm.first_source_index
        ))

    # Stage 7: Unpaired SAP Invoices
    for cu in sap_only_cus:
        sap_norm = sap_map[cu]
        inv_type = InvoiceType.MIXED_TAX if sap_norm.is_mixed_tax else InvoiceType.SINGLE_TAX
        results.append(ReconciliationResult(
            cu_number=cu,
            sap=sap_norm.representative_invoice,
            kra=None,
            status=ReconciliationStatus.MISSING_IN_KRA,
            invoice_type=inv_type,
            amount_match=False,
            vat_match=False,
            date_match=True,
            partner_name_matches=False,
            pin_matches=False,
            differences=[],
            sap_source_index=sap_norm.first_source_index,
            kra_source_index=None
        ))

    # Stage 7: Unpaired KRA Invoices
    for cu in kra_only_cus:
        kra_norm = kra_map[cu]
        inv_type = InvoiceType.MIXED_TAX if kra_norm.is_mixed_tax else InvoiceType.SINGLE_TAX
        results.append(ReconciliationResult(
            cu_number=cu,
            sap=None,
            kra=kra_norm.representative_invoice,
            status=ReconciliationStatus.MISSING_IN_SAP,
            invoice_type=inv_type,
            amount_match=False,
            vat_match=False,
            date_match=True,
            partner_name_matches=False,
            pin_matches=False,
            differences=[],
            sap_source_index=None,
            kra_source_index=kra_norm.first_source_index
        ))

    # Calculate summary metrics
    total_sap = len(sap)
    total_kra = len(kra)
    matches = sum(1 for r in results if r.status == ReconciliationStatus.MATCH)
    missing_in_sap = sum(1 for r in results if r.status == ReconciliationStatus.MISSING_IN_SAP)
    missing_in_kra = sum(1 for r in results if r.status == ReconciliationStatus.MISSING_IN_KRA)
    missing_cu = sum(1 for r in results if r.status == ReconciliationStatus.MISSING_CU_NUMBER)
    duplicate_cu = sum(1 for r in results if r.status == ReconciliationStatus.DUPLICATE_SOURCE_KEY)
    mismatches = sum(1 for r in results if r.status in (
        ReconciliationStatus.AMOUNT_MISMATCH,
        ReconciliationStatus.VAT_MISMATCH,
        ReconciliationStatus.MULTIPLE_MISMATCHES
    ))

    total_distinct = len(results)
    match_percentage = (matches / total_distinct) * 100.0 if total_distinct > 0 else 100.0
    completion_percentage = (matches / total_sap) * 100.0 if total_sap > 0 else 100.0

    mismatch_stats = MismatchStats(amount=0, vat=0, date=0)
    for r in results:
        if r.status in (
            ReconciliationStatus.AMOUNT_MISMATCH,
            ReconciliationStatus.VAT_MISMATCH,
            ReconciliationStatus.MULTIPLE_MISMATCHES
        ):
            if not r.amount_match:
                mismatch_stats.amount += 1
            if not r.vat_match:
                mismatch_stats.vat += 1

    summary = ReconciliationSummary(
        total_sap=total_sap,
        total_kra=total_kra,
        matches=matches,
        missing_in_sap=missing_in_sap,
        missing_in_kra=missing_in_kra,
        missing_cu=missing_cu,
        mismatches=mismatches,
        duplicate_cu=duplicate_cu,
        match_percentage=match_percentage,
        completion_percentage=completion_percentage,
        total_reconciled_rows=total_distinct,
        mismatch_stats=mismatch_stats
    )

    # Sort results deterministically by:
    # 1. status priority (severity)
    # 2. CU number
    def get_sort_key(r: ReconciliationResult):
        sap_idx = r.sap_source_index if r.sap_source_index is not None else 999999
        kra_idx = r.kra_source_index if r.kra_source_index is not None else 999999
        return (
            STATUS_PRIORITY.get(r.status, 99),
            r.cu_number,
            sap_idx,
            kra_idx
        )

    results.sort(key=get_sort_key)

    return summary, results
