import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, String, Date, Enum, Numeric, Index, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.schemas.invoice import InvoiceSource, ReconciliationType
from app.domain.reconciliation_status import ReconciliationStatus


class ReconciliationSession(Base):
    __tablename__ = "reconciliation_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_compared: Mapped[bool] = mapped_column(default=False, nullable=False)
    comparison_results: Mapped[dict | None] = mapped_column(JSON, nullable=True) # kept as JSON to preserve schema
    session_type: Mapped[ReconciliationType] = mapped_column(
        Enum(ReconciliationType, native_enum=False),
        default=ReconciliationType.SALES,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    import_profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("import_profiles.id", ondelete="SET NULL"), nullable=True)
    import_profile_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    import_profile_version_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    import_profile_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="Immutable copy of ImportProfileSnapshot used for parsing")

    invoices: Mapped[list["SessionInvoice"]] = relationship(
        "SessionInvoice", back_populates="session", cascade="all, delete-orphan"
    )

    results: Mapped[list["SessionReconciliationResult"]] = relationship(
        "SessionReconciliationResult", back_populates="session", cascade="all, delete-orphan"
    )


class SessionInvoice(Base):
    __tablename__ = "session_invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[InvoiceSource] = mapped_column(Enum(InvoiceSource, native_enum=False), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pin: Mapped[str] = mapped_column(String(100), nullable=False)
    partner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    cu_number: Mapped[str] = mapped_column(String(100), nullable=False)
    vat_group: Mapped[str] = mapped_column(String(50), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    session: Mapped["ReconciliationSession"] = relationship("ReconciliationSession", back_populates="invoices")


    __table_args__ = (
        UniqueConstraint("session_id", "source", "row_number", name="uq_session_invoice_row"),
        Index("ix_session_invoices_session_id", "session_id"),
        Index("ix_session_invoices_session_source_row", "session_id", "source", "row_number"),
        Index("ix_session_invoices_session_cu", "session_id", "cu_number"),
    )


class SessionReconciliationResult(Base):
    __tablename__ = "session_reconciliation_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cu_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Single Tax")
    status: Mapped[ReconciliationStatus] = mapped_column(Enum(ReconciliationStatus, native_enum=False), nullable=False)
    amount_match: Mapped[bool] = mapped_column(default=True, nullable=False)
    vat_match: Mapped[bool] = mapped_column(default=True, nullable=False)
    date_match: Mapped[bool] = mapped_column(default=True, nullable=False)
    partner_name_matches: Mapped[bool] = mapped_column(default=True, nullable=False)
    pin_matches: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Snapshot values for SAP
    sap_invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sap_partner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sap_invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sap_base_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sap_vat_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sap_base_16: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sap_base_8: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sap_base_0: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sap_base_exempt: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    # Snapshot values for KRA
    kra_invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kra_partner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kra_invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    kra_base_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    kra_vat_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    kra_base_16: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    kra_base_8: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    kra_base_0: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    kra_base_exempt: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    # PIN snapshot — populated at /compare time from session_invoices
    sap_pin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kra_pin: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Per-side CU snapshot. `cu_number` above holds only the SAP-side pairing key, so a
    # row paired by the fallback heuristic (amount + partner, used precisely when the two
    # CUs differ) used to redisplay the SAP CU on both sides — a CU Mismatch whose two
    # values looked identical. Nullable: rows compared before this column existed have
    # no per-side value, and the read path falls back to `cu_number`.
    sap_cu_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kra_cu_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    session: Mapped["ReconciliationSession"] = relationship("ReconciliationSession", back_populates="results")

    __table_args__ = (
        UniqueConstraint("session_id", "row_number", name="uq_session_result_row"),
        Index("ix_results_session_row", "session_id", "row_number"),
    )
