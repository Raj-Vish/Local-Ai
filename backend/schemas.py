"""The shape of every request and response.

Pydantic checks incoming data before a route ever runs, so a route can trust
what it is given. Anything that fails these rules gets a 422 with a message
naming the field, without a line of validation code in the route itself.
"""
from datetime import date, datetime

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from core.security import BCRYPT_MAX_BYTES
from models import ExpenseCategory


class UserRegister(BaseModel):
    employee_id: str = Field(min_length=2, max_length=32, examples=["EMP001"])
    full_name: str = Field(min_length=2, max_length=120, examples=["Raj Vishwakarma"])
    email: EmailStr = Field(examples=["raj@company.com"])
    password: str = Field(min_length=8, max_length=128, examples=["a-good-password"])

    @field_validator("password")
    @classmethod
    def within_bcrypt_limit(cls, v: str) -> str:
        # Long passwords are fine; silently ignored characters are not.
        if len(v.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(
                f"Password must be at most {BCRYPT_MAX_BYTES} bytes "
                "(accented and non-Latin characters count as more than one)."
            )
        return v

    @field_validator("employee_id")
    @classmethod
    def tidy_employee_id(cls, v: str) -> str:
        # Stored uppercase so EMP001 and emp001 cannot become two accounts.
        return v.strip().upper()

    @field_validator("full_name")
    @classmethod
    def tidy_name(cls, v: str) -> str:
        return " ".join(v.split())


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    employee_id: str
    full_name: str
    email: EmailStr
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: int
    original_filename: str
    mime_type: str
    file_size: int
    status: str
    ocr_used: bool
    # Why extraction failed, in words the uploader can act on. None unless
    # status is "failed".
    error_message: str | None = None
    uploaded_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentOut]
    count: int


class DocumentText(BaseModel):
    """What was read out of a document.

    Deliberately separate from DocumentOut: extracted text can run to tens of
    thousands of characters, and the document list should not carry that.
    """
    document_id: int
    original_filename: str
    status: str
    ocr_used: bool
    error_message: str | None
    char_count: int
    text: str


class ProposedFieldOut(BaseModel):
    """One suggested value, with the line of the document it came from.

    The evidence is not decoration. A person confirming a figure should be
    able to check it against the receipt without opening the receipt.
    """
    value: str | None
    confidence: float
    line_no: int | None
    evidence: str | None
    note: str | None


class ExpenseProposalOut(BaseModel):
    """A suggestion, not a record. Nothing is stored until a person confirms.

    Returned by a GET-shaped, read-only endpoint: proposing changes nothing
    in the database, so abandoning a proposal leaves no trace.
    """
    document_id: int
    original_filename: str
    amount: ProposedFieldOut
    expense_date: ProposedFieldOut
    vendor: ProposedFieldOut
    category: ProposedFieldOut
    # Field names that could not be read; the form asks for these by hand.
    unresolved: list[str]


# --- expenses ---------------------------------------------------------------

# Two decimal places, and small enough that a typo cannot produce a number no
# real expense claim would contain.
Amount = Decimal


