from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

from app.schemas.invoice import Invoice, InvoiceSource


@dataclass(frozen=True)
class NormalizedInvoice:
    """
    Internal domain model representing a logical invoice accumulated at the CU Number level.
    Preserves all raw source rows in `source_rows` for complete auditability & drill-down.
    """
    cu_number: str
    invoice_number: str
    pin: str
    partner_name: str
    invoice_date: Optional[date]
    total_base: Decimal
    total_vat: Decimal
    tax_breakdown: Dict[str, Decimal]  # e.g., {"16": Decimal("520.69"), "0": Decimal("2784.00")}
    source_rows: List[Invoice]
    source: InvoiceSource
    first_source_index: int = 0

    @property
    def is_mixed_tax(self) -> bool:
        return len(self.tax_breakdown) > 1

    @property
    def base_16(self) -> Decimal:
        return self.tax_breakdown.get("16", Decimal("0.00"))

    @property
    def base_8(self) -> Decimal:
        return self.tax_breakdown.get("8", Decimal("0.00"))

    @property
    def base_0(self) -> Decimal:
        return self.tax_breakdown.get("0", Decimal("0.00"))

    @property
    def base_exempt(self) -> Decimal:
        return self.tax_breakdown.get("EXEMPT", Decimal("0.00"))

    @property
    def invoice_type(self) -> "InvoiceType":
        from app.domain.invoice_type import InvoiceType
        return InvoiceType.MIXED_TAX if self.is_mixed_tax else InvoiceType.SINGLE_TAX

    @property
    def representative_invoice(self) -> Invoice:
        """
        Returns a single Invoice schema object representing the accumulated logical invoice.
        Used for backward-compatibility with API schemas, DB persistence, and exporters.
        """
        first = self.source_rows[0] if self.source_rows else None
        vat_grp = ", ".join(sorted(self.tax_breakdown.keys())) if self.tax_breakdown else "16"
        return Invoice(
            pin=self.pin or (first.pin if first else ""),
            partner_name=self.partner_name or (first.partner_name if first else ""),
            invoice_number=self.invoice_number or (first.invoice_number if first else ""),
            invoice_date=self.invoice_date or (first.invoice_date if first else None),
            cu_number=self.cu_number,
            vat_group=vat_grp,
            base_amount=self.total_base,
            source=self.source,
            provider=first.provider if first else None,
        )


def normalize_and_group_invoices(
    invoices: List[Invoice]
) -> Tuple[List[NormalizedInvoice], List[Tuple[Invoice, int]]]:
    """
    Groups raw Invoice items sharing the same CU Number into a single NormalizedInvoice.
    Deterministic metadata selection rules:
    - total_base: SUM(base_amount)
    - tax_breakdown: SUM(base_amount) per vat_group
    - invoice_number: first non-empty value
    - pin: first non-empty value
    - partner_name: first non-empty value
    - invoice_date: earliest valid date

    Returns:
    - valid_normalized: list of NormalizedInvoice objects for non-empty CU Numbers.
    - invalid_missing_cu: list of tuples (Invoice, source_index) where cu_number is missing/empty.
    """
    invalid_missing_cu: List[Tuple[Invoice, int]] = []
    groups: Dict[str, List[Tuple[Invoice, int]]] = defaultdict(list)

    for idx, inv in enumerate(invoices):
        cu = inv.normalized_cu_number
        if not cu or cu.strip() == "":
            invalid_missing_cu.append((inv, idx))
        else:
            groups[cu].append((inv, idx))

    valid_normalized: List[NormalizedInvoice] = []

    for cu_num, items in groups.items():
        total_base = Decimal("0.00")
        total_vat = Decimal("0.00")
        tax_breakdown: Dict[str, Decimal] = defaultdict(Decimal)

        rows = [inv for inv, _ in items]
        first_source_idx = items[0][1] if items else 0

        first_inv_num = ""
        first_pin = ""
        first_partner = ""
        earliest_date: Optional[date] = None

        for inv in rows:
            if inv.base_amount is not None:
                total_base += inv.base_amount
                vat_key = inv.normalized_vat_group or "UNKNOWN"
                tax_breakdown[vat_key] += inv.base_amount

            if not first_inv_num and inv.invoice_number and inv.invoice_number.strip():
                first_inv_num = inv.invoice_number.strip()

            if not first_pin and inv.normalized_pin:
                first_pin = inv.normalized_pin

            if not first_partner and inv.partner_name and inv.partner_name.strip():
                first_partner = inv.partner_name.strip()

            if inv.invoice_date is not None:
                if earliest_date is None or inv.invoice_date < earliest_date:
                    earliest_date = inv.invoice_date

        source = rows[0].source if rows else InvoiceSource.KRA

        norm = NormalizedInvoice(
            cu_number=cu_num,
            invoice_number=first_inv_num,
            pin=first_pin,
            partner_name=first_partner,
            invoice_date=earliest_date,
            total_base=total_base.quantize(Decimal("0.01")),
            total_vat=total_vat.quantize(Decimal("0.01")),
            tax_breakdown=dict(tax_breakdown),
            source_rows=rows,
            source=source,
            first_source_index=first_source_idx
        )
        valid_normalized.append(norm)

    return valid_normalized, invalid_missing_cu
