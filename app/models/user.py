from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.refresh_token import RefreshToken



class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="checker", nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now())

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    company: Mapped["Company | None"] = relationship("Company")

    @property
    def company_name(self) -> str | None:
        """Name of the company this user belongs to, for display alongside the username.

        Read by UserResponse via from_attributes. SaaS admins have no company_id, so this
        is None for them.
        """
        return self.company.name if self.company else None


# Late import to register model in SQLAlchemy registry without circular dependency
from app.models.refresh_token import RefreshToken  # noqa: F401
