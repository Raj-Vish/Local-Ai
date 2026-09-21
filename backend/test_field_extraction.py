"""Checks for the receipt field proposer.

Runs without a server and without a database:

    ./venv/bin/python test_field_extraction.py

The cases that matter are the ones where a naive reading goes wrong: a
subtotal sitting above the total, a date that could be read two ways, an
invoice number full of slashes, and OCR that turned a quantity into a letter.
"""
import sys
from datetime import date, timedelta

from models import ExpenseCategory
from services import field_extraction as fx

PASSED, FAILED = [], []


def check(name, condition, detail=""):
    (PASSED if condition else FAILED).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


TAJ = """TAJ RESIDENCY
Colaba, Mumbai 400001
GSTIN: 27AABCT1234M1Z5

TAX INVOICE
Invoice No: TR/2026/09/4417
Date: 01/09/2026
Guest: Raj Vishwakarma

Description              Qty      Amount
Room Charges (Deluxe)      2      4237.29
CGST 9%                            381.36
SGST 9%                            381.35

TOTAL                             5000.00
Payment Mode: Corporate Card"""

# Exactly what Tesseract produced from the photographed receipt.
CAFE_OCR = """CAFE MADRAS

Matunga East, Mumbai

Bill No: 20916
Date: 03/09/2026

Filter Coffee 2 80.00
Masala Dosa 2 360.00
Rava Idli 1 140.00
Subtotal 580.00

GST 5% 29.00

TOTAL 609.00
CASH

THANK YOU VISIT AGAIN"""

# The same, with the OCR damage we actually observed on the scanned PDF.
CAFE_DAMAGED = CAFE_OCR.replace("Rava Idli 1 140.00", "Rava Idli I 140.00")


def main():
    print("Receipt field proposal checks\n" + "=" * 62)

    print("\nA clean digital invoice")
    p = fx.propose(TAJ)
    check("amount is the TOTAL", p.amount.value == "5000.00", f"-> {p.amount.value}")
    check("amount cites its line", "TOTAL" in (p.amount.evidence or ""), f"-> {p.amount.evidence!r}")
    check("date read as DD/MM", p.expense_date.value == "2026-09-01", f"-> {p.expense_date.value}")
    check("vendor is the letterhead", p.vendor.value == "TAJ RESIDENCY", f"-> {p.vendor.value}")
    check("category is Hotel", p.category.value == "Hotel", f"-> {p.category.value}")
    check("nothing unresolved", p.unresolved == [], f"-> {p.unresolved}")

    print("\nThe invoice number must not be mistaken for a date")
    # "Invoice No: TR/2026/09/4417" would read as 26 Sep 4417 without the guard.
    check("year 4417 rejected", p.expense_date.value == "2026-09-01",
          f"-> {p.expense_date.value}")

    print("\nA subtotal must not beat the total")
    p = fx.propose(CAFE_OCR)
    check("amount is 609.00 not 580.00", p.amount.value == "609.00", f"-> {p.amount.value}")
    check("evidence is the TOTAL line", (p.amount.evidence or "").strip() == "TOTAL 609.00",
          f"-> {p.amount.evidence!r}")
    check("category is Food", p.category.value == "Food", f"-> {p.category.value}")
    check("vendor is CAFE MADRAS", p.vendor.value == "CAFE MADRAS", f"-> {p.vendor.value}")

    print("\nA line item's quantity must never become the amount")
    check("360.00 not proposed", p.amount.value != "360.00", f"-> {p.amount.value}")
    check("2 not proposed", p.amount.value != "2.00", f"-> {p.amount.value}")

    print("\nDamaged OCR ('Rava Idli I 140.00')")
    d = fx.propose(CAFE_DAMAGED)
    check("total still correct", d.amount.value == "609.00", f"-> {d.amount.value}")
    check("stray 'I' not read as a value", d.amount.value not in ("1.00", "140.00"),
          f"-> {d.amount.value}")

    print("\nAn ambiguous date is flagged, not silently guessed")
    # 03/09 could be 3 September or 9 March.
    check("confidence dropped", p.expense_date.confidence <= 0.65,
          f"-> {p.expense_date.confidence}")
    check("a note explains why", bool(p.expense_date.note), f"-> {p.expense_date.note}")
    # 27/09 cannot be anything but 27 September.
    # Day 27 cannot be a month, so the reading is forced. Kept in the past:
    # a future date is dropped entirely, which would test the wrong thing.
    forced = fx.propose("Bill\nDate: 27/08/2026\nTOTAL 100.00")
    check("unambiguous date not flagged", forced.expense_date.note is None,
          f"-> {forced.expense_date.value}")

    print("\nA future date is dropped rather than proposed")
    future = (date.today() + timedelta(days=30)).strftime("%d/%m/%Y")
    f = fx.propose(f"SOME SHOP\nDate: {future}\nTOTAL 250.00")
    check("no future date proposed", not f.expense_date.found, f"-> {f.expense_date.value}")
    check("it is listed as unresolved", "expense_date" in f.unresolved, f"-> {f.unresolved}")

    print("\nA missing total is admitted, not invented")
    none = fx.propose("RANDOM SHOP\nDate: 01/09/2026\nThanks for visiting")
    check("amount is None", not none.amount.found, f"-> {none.amount.value}")
    check("a reason is given", bool(none.amount.note), f"-> {none.amount.note}")
    check("amount listed as unresolved", "amount" in none.unresolved, f"-> {none.unresolved}")

    print("\nNothing is ever calculated")
    # Line items sum to 580.00; the printed TOTAL is deliberately different.
    odd = fx.propose("SHOP\nItem A 100.00\nItem B 200.00\nTOTAL 999.00")
    check("takes the printed total, not the sum", odd.amount.value == "999.00",
          f"-> {odd.amount.value}")
    check("verbatim guard accepts a real figure", fx.appears_verbatim("999.00", odd.amount.evidence))
    check("verbatim guard rejects an invented figure",
          not fx.appears_verbatim("300.00", "SHOP\nItem A 100.00\nItem B 200.00\nTOTAL 999.00"))

    print("\nIndian number grouping")
    lakh = fx.propose("HOTEL X\nDate: 01/09/2026\nGRAND TOTAL  Rs. 1,25,400.50")
    check("1,25,400.50 -> 125400.50", lakh.amount.value == "125400.50", f"-> {lakh.amount.value}")

    print("\nCategories stay in step with the database")
    known = {c.value for c in ExpenseCategory}
    mine = set(fx.CATEGORY_KEYWORDS) | {fx.DEFAULT_CATEGORY}
    check("category lists match models.py", mine == known, f"-> {sorted(mine ^ known) or 'identical'}")

    print("\nEmpty input")
    e = fx.propose("")
    check("nothing proposed", len(e.unresolved) == 4, f"-> {e.unresolved}")

    print("\n" + "=" * 62)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("\n  FAILED: " + ", ".join(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
