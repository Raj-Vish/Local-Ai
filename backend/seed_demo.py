"""Reset the database to a known demo state.

Wipes everything and creates two employees with expenses and documents, so a
demo takes seconds to set up rather than being typed live.

    ./venv/bin/python seed_demo.py

Destructive by design: it deletes every user, document, expense and report.
"""
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from config import settings
from core.security import hash_password
from database import Base, SessionLocal, engine
from fixtures import build_receipt_pdf
from models import Document, Expense, ExpenseReport, User
from services import document_pipeline, storage

DEMO_PASSWORD = "demo12345678"

PEOPLE = [
    {
        "employee_id": "EMP001",
        "full_name": "Raj Vishwakarma",
        "email": "raj@company.com",
        # Mirrors the Hotel expense below, so the receipt and the claim agree.
        "receipt": [
            "TAJ RESIDENCY", "Colaba, Mumbai 400001", "GSTIN: 27AABCT1234M1Z5", "",
            "TAX INVOICE", "Invoice No: TR/2026/09/4417", "Date: {{DATE}}",
            "Guest: Raj Vishwakarma", "",
            "Description              Qty      Amount",
            "Room Charges (Deluxe)      2      4237.29",
            "CGST 9%                            381.36",
            "SGST 9%                            381.35", "",
            "TOTAL                             5000.00",
            "Payment Mode: Corporate Card",
        ],
        "expenses": [
            (0,  "Hotel",     "Taj Residency",     "5000.00", "Client visit, Mumbai"),
            (1,  "Transport", "Ola Cabs",           "840.00", "Airport to hotel"),
            (1,  "Food",      "Cafe Madras",       "1250.50", "Team dinner"),
            (2,  "Client",    "The Bombay Canteen","3200.00", "Lunch with client"),
            (3,  "Transport", "IndiGo",            "6499.00", "Return flight"),
            (5,  "Food",      "Barista",            "320.00", None),
            (8,  "Event",     "Conference Desk",   "2500.00", "Annual summit ticket"),
        ],
    },
    {
        "employee_id": "EMP002",
        "full_name": "Priya Sharma",
        "email": "priya@company.com",
        "receipt": [
            "LEMON TREE HOTEL", "Hinjewadi, Pune 411057", "GSTIN: 27AACCL9876P1Z2", "",
            "TAX INVOICE", "Invoice No: LT/2026/09/2210", "Date: {{DATE}}",
            "Guest: Priya Sharma", "",
            "Description              Qty      Amount",
            "Room Charges (Superior)    1      3559.32",
            "CGST 9%                            320.34",
            "SGST 9%                            320.34", "",
            "TOTAL                             4200.00",
            "Payment Mode: Corporate Card",
        ],
        "expenses": [
            (1,  "Transport", "Uber",               "460.00", None),
            (2,  "Food",      "Social Offline",     "980.00", "Client coffee"),
            (4,  "Hotel",     "Lemon Tree",        "4200.00", "Overnight, Pune"),
        ],
    },
]


def wipe(db):
    for model in (ExpenseReport, Expense, Document, User):
        db.query(model).delete()
    db.commit()
    root = Path(settings.STORAGE_ROOT) / "users"
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file():
                path.unlink()


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        wipe(db)
        today = date.today()
        document_ids = []

        for person in PEOPLE:
            user = User(
                employee_id=person["employee_id"],
                full_name=person["full_name"],
                email=person["email"],
                password_hash=hash_password(DEMO_PASSWORD),
            )
            db.add(user)
            db.flush()

            # One sample receipt, so the document list and the receipt
            # dropdown are not empty during a demo -- and so Stage 1 has
            # something real to read.
            # The receipt is dated to match the Hotel expense it supports, so
            # a field proposal read from it agrees with the claim beside it.
            hotel_days_ago = next(
                (days for days, category, *_ in person["expenses"] if category == "Hotel"), 0
            )
            receipt_date = today - timedelta(days=hotel_days_ago)
            lines = [
                line.replace("{{DATE}}", f"{receipt_date:%d/%m/%Y}")
                for line in person["receipt"]
            ]
            pdf = build_receipt_pdf(lines)
            stored, path = storage.save(user.user_id, pdf, ".pdf")
            document = Document(
                user_id=user.user_id,
                original_filename="hotel_invoice.pdf",
                stored_filename=stored,
                file_path=path,
                mime_type="application/pdf",
                file_size=len(pdf),
                # The real hash of the real bytes. Each person's receipt names
                # them, so the two differ naturally and the checksum stays a
                # usable integrity check rather than a salted stand-in.
                checksum_sha256=storage.checksum(pdf),
            )
            db.add(document)
            db.flush()
            document_ids.append(document.document_id)

            for days_ago, category, vendor, amount, note in person["expenses"]:
                db.add(Expense(
                    user_id=user.user_id,
                    # Hotel rows carry the receipt so the paperclip icon shows.
                    document_id=document.document_id if category == "Hotel" else None,
                    expense_date=today - timedelta(days=days_ago),
                    category=category,
                    vendor=vendor,
                    description=note,
                    amount=Decimal(amount),
                    is_verified=True,
                    extraction_confidence=Decimal("1.00"),
                ))

            total = sum(Decimal(e[3]) for e in person["expenses"])
            print(f"  {person['employee_id']}  {person['full_name']:<20} "
                  f"{len(person['expenses'])} expenses  total {total}")

        db.commit()

        # Read each seeded receipt, so a fresh demo opens on "Text ready"
        # rather than a row that has not been processed yet.
        for document_id in document_ids:
            document_pipeline.extract_document(document_id)
        print(f"\n  {len(document_ids)} receipt(s) seeded and read into text.")

        print(f"\n  Sign in with any of the emails above and password: {DEMO_PASSWORD}")
        print("  Expenses span the last 8 days, so this month's view is populated.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
