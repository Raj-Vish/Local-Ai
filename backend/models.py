"""Database tables.

Phase one holds users, documents, expenses and reports. Chat tables arrive
with the AI phase; create_all() adds missing tables, so there is no cost to
leaving them out until they are actually used.

Money is DECIMAL everywhere. Float cannot represent 0.1 exactly, so totals
drift by fractions of a rupee -- unacceptable in a system about expenses.
"""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Index,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ExpenseCategory(str, Enum):
    """The fixed list of categories.

    Kept in Python rather than a MySQL ENUM: adding a category here is a code
    change, whereas an ENUM column would need an ALTER TABLE on a live table.
    The column stays VARCHAR and this class does the validating.
    """
    HOTEL = "Hotel"
    TRANSPORT = "Transport"
    FOOD = "Food"
    CLIENT = "Client"
    EVENT = "Event"
    OTHER = "Other"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"       # stored, nothing read from it yet
    PROCESSING = "processing"   # extraction running (AI phase)
    READY = "ready"
    FAILED = "failed"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    GENERATED = "generated"


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    # bcrypt output is 60 chars; 255 leaves room to move to argon2 later.
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reports: Mapped[list["ExpenseReport"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.employee_id} {self.email}>"


class Document(Base):
    __tablename__ = "documents"

    document_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )

    # What the employee called it -- display only. Never used to build a path.
    original_filename: Mapped[str] = mapped_column(String(255))
    # What it is called on disk: a UUID, so a hostile filename cannot escape
    # the storage folder.
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_path: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(BigInteger)
    # SHA-256 of the bytes. Catches the same receipt uploaded twice, which
    # would otherwise be claimed twice.
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)

    # Set by the AI phase; harmless nulls until then.
    extracted_text_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.UPLOADED.value)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="documents")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="document")

    __table_args__ = (
        # The same file uploaded twice by one person is a duplicate; the same
        # file uploaded by two people is not.
        Index("ux_user_checksum", "user_id", "checksum_sha256", unique=True),
        Index("ix_documents_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Document {self.document_id} {self.original_filename}>"


class Expense(Base):
    __tablename__ = "expenses"

    expense_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Reachable via documents, but stored directly too: every security-critical
    # query filters on user_id, and one column beats a join on the hot path.
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    # Nullable: an expense typed in by hand has no source document.
    document_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("documents.document_id", ondelete="SET NULL"), nullable=True
    )

    expense_date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(32))
    vendor: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    # False until a human has confirmed it. Only verified rows reach a report.
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Filled by the AI phase; 1.0 for anything a person typed themselves.
    extraction_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="expenses")
    document: Mapped["Document | None"] = relationship(back_populates="expenses")
    report_items: Mapped[list["ExpenseReportItem"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # The query the expenses page runs on every load.
        Index("ix_expenses_user_date", "user_id", "expense_date"),
        Index("ix_expenses_user_category", "user_id", "category"),
    )

    def __repr__(self) -> str:
        return f"<Expense {self.expense_id} {self.category} {self.amount}>"


class ExpenseReport(Base):
    __tablename__ = "expense_reports"

    report_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )

    report_name: Mapped[str] = mapped_column(String(180))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(20), default=ReportStatus.DRAFT.value)

    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="reports")
    items: Mapped[list["ExpenseReportItem"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_reports_user_period", "user_id", "period_start"),)

    def __repr__(self) -> str:
        return f"<ExpenseReport {self.report_id} {self.report_name}>"


class ExpenseReportItem(Base):
    """Freezes which expenses went into which report.

    amount_at_generation is deliberately a copy, not a lookup. A submitted
    report is a historical record: editing an expense next month must not
    silently change a report already handed in.
    """
    __tablename__ = "expense_report_items"

    report_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("expense_reports.report_id", ondelete="CASCADE"), index=True
    )
    expense_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("expenses.expense_id", ondelete="CASCADE"), index=True
    )

    amount_at_generation: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    report: Mapped["ExpenseReport"] = relationship(back_populates="items")
    expense: Mapped["Expense"] = relationship(back_populates="report_items")

    __table_args__ = (
        # One expense appears at most once in a given report.
        Index("ux_report_expense", "report_id", "expense_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ExpenseReportItem r{self.report_id} e{self.expense_id}>"
