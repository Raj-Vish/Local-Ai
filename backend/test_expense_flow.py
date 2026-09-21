"""End-to-end check of the receipt-to-expense flow, against the running API.

    ./venv/bin/python test_expense_flow.py     (server must be running)

    document -> extracted text -> proposed fields -> human edit -> expense

The assertion this exists for: proposing must create NOTHING. Counts and
totals are compared before and after, and after proposing twice, because an
endpoint that quietly wrote a draft row would be easy to miss and would put
unconfirmed figures one bug away from a report.
"""
import json, sys, time
import requests

BASE = "http://127.0.0.1:8000"
ok, bad = [], []
def check(name, cond, detail=""):
    (ok if cond else bad).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")

h = {"Authorization": "Bearer " + requests.post(f"{BASE}/auth/login",
     json={"email": "raj@company.com", "password": "demo12345678"}).json()["access_token"]}

# Pick the seeded hotel invoice by name. Taking items[0] made this test
# depend on what happened to be uploaded most recently.
items = requests.get(f"{BASE}/documents", headers=h).json()["items"]
doc = next((d for d in items if d["original_filename"] == "hotel_invoice.pdf"), items[0])
did = doc["document_id"]
print(f"document {did}: {doc['original_filename']}  status={doc['status']}\n")

print("1. Extracted text is available")
t = requests.get(f"{BASE}/documents/{did}/text", headers=h).json()
check("status is ready", t["status"] == "ready", f"-> {t['status']}")
check("text was extracted", t["char_count"] > 50, f"-> {t['char_count']} chars")

print("\n2. Proposing fields is READ-ONLY")
before_expenses = requests.get(f"{BASE}/expenses", headers=h).json()
before_docs = requests.get(f"{BASE}/documents", headers=h).json()
r = requests.get(f"{BASE}/documents/{did}/propose-expense", headers=h)
check("HTTP 200", r.status_code == 200, f"-> {r.status_code}")
p = r.json()
after_expenses = requests.get(f"{BASE}/expenses", headers=h).json()
after_docs = requests.get(f"{BASE}/documents", headers=h).json()
check("no expense created", after_expenses["count"] == before_expenses["count"],
      f"-> {before_expenses['count']} then {after_expenses['count']}")
check("expense total unchanged", after_expenses["total"] == before_expenses["total"],
      f"-> {before_expenses['total']} then {after_expenses['total']}")
check("no document created or changed", after_docs["count"] == before_docs["count"],
      f"-> {before_docs['count']} then {after_docs['count']}")
# proposing twice must be identical and still create nothing
p2 = requests.get(f"{BASE}/documents/{did}/propose-expense", headers=h).json()
check("repeatable", p == p2)
check("still no expense after 2 calls",
      requests.get(f"{BASE}/expenses", headers=h).json()["count"] == before_expenses["count"])

print("\n3. The proposal itself")
for name in ("amount", "expense_date", "vendor", "category"):
    f = p[name]
    print(f"     {name:13} = {str(f['value']):24} conf={f['confidence']:.2f}  line {f['line_no']}")
    print(f"                     evidence: {f['evidence']!r}")
    if f["note"]:
        print(f"                     note: {f['note']}")
check("amount found", p["amount"]["value"] == "5000.00", f"-> {p['amount']['value']}")
check("vendor found", p["vendor"]["value"] == "TAJ RESIDENCY", f"-> {p['vendor']['value']}")
check("category is Hotel", p["category"]["value"] == "Hotel", f"-> {p['category']['value']}")
check("date found", p["expense_date"]["value"] is not None, f"-> {p['expense_date']['value']}")
check("nothing unresolved", p["unresolved"] == [], f"-> {p['unresolved']}")

print("\n4. Every figure is verbatim in the document")
raw = t["text"].replace(",", "")
check("amount appears in the text", p["amount"]["value"] in raw or p["amount"]["value"][:-3] in raw)
check("evidence line is really in the text", p["amount"]["evidence"].strip() in t["text"])

print("\n5. Confirming — the user edits the amount first")
edited = {
    "expense_date": p["expense_date"]["value"],
    "category": p["category"]["value"],
    "vendor": p["vendor"]["value"],
    "amount": "4999.00",                     # a deliberate human correction
    "description": "Confirmed from receipt",
    "document_id": did,
}
created = requests.post(f"{BASE}/expenses", headers=h, json=edited)
check("expense created", created.status_code == 201, f"-> {created.status_code}")
e = created.json()
check("user's edit was kept", e["amount"] == "4999.00", f"-> {e['amount']}")
check("verified, because a person confirmed it", e["is_verified"] is True, f"-> {e['is_verified']}")
check("linked to its receipt", e["document_id"] == did, f"-> {e['document_id']}")
check("expense count rose by exactly 1",
      requests.get(f"{BASE}/expenses", headers=h).json()["count"] == before_expenses["count"] + 1)

print("\n6. Discarding leaves no trace")
n_before = requests.get(f"{BASE}/expenses", headers=h).json()["count"]
requests.get(f"{BASE}/documents/{did}/propose-expense", headers=h)   # propose, then walk away
check("nothing saved on discard",
      requests.get(f"{BASE}/expenses", headers=h).json()["count"] == n_before)

print("\n7. A document that has not been read cannot be proposed from")
pdf = b"%PDF-1.4\nnot really a pdf\n%%EOF\n"
up = requests.post(f"{BASE}/documents/upload", headers=h,
                   files={"file": ("broken.pdf", pdf, "application/pdf")})
if up.status_code == 201:
    bid = up.json()["document_id"]
    time.sleep(3)
    rr = requests.get(f"{BASE}/documents/{bid}/propose-expense", headers=h)
    check("409 with a reason", rr.status_code == 409, f"-> {rr.status_code}: {rr.json().get('detail','')[:70]}")
    requests.delete(f"{BASE}/documents/{bid}", headers=h)
else:
    check("unreadable upload rejected at the door", up.status_code == 400, f"-> {up.status_code}")

# tidy up the expense this test created
requests.delete(f"{BASE}/expenses/{e['expense_id']}", headers=h)

print("\n" + "=" * 62)
print(f"  {len(ok)} passed, {len(bad)} failed")
if bad: print("  FAILED: " + ", ".join(bad))
sys.exit(1 if bad else 0)
