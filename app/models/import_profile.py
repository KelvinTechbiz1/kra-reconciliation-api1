from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database.base import Base
from app.schemas.invoice import ReconciliationType


class ProfileScope(str, Enum):
    BUILTIN = "builtin"
    COMPANY = "company"


class SourceFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"


class ImportProfile(Base):
    __tablename__ = "import_profiles"
    __table_args__ = (
        # 1. Company profile name uniqueness per company & module
        UniqueConstraint("company_id", "module", "name", name="uq_company_module_profile_name"),
        # 2. Global built-in profile name uniqueness (where scope='builtin')
        Index("uq_builtin_module_profile_name", "module", "name", unique=True, sqlite_where=text("scope = 'builtin'")),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=True, index=True)
    scope = Column(SQLEnum(ProfileScope, native_enum=False, length=20), nullable=False, default=ProfileScope.COMPANY)

    name = Column(String(100), nullable=False)
    module = Column(SQLEnum(ReconciliationType, native_enum=False, length=20), nullable=False)  # sales | purchases
    provider = Column(String(50), nullable=False, default="CUSTOM")  # ZOHO | QUICKBOOKS | XERO | CUSTOM | GENERIC
    description = Column(Text, nullable=True)

    source_format = Column(SQLEnum(SourceFormat, native_enum=False, length=10), nullable=False, default=SourceFormat.CSV)

    # Structured JSON configurations
    parsing_hints = Column(JSON, nullable=False)
    column_mapping = Column(JSON, nullable=False)
    validation_rules = Column(JSON, nullable=False)

    is_builtin = Column(Boolean, nullable=False, default=False)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    archived_at = Column(DateTime, nullable=True)

    company = relationship("Company")
