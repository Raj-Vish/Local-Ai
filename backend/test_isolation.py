"""Data isolation checks.

The most important rule in the system: one employee must never reach another
employee's documents, expenses or reports. Everything else can be rebuilt; a
leak here is the failure that matters.

Run with the server up:   ./venv/bin/python test_isolation.py

Deliberately written against the live HTTP API rather than the database, so
it tests what an attacker can actually reach -- not what the code intends.
"""
import sys
from datetime import date
from decimal import Decimal

import requests

BASE = "http://127.0.0.1:8000"

A = {"employee_id": "TEST_A", "full_name": "Employee A", "email": "iso-a@example.com", "password": "test-password-a"}
B = {"employee_id": "TEST_B", "full_name": "Employee B", "email": "iso-b@example.com", "password": "test-password-b"}

PASSED, FAILED = [], []


def check(name, condition, detail=""):
    (PASSED if condition else FAILED).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


def register_and_login(who):
    requests.post(f"{BASE}/auth/register", json=who)  # 409 if already there, fine
    r = requests.post(f"{BASE}/auth/login", json={"email": who["email"], "password": who["password"]})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def seed(headers, vendor):
    """Give an employee one document, one expense and one report."""
    pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n" + vendor.encode()
    doc = requests.post(
        f"{BASE}/documents/upload", headers=headers,
        files={"file": (f"{vendor}.pdf", pdf, "application/pdf")},
    ).json()

    exp = requests.post(
        f"{BASE}/expenses", headers=headers,
        json={
            "expense_date": str(date.today()),
            "category": "Hotel",
            "vendor": vendor,
            "amount": "1000.00",
            "document_id": doc["document_id"],
        },
    ).json()

    rep = requests.post(
        f"{BASE}/reports/generate", headers=headers,
        json={
            "report_name": f"{vendor} report",
            "period_start": str(date.today()),
            "period_end": str(date.today()),
        },
    ).json()

    return doc["document_id"], exp["expense_id"], rep["report_id"]


def cleanup():
    for who in (A, B):
        r = requests.post(f"{BASE}/auth/login", json={"email": who["email"], "password": who["password"]})
        if r.status_code != 200:
            continue
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        for rep in requests.get(f"{BASE}/reports", headers=h).json()["items"]:
            requests.delete(f"{BASE}/reports/{rep['report_id']}", headers=h)
        for exp in requests.get(f"{BASE}/expenses", headers=h).json()["items"]:
            requests.delete(f"{BASE}/expenses/{exp['expense_id']}", headers=h)
        for doc in requests.get(f"{BASE}/documents", headers=h).json()["items"]:
            requests.delete(f"{BASE}/documents/{doc['document_id']}", headers=h)


def main():
    print("Data isolation checks\n" + "=" * 62)
    cleanup()

    ha = register_and_login(A)
    hb = register_and_login(B)
    doc_a, exp_a, rep_a = seed(ha, "AlphaVendor")
    seed(hb, "BetaVendor")
    print(f"  set up: A has document {doc_a}, expense {exp_a}, report {rep_a}\n")

    print("Employee B tries to reach Employee A's data")
    attempts = [
        ("read A's document",     "GET",    f"/documents/{doc_a}"),
        ("download A's file",     "GET",    f"/documents/{doc_a}/file"),
        ("delete A's document",   "DELETE", f"/documents/{doc_a}"),
        ("read A's expense",      "GET",    f"/expenses/{exp_a}"),
        ("edit A's expense",      "PATCH",  f"/expenses/{exp_a}"),
        ("delete A's expense",    "DELETE", f"/expenses/{exp_a}"),
        ("view A's report",       "GET",    f"/reports/{rep_a}"),
        ("download A's report",   "GET",    f"/reports/{rep_a}/download"),
        ("delete A's report",     "DELETE", f"/reports/{rep_a}"),
    ]
    for label, method, path in attempts:
        kwargs = {"json": {"amount": "1.00"}} if method == "PATCH" else {}
        code = requests.request(method, f"{BASE}{path}", headers=hb, **kwargs).status_code
        # 404 rather than 403: "forbidden" would confirm the row exists.
        check(label, code == 404, f"-> HTTP {code}")

    print("\nListings show only your own rows")
    for label, path in [("documents", "/documents"), ("expenses", "/expenses"), ("reports", "/reports")]:
        items = requests.get(f"{BASE}{path}", headers=hb).json()["items"]
        names = str(items)
        check(f"B's {label} list excludes A's", "Alpha" not in names, f"-> {len(items)} own item(s)")

    print("\nA's data survived every attempt")
    for label, path in [("document", f"/documents/{doc_a}"), ("expense", f"/expenses/{exp_a}"), ("report", f"/reports/{rep_a}")]:
        code = requests.get(f"{BASE}{path}", headers=ha).status_code
        check(f"A's {label} still there", code == 200, f"-> HTTP {code}")

    print("\nUnauthenticated access")
    for label, path in [("documents", "/documents"), ("expenses", "/expenses"), ("reports", "/reports"),
                        ("a specific document", f"/documents/{doc_a}")]:
        code = requests.get(f"{BASE}{path}").status_code
        check(f"no token on {label}", code in (401, 403), f"-> HTTP {code}")

    print("\nTotals are per user, not global")
    ta = Decimal(requests.get(f"{BASE}/expenses", headers=ha).json()["total"])
    tb = Decimal(requests.get(f"{BASE}/expenses", headers=hb).json()["total"])
    check("A's total counts only A", ta == Decimal("1000.00"), f"-> {ta}")
    check("B's total counts only B", tb == Decimal("1000.00"), f"-> {tb}")

    cleanup()
    print("\n" + "=" * 62)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("\n  FAILED: " + ", ".join(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
