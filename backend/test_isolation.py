"""Data isolation checks.

The most important rule in the system: one employee must never reach another
employee's documents, expenses or reports. Everything else can be rebuilt; a
leak here is the failure that matters.

Run with the server up:   ./venv/bin/python test_isolation.py

Deliberately written against the live HTTP API rather than the database, so
it tests what an attacker can actually reach -- not what the code intends.
"""
import sys
import time
from datetime import date
from decimal import Decimal

import requests

from fixtures import build_receipt_pdf

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
    """Give an employee one document, one expense and one report.

    The document is a real, readable PDF so extraction reaches "ready". A
    placeholder that fails to extract would leave /text and /propose-expense
    short-circuiting on status before the ownership check was ever reached --
    the isolation checks would pass without testing anything.
    """
    pdf = build_receipt_pdf([vendor, "TAX INVOICE", "Date: 01/08/2026", "TOTAL 1000.00"])
    doc = requests.post(
        f"{BASE}/documents/upload", headers=headers,
        files={"file": (f"{vendor}.pdf", pdf, "application/pdf")},
    ).json()

    # Extraction runs in the background; wait for it so the checks below hit
    # the real code path rather than a "not ready yet" short circuit.
    for _ in range(20):
        state = requests.get(f"{BASE}/documents/{doc['document_id']}", headers=headers).json()
        if state["status"] in ("ready", "failed"):
            break
        time.sleep(0.25)

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
    state = requests.get(f"{BASE}/documents/{doc_a}", headers=ha).json()["status"]
    print(f"  set up: A has document {doc_a} ({state}), expense {exp_a}, report {rep_a}")
    check("A's document really was readable", state == "ready", f"-> {state}")
    print()

    print("Employee B tries to reach Employee A's data")
    attempts = [
        ("read A's document",     "GET",    f"/documents/{doc_a}"),
        ("download A's file",     "GET",    f"/documents/{doc_a}/file"),
        # Extracted text is the document's contents in another form, so it
        # carries exactly the same isolation rule as the file itself.
        ("read A's extracted text", "GET",  f"/documents/{doc_a}/text"),
        ("re-extract A's document", "POST", f"/documents/{doc_a}/extract"),
        # A proposal is built from A's receipt text, so it leaks the same
        # contents by another route.
        ("propose from A's document", "GET", f"/documents/{doc_a}/propose-expense"),
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

    # A document with no extracted text never reaches resolve_for_read, so the
    # route's own ownership check is the ONLY thing protecting it. Without
    # this case the storage-containment layer silently covers for a missing
    # check and the suite cannot tell the difference.
    print("\nA document with no extracted text (ownership check standing alone)")
    unreadable = b"%PDF-1.4\nnot a real pdf\n%%EOF\n"
    broken = requests.post(
        f"{BASE}/documents/upload", headers=ha,
        files={"file": ("unreadable.pdf", unreadable, "application/pdf")},
    )
    if broken.status_code == 201:
        broken_id = broken.json()["document_id"]
        for _ in range(20):
            st = requests.get(f"{BASE}/documents/{broken_id}", headers=ha).json()["status"]
            if st in ("ready", "failed"):
                break
            time.sleep(0.25)
        r = requests.get(f"{BASE}/documents/{broken_id}/text", headers=hb)
        check("B cannot read text of A's unreadable document", r.status_code == 404,
              f"-> HTTP {r.status_code}")
        r = requests.get(f"{BASE}/documents/{broken_id}/propose-expense", headers=hb)
        check("B cannot propose from A's unreadable document", r.status_code == 404,
              f"-> HTTP {r.status_code}")
        requests.delete(f"{BASE}/documents/{broken_id}", headers=ha)
    else:
        check("unreadable fixture uploaded", False, f"-> HTTP {broken.status_code}")

    print("\nListings show only your own rows")
    for label, path in [("documents", "/documents"), ("expenses", "/expenses"), ("reports", "/reports")]:
        items = requests.get(f"{BASE}{path}", headers=hb).json()["items"]
        names = str(items)
        check(f"B's {label} list excludes A's", "Alpha" not in names, f"-> {len(items)} own item(s)")

    print("\nA's data survived every attempt")
    for label, path in [("document", f"/documents/{doc_a}"), ("expense", f"/expenses/{exp_a}"), ("report", f"/reports/{rep_a}")]:
        code = requests.get(f"{BASE}{path}", headers=ha).status_code
        check(f"A's {label} still there", code == 200, f"-> HTTP {code}")

    # Vectors are a second copy of every document's contents. A search that
    # ignored ownership would answer questions about documents the asker
    # cannot open -- the same leak by a different route.
    print("\nSemantic search is scoped to the asker")
    requests.post(f"{BASE}/documents/{doc_a}/index", headers=ha)
    time.sleep(3)
    for query in ("AlphaVendor", "hotel invoice total"):
        res = requests.post(f"{BASE}/rag/search", headers=hb, json={"query": query})
        hits = res.json().get("results", []) if res.status_code == 200 else []
        check(f"B searching {query!r} gets none of A's documents",
              all(h["document_id"] != doc_a for h in hits),
              f"-> HTTP {res.status_code}, {len(hits)} own hit(s)")

    print("\nUnauthenticated access")
    for label, path in [("documents", "/documents"), ("expenses", "/expenses"), ("reports", "/reports"),
                        ("a specific document", f"/documents/{doc_a}"),
                        ("extracted text", f"/documents/{doc_a}/text"),
                        ("an expense proposal", f"/documents/{doc_a}/propose-expense"),
                        ("the index status", "/rag/status")]:
        code = requests.get(f"{BASE}{path}").status_code
        check(f"no token on {label}", code in (401, 403), f"-> HTTP {code}")

    for label, path, body in [("semantic search", "/rag/search", {"query": "hotel"}),
                              ("ask", "/rag/ask", {"question": "hotel?"})]:
        code = requests.post(f"{BASE}{path}", json=body).status_code
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
