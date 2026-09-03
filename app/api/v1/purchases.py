from datetime import date
from fastapi import APIRouter, Depends, Query, UploadFile

from app.api.v1._session_helpers import (
    load_sap_invoices,
    remove_kra_file,
    upload_kra_csvs,
)
from app.core.dependencies import get_company_sap_client, get_current_user, get_db
from app.core.sap_client import SAPClient
from app.models.user import User
from app.schemas.invoice import (
    ReconciliationType,
    InvoiceFetchResponse,
    KRAFileRemovalResponse,
    MultipleInvoiceUploadResponse,
)

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.get("", response_model=InvoiceFetchResponse)
def get_purchases(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    session_id: str | None = Query(
        None,
        description="Append to this existing session instead of starting a new one. "
                    "Used to load a long range as successive windows.",
    ),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
    sap_client: SAPClient = Depends(get_company_sap_client),
) -> InvoiceFetchResponse:
    """
    Fetch purchase invoices within a given date range from SAP `/PurchaseInvoices`.
    Stores the loaded invoices in a database-backed session with ReconciliationType.PURCHASES.
    """
    return load_sap_invoices(
        db, current_user, sap_client, ReconciliationType.PURCHASES, from_date, to_date, session_id=session_id
    )


@router.post("/upload", response_model=MultipleInvoiceUploadResponse)
def upload_purchases_csv(
    files: list[UploadFile],
    session_id: str = Query(..., description="Active reconciliation session ID"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> MultipleInvoiceUploadResponse:
    """
    Upload multiple KRA CSV files containing purchase invoices. Normalizes and appends records to the active session.
    """
    return upload_kra_csvs(db, current_user, ReconciliationType.PURCHASES, files, session_id)


@router.delete("/upload", response_model=KRAFileRemovalResponse)
def remove_purchases_csv(
    filename: str = Query(..., description="Name of the uploaded KRA CSV to remove"),
    session_id: str = Query(..., description="Active reconciliation session ID"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> KRAFileRemovalResponse:
    """
    Remove one previously uploaded KRA CSV from the active session, so a mistaken upload
    can be undone without reloading the page and re-fetching purchase data.
    """
    return remove_kra_file(db, current_user, ReconciliationType.PURCHASES, session_id, filename)


@router.post("/upload-erp")
def upload_purchases_erp(
    files: list[UploadFile],
    profile_id: int | None = Query(None, description="Import profile ID. If omitted, active company default profile is resolved."),
    session_id: str | None = Query(None, description="Optional existing active session ID."),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Upload Purchases ERP file (CSV or XLSX). Normalizes invoices using active ImportProfile snapshot.
    """
    from app.api.v1._session_helpers import upload_erp_invoices
    return upload_erp_invoices(
        db, current_user, ReconciliationType.PURCHASES, files, profile_id=profile_id, session_id=session_id
    )