class ExpenseBase(BaseModel):
    expense_date: date
    category: ExpenseCategory
    vendor: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    amount: Amount = Field(gt=0, le=Decimal("9999999999.99"))
    currency: str = Field(default="INR", min_length=3, max_length=3)

    @field_validator("expense_date")
    @classmethod
    def not_in_the_future(cls, v: date) -> date:
        # A future date is nearly always a typo, or a day/month swap on an
        # Indian-format receipt. Catching it here beats finding it in a report.
        if v > date.today():
            raise ValueError("Expense date cannot be in the future.")
        return v

    @field_validator("amount")
    @classmethod
    def sensible_precision(cls, v: Decimal) -> Decimal:
        # Money is stored as DECIMAL(12,2); quantise here so the value that
        # comes back matches the value that was stored.
        return v.quantize(Decimal("0.01"))

    @field_validator("vendor")
    @classmethod
    def tidy_vendor(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()


class ExpenseCreate(ExpenseBase):
    document_id: int | None = None


class ExpenseUpdate(BaseModel):
    """Every field optional: a PATCH changes only what it names."""
    expense_date: date | None = None
    category: ExpenseCategory | None = None
    vendor: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    amount: Amount | None = Field(default=None, gt=0, le=Decimal("9999999999.99"))
    document_id: int | None = None

    @field_validator("expense_date")
    @classmethod
    def not_in_the_future(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Expense date cannot be in the future.")
        return v

    @field_validator("amount")
    @classmethod
    def sensible_precision(cls, v: Decimal | None) -> Decimal | None:
        return v if v is None else v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expense_id: int
    expense_date: date
    category: str
    vendor: str
    description: str | None
    amount: Amount
    currency: str
    document_id: int | None
    is_verified: bool
    created_at: datetime


class ExpenseList(BaseModel):
    items: list[ExpenseOut]
    count: int
    # Computed by the server so the figure on screen is never something the
    # browser worked out for itself.
    total: Amount


class CategoryTotal(BaseModel):
    category: str
    total: Amount
    count: int


class ExpenseSummary(BaseModel):
    total: Amount
    count: int
    currency: str
    by_category: list[CategoryTotal]
    period_start: date | None
    period_end: date | None


# --- retrieval (RAG) ---------------------------------------------------------

class SearchQuery(BaseModel):
    """What the caller may ask for.

    Note what is NOT here: there is no user_id and no document scope. The
    backend takes the user from the authenticated token, so no request shape
    can widen a search beyond its own documents.
    """
    query: str = Field(min_length=1, max_length=500, examples=["Mumbai hotel receipt"])
    top_k: int | None = Field(default=None, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def tidy_query(cls, v: str) -> str:
        cleaned = " ".join(v.split())
        if not cleaned:
            raise ValueError("Enter something to search for.")
        return cleaned


class SearchHit(BaseModel):
    document_id: int
    chunk_id: str
    chunk_index: int
    filename: str
    text: str
    # 1.0 is identical, 0.0 is unrelated. Derived from cosine distance so a
    # larger number means a closer match, which is what a reader expects.
    score: float | None
    start_line: int
    end_line: int


class SearchResults(BaseModel):
    query: str
    count: int
    top_k: int
    results: list[SearchHit]
    # True when the index holds nothing for this user yet, so the frontend can
    # say "nothing indexed" rather than "no matches", which mean different things.
    index_empty: bool = False


class AskQuery(BaseModel):
    question: str = Field(min_length=1, max_length=500,
                          examples=["Which hotel did I stay at in Mumbai?"])
    top_k: int | None = Field(default=None, ge=1, le=50)

    @field_validator("question")
    @classmethod
    def tidy_question(cls, v: str) -> str:
        cleaned = " ".join(v.split())
        if not cleaned:
            raise ValueError("Enter a question.")
        return cleaned


class AskAnswer(BaseModel):
    """A phrased answer, plus everything it was based on.

    `facts` are figures computed by MySQL. `sources` are the document extracts
    retrieved. Both are returned so the answer can always be checked against
    what produced it -- and so the frontend can show retrieval working even
    when no language service is connected.
    """
    question: str
    answer: str | None
    answered_by_model: bool
    # Why there is no answer, when there is none.
    unavailable_reason: str | None = None
    facts: list[str]
    sources: list[SearchHit]


class IndexStatusOut(BaseModel):
    """What this user has searchable, and what still needs doing."""
    documents_total: int
    documents_indexed: int
    documents_failed: int
    documents_pending: int
    chunks_indexed: int
    embed_model: str
    search_available: bool


# --- reports -----------------------------------------------------------------

class ReportGenerate(BaseModel):
    report_name: str = Field(min_length=1, max_length=180, examples=["September trip"])
    period_start: date
    period_end: date

    @field_validator("report_name")
    @classmethod
    def tidy_name(cls, v: str) -> str:
        return " ".join(v.split())

    @model_validator(mode="after")
    def sensible_period(self):
        if self.period_end < self.period_start:
            raise ValueError("The end date cannot be before the start date.")
        return self


class ReportItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_item_id: int
    expense_id: int
    # The amount as it was when the report was made, not as it is now.
    amount_at_generation: Amount
    remarks: str | None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: int
    report_name: str
    period_start: date
    period_end: date
    total_amount: Amount
    currency: str
    status: str
    generated_at: datetime | None
    item_count: int = 0


class ReportDetail(ReportOut):
    items: list[ReportItemOut] = []


class ReportList(BaseModel):
    items: list[ReportOut]
    count: int
