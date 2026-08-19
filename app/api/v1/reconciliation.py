from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_active_session
from app.database.database import get_db
from app.models.user import User
from app.models.reconciliation_session import SessionReconciliationResult
from app.reporting.context import ExportContext
from app.reporting.errors import UnsupportedExportFormatError, ReconciliationSummaryMissingError
from app.reporting.export_format import ExportFormat
from app.reporting.exporter import build_export
from app.reporting.registry import ExportStrategyRegistry
from app.schemas.invoice import Invoice, InvoiceSource
from app.schemas.reconciliation import ReconciliationCompareRequest, ReconciliationResponse
from app.services import reconciliation_service

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])
logger = logging.getLogger(__name__)


@router.post("/compare", response_model=ReconciliationResponse)
def compare_session_invoices(
    body: ReconciliationCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Runs the reconciliation matching engine on the loaded SAP and KRA invoices for the active session.
    Saves the calculated results to the session database, keeping it available for export/review.
    """
    # 1. Validate active session
    session = get_active_session(session_id=body.session_id, db=db, current_user=current_user)

    # 2. Return cached results immediately if comparison has already run
    if session.is_compared and session.comparison_results:
        return ReconciliationResponse(
            session_id=session.id,
            summary=session.comparison_results["summary"]
        )

    # 3. Retrieve session invoices and build Invoice domain lists
    invoices = session.invoices
    
    primary_invoices = [
        Invoice(
            pin=i.pin,
            partner_name=i.partner_name,
            invoice_number=i.invoice_number,
            invoice_date=i.invoice_date,
            cu_number=i.cu_number,
            vat_group=i.vat_group,
            base_amount=i.base_amount,
            source=InvoiceSource(i.source)
        )
        for i in invoices if i.source != InvoiceSource.KRA and i.source != InvoiceSource.KRA.value
    ]
    
    kra_invoices = [
        Invoice(
            pin=i.pin,
            partner_name=i.partner_name,
            invoice_number=i.invoice_number,
            invoice_date=i.invoice_date,
            cu_number=i.cu_number,
            vat_group=i.vat_group,
            base_amount=i.base_amount,
            source=InvoiceSource(i.source)
        )
        for i in invoices if i.source == InvoiceSource.KRA
    ]

    # Validate that both sides have data before comparing
    if not primary_invoices:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="ERP or SAP invoice load is required before starting reconciliation comparison."
         )

    if not kra_invoices:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="KRA CSV upload is required before starting reconciliation comparison."
         )

    # 4. Run reconciliation match algorithm inside single database transaction context
    try:
        from app.services.settings_service import SettingsService
        target_company_id = session.company_id or current_user.company_id
        company_setting = SettingsService.get_or_create_company_settings(db, target_company_id)
        summary, results = reconciliation_service.reconcile_invoices(
            primary_invoices, kra_invoices, amount_tolerance=company_setting.amount_tolerance
        )
        
        # Clear any stale results for this session (if run again somehow)
        db.query(SessionReconciliationResult).filter(
            SessionReconciliationResult.session_id == session.id
        ).delete()

        # Cache results relationally
        db_results = [
            SessionReconciliationResult(
                session_id=session.id,
                row_number=idx + 1,
                cu_number=r.cu_number,
                status=r.status,
                amount_match=r.amount_match,
                vat_match=r.vat_match,
                date_match=r.date_match,
                partner_name_matches=r.partner_name_matches,
                pin_matches=r.pin_matches,
                
                sap_invoice_number=r.sap.invoice_number if r.sap else None,
                sap_partner_name=r.sap.partner_name if r.sap else None,
                sap_pin=r.sap.pin if r.sap else None,
                sap_cu_number=r.sap.cu_number if r.sap else None,
                sap_invoice_date=r.sap.invoice_date if r.sap else None,
                sap_base_amount=r.sap.base_amount if r.sap else None,
                sap_vat_group=r.sap.vat_group if r.sap else None,
                sap_base_16=r.sap_base_16,
                sap_base_8=r.sap_base_8,
                sap_base_0=r.sap_base_0,
                sap_base_exempt=r.sap_base_exempt,
                
                kra_invoice_number=r.kra.invoice_number if r.kra else None,
                kra_partner_name=r.kra.partner_name if r.kra else None,
                kra_pin=r.kra.pin if r.kra else None,
                kra_cu_number=r.kra.cu_number if r.kra else None,
                kra_invoice_date=r.kra.invoice_date if r.kra else None,
                kra_base_amount=r.kra.base_amount if r.kra else None,
                kra_vat_group=r.kra.vat_group if r.kra else None,
                kra_base_16=r.kra_base_16,
                kra_base_8=r.kra_base_8,
                kra_base_0=r.kra_base_0,
                kra_base_exempt=r.kra_base_exempt,
            )
            for idx, r in enumerate(results)
        ]
        
        db.add_all(db_results)
        
        # Persist comparison summary to session model
        session.is_compared = True
        session.comparison_results = {"summary": summary.model_dump(mode="json")}
        
        db.commit()
        
        return ReconciliationResponse(
            session_id=session.id,
            summary=summary
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation engine failed: {str(e)}"
        )


@router.get("/{session_id}/export")
def export_session(
    session_id: str,
    request: Request,
    format: ExportFormat = Query(default=ExportFormat.ZIP),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export reconciliation results as a ZIP archive containing Excel workbooks."""
    session = get_active_session(session_id=session_id, db=db, current_user=current_user)

    if not session.is_compared:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session must be compared before export. Run /compare first.",
        )

    registry: ExportStrategyRegistry = request.app.state.export_registry
    settings = get_settings()

    context = ExportContext(
        generated_by=current_user.username,
        app_version=settings.app_version,
        generated_at=datetime.now(timezone.utc),
    )

    try:
        artifact = build_export(session, db, context, format, registry)
    except UnsupportedExportFormatError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ReconciliationSummaryMissingError as e:
        logger.error(
            "Unable to generate export: Reconciliation summary missing for compared session.",
            exc_info=True,
            extra={
                "session_id": session_id,
                "session_type": session.session_type.value,
                "schema_version": context.export_version,
                "user_id": current_user.id,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate export due to an internal reconciliation state error.",
        )

    return StreamingResponse(
        artifact.content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )
