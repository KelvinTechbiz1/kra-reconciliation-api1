from datetime import date
from fastapi import APIRouter, Depends, Query, UploadFile

from app.api.v1._session_helpers import load_sap_invoices, upload_kra_csvs
from app.core.dependencies import get_company_sap_client, get_current_user, get_db
from app.core.sap_client import SAPClient
from app.models.user import User
from app.schemas.invoice import (
    ReconciliationType,
    InvoiceFetchResponse,
    MultipleInvoiceUploadResponse,
)

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("", response_model=InvoiceFetchResponse)
def get_sales(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
    sap_client: SAPClient = Depends(get_company_sap_client),
) -> InvoiceFetchResponse:
    """
    Fetch sales invoices within a given date range. Currently returns normalized SAP data.
    Stores the loaded invoices in a database-backed session with ReconciliationType.SALES.
    """
    return load_sap_invoices(db, current_user, sap_client, ReconciliationType.SALES, from_date, to_date)


@router.post("/upload", response_model=MultipleInvoiceUploadResponse)
def upload_sales_csv(
    files: list[UploadFile],
    session_id: str = Query(..., description="Active reconciliation session ID"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> MultipleInvoiceUploadResponse:
    """
    Upload multiple KRA CSV files containing sales invoices. Normalizes and appends records to the active session.
    """
    return upload_kra_csvs(db, current_user, ReconciliationType.SALES, files, session_id)


@router.post("/upload-erp")
def upload_sales_erp(
    files: list[UploadFile],
    profile_id: int | None = Query(None, description="Import profile ID. If omitted, active company default profile is resolved."),
    session_id: str | None = Query(None, description="Optional existing active session ID."),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Upload Sales ERP file (CSV or XLSX). Normalizes invoices using active ImportProfile snapshot.
    """
    from app.api.v1._session_helpers import upload_erp_invoices
    return upload_erp_invoices(
        db, current_user, ReconciliationType.SALES, files, profile_id=profile_id, session_id=session_id
    )

