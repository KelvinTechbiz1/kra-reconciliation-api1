from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_platform_admin
from app.models.company import Company
from app.models.user import User
from app.schemas.settings import (
    SAPConnectionResponse,
    SAPConnectionUpdate,
    SettingAuditLogResponse,
    SettingsCompositeResponse,
    SystemSettingsResponse,
    SystemSettingsUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
    VATMappingItem,
    VATMappingsUpdatePayload,
    KRAVATMappingItem,
    KRAVATMappingsUpdatePayload,
)
from app.services.settings_service import SettingsConflictError, SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


def require_admin_role(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "checker"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator or checker privileges required to modify system settings.",
        )
    return current_user


def _resolve_settings_company(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    company_id: Optional[int] = Query(None, description="Target company (platform admin only)"),
) -> Company:
    """Resolve the company whose settings are being accessed.

    - Company users are locked to their own company (the param is ignored).
    - Platform admins may pass ``company_id`` to manage a specific tenant; if
      omitted, they fall back to the first company so the UI can render.
    """
    if current_user.company_id is None:
        # Platform admin: explicit target if provided, else the first company.
        if company_id is not None:
            company = db.query(Company).filter(Company.id == company_id).first()
            if company is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
            return company
        company = db.query(Company).order_by(Company.id.asc()).first()
        if company is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No companies exist yet.")
        return company
    # Company user: always their own company.
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated company not found.")
    return company


@router.get("", response_model=SettingsCompositeResponse)
def get_settings(
    company: Company = Depends(_resolve_settings_company),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a company's SAP connection, operational settings, and VAT mappings."""
    return SettingsService.get_composite_settings(db, company.id)


@router.put("/sap-connection", response_model=SAPConnectionResponse)
def update_sap_connection(
    payload: SAPConnectionUpdate,
    company: Company = Depends(_resolve_settings_company),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_role),
):
    """Create or update a company's SAP Service Layer connection."""
    try:
        return SettingsService.save_or_update_sap_connection(db, company.id, payload, current_user)
    except SettingsConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/system-settings", response_model=SystemSettingsResponse)
def update_system_settings(
    payload: SystemSettingsUpdate,
    company: Company = Depends(_resolve_settings_company),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_role),
):
    """Update a company's operational reconciliation rules and tolerances."""
    try:
        return SettingsService.update_system_settings(db, company.id, payload, current_user)
    except SettingsConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/vat-mappings", response_model=List[VATMappingItem])
def update_vat_mappings(
    payload: VATMappingsUpdatePayload,
    company: Company = Depends(_resolve_settings_company),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_role),
):
    """Update a company's module-level SAP VAT code mappings."""
    try:
        return SettingsService.save_vat_mappings(db, company.id, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/kra-vat-mappings", response_model=List[KRAVATMappingItem])
def update_kra_vat_mappings(
    payload: KRAVATMappingsUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_role),
):
    """Update the shared KRA CSV Section Prefix to VAT rate mappings."""
    try:
        return SettingsService.save_kra_vat_mappings(db, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/test-sap", response_model=TestConnectionResponse)
def test_sap_connection(
    payload: TestConnectionRequest,
    company: Company = Depends(_resolve_settings_company),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_role),
):
    """Test SAP Service Layer connectivity using the company's connection or form parameters."""
    return SettingsService.test_sap_connection(db, company.id, payload)


@router.get("/audit-logs", response_model=List[SettingAuditLogResponse])
def get_audit_logs(
    limit: int = 50,
    company: Company = Depends(_resolve_settings_company),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a company's historical audit logs of configuration changes."""
    raw_logs = SettingsService.get_audit_logs(db, company_id=company.id, limit=limit)
    return [SettingAuditLogResponse.model_validate(log) for log in raw_logs]
