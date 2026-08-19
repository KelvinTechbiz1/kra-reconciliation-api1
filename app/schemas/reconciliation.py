from enum import Enum
from decimal import Decimal
from pydantic import BaseModel
from app.schemas.invoice import Invoice

# Re-exported from domain for backward compatibility — import from here or from domain directly
from app.domain.reconciliation_status import ReconciliationStatus  # noqa: F401

class DifferenceField(str, Enum):
    BASE_AMOUNT = "base_amount"
    VAT_GROUP = "vat_group"
    INVOICE_DATE = "invoice_date"
    CU_NUMBER = "cu_number"
    PIN = "pin"

class Difference(BaseModel):
    field: DifferenceField
    match: bool
    sap_value: str
    kra_value: str

from app.domain.invoice_type import InvoiceType

class ReconciliationResult(BaseModel):
    cu_number: str
    sap: Invoice | None = None
    kra: Invoice | None = None
    status: ReconciliationStatus
    invoice_type: InvoiceType = InvoiceType.SINGLE_TAX
    amount_match: bool
    vat_match: bool
    date_match: bool
    partner_name_matches: bool = True
    pin_matches: bool = True
    differences: list[Difference]
    sap_source_index: int | None = None
    kra_source_index: int | None = None

    sap_base_16: Decimal | None = None
    sap_base_8: Decimal | None = None
    sap_base_0: Decimal | None = None
    sap_base_exempt: Decimal | None = None

    kra_base_16: Decimal | None = None
    kra_base_8: Decimal | None = None
    kra_base_0: Decimal | None = None
    kra_base_exempt: Decimal | None = None

class MismatchStats(BaseModel):
    amount: int = 0
    vat: int = 0
    date: int = 0

class ReconciliationSummary(BaseModel):
    total_sap: int
    total_kra: int
    matches: int
    missing_in_sap: int
    missing_in_kra: int
    missing_cu: int = 0
    mismatches: int
    duplicate_cu: int
    match_percentage: float
    completion_percentage: float
    total_reconciled_rows: int = 0
    mismatch_stats: MismatchStats

class ReconciliationCompareRequest(BaseModel):
    session_id: str

class ReconciliationResponse(BaseModel):
    session_id: str
    summary: ReconciliationSummary

class PaginatedReconciliationResultsResponse(BaseModel):
    session_id: str
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[ReconciliationResult]
    # The filter this page was built with, echoed back so a late response for a
    # superseded filter can be recognised and discarded.
    status_filter: str = "All"
    # Whole-session totals per filter chip, independent of the page being viewed.
    status_counts: dict[str, int] = {}

