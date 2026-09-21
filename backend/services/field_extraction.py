"""Stage 1b: propose expense fields from a receipt's extracted text.

Deliberately deterministic. A total on a receipt is a labelled number on a
line -- finding it is a job for a pattern, not a language model, and a pattern
can show its working. Every proposed value carries the exact line it came
from, so a person confirming it can check in one glance rather than trusting.

The rule that matters most:

    NOTHING HERE IS EVER CALCULATED.

Every figure is a substring lifted out of the document. Line items are never
summed, a missing total is never reconstructed, and a value that cannot be
pointed at in the source is not proposed at all. That is the same boundary
the reports keep -- the database calculates, nothing else does -- enforced at
the earliest possible moment.

Nothing here writes to the database either. A proposal is a suggestion; only
a person pressing Confirm creates an expense.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime

# The fixed category list, mirrored from models.ExpenseCategory. Imported
# rather than re-declared would couple this module to SQLAlchemy for no gain;
# the test suite checks the two stay in step.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Hotel": ("room charge", "room", "hotel", "residency", "inn", "lodge",
              "guest", "check-in", "checkout", "check out", "accommodation", "tariff"),
    "Transport": ("taxi", "cab", "uber", "ola", "flight", "indigo", "airfare",
                  "fare", "toll", "airport", "railway", "train", "pnr", "boarding"),
    "Food": ("cafe", "restaurant", "dosa", "idli", "coffee", "dinner", "lunch",
             "canteen", "kitchen", "bakery", "beverage", "food", "meal"),
    "Client": ("client", "hospitality", "business meeting"),
    "Event": ("conference", "summit", "ticket", "registration", "delegate", "seminar"),
}
DEFAULT_CATEGORY = "Other"

# Ordered by how strongly the label means "this is the figure being claimed".
# SUBTOTAL is handled separately -- see _is_subtotal.
AMOUNT_LABELS: tuple[tuple[str, float], ...] = (
    ("grand total", 0.95),
    ("amount payable", 0.95),
    ("net payable", 0.95),
    ("net amount", 0.90),
    ("total", 0.90),
    ("amount", 0.70),
)

# A money token: optional currency mark, digits with optional Indian or
# Western grouping, optional two decimals.
#
# The grouped alternative requires at least one comma. With `*` it also
# matched the first three digits of a plain number, so "5000.00" came back as
# "500" followed by "0.00" -- and the receipt's real total was never seen.
# The surrounding (?<!\d) / (?!\d) stop any partial match for the same reason.
_MONEY = re.compile(
    r"(?:(?:₹|rs\.?|inr)\s*)?"
    r"(?<!\d)(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?!\d)",
    re.I,
)

# (?<!\d) stops "TR/2026/09/4417" being read as 26 September 4417.
_DATE_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)"), "dmy"),
    (re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)"), "ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})(?!\d)"), "dMy"),
    (re.compile(r"(?<!\w)([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})(?!\d)"), "Mdy"),
    (re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{2})(?!\d)"), "dmy2"),
)

_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}

# Lines that describe the document rather than the vendor.
_NOT_A_VENDOR = (
    "tax invoice", "invoice", "receipt", "bill", "gstin", "gst no", "cash memo",
    "credit note", "statement", "duplicate", "original", "customer copy",
)

_EARLIEST_YEAR = 1990


@dataclass
class ProposedField:
    """One suggested value, with the evidence for it."""
    value: str | None = None
    confidence: float = 0.0
    line_no: int | None = None
    evidence: str | None = None
    note: str | None = None

    @property
    def found(self) -> bool:
        return self.value is not None


@dataclass
class Proposal:
    amount: ProposedField = field(default_factory=ProposedField)
    expense_date: ProposedField = field(default_factory=ProposedField)
    vendor: ProposedField = field(default_factory=ProposedField)
    category: ProposedField = field(default_factory=ProposedField)
    unresolved: list[str] = field(default_factory=list)


# --- helpers ----------------------------------------------------------------

def _numbered_lines(text: str) -> list[tuple[int, str]]:
    """1-indexed, blank lines dropped but numbering preserved."""
    return [(n, ln.strip()) for n, ln in enumerate(text.splitlines(), start=1) if ln.strip()]


def _is_subtotal(lowered: str) -> bool:
    """A subtotal is not the amount being claimed, and contains the word 'total'."""
    return "subtotal" in lowered or "sub total" in lowered or "sub-total" in lowered


def _money_tokens(line: str) -> list[str]:
    """Every money-like token on a line, in order."""
    return [m.group(1) for m in _MONEY.finditer(line)]


def _normalise_amount(token: str) -> str | None:
    """'5,000.00' -> '5000.00'. Returns None if it is not a usable amount."""
    cleaned = token.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", cleaned):
        return None
    if "." not in cleaned:
        cleaned += ".00"
    whole, _, frac = cleaned.partition(".")
    cleaned = f"{whole}.{frac.ljust(2, '0')}"
    if cleaned.startswith("0.00") or float(cleaned) <= 0:
        return None
    return cleaned


def appears_verbatim(value: str, text: str) -> bool:
    """Guard: the proposed figure must be readable in the document itself.

    Not a formality. If a future change ever computes a total instead of
    lifting one, this is what catches it before the number reaches a person
    wearing the authority of 'the system read your receipt'.
    """
    flattened = text.replace(",", "")
    if value in flattened:
        return True
    # A receipt may print 5000 where we normalised to 5000.00.
    whole = value[:-3] if value.endswith(".00") else value
    return whole in flattened


# --- the four fields --------------------------------------------------------

def find_amount(lines: list[tuple[int, str]], text: str) -> ProposedField:
    """The figure being claimed: a labelled total, never a computed one."""
    best: tuple[float, int, str, str] | None = None   # confidence, line_no, line, token

    for line_no, line in lines:
        lowered = line.lower()
        if _is_subtotal(lowered):
            continue
        for label, confidence in AMOUNT_LABELS:
            if label not in lowered:
                continue
            tokens = _money_tokens(line)
            if not tokens:
                continue
            # Rightmost token: receipts put the amount in the last column,
            # after any quantity or rate.
            if best is None or confidence > best[0]:
                best = (confidence, line_no, line, tokens[-1])
            break   # strongest label on this line wins

    if best is None:
        return ProposedField(note="No line labelled with a total was found.")

    confidence, line_no, line, token = best
    value = _normalise_amount(token)
    if value is None:
        return ProposedField(
            note=f"The total on line {line_no} could not be read as an amount.")

    if not appears_verbatim(value, text):
        # Cannot happen by construction; kept so it never starts happening.
        return ProposedField(
            note="A total was found but could not be verified against the text.")

    return ProposedField(value=value, confidence=confidence, line_no=line_no, evidence=line)


def _build_date(day: int, month: int, year: int) -> date | None:
    if year < _EARLIEST_YEAR or year > date.today().year + 1:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_on_line(line: str) -> tuple[date, bool] | None:
    """Returns (date, ambiguous). Ambiguous means DD/MM vs MM/DD is a coin toss."""
    for pattern, kind in _DATE_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        a, b, c = match.groups()
        try:
            if kind in ("dmy", "dmy2"):
                day, month = int(a), int(b)
                year = int(c) if kind == "dmy" else 2000 + int(c)
                # Indian receipts are DD/MM. When the day is 13 or more the
                # reading is forced; at 12 or less it genuinely is not.
                ambiguous = day <= 12 and month <= 12
                built = _build_date(day, month, year)
                if built is None and ambiguous:
                    built = _build_date(month, day, year)   # try the other way
                return (built, ambiguous) if built else None
            if kind == "ymd":
                built = _build_date(int(c), int(b), int(a))
                return (built, False) if built else None
            if kind == "dMy":
                month = _MONTHS.get(b[:3].lower())
                if month is None:
                    continue
                built = _build_date(int(a), month, int(c))
                return (built, False) if built else None
            if kind == "Mdy":
                month = _MONTHS.get(a[:3].lower())
                if month is None:
                    continue
                built = _build_date(int(b), month, int(c))
                return (built, False) if built else None
        except (TypeError, ValueError):
            continue
    return None


def find_date(lines: list[tuple[int, str]]) -> ProposedField:
    """When the money was spent. A labelled date wins over a loose one."""
    labelled: tuple[int, str, date, bool] | None = None
    loose: tuple[int, str, date, bool] | None = None
    today = date.today()

    for line_no, line in lines:
        parsed = _parse_on_line(line)
        if parsed is None:
            continue
        value, ambiguous = parsed
        # The schema refuses a future date, so proposing one would only
        # produce a 422 the person cannot act on.
        if value > today:
            continue
        is_labelled = "date" in line.lower() or "dated" in line.lower()
        if is_labelled and labelled is None:
            labelled = (line_no, line, value, ambiguous)
        elif loose is None:
            loose = (line_no, line, value, ambiguous)

    chosen = labelled or loose
    if chosen is None:
        return ProposedField(note="No usable date was found in this document.")

    line_no, line, value, ambiguous = chosen
    confidence = 0.90 if labelled else 0.75
    note = None
    if ambiguous:
        confidence = 0.60
        note = (f"Read as day/month. Confirm this is "
                f"{value:%d %B}, not {value.month:02d}/{value.day:02d} read the other way.")

    return ProposedField(value=value.isoformat(), confidence=confidence,
                         line_no=line_no, evidence=line, note=note)


def find_vendor(lines: list[tuple[int, str]]) -> ProposedField:
    """Who was paid: the letterhead, which is the first real line.

    An earlier version preferred the line directly above the GSTIN. On a
    letterhead of "TAJ RESIDENCY / Colaba, Mumbai 400001 / GSTIN: ..." that
    is the address, not the vendor. The first plausible line is right far
    more often, so the GSTIN rule is now only a fallback.
    """
    for line_no, line in lines[:6]:
        if _plausible_vendor(line):
            return ProposedField(value=line, confidence=0.85, line_no=line_no, evidence=line)

    for index, (_line_no, line) in enumerate(lines):
        if ("gstin" in line.lower() or "gst no" in line.lower()) and index > 0:
            previous_no, previous = lines[index - 1]
            if _plausible_vendor(previous):
                return ProposedField(value=previous, confidence=0.70,
                                     line_no=previous_no, evidence=previous)
            break

    return ProposedField(note="No vendor name could be identified.")


def _plausible_vendor(line: str) -> bool:
    lowered = line.lower()
    if len(line) < 3 or len(line) > 180:
        return False
    if any(word in lowered for word in _NOT_A_VENDOR):
        return False
    letters = sum(c.isalpha() for c in line)
    return letters >= 3 and letters >= len(line) / 2


def find_category(lines: list[tuple[int, str]]) -> ProposedField:
    """Which bucket this belongs in, by keyword. Scored, not first-match."""
    scores: dict[str, int] = {}
    evidence: dict[str, tuple[int, str]] = {}

    for line_no, line in lines:
        lowered = line.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in lowered:
                    scores[category] = scores.get(category, 0) + 1
                    evidence.setdefault(category, (line_no, line))

    if not scores:
        return ProposedField(value=DEFAULT_CATEGORY, confidence=0.30,
                             note="No category keywords matched; defaulted to Other.")

    best = max(scores, key=lambda c: scores[c])
    line_no, line = evidence[best]
    confidence = 0.85 if scores[best] >= 2 else 0.60
    return ProposedField(value=best, confidence=confidence, line_no=line_no, evidence=line)


# --- entry point ------------------------------------------------------------

def propose(text: str) -> Proposal:
    """Read a document's text and suggest the four fields of an expense."""
    lines = _numbered_lines(text or "")
    if not lines:
        empty = Proposal()
        empty.unresolved = ["amount", "expense_date", "vendor", "category"]
        return empty

    proposal = Proposal(
        amount=find_amount(lines, text),
        expense_date=find_date(lines),
        vendor=find_vendor(lines),
        category=find_category(lines),
    )
    proposal.unresolved = [
        name for name in ("amount", "expense_date", "vendor", "category")
        if not getattr(proposal, name).found
    ]
    return proposal
