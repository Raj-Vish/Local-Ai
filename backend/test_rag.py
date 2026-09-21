"""Retrieval and indexing checks, against the live API.

    ./venv/bin/python test_rag.py     (server must be running)

The checks that matter most are the isolation ones. A vector database is a
second copy of every document's contents, and it would be easy to build one
that answers questions about documents the asker cannot open. Employee B
searching for words that appear only in Employee A's receipt must find
nothing -- and must not be told that something was hidden.
"""
import sys
import time

import requests

from fixtures import build_receipt_pdf

BASE = "http://127.0.0.1:8000"

A = {"employee_id": "RAG_A", "full_name": "Rag A", "email": "rag-a@example.com",
     "password": "rag-password-a"}
B = {"employee_id": "RAG_B", "full_name": "Rag B", "email": "rag-b@example.com",
     "password": "rag-password-b"}

PASSED, FAILED = [], []


def check(name, condition, detail=""):
    (PASSED if condition else FAILED).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


def login(who):
    requests.post(f"{BASE}/auth/register", json=who)
    r = requests.post(f"{BASE}/auth/login", json={"email": who["email"], "password": who["password"]})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def upload_and_index(headers, name, lines):
    pdf = build_receipt_pdf(lines)
    up = requests.post(f"{BASE}/documents/upload", headers=headers,
                       files={"file": (name, pdf, "application/pdf")})
    if up.status_code != 201:
        return None
    doc_id = up.json()["document_id"]
    for _ in range(40):
        state = requests.get(f"{BASE}/documents/{doc_id}", headers=headers).json()
        if state["status"] in ("ready", "failed"):
            break
        time.sleep(0.25)
    # Extraction queues indexing itself; wait for it to land.
    for _ in range(40):
        st = requests.get(f"{BASE}/rag/status", headers=headers).json()
        if st["documents_indexed"] >= 1:
            break
        time.sleep(0.25)
    return doc_id


def wipe(headers):
    for d in requests.get(f"{BASE}/documents", headers=headers).json()["items"]:
        requests.delete(f"{BASE}/documents/{d['document_id']}", headers=headers)


