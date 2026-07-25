from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

import secrets

ALLOWED_ROLES = {"admin", "checker"}


def generate_secure_password(length: int = 14) -> str:
    lowers = "abcdefghjkmnpqrstuvwxyz"
    uppers = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    specials = "!@#$%^&*()_+-="
    all_chars = lowers + uppers + digits + specials

    password_chars = [
        secrets.choice(lowers),
        secrets.choice(uppers),
        secrets.choice(digits),
        secrets.choice(specials),
    ]
    for _ in range(length - 4):
        password_chars.append(secrets.choice(all_chars))

    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


def create_user(db: Session, user_in: UserCreate) -> User:
    raw_password = user_in.password if user_in.password else generate_secure_password()
    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        password_hash=hash_password(raw_password),
        role=user_in.role,
        company_id=user_in.company_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.generated_password = raw_password
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if user is None or not verify_password(password, user.password_hash):
        return None
    # Track last login
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return user


def get_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_by_identifier(db: Session, identifier: str) -> User | None:
    """Find user by username or email address (case-insensitive for email)."""
    clean_id = identifier.strip()
    return (
        db.query(User)
        .filter(
            (User.username == clean_id) | (User.email != None) & (User.email.ilike(clean_id))
        )
        .first()
    )


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def list_users(db: Session, company_id: int | None = None) -> list[User]:
    query = db.query(User)
    if company_id is not None:
        query = query.filter(User.company_id == company_id)
    return query.order_by(User.created_at.asc()).all()


def update_user(db: Session, user_id: int, payload: UserUpdate) -> Optional[User]:
    user = get_by_id(db, user_id)
    if user is None:
        return None
    if payload.username is not None and payload.username.strip():
        new_username = payload.username.strip()
        if new_username != user.username:
            existing = get_by_username(db, new_username)
            if existing and existing.id != user_id:
                raise ValueError(f"Username '{new_username}' is already in use.")
            user.username = new_username
    if payload.email is not None:
        user.email = payload.email
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        if payload.role not in ALLOWED_ROLES:
            raise ValueError(f"Invalid role '{payload.role}'. Allowed: {sorted(ALLOWED_ROLES)}")
        user.role = payload.role
    if payload.company_id is not None:
        user.company_id = payload.company_id
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user_id: int, new_password: str) -> Optional[User]:
    user = get_by_id(db, user_id)
    if user is None:
        return None
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    user = get_by_id(db, user_id)
    if user is None:
        return False
    db.delete(user)
    db.commit()
    return True

