from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.reconciliation_session import ReconciliationSession, SessionInvoice
from app.schemas.invoice import (
    Invoice,
    InvoiceSource,
    ReconciliationType,
)
from app.services import invoice_service, kra_service
from app.services.settings_service import SettingsService
from app.services.vat_normalizer import VatNormalizer

SESSION_EXPIRY_MINUTES = 30


def _save_invoices(db: Session, session_id: str, invoices: list[Invoice], source: InvoiceSource) -> None:
    db_invoices = [
        SessionInvoice(
            session_id=session_id,
            row_number=idx + 1,
            source=inv.source,
            pin=inv.pin,
            partner_name=inv.partner_name,
            invoice_number=inv.invoice_number,
            invoice_date=inv.invoice_date,
            cu_number=inv.cu_number,
            vat_group=inv.vat_group,
            base_amount=inv.base_amount,
        )
        for idx, inv in enumerate(invoices)
    ]
    db.add_all(db_invoices)
    db.commit()


def load_sap_invoices(
    db: Session,
    current_user,
    sap_client,
    reconciliation_type: ReconciliationType,
    from_date: date,
    to_date: date,
):
    """Fetch SAP invoices for a date range, create a session, and persist them."""
    expiry_time = datetime.now(timezone.utc) - timedelta(minutes=SESSION_EXPIRY_MINUTES)
    db.query(ReconciliationSession).filter(
        ReconciliationSession.user_id == current_user.id,
        ReconciliationSession.last_accessed_at < expiry_time,
    ).delete()
    db.commit()

    company_id = current_user.company_id
    if company_id is None:
        from app.models.company import Company
        comp = db.query(Company).order_by(Company.id.asc()).first()
        company_id = comp.id if comp else None

    session = ReconciliationSession(
        company_id=company_id,
        user_id=current_user.id,
        from_date=from_date,
        to_date=to_date,
        session_type=reconciliation_type,
        is_compared=False,
    )
    db.add(session)
    db.commit()

    system_setting = SettingsService.get_or_create_company_settings(db, company_id)

    # Resolve this company's configured SAP VAT code mappings once per load, into a
    # request-local normalizer. Without this the engine would only ever recognise the
    # built-in default codes and every custom code would become its own tax bucket.
    normalizer = VatNormalizer()
    active_connection = SettingsService.get_active_connection(db, company_id)
    if active_connection:
        normalizer.load_from_db(db, active_connection.id)

    invoices = invoice_service.get_invoices(
        from_date,
        to_date,
        reconciliation_type=reconciliation_type,
        sap_client=sap_client,
        reconciliation_session_id=session.id,
        sales_cu_source=system_setting.sales_cu_source,
        purchase_cu_source=system_setting.purchase_cu_source,
        base_amount_policy=system_setting.base_amount_policy,
        vat_normalizer_override=normalizer,
        unmapped_vat_policy=system_setting.unmapped_vat_policy,
    )

    _save_invoices(db, session.id, invoices, InvoiceSource.SAP)

    return {
        "session_id": session.id,
        "source": "SAP",
        "count": len(invoices),
        "from_date": from_date,
        "to_date": to_date,
        "invoices": invoices[:100],
    }


def upload_kra_csvs(
    db: Session,
    current_user,
    reconciliation_type: ReconciliationType,
    files: list,
    session_id: str,
):
    """Validate the active session, parse KRA CSVs, and replace stored KRA invoices."""
    from app.core.dependencies import get_active_session

    session = get_active_session(session_id=session_id, db=db, current_user=current_user)
    if session.session_type != reconciliation_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Active session type is not for {reconciliation_type.value.capitalize()} reconciliation.",
        )

    company_id = session.company_id or current_user.company_id
    all_invoices, file_statuses = kra_service.parse_multiple_kra_csvs(files, db, company_id=company_id)

    if all_invoices:
        db.query(SessionInvoice).filter(
            SessionInvoice.session_id == session.id,
            SessionInvoice.source == InvoiceSource.KRA,
        ).delete()
        session.is_compared = False
        session.comparison_results = None
        _save_invoices(db, session.id, all_invoices, InvoiceSource.KRA)

    return {
        "session_id": session.id,
        "files": file_statuses,
        "invoices": all_invoices[:100],
    }


def upload_erp_invoices(
    db: Session,
    current_user,
    reconciliation_type: ReconciliationType,
    files: list,
    profile_id: int | None = None,
    session_id: str | None = None,
):
    """Upload and parse ERP file (CSV/XLSX) using an ImportProfile snapshot. Initializes session if needed."""
    from app.core.dependencies import get_active_session
    from app.services.erp_profile_service import ERPProfileService
    from app.services.erp_import_service import ERPImportService

    company_id = current_user.company_id
    if company_id is None:
        from app.models.company import Company
        comp = db.query(Company).order_by(Company.id.asc()).first()
        company_id = comp.id if comp else None

    # Resolve profile deterministically
    profile = ERPProfileService.resolve_profile_for_import(db, company_id, reconciliation_type, profile_id)
    snapshot = ERPProfileService.create_snapshot(profile)

    # Initialize session or fetch existing
    if session_id:
        session = get_active_session(session_id=session_id, db=db, current_user=current_user)
        if session.session_type != reconciliation_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Active session type is not for {reconciliation_type.value.capitalize()} reconciliation.",
            )
    else:
        # Delete expired sessions
        expiry_time = datetime.now(timezone.utc) - timedelta(minutes=SESSION_EXPIRY_MINUTES)
        db.query(ReconciliationSession).filter(
            ReconciliationSession.user_id == current_user.id,
            ReconciliationSession.last_accessed_at < expiry_time,
        ).delete()
        db.commit()

        today = date.today()
        session = ReconciliationSession(
            company_id=company_id,
            user_id=current_user.id,
            from_date=today.replace(day=1),
            to_date=today,
            session_type=reconciliation_type,
            is_compared=False,
        )
        db.add(session)
        db.commit()

    # Save immutable profile snapshot to session
    session.import_profile_id = profile.id
    session.import_profile_name = profile.name
    session.import_profile_version_used = profile.version
    session.provider = profile.provider
    session.source_format = profile.source_format.value
    session.import_profile_snapshot = snapshot.model_dump(mode="json")
    db.commit()

    all_invoices: list[Invoice] = []
    file_statuses = []

    for upload_file in files:
        filename = upload_file.filename or "uploaded_erp_file.csv"
        file_bytes = upload_file.file.read()
        invoices, errors = ERPImportService.parse_erp_file(file_bytes, filename, snapshot)
        all_invoices.extend(invoices)
        file_statuses.append({
            "filename": filename,
            "rows": len(invoices) + len(errors),
            "parsed": len(invoices),
            "errors_count": len(errors),
            "errors": errors,
        })

    if all_invoices:
        # Clear previous ERP / SAP invoices in this session
        db.query(SessionInvoice).filter(
            SessionInvoice.session_id == session.id,
            SessionInvoice.source.in_([InvoiceSource.ERP, InvoiceSource.SAP]),
        ).delete()
        session.is_compared = False
        session.comparison_results = None
        _save_invoices(db, session.id, all_invoices, InvoiceSource.ERP)

    return {
        "session_id": session.id,
        "source": "ERP",
        "provider": profile.provider,
        "profile_name": profile.name,
        "count": len(all_invoices),
        "files": file_statuses,
        "invoices": all_invoices[:100],
    }

