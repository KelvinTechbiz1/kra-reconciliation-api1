import datetime
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List
from app.core.config import get_settings
from app.core.exceptions import SAPQueryError
from app.services.vat_normalizer import vat_normalizer
from app.utils.vat_utils import normalize_vat_rate
from app.domain.document_types import CanonicalReconciliationRow, IngestionProvenance

logger = logging.getLogger(__name__)


def parse_sap_date(date_val: Any) -> datetime.date:
    """
    Parses various date formats from SAP Service Layer into a python date object.
    """
    if isinstance(date_val, datetime.date):
        return date_val
    if isinstance(date_val, datetime.datetime):
        return date_val.date()

    date_str = str(date_val).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    try:
        return datetime.date.fromisoformat(date_str[:10])
    except ValueError:
        raise ValueError(f"Invalid SAP DocDate format: '{date_val}'")


def extract_cu_number(raw_document: Dict[str, Any], cu_field: str) -> str:
    """
    Extracts the CU (Control Unit) number from a raw SAP document using the configured
    SAP field name. Strips surrounding whitespace and a leading pipe '|' (SAP UDF convention).
    Centralizing this makes future field-specific tweaks a one-function change.
    """
    value = raw_document.get(cu_field)
    return str(value).strip().lstrip("|").strip() if value else ""


