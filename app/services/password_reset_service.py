import uuid
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt

from app.core.config import get_settings


def create_password_reset_token(user_id: int, username: str) -> str:
    """Generate a signed JWT token specifically for password resets."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.password_reset_token_expire_minutes)
    
    payload = {
        "sub": username,
        "user_id": user_id,
        "type": "password_reset",
        "exp": expire,
        "iat": now,
        "jti": uuid.uuid4().hex,
    }
    
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def verify_password_reset_token(token: str) -> dict | None:
    """Verify and decode a password reset token. Returns payload dict or None if invalid/expired."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
        )
        if payload.get("type") != "password_reset":
            return None
        return payload
    except JWTError:
        return None
