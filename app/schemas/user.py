import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def validate_password_complexity(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least 1 lowercase letter.")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least 1 uppercase letter.")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least 1 number.")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?~`]", v):
        raise ValueError("Password must contain at least 1 special character.")
    return v


class UserCreate(BaseModel):
    username: str = Field(min_length=1, description="Username")
    password: str = Field(min_length=8, description="Password, minimum 8 characters with policy requirements")
    email: str | None = Field(default=None, description="Email address")
    full_name: str | None = Field(default=None, description="Display name")
    role: str = Field(default="checker", description="User role: admin or checker")
    company_id: int | None = Field(default=None, description="Associated company ID")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in {"admin", "checker"}:
            raise ValueError("Role must be 'admin' or 'checker'")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    company_id: Optional[int] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"admin", "checker"}:
            raise ValueError("Role must be 'admin' or 'checker'")
        return v


class UserPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, description="New password, minimum 8 characters with policy requirements")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, description="Current password")
    new_password: str = Field(min_length=8, description="New password, minimum 8 characters with policy requirements")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class UserLogin(BaseModel):
    username: str = Field(description="Username")
    password: str = Field(description="Password")


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    full_name: str | None = None
    role: str
    company_id: int | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1, description="Username or email address")


class VerifyResetTokenRequest(BaseModel):
    token: str = Field(min_length=1, description="Password reset JWT token")


class ResetPasswordWithTokenRequest(BaseModel):
    token: str = Field(min_length=1, description="Password reset JWT token")
    new_password: str = Field(min_length=8, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_complexity(v)

