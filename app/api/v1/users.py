from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserPasswordReset, UserResponse, UserUpdate
from app.services import email_service, password_reset_service, user_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


def _resolve_list_scope(
    current_user: User = Depends(get_current_user),
    company_id: Optional[int] = Query(None, description="Filter by company (admin only)"),
) -> Optional[int]:
    """Admin users may list any company's users or filter by company."""
    if current_user.role not in ("admin", "company_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator or company admin privileges required to manage users.",
        )
    return company_id if current_user.company_id is None else current_user.company_id


@router.get("", response_model=List[UserResponse])
def list_users(
    scope_company_id: Optional[int] = Depends(_resolve_list_scope),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List users. Admin only."""
    return user_service.list_users(db, company_id=scope_company_id)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new user.

    - Platform admins (company_id is None) can create users for any company or global admins.
    - Company admins can create users for their assigned company only.
    """
    if current_user.company_id is not None:
        if current_user.role not in ("admin", "company_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can manage users.",
            )
        # Enforce target user company scope to match current company admin scope
        body.company_id = current_user.company_id

    existing = user_service.get_by_username(db, body.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists.",
        )
    user = user_service.create_user(db, body)

    if user.email and getattr(user, "generated_password", None):
        try:
            company_name = None
            if user.company_id:
                from app.models.company import Company
                company = db.query(Company).filter(Company.id == user.company_id).first()
                company_name = company.name if company else None

            email_service.send_welcome_account_email(
                to_email=user.email,
                username=user.username,
                password=user.generated_password,
                full_name=user.full_name,
                company_name=company_name,
            )
        except Exception as e:
            logger.error(f"Failed to send welcome email to {user.email}: {e}")

    return user



@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a user. Platform admins can update any user; company admins can update users in their company."""
    target_user = user_service.get_by_id(db, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if current_user.company_id is not None:
        if current_user.role not in ("admin", "company_admin") or target_user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage users within your company.",
            )
        if body.company_id is not None and body.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign user to a different company.",
            )

    if body.is_active is False and user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )

    try:
        updated = user_service.update_user(db, user_id, body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return updated


@router.post("/{user_id}/reset-password", response_model=UserResponse)
def reset_password(
    user_id: int,
    body: UserPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset a user's password. Accessible by platform admins or company admins for users in their company."""
    target_user = user_service.get_by_id(db, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if current_user.company_id is not None:
        if current_user.role not in ("admin", "company_admin") or target_user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only reset passwords for users within your company.",
            )

    updated = user_service.reset_password(db, user_id, body.new_password)
    return updated


@router.post("/{user_id}/send-reset-email", status_code=status.HTTP_200_OK)
def send_reset_email(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a password reset email via SendGrid to a user. Admin accessible."""
    target_user = user_service.get_by_id(db, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if current_user.company_id is not None:
        if current_user.role not in ("admin", "company_admin") or target_user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage users within your company.",
            )

    if not target_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User @{target_user.username} does not have an email address configured.",
        )

    token = password_reset_service.create_password_reset_token(target_user.id, target_user.username)
    settings = get_settings()
    reset_link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"

    company_name = None
    if target_user.company_id:
        from app.models.company import Company
        company = db.query(Company).filter(Company.id == target_user.company_id).first()
        company_name = company.name if company else None

    sent = email_service.send_password_reset_email(target_user.email, target_user.username, reset_link, company_name=company_name)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send password reset email via SendGrid SMTP.",
        )

    return {"detail": f"Password reset email sent successfully to {target_user.email}."}


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a user account. Admins only; users cannot delete their own account."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    target_user = user_service.get_by_id(db, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if current_user.company_id is not None:
        if current_user.role not in ("admin", "company_admin") or target_user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage users within your company.",
            )

    username = target_user.username
    user_service.delete_user(db, user_id)
    return {"detail": f"User @{username} deleted successfully."}