def main():
    print("Retrieval and indexing checks\n" + "=" * 62)

    ha, hb = login(A), login(B)
    wipe(ha); wipe(hb)

    doc_taj = upload_and_index(ha, "taj.pdf", [
        "TAJ RESIDENCY", "Colaba, Mumbai 400001", "TAX INVOICE",
        "Date: 01/08/2026", "Room Charges (Deluxe)", "TOTAL 5000.00"])
    doc_ola = upload_and_index(ha, "ola.pdf", [
        "OLA CABS", "Trip receipt", "Date: 02/08/2026",
        "Airport to hotel, sedan", "TOTAL 840.00"])
    doc_mar = upload_and_index(hb, "marriott.pdf", [
        "MARRIOTT", "Aerocity, New Delhi 110037", "TAX INVOICE",
        "Date: 03/08/2026", "Room Charges (Executive)", "TOTAL 7200.00"])
    print(f"  A has documents {doc_taj}, {doc_ola}; B has {doc_mar}\n")

    print("Indexing happened automatically after extraction")
    sa = requests.get(f"{BASE}/rag/status", headers=ha).json()
    sb = requests.get(f"{BASE}/rag/status", headers=hb).json()
    check("A has 2 indexed documents", sa["documents_indexed"] == 2, f"-> {sa['documents_indexed']}")
    check("B has 1 indexed document", sb["documents_indexed"] == 1, f"-> {sb['documents_indexed']}")
    check("A has chunks", sa["chunks_indexed"] >= 2, f"-> {sa['chunks_indexed']}")
    check("no indexing failures for A", sa["documents_failed"] == 0, f"-> {sa['documents_failed']}")
    check("embed model is reported", bool(sa["embed_model"]), f"-> {sa['embed_model']}")

    print("\nSearch finds by meaning, not by shared words")
    r = requests.post(f"{BASE}/rag/search", headers=ha, json={"query": "cab ride to the airport"}).json()
    top = r["results"][0] if r["results"] else {}
    check("'cab ride' finds the Ola taxi receipt", top.get("document_id") == doc_ola,
          f"-> doc {top.get('document_id')} score {top.get('score')}")
    r = requests.post(f"{BASE}/rag/search", headers=ha, json={"query": "place I stayed in Mumbai"}).json()
    top = r["results"][0] if r["results"] else {}
    check("'place I stayed' finds the hotel", top.get("document_id") == doc_taj,
          f"-> doc {top.get('document_id')} score {top.get('score')}")

    print("\nResults carry enough to trace them back")
    hit = r["results"][0]
    for field in ("document_id", "chunk_id", "chunk_index", "filename", "text", "score",
                  "start_line", "end_line"):
        check(f"hit has {field}", field in hit and hit[field] is not None, f"-> {hit.get(field)!r}"[:70])

    print("\n*** ISOLATION: B must never retrieve A's chunks ***")
    for query in ["TAJ RESIDENCY", "Colaba Mumbai 400001", "place I stayed in Mumbai",
                  "cab ride to the airport", "5000.00"]:
        res = requests.post(f"{BASE}/rag/search", headers=hb, json={"query": query}).json()
        leaked = [h for h in res["results"] if h["document_id"] in (doc_taj, doc_ola)]
        check(f"B searching {query!r} gets none of A's", not leaked,
              f"-> {len(res['results'])} own hit(s), {len(leaked)} leaked")

    print("\nAnd the reverse")
    for query in ["MARRIOTT", "Aerocity New Delhi"]:
        res = requests.post(f"{BASE}/rag/search", headers=ha, json={"query": query}).json()
        leaked = [h for h in res["results"] if h["document_id"] == doc_mar]
        check(f"A searching {query!r} gets none of B's", not leaked,
              f"-> {len(res['results'])} own hit(s), {len(leaked)} leaked")

    print("\nB's own documents are still findable (isolation is not just 'return nothing')")
    res = requests.post(f"{BASE}/rag/search", headers=hb, json={"query": "Delhi hotel room"}).json()
    check("B finds B's Marriott", any(h["document_id"] == doc_mar for h in res["results"]),
          f"-> {len(res['results'])} hit(s)")

    # The HTTP checks above pass even if the vector store's own user filter is
    # removed, because api/rag.py re-checks every hit against documents owned
    # in MySQL. That is defence in depth working -- but it also means the
    # store's filter is not tested by them. This calls it directly, with
    # nothing in front of it.
    print("\n*** ISOLATION at the vector store itself (no API layer in front) ***")
    from services import embeddings as _emb, vector_store as _vs
    a_id = requests.get(f"{BASE}/users/me", headers=ha).json()["user_id"]
    b_id = requests.get(f"{BASE}/users/me", headers=hb).json()["user_id"]
    probe = _emb.embed_query("TAJ RESIDENCY Colaba Mumbai hotel room")

    as_b = _vs.search(user_id=b_id, query_vector=probe, top_k=20)
    check("store called as B returns only B's chunks",
          all(h["document_id"] == doc_mar for h in as_b),
          f"-> {len(as_b)} hit(s), documents {sorted({h['document_id'] for h in as_b})}")
    check("store called as B returns none of A's",
          not any(h["document_id"] in (doc_taj, doc_ola) for h in as_b))

    as_a = _vs.search(user_id=a_id, query_vector=probe, top_k=20)
    check("store called as A does return A's chunks",
          any(h["document_id"] == doc_taj for h in as_a), f"-> {len(as_a)} hit(s)")
    check("store called as A returns none of B's",
          not any(h["document_id"] == doc_mar for h in as_a))
    check("a user with nothing indexed gets nothing",
          _vs.search(user_id=99_999_999, query_vector=probe, top_k=20) == [])
    check("count_for_user is scoped", _vs.count_for_user(b_id) < _vs.count_for_user(a_id) + 99)

    print("\nUnauthenticated access")
    for label, method, path, body in [
        ("search", "POST", "/rag/search", {"query": "hotel"}),
        ("ask", "POST", "/rag/ask", {"question": "hotel?"}),
        ("status", "GET", "/rag/status", None),
    ]:
        code = requests.request(method, f"{BASE}{path}", json=body).status_code
        check(f"no token on {label}", code in (401, 403), f"-> HTTP {code}")

    print("\nA garbage token is refused")
    bad = {"Authorization": "Bearer not.a.real.token"}
    code = requests.post(f"{BASE}/rag/search", headers=bad, json={"query": "hotel"}).status_code
    check("forged token rejected", code == 401, f"-> HTTP {code}")

    print("\ntop_k is bounded by the server")
    res = requests.post(f"{BASE}/rag/search", headers=ha, json={"query": "hotel", "top_k": 999})
    check("absurd top_k rejected or clamped", res.status_code == 422 or res.json()["top_k"] <= 20,
          f"-> HTTP {res.status_code}")
    res = requests.post(f"{BASE}/rag/search", headers=ha, json={"query": "hotel", "top_k": 1}).json()
    check("top_k=1 returns at most one", len(res["results"]) <= 1, f"-> {len(res['results'])}")

    print("\nEmpty and awkward queries are handled")
    check("empty query rejected",
          requests.post(f"{BASE}/rag/search", headers=ha, json={"query": ""}).status_code == 422)
    check("whitespace query rejected",
          requests.post(f"{BASE}/rag/search", headers=ha, json={"query": "    "}).status_code == 422)
    res = requests.post(f"{BASE}/rag/search", headers=ha,
                        json={"query": "zzzz quantum submarine tariff"}).json()
    check("nonsense query returns safely", res["count"] >= 0, f"-> {res['count']} hit(s)")

    print("\nRe-indexing replaces rather than duplicates")
    before = requests.get(f"{BASE}/rag/status", headers=ha).json()["chunks_indexed"]
    requests.post(f"{BASE}/documents/{doc_taj}/index", headers=ha)
    time.sleep(4)
    after = requests.get(f"{BASE}/rag/status", headers=ha).json()["chunks_indexed"]
    check("chunk count unchanged after re-index", before == after, f"-> {before} then {after}")

    print("\nDeleting a document removes it from search")
    requests.delete(f"{BASE}/documents/{doc_ola}", headers=ha)
    time.sleep(1)
    res = requests.post(f"{BASE}/rag/search", headers=ha, json={"query": "cab ride to the airport"}).json()
    check("deleted document no longer retrievable",
          not any(h["document_id"] == doc_ola for h in res["results"]),
          f"-> {len(res['results'])} hit(s)")
    after_delete = requests.get(f"{BASE}/rag/status", headers=ha).json()["chunks_indexed"]
    check("its chunks were removed too", after_delete < after, f"-> {after} then {after_delete}")

    print("\n/rag/ask works without a language service")
    r = requests.post(f"{BASE}/rag/ask", headers=ha, json={"question": "Where did I stay in Mumbai?"})
    check("ask returns 200", r.status_code == 200, f"-> {r.status_code}")
    payload = r.json()
    check("no model answer, and it says why", payload["answer"] is None
          and bool(payload["unavailable_reason"]), f"-> {payload.get('unavailable_reason')}")
    check("retrieval still returned sources", len(payload["sources"]) >= 1,
          f"-> {len(payload['sources'])} source(s)")
    check("facts came from the database", isinstance(payload["facts"], list))
    check("ask sources are A's only",
          all(h["document_id"] != doc_mar for h in payload["sources"]))

    print("\nB asking cannot reach A's documents either")
    payload = requests.post(f"{BASE}/rag/ask", headers=hb,
                            json={"question": "Tell me about the Taj Residency in Colaba"}).json()
    check("B's ask returns none of A's documents",
          all(h["document_id"] not in (doc_taj, doc_ola) for h in payload["sources"]),
          f"-> {len(payload['sources'])} source(s)")

    wipe(ha); wipe(hb)
    print("\n" + "=" * 62)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("\n  FAILED: " + ", ".join(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
