from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.import_profile import (
    HeaderDetectionResponse,
    ImportProfileCreate,
    ImportProfileResponse,
    ImportProfileUpdate,
    MappingPreviewRequest,
    MappingPreviewResponse,
)
from app.schemas.invoice import ReconciliationType
from app.services.erp_profile_service import ERPProfileService
from app.services.erp_import_service import ERPImportService

router = APIRouter(prefix="/import-profiles", tags=["import-profiles"])


def _get_company_id(current_user: User, db: Session) -> Optional[int]:
    if current_user.company_id is not None:
        return current_user.company_id
    from app.models.company import Company
    comp = db.query(Company).order_by(Company.id.asc()).first()
    return comp.id if comp else None


@router.get("", response_model=List[ImportProfileResponse])
@router.get("/", response_model=List[ImportProfileResponse], include_in_schema=False)
def list_import_profiles(
    module: Optional[ReconciliationType] = Query(None, description="Filter profiles by module (sales or purchases)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all import profiles available to the current user's company."""
    company_id = _get_company_id(current_user, db)
    return ERPProfileService.list_profiles(db, company_id, module=module)


@router.post("", response_model=ImportProfileResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ImportProfileResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_import_profile(
    payload: ImportProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a custom import profile for the current user's company."""
    company_id = _get_company_id(current_user, db)
    if not company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No company context found for current user.")

    try:
        return ERPProfileService.create_profile(db, company_id, payload)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'"))
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{id}", response_model=ImportProfileResponse)
def get_import_profile(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch details of a single import profile."""
    company_id = _get_company_id(current_user, db)
    profile = ERPProfileService.get_profile(db, id, company_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import profile not found.")
    return profile


@router.put("/{id}", response_model=ImportProfileResponse)
def update_import_profile(
    id: int,
    payload: ImportProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing custom import profile (increments version)."""
    company_id = _get_company_id(current_user, db)
    try:
        return ERPProfileService.update_profile(db, id, company_id, payload)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'"))
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_import_profile(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete a custom import profile."""
    company_id = _get_company_id(current_user, db)
    try:
        ERPProfileService.delete_profile(db, id, company_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'"))
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/clone", response_model=ImportProfileResponse, status_code=status.HTTP_201_CREATED)
def clone_import_profile(
    id: int,
    name: Optional[str] = Query(None, description="Optional new profile name"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clone an existing built-in preset or company profile into an editable custom company profile."""
    company_id = _get_company_id(current_user, db)
    if not company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No company context available.")

    try:
        return ERPProfileService.clone_profile(db, id, company_id, new_name=name)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'"))
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/set-default", response_model=ImportProfileResponse)
def set_default_import_profile(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set an import profile as default for its module in the company."""
    company_id = _get_company_id(current_user, db)
    try:
        return ERPProfileService.set_default_profile(db, company_id, id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'"))
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/preview", response_model=MappingPreviewResponse)
async def preview_import_profile_mapping(
    file: UploadFile = File(...),
    module: ReconciliationType = Query(..., description="Target module (sales or purchases)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dry-run preview of parsing a sample file against active or default profile mapping."""
    company_id = _get_company_id(current_user, db)
    profile = ERPProfileService.resolve_profile_for_import(db, company_id, module)
    snapshot = ERPProfileService.create_snapshot(profile)

    file_bytes = await file.read()
    filename = file.filename or "sample_file.csv"

    return ERPImportService.preview_mapping(file_bytes, filename, snapshot)


@router.post("/detect-headers", response_model=HeaderDetectionResponse)
async def detect_headers_from_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Auto-detect which row contains headers in an uploaded sample file."""
    file_bytes = await file.read()
    filename = file.filename or "sample_file.csv"
    return ERPImportService.detect_headers(file_bytes, filename)

