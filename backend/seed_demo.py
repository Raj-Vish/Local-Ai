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
from models import Document, Expense, ExpenseReport, User
from services import storage

DEMO_PASSWORD = "demo12345678"

PEOPLE = [
    {
        "employee_id": "EMP001",
        "full_name": "Raj Vishwakarma",
        "email": "raj@company.com",
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
            # dropdown are not empty during a demo.
            pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
                   b"trailer<</Root 1 0 R>>\n%%EOF\n")
            stored, path = storage.save(user.user_id, pdf, ".pdf")
            document = Document(
                user_id=user.user_id,
                original_filename="hotel_invoice.pdf",
                stored_filename=stored,
                file_path=path,
                mime_type="application/pdf",
                file_size=len(pdf),
                checksum_sha256=storage.checksum(pdf + person["employee_id"].encode()),
            )
            db.add(document)
            db.flush()

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
        print(f"\n  Sign in with any of the emails above and password: {DEMO_PASSWORD}")
        print("  Expenses span the last 8 days, so this month's view is populated.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
