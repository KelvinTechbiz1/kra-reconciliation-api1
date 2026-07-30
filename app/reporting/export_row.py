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
            )
        )
    return rows
