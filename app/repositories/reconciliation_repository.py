from sqlalchemy import case
from sqlalchemy.orm import Session

from app.domain.reconciliation_constants import STATUS_ORDER, STATUS_PRIORITY
from app.domain.reconciliation_status import ReconciliationStatus
from app.models.reconciliation_session import SessionReconciliationResult
from app.repositories.projections import ReconciliationProjection

# Ranks a row by STATUS_ORDER so the statuses needing attention lead.
#
# Keyed on the enum NAME, not its value: the column is Enum(..., native_enum=False),
# and SQLAlchemy persists `MATCH`, not `Match`. Keying on `.value` compiled to a CASE
# that could never match, so every row scored `else_` and the ordering silently
# collapsed to the tie-breakers.
STATUS_ORDER_EXPR = case(
    {s.name: p for s, p in STATUS_PRIORITY.items()},
    value=SessionReconciliationResult.status,
    else_=len(STATUS_ORDER) + 1,
)


def get_projections(session_id: str, db: Session) -> list[ReconciliationProjection]:
    """Fetch ordered reconciliation projections for a session.

    Ordered by (status_priority, cu_number, sap_invoice_number, kra_invoice_number).
    Explicit tie-breakers prevent non-deterministic ordering for duplicate CUs.
    """
    rows = (
        db.query(SessionReconciliationResult)
        .filter(SessionReconciliationResult.session_id == session_id)
        .order_by(
            STATUS_ORDER_EXPR,
            SessionReconciliationResult.cu_number,
            SessionReconciliationResult.sap_invoice_number,
            SessionReconciliationResult.kra_invoice_number,
        )
        .all()
    )
    return [_to_projection(r) for r in rows]


from app.domain.invoice_type import InvoiceType


def _to_projection(r: SessionReconciliationResult) -> ReconciliationProjection:
    """Explicit constructor — no reflection, compile-time field safety.

    Fail-fast on invalid status: ReconciliationStatus(r.status) raises ValueError
    if the DB contains an unrecognised status string. This is intentional — a corrupted
    or migrated status aborts the export rather than silently producing wrong data.
    The ValueError propagates to the endpoint and returns HTTP 500.
    """
    raw_type = getattr(r, "invoice_type", None) or "Single Tax"
    inv_type = InvoiceType(raw_type) if raw_type in [e.value for e in InvoiceType] else InvoiceType.SINGLE_TAX

    return ReconciliationProjection(
        cu_number=r.cu_number,
        invoice_type=inv_type,
        status=ReconciliationStatus(r.status),
        amount_match=r.amount_match,
        vat_match=r.vat_match,
        date_match=r.date_match,
        sap_invoice_number=r.sap_invoice_number,
        sap_partner_name=r.sap_partner_name,
        sap_pin=r.sap_pin,
        sap_invoice_date=r.sap_invoice_date,
        sap_base_amount=r.sap_base_amount,
        sap_vat_group=r.sap_vat_group,
        sap_cu_number=getattr(r, "sap_cu_number", None) or r.cu_number,
        sap_base_16=getattr(r, "sap_base_16", None),
        sap_base_8=getattr(r, "sap_base_8", None),
        sap_base_0=getattr(r, "sap_base_0", None),
        sap_base_exempt=getattr(r, "sap_base_exempt", None),

        kra_invoice_number=r.kra_invoice_number,
        kra_partner_name=r.kra_partner_name,
        kra_pin=r.kra_pin,
        kra_invoice_date=r.kra_invoice_date,
        kra_base_amount=r.kra_base_amount,
        kra_vat_group=r.kra_vat_group,
        kra_cu_number=getattr(r, "kra_cu_number", None) or r.cu_number,
        kra_base_16=getattr(r, "kra_base_16", None),
        kra_base_8=getattr(r, "kra_base_8", None),
        kra_base_0=getattr(r, "kra_base_0", None),
        kra_base_exempt=getattr(r, "kra_base_exempt", None),
    )
