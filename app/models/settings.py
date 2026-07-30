from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database.base import Base


class BaseAmountPolicy(str, Enum):
    ALLOW = "allow"
    SKIP = "skip"
    REJECT = "reject"
    REJECT_SESSION = "reject_session"
    TREAT_AS_ZERO = "treat_as_zero"


class UnmappedVatPolicy(str, Enum):
    REJECT_INVOICE = "reject_invoice"
    NEEDS_REVIEW = "needs_review"


class VatModule(str, Enum):
    SALES = "sales"
    PURCHASES = "purchases"


class PurchaseCUField(str, Enum):
    """SAP field that holds the Control Unit (CU) number on Purchase Invoices.

    Values are the exact SAP field names; the UI displays business-friendly labels.
    """

    KRA = "U_CUINV"
    NUM_AT_CARD = "NumAtCard"
    COMMENTS = "Comments"
    JOURNAL_MEMO = "JournalMemo"
    INVOICE_NUMBER = "Reference1"


class CompanySAPConnection(Base):
    """Per-company SAP Service Layer connection. Replaces the legacy global
    ``sap_connections`` table so every company manages its own SAP tenant."""

    __tablename__ = "company_sap_connections"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, default="Primary SAP Connection")
    base_url = Column(String(500), nullable=False)
    company_db = Column(String(100), nullable=False)
    username = Column(String(100), nullable=False)
    password = Column(String(500), nullable=False)
    verify_ssl = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by_id = Column(Integer, nullable=True)

    company = relationship("Company")
    vat_mappings = relationship("VATMapping", back_populates="connection", cascade="all, delete-orphan")


class CompanySetting(Base):
    """Per-company operational reconciliation settings. Replaces the legacy
    global ``system_settings`` table for multi-tenant SaaS isolation."""

    __tablename__ = "company_settings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    active_connection_id = Column(Integer, ForeignKey("company_sap_connections.id", ondelete="SET NULL"), nullable=True)

    amount_tolerance = Column(Numeric(10, 2), nullable=False, default=10.00)
    base_amount_policy = Column(
        SQLEnum(BaseAmountPolicy, native_enum=False, length=50),
        nullable=False,
        default=BaseAmountPolicy.SKIP,
    )
    unmapped_vat_policy = Column(
        SQLEnum(UnmappedVatPolicy, native_enum=False, length=50),
        nullable=False,
        default=UnmappedVatPolicy.NEEDS_REVIEW,
    )

    ignore_missing_cu = Column(Boolean, nullable=False, default=False)
    include_credit_notes = Column(Boolean, nullable=False, default=True)
    include_debit_notes = Column(Boolean, nullable=False, default=True)
    skip_cancelled = Column(Boolean, nullable=False, default=True)

    sales_cu_source = Column(
        String(50),
        nullable=False,
        default="U_CUINV",
        comment="SAP field holding the CU number on Sales Invoices (e.g. U_CUINV, NumAtCard, Comments, JournalMemo, Reference1)",
    )
    purchase_cu_source = Column(
        String(50),
        nullable=False,
        default="U_CUINV",
        comment="SAP field holding the CU number on Purchase Invoices (e.g. U_CUINV, NumAtCard, Comments, JournalMemo, Reference1)",
    )


    kra_parsing_profiles = Column(JSON, nullable=True, comment="JSON configuration mapping KRA section prefixes to CSV parsing rules")

    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by_id = Column(Integer, nullable=True)

    company = relationship("Company")
    active_connection = relationship("CompanySAPConnection", foreign_keys=[active_connection_id])


class VATMapping(Base):
    __tablename__ = "vat_mappings"
    __table_args__ = (
        UniqueConstraint("connection_id", "module", "sap_code", name="uq_connection_module_sap_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("company_sap_connections.id", ondelete="CASCADE"), nullable=False)
    module = Column(SQLEnum(VatModule, native_enum=False, length=20), nullable=False)
    sap_code = Column(String(50), nullable=False)
    description = Column(String(200), nullable=False, default="")
    canonical_rate = Column(String(20), nullable=False)
    is_builtin = Column(Boolean, nullable=False, default=False)
    is_system_generated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    connection = relationship("CompanySAPConnection", back_populates="vat_mappings")


class SettingAuditLog(Base):
    __tablename__ = "setting_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, nullable=True)
    user_email = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    changes_json = Column(JSON, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class KRAVATMapping(Base):
    __tablename__ = "kra_vat_mappings"

    id = Column(Integer, primary_key=True, index=True)
    section_prefix = Column(String(50), unique=True, index=True, nullable=False, comment="E.g., SEC_B")
    canonical_rate = Column(String(20), nullable=False)
    description = Column(String(200), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
