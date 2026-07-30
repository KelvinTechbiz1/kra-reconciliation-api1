from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.reconciliation_status import ReconciliationStatus


from app.domain.invoice_type import InvoiceType

@dataclass(frozen=True)
class ReconciliationProjection:
    """Repository-layer projection of session_reconciliation_results.

    Frozen to prevent accidental mutation. Carries only persisted fields —
    no derived presentation data.
    """

    cu_number:           str
    invoice_type:        InvoiceType
    status:              ReconciliationStatus
    amount_match:        bool
    vat_match:           bool
    date_match:          bool
    sap_invoice_number:  str | None
    sap_partner_name:    str | None
    sap_pin:             str | None
    sap_invoice_date:    date | None
    sap_base_amount:     Decimal | None
    sap_vat_group:       str | None
    kra_invoice_number:  str | None
    kra_partner_name:    str | None
    kra_pin:             str | None
    kra_invoice_date:    date | None
    kra_base_amount:     Decimal | None
    kra_vat_group:       str | None
