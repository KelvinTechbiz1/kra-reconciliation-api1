from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.reconciliation_session import (
    ReconciliationSession,
    SessionInvoice,
    SessionReconciliationResult,
)
from app.schemas.invoice import (
    Invoice,
    InvoiceSource,
    ReconciliationType,
)
from app.services import invoice_service, kra_service
from app.services.settings_service import SettingsService
from app.services.vat_normalizer import VatNormalizer

SESSION_EXPIRY_MINUTES = 30


def _next_row_number(db: Session, session_id: str, source: InvoiceSource) -> int:
    """First free row_number for (session, source).

    session_invoices carries UniqueConstraint(session_id, source, row_number), so an
    append must continue the sequence rather than restart at 1.
    """
    highest = (
        db.query(func.max(SessionInvoice.row_number))
        .filter(
            SessionInvoice.session_id == session_id,
            SessionInvoice.source == source,
        )
        .scalar()
    )
    return (highest or 0) + 1


def _save_invoices(
    db: Session,
    session_id: str,
    invoices: list[Invoice],
    source: InvoiceSource,
    row_number_offset: int = 1,
) -> None:
    db_invoices = [
        SessionInvoice(
            session_id=session_id,
            row_number=row_number_offset + idx,
            source=inv.source,
            pin=inv.pin,
            partner_name=inv.partner_name,
            invoice_number=inv.invoice_number,
            invoice_date=inv.invoice_date,
            cu_number=inv.cu_number,
            vat_group=inv.vat_group,
            base_amount=inv.base_amount,
            source_filename=inv.source_filename,
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

    # Partial success is reported per file and still imports. But when nothing at all
    # could be read there is no "rest" to keep, so fail loudly rather than return an
    # empty 200 the UI would render as a successful upload.
    if not all_invoices and any(f.errors_count for f in file_statuses):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(
                f"{f.filename}: {f.errors[0].message}"
                for f in file_statuses if f.errors
            ),
        )

    # Append to whatever the session already holds. KRA publishes one export per rate
    # section, so users upload in several passes ("Upload More CSVs"); this used to
    # delete every previously uploaded KRA row, silently discarding earlier sections.
    existing_keys = {
        (inv.pin, inv.invoice_number, inv.invoice_date, inv.cu_number, inv.vat_group, inv.base_amount)
        for inv in db.query(SessionInvoice).filter(
            SessionInvoice.session_id == session.id,
            SessionInvoice.source == InvoiceSource.KRA,
        )
    }

    # Re-uploading a file already in the session must not double-count it. Identical
    # rows are skipped; genuinely repeated invoices differing in any field still load.
    new_invoices = []
    duplicates = 0
    for inv in all_invoices:
        key = (inv.pin, inv.invoice_number, inv.invoice_date, inv.cu_number, inv.vat_group, inv.base_amount)
        if key in existing_keys:
            duplicates += 1
            continue
        existing_keys.add(key)
        new_invoices.append(inv)

    if new_invoices:
        session.is_compared = False
        session.comparison_results = None
        _save_invoices(
            db, session.id, new_invoices, InvoiceSource.KRA,
            row_number_offset=_next_row_number(db, session.id, InvoiceSource.KRA),
        )

    total_kra = db.query(SessionInvoice).filter(
        SessionInvoice.session_id == session.id,
        SessionInvoice.source == InvoiceSource.KRA,
    ).count()

    return {
        "session_id": session.id,
        "files": file_statuses,
        "added": len(new_invoices),
        "duplicates_skipped": duplicates,
        "total_kra_records": total_kra,
        "invoices": new_invoices[:100],
    }


def remove_kra_file(
    db: Session,
    current_user,
    reconciliation_type: ReconciliationType,
    session_id: str,
    filename: str,
):
    """Delete the KRA rows one upload contributed, leaving the rest of the session intact.

    Uploading the wrong CSV used to be unrecoverable without reloading the page and
    starting over, because KRA uploads append and nothing tracked which rows came from
    which file.

    Rows are matched on `source_filename`. A row that a later file repeated verbatim was
    skipped as a duplicate at upload time, so it is attributed to — and removed with —
    the first file that carried it; re-upload the file that still needs it.
    """
    from app.core.dependencies import get_active_session

    session = get_active_session(session_id=session_id, db=db, current_user=current_user)
    if session.session_type != reconciliation_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Active session type is not for {reconciliation_type.value.capitalize()} reconciliation.",
        )

    name = (filename or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filename is required.",
        )

    removed = (
        db.query(SessionInvoice)
        .filter(
            SessionInvoice.session_id == session.id,
            SessionInvoice.source == InvoiceSource.KRA,
            SessionInvoice.source_filename == name,
        )
        .delete(synchronize_session=False)
    )

    if removed:
        # Any cached comparison described the rows that just went away.
        session.is_compared = False
        session.comparison_results = None
        db.query(SessionReconciliationResult).filter(
            SessionReconciliationResult.session_id == session.id
        ).delete(synchronize_session=False)

    db.commit()

    total_kra = db.query(SessionInvoice).filter(
        SessionInvoice.session_id == session.id,
        SessionInvoice.source == InvoiceSource.KRA,
    ).count()

    # Authoritative list of what the session still holds, so the UI's tags cannot drift
    # out of step with the database.
    remaining = [
        row[0]
        for row in db.query(SessionInvoice.source_filename)
        .filter(
            SessionInvoice.session_id == session.id,
            SessionInvoice.source == InvoiceSource.KRA,
            SessionInvoice.source_filename.isnot(None),
        )
        .distinct()
        .order_by(SessionInvoice.source_filename)
    ]

    return {
        "session_id": session.id,
        "filename": name,
        "removed": removed,
        "total_kra_records": total_kra,
        "remaining_files": remaining,
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

