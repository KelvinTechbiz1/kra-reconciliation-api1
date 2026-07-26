from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_serializer


class ReconciliationType(str, Enum):
    SALES = "sales"
    PURCHASES = "purchases"


class InvoiceSource(str, Enum):
    SAP = "SAP"
    KRA = "KRA"
    ERP = "ERP"


class Invoice(BaseModel):
    pin: str
    partner_name: str
    invoice_number: str
    invoice_date: Optional[date] = None
    cu_number: str
    vat_group: str
    base_amount: Optional[Decimal] = None
    source: InvoiceSource
    provider: Optional[str] = None


    @field_serializer("base_amount")
    def serialize_base_amount(self, base_amount: Optional[Decimal]) -> Optional[float]:
        return float(base_amount) if base_amount is not None else None

    @property
    def normalized_pin(self) -> str:
        return self.pin.strip().upper() if self.pin else ""

    @property
    def normalized_cu_number(self) -> str:
        return self.cu_number.strip() if self.cu_number else ""

    @property
    def normalized_vat_group(self) -> str:
        return self.vat_group.strip().upper() if self.vat_group else ""


class InvoiceFetchResponse(BaseModel):
    session_id: str
    source: str
    count: int
    from_date: date
    to_date: date
    invoices: list[Invoice]


class CSVValidationErrorDetail(BaseModel):
    row: int
    column: str | None = None
    message: str


class InvoiceUploadResponse(BaseModel):
    session_id: str = ""
    filename: str
    rows: int
    parsed: int
    errors_count: int
    errors: list[CSVValidationErrorDetail]
    invoices: list[Invoice]


class FileUploadStatus(BaseModel):
    filename: str
    rows: int
    parsed: int
    errors_count: int
    errors: list[CSVValidationErrorDetail]


class MultipleInvoiceUploadResponse(BaseModel):
    session_id: str = ""
    files: list[FileUploadStatus]
    invoices: list[Invoice]


class PaginatedInvoicesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[Invoice]