def map_sap_document_to_canonical_rows(
    raw_document: Dict[str, Any],
    source_document_type: str,
    endpoint_name: str,
    reconciliation_type: str = "sales",
    reconciliation_session_id: str = "N/A",
    purchase_cu_source: str = "U_CUINV",
    base_amount_policy: str | None = None,
) -> List[CanonicalReconciliationRow]:
    """
    Flattens a raw SAP document and maps it to a list of CanonicalReconciliationRow objects.
    Applies configurable base amount policies, aggregates by VAT group, applies sign normalization,
    and warns on missing/invalid fields.
    """
    settings = get_settings()
    # Per-company policy from system_settings takes precedence; falls back to the
    # global env setting (SAP_BASE_AMOUNT_POLICY) when no explicit policy is passed.
    policy = str(base_amount_policy).lower() if base_amount_policy is not None else settings.sap_base_amount_policy.value

    # Extract header fields
    invoice_number_raw = raw_document.get("DocNum")
    if invoice_number_raw is None:
        raise SAPQueryError(f"SAP {source_document_type} is missing required field: DocNum")
    invoice_number = str(invoice_number_raw).strip()

    partner_name_raw = raw_document.get("CardName")
    partner_name = str(partner_name_raw).strip() if partner_name_raw is not None else ""

    doc_date_raw = raw_document.get("DocDate")
    if doc_date_raw is None:
        raise SAPQueryError(f"SAP {source_document_type} {invoice_number} is missing required field: DocDate")

    try:
        invoice_date = parse_sap_date(doc_date_raw)
    except ValueError as exc:
        raise SAPQueryError(f"SAP {source_document_type} {invoice_number} has invalid DocDate: {exc}")

    # Fallbacks and warnings for PIN
    raw_pin = raw_document.get("FederalTaxID")
    if not raw_pin:
        pin = ""
        logger.warning(
            f"[ReconciliationSession: {reconciliation_session_id}] {source_document_type} {invoice_number} has missing FederalTaxID; using empty string."
        )
    else:
        pin = str(raw_pin).strip()

    # CU Number (Relaxed validation, allows empty/missing)
    # For purchases, the source SAP field is configurable (purchase_cu_source);
    # for sales the caller passes "U_CUINV" (the standard field).
    cu_number = extract_cu_number(raw_document, purchase_cu_source)

    document_lines = raw_document.get("DocumentLines", [])
    if not document_lines:
        logger.warning(
            f"[ReconciliationSession: {reconciliation_session_id}] {source_document_type} {invoice_number} has no DocumentLines."
        )
        return []

    # Determine exact document type (differentiate Debit Memos from standard Invoices)
    actual_document_type = source_document_type
    subtype = raw_document.get("DocumentSubType")
    if source_document_type == "Invoice" and subtype == "bod_DebitMemo":
        actual_document_type = "DebitNote"

    valid_lines = []
    for line_idx, line in enumerate(document_lines):
        # 1. Tax Percentage / VAT Group Extraction
        tax_pct_raw = line.get("TaxPercentagePerRow")
        vat_group_raw = line.get("VatGroup")

        if tax_pct_raw is not None:
            try:
                tax_pct = Decimal(str(tax_pct_raw).strip())
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise SAPQueryError(
                    f"SAP {source_document_type} {invoice_number} line {line_idx} has invalid TaxPercentagePerRow: {exc}"
                )

            if tax_pct > 0:
                vat_group_str = normalize_vat_rate(tax_pct)
            else:
                # Rate is 0.0: Check if VatGroup specifies EXEMPT classification
                vat_group_raw_str = str(vat_group_raw).strip() if vat_group_raw is not None else ""
                if vat_group_raw_str and vat_normalizer.normalize("sap", reconciliation_type, vat_group_raw_str) == "EXEMPT":
                    vat_group_str = "EXEMPT"
                else:
                    vat_group_str = "0"
        elif vat_group_raw is not None:
            vat_group_str = str(vat_group_raw).strip()
            if not vat_group_str:
                raise SAPQueryError(
                    f"SAP {source_document_type} {invoice_number} line {line_idx} has empty VatGroup"
                )
            vat_group_str = vat_normalizer.normalize("sap", reconciliation_type, vat_group_str)
        else:
            raise SAPQueryError(
                f"SAP {source_document_type} {invoice_number} line {line_idx} has missing tax fields (neither TaxPercentagePerRow nor VatGroup present)"
            )

        # 2. Base Amount (LineTotal)
        line_total_raw = line.get("LineTotal")
        if line_total_raw is None:
            raise SAPQueryError(
                f"SAP {source_document_type} {invoice_number} line {line_idx} is missing required field: LineTotal"
            )

        try:
            base_amount = Decimal(str(line_total_raw).strip())
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise SAPQueryError(
                f"SAP {source_document_type} {invoice_number} line {line_idx} has invalid LineTotal: {exc}"
            )

        # 3. Base Amount Policy Check
        # Negative base amounts (e.g. Credit Notes, adjustments) are explicitly allowed.
        # Zero base amounts are filtered or rejected based on policy.
        if base_amount == 0:
            if policy == "skip":
                logger.warning(
                    f"[ReconciliationSession: {reconciliation_session_id}] {source_document_type} {invoice_number} line {line_idx} skipped because base_amount is 0.00 under policy 'skip'."
                )
                continue
            elif policy in ("reject", "reject_session"):
                logger.error(
                    f"[ReconciliationSession: {reconciliation_session_id}] {source_document_type} {invoice_number} line {line_idx} rejected because base_amount is 0.00 under policy 'reject'."
                )
                raise SAPQueryError(
                    f"SAP {source_document_type} {invoice_number} line {line_idx} rejected: Base Amount is zero."
                )
            # Under ALLOW ("allow") or TREAT_AS_ZERO, zero amount lines are kept and processed

        valid_lines.append((vat_group_str, base_amount))

    # Group by normalized VAT Group and sum LineTotal
    grouped_totals = {}
    for vat_group_str, base_amount in valid_lines:
        grouped_totals[vat_group_str] = grouped_totals.get(vat_group_str, Decimal("0.00")) + base_amount

    # Create canonical reconciliation rows
    canonical_rows = []
    for vat_group_str, total_amount in grouped_totals.items():
        # Sign normalization: +abs for Invoices/DebitNotes, -abs for CreditNotes
        if actual_document_type in ("Invoice", "DebitNote"):
            normalized_amount = abs(total_amount)
        elif actual_document_type == "CreditNote":
            normalized_amount = -abs(total_amount)
        else:
            normalized_amount = abs(total_amount)

        provenance = IngestionProvenance(
            session_source=f"SAP {reconciliation_type.capitalize()}",
            source_endpoint=endpoint_name,
            source_table=None,
            sap_object_type=None,
            source_document_type=actual_document_type,
            doc_entry=raw_document.get("DocEntry"),
            doc_num=invoice_number,
            base_doc_entry=None,
            base_doc_num=None,
            doc_object_code=None,
            raw_amount=total_amount,
            normalized_amount=normalized_amount
        )

        row = CanonicalReconciliationRow(
            pin=pin,
            partner_name=partner_name,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            cu_number=cu_number,
            vat_group=vat_group_str,
            base_amount=normalized_amount.quantize(Decimal("0.01")),
            provenance=provenance
        )
        canonical_rows.append(row)

    return canonical_rows


