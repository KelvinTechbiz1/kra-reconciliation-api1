from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.invoice_type import InvoiceType
from app.domain.reconciliation_constants import REMARK_MAP
from app.domain.reconciliation_status import ReconciliationStatus
from app.repositories.projections import ReconciliationProjection


@dataclass(frozen=True)
class ReconciliationExportRow:
    """Reporting-layer DTO. Carries derived presentation fields (remark, symbols, invoice_type).

    Lives in reporting/, not domain/ — it belongs to the export layer.
    """

    cu_number:           str
    invoice_type:        str         # "Single Tax" or "Mixed Tax"
    status:              ReconciliationStatus
    remark:              str         # derived from REMARK_MAP at export time
    amount_match:        bool
    vat_match:           bool
    date_match:          bool
    amount_match_symbol: str         # "✓" or "✗"
    vat_match_symbol:    str         # "✓", "✗", or "—"
    sap_invoice_number:  str | None
    sap_partner_name:    str | None
    sap_pin:             str | None
    sap_invoice_date:    date | None
    sap_base_amount:     Decimal | None
    sap_vat_group:       str | None
    sap_base_16:          Decimal | None = None
    sap_base_8:           Decimal | None = None
    sap_base_0:           Decimal | None = None
    sap_base_exempt:      Decimal | None = None

    kra_invoice_number:  str | None = None
    kra_partner_name:    str | None = None
    kra_pin:             str | None = None
    kra_invoice_date:    date | None = None
    kra_base_amount:     Decimal | None = None
    kra_vat_group:       str | None = None
    kra_base_16:          Decimal | None = None
    kra_base_8:          Decimal | None = None
    kra_base_0:          Decimal | None = None
    kra_base_exempt:      Decimal | None = None
    sap_tax_breakdown:   str = "—"
    kra_tax_breakdown:   str = "—"


def _format_tax_breakdown(
    vat_group: str | None,
    b16: Decimal | None,
    b8: Decimal | None,
    b0: Decimal | None,
    b_exempt: Decimal | None,
    base_amount: Decimal | None,
) -> str:
    parts: list[str] = []
    if b16 is not None and b16 > 0:
        parts.append(f"16%: {b16:,.2f}")
    if b8 is not None and b8 > 0:
        parts.append(f"8%: {b8:,.2f}")
    if b0 is not None and b0 > 0:
        parts.append(f"0%: {b0:,.2f}")
    if b_exempt is not None and b_exempt > 0:
        parts.append(f"EXEMPT: {b_exempt:,.2f}")

    if parts:
        return "\n".join(parts)

    if not vat_group and base_amount is None:
        return "—"

    vat_str = vat_group or "16%"
    amt_str = f"{base_amount:,.2f}" if base_amount is not None else "—"
    return f"{vat_str}: {amt_str}"


def to_export_rows(projections: list[ReconciliationProjection]) -> list[ReconciliationExportRow]:
    """Explicit constructor — no reflection. Future field additions are compile-time errors."""
    rows: list[ReconciliationExportRow] = []
    for p in projections:
        # Unpaired / Missing rows have no counterpart to compare against, so match symbols are "—"
        if p.status in (
            ReconciliationStatus.MISSING_IN_SAP,
            ReconciliationStatus.MISSING_IN_KRA,
            ReconciliationStatus.MISSING_CU_NUMBER,
            ReconciliationStatus.DUPLICATE_SOURCE_KEY,
        ):
            amt_sym = "—"
            vat_sym = "—"
        elif not p.amount_match:
            amt_sym = "✗"
            vat_sym = "—"
        elif p.vat_match:
            amt_sym = "✓"
            vat_sym = "✓"
        else:
            amt_sym = "✓"
            vat_sym = "✗"

        inv_type_str = p.invoice_type.value if hasattr(p.invoice_type, "value") else str(p.invoice_type)

        sap_bd = "—"
        if p.status != ReconciliationStatus.MISSING_IN_SAP:
            sap_bd = _format_tax_breakdown(
                p.sap_vat_group, p.sap_base_16, p.sap_base_8, p.sap_base_0, p.sap_base_exempt, p.sap_base_amount
            )

        kra_bd = "—"
        if p.status not in (ReconciliationStatus.MISSING_IN_KRA, ReconciliationStatus.MISSING_CU_NUMBER):
            kra_bd = _format_tax_breakdown(
                p.kra_vat_group, p.kra_base_16, p.kra_base_8, p.kra_base_0, p.kra_base_exempt, p.kra_base_amount
            )

        rows.append(
            ReconciliationExportRow(
                cu_number=p.cu_number,
                invoice_type=inv_type_str,
                status=p.status,
                remark=REMARK_MAP[p.status],
                amount_match=p.amount_match,
                vat_match=p.vat_match,
                date_match=p.date_match,
                amount_match_symbol=amt_sym,
                vat_match_symbol=vat_sym,
                sap_invoice_number=p.sap_invoice_number,
                sap_partner_name=p.sap_partner_name,
                sap_pin=p.sap_pin,
                sap_invoice_date=p.sap_invoice_date,
                sap_base_amount=p.sap_base_amount,
                sap_vat_group=p.sap_vat_group,
                sap_base_16=p.sap_base_16,
                sap_base_8=p.sap_base_8,
                sap_base_0=p.sap_base_0,
                sap_base_exempt=p.sap_base_exempt,
                sap_tax_breakdown=sap_bd,
                kra_invoice_number=p.kra_invoice_number,
                kra_partner_name=p.kra_partner_name,
                kra_pin=p.kra_pin,
                kra_invoice_date=p.kra_invoice_date,
                kra_base_amount=p.kra_base_amount,
                kra_vat_group=p.kra_vat_group,
                kra_base_16=p.kra_base_16,
                kra_base_8=p.kra_base_8,
                kra_base_0=p.kra_base_0,
                kra_base_exempt=p.kra_base_exempt,
                kra_tax_breakdown=kra_bd,
            )
        )
    return rows
