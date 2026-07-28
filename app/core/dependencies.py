from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.database import get_db
from app.models.user import User
from app.models.reconciliation_session import ReconciliationSession
from app.core.sap_client import SAPClient

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_sap_client(request: Request = None) -> SAPClient:
    """
    Dependency to retrieve the SAPClient instance.
    Uses app.state if running in the FastAPI app context, otherwise falls back to request-scoped instance.
    """
    if request and hasattr(request.app.state, "sap_client"):
        return request.app.state.sap_client
    # Fallback for testing or scripts
    if not hasattr(get_sap_client, "_fallback_client"):
        get_sap_client._fallback_client = SAPClient()
    return get_sap_client._fallback_client


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
        )
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Admin (SaaS Owner) role check."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user


def get_current_company(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> "Company":
    """Resolve the company a user belongs to. Admins without a specific company
    are associated with the primary company (first created)."""
    from app.models.company import Company

    if current_user.company_id is None:
        company = db.query(Company).order_by(Company.id.asc()).first()
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No company profiles exist yet.",
            )
        return company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated company not found.",
        )
    return company


def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    """Admin (SaaS Owner) role check."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required.",
        )
    return current_user


def get_company_sap_client(
    company: "Company" = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> SAPClient:
    """Build an SAPClient configured from the caller's company SAP connection."""
    from app.services.settings_service import SettingsService

    connection = SettingsService.get_active_connection(db, company.id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SAP connection configured for your company.",
        )
    return SAPClient.from_connection(connection)


def get_active_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ReconciliationSession:
    from datetime import datetime, timedelta, timezone

    query_filters = [
        ReconciliationSession.id == session_id,
        ReconciliationSession.user_id == current_user.id,
    ]
    if current_user.company_id is not None:
        query_filters.append(ReconciliationSession.company_id == current_user.company_id)

    session = db.query(ReconciliationSession).filter(*query_filters).first()
    
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation session not found."
        )
        
    # Check if expired (> 30 min idle)
    # Using timezone-aware UTC comparison
    expiry_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    
    last_accessed = session.last_accessed_at
    if last_accessed.tzinfo is None:
        last_accessed = last_accessed.replace(tzinfo=timezone.utc)
        
    if last_accessed < expiry_time:
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has expired. Please start a new load request."
        )
        
    # Update last accessed time
    session.last_accessed_at = datetime.now(timezone.utc)
    db.commit()
    return session
