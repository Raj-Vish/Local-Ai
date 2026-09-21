# AI-Assisted Enterprise Expense Management System

A private, self-hosted web application where employees upload their bills and
receipts, record what they spent, and download a finished expense report as a
spreadsheet.

Built as a B.Sc. IT major project. Everything runs on one server inside the
organisation's own network — no data leaves the building, and no cloud service
is involved.

---

## Current state

**Phase one is complete and working.** The application does something genuinely
useful today, with no AI involved:

| Feature | Status |
|---|---|
| Register and sign in with an employee ID | Working |
| Passwords hashed with bcrypt, JWT sessions | Working |
| Upload receipts (PDF, JPG, PNG) | Working |
| List, download and delete documents | Working |
| Record expenses by hand, with categories | Working |
| Filter by month and category | Working |
| Exact totals and per-category subtotals | Working |
| Generate an expense report | Working |
| Download it as a real `.xlsx` file | Working |
| Complete separation between employees | Working, and tested |
| Reading text out of uploaded documents | Working (Stage 1) |
| OCR for photographed receipts | Working, needs `tesseract-ocr` installed |
| Proposing expense fields from a receipt | Working (Stage 1b) |
| Chunking, embeddings and a local vector index | Working (Stages 2–5) |
| Semantic search over your own documents | Working (Stage 6) |
| **Phrasing answers with a local LLM** | **Teammate's half — see [LLM-INTEGRATION.md](LLM-INTEGRATION.md)** |

The chat screen is built but deliberately not connected — it says so on screen
rather than replying with placeholder text.

Stages 1 and 1b of the AI phase are in. An uploaded document is read into
text in the background; from that text the system proposes a date, vendor,
amount and category, each shown beside the exact line it came from. Nothing
is saved until a person presses Confirm — reading a receipt is not the same
as claiming one.

**No figure is ever calculated.** Every proposed amount is a substring lifted
out of the document. Line items are never summed and a missing total is never
reconstructed; a value that cannot be pointed at in the text is not proposed
at all. This is deterministic pattern matching, not a language model.

**What the AI adds later is not the ability to work. It removes the typing.**
Today an employee enters an expense by hand; next phase the system reads it off
the receipt and asks them to confirm it.

---

## How it fits together

```
Employee's browser
        |  HTTP (JSON)
        v
   React frontend          screens only, never touches the database
        |  REST API
        v
   FastAPI backend         authenticates, authorises, coordinates
        |
        +---> MySQL           users, documents, expenses, reports
        +---> File storage    the actual PDFs and photos, plus extracted text
        +---> Extraction      pdfplumber for digital PDFs, Tesseract for photos
        +---> ChromaDB        chunks + embeddings, for semantic search
        +---> (teammate)      Qwen via Ollama, over HTTP, for phrasing only
```

Three storage systems, three different jobs:

- **MySQL** holds structured facts you query exactly — who, what, how much.
- **The filesystem** holds the actual uploaded files. MySQL stores only the path.
- **ChromaDB** holds document meaning for search: one vector per chunk, each
  tagged with the user who owns it. Local, persisted to `rag/chroma/`, never
  committed.

### Rules the code follows

- **React never talks to MySQL.** Every request goes through FastAPI, so
  authorisation is checked in exactly one place.
- **Python does all arithmetic.** Money is `DECIMAL` in the database and
  `Decimal` in Python, never `float`. When the language model arrives it will
  write the sentences around the figures and never produce a figure itself.
- **The frontend is never trusted for security.** Hiding a button stops nobody;
  every check is repeated on the server.
- **Another employee's data returns 404, not 403.** "Forbidden" would confirm
  the record exists.
- **Search is scoped by the server, not the request.** A search carries no
  user id and no document scope; the backend filters by the authenticated
  user, so there is no request shape that reaches someone else's chunks.
- **The database calculates, the model only phrases.** Totals come from
  `SELECT SUM(...)` over verified expenses and are handed to the model as
  facts it must copy. It is never asked to do arithmetic.

---

## Running it

Requires Python 3.11+, Node 20+, and MySQL 8. Full setup instructions,
including a fresh machine, are in [TECH-STACK.md](TECH-STACK.md).

```bash
# backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# frontend, in a second terminal
cd enterprise-rag-ui
npm run dev
```

Then open **http://localhost:5180**. The API's own documentation is at
**http://localhost:8000/docs**.

### Demo data

```bash
cd backend && ./venv/bin/python seed_demo.py
```

Wipes the database and creates two employees with expenses and a receipt each.
Sign in as `raj@company.com` or `priya@company.com`, password `demo12345678`.

### The isolation test

The most important rule in the system is that one employee can never reach
another's data. It is checked automatically:

```bash
cd backend && ./venv/bin/python test_isolation.py
```

34 checks covering documents, expenses, reports and semantic search — reading, editing,
deleting, downloading, listing, extracted text, expense proposals and
totals, plus unauthenticated access.

Two of those checks exist for a subtle reason. `resolve_for_read` refuses any
path outside the caller's own folder, so it independently blocks a cross-user
read even when the route's ownership check is missing. That is defence in
depth working — but it also meant the suite could not tell a present check
from an absent one. The two checks against a document with *no* extracted
text reach the ownership check alone, with nothing behind it.

To be precise about what this does *not* cover: there is no automated check
here for malformed, expired or tampered JWTs, password hashing, or duplicate
email handling. Those are implemented and were checked by hand, but they are
not in this suite.

This test has been verified by breaking the code on purpose: removing the
ownership check from documents makes it fail with `read A's document -> HTTP
200` and `delete A's document -> HTTP 204`. Removing it from the text and
proposal routes makes it fail with `B cannot read text of A's unreadable
document -> HTTP 200`. A test never seen failing is not known to work.

There is also a unit suite for the field proposer, which needs no server:

```bash
cd backend && ./venv/bin/python test_field_extraction.py
```

29 checks, including the cases where a naive reading goes wrong: a subtotal
sitting above the total, an invoice number full of slashes that looks like a
date, a date that could be read two ways, and OCR that turned a quantity into
the letter I.

And two more suites:

```bash
cd backend && ./venv/bin/python test_chunking.py   # 25 checks, no server needed
cd backend && ./venv/bin/python test_rag.py        # 47 checks, server must be up
```

`test_rag.py` is where cross-user isolation of the vector index is proved. It
checks both through the API and directly against the vector store, because
the API layer independently re-checks every hit against documents owned in
MySQL — which meant the HTTP checks alone could not tell a working filter
from a missing one.

---

## Where the code lives

```
rag/
├── backend/                    Python, FastAPI
│   ├── main.py                 startup, routers, health check
│   ├── config.py               every setting, read from .env
│   ├── models.py               the five database tables
│   ├── schemas.py              what data is allowed in and out
│   ├── api/                    auth, users, documents, expenses, reports
│   ├── core/                   security.py (hashing, tokens), deps.py (the gatekeeper)
│   ├── services/               storage.py (safe files), report_builder.py (Excel),
│   │                           extraction.py (file -> text), document_pipeline.py,
│   │                           field_extraction.py (text -> proposed fields),
│   │                           chunking.py, embeddings.py, vector_store.py,
│   │                           indexing.py, llm.py (the teammate's model)
│   ├── api/rag.py             semantic search, index status, ask
│   ├── fixtures.py             sample receipt PDFs for the seed and the tests
│   ├── test_field_extraction.py  the proposer's own checks
│   ├── test_chunking.py       the chunker's own checks
│   ├── test_rag.py            retrieval, indexing and cross-user isolation
│   ├── backfill_extraction.py  read documents uploaded before Stage 1
│   ├── seed_demo.py            demo data
│   └── test_isolation.py       the data separation test
│
├── enterprise-rag-ui/          React, Vite
│   └── src/
│       ├── api/                the only files that call the server
│       ├── pages/              Documents, Expenses, Reports
│       ├── components/         login, sidebar, forms, chat
│       ├── hooks/              theme, session health, dialog behaviour
│       └── styles/             plain CSS with theme variables
│
├── storage/                    uploaded files (not in git)
└── chroma/                     the vector index (not in git, rebuildable)
```

### Two files that must never be committed

`backend/.env` holds the database password and the token signing key.
`enterprise-rag-ui/.env` holds the API address. Both are in `.gitignore`.

---

## Known limitations

Stated deliberately rather than left to be discovered:

- **No rate limiting on login.** Someone on the network could try passwords as
  fast as the server answers. Acceptable on a trusted LAN; it should be added
  before any wider deployment.
- **Runs on localhost only.** LAN deployment needs firewall and static IP work.
- **Only INR.** The currency column exists, but amounts in different currencies
  are never summed together — that needs exchange rates as of each transaction
  date, which is a project of its own.
- **`create_all()` creates tables but never alters them.** Changing a column
  during development means dropping the table. Alembic belongs here once the
  schema settles.
- **One report format.** Excel only; PDF is not built.

---

## What comes next

The architecture for the AI phase is designed and documented. In order:

1. ~~**Text extraction**~~ — **done.** `pdfplumber` for digital PDFs;
   Tesseract for photographs and for PDFs that turn out to be pictures.
   Runs as a background task, so an upload still returns immediately.
2. ~~**Field extraction**~~ — **done, and without a language model.** A
   receipt's total is a labelled number on a line; a pattern finds it and can
   show its working, which a model cannot. Every figure is checked against the
   raw text and confirmed by a human before it counts. A model may still help
   later with the messy minority, but it is not the foundation.
3. ~~**Retrieval**~~ — **done.** Documents are chunked, embedded with
   all-MiniLM-L6-v2 through ONNX Runtime, and stored in a local ChromaDB
   index. `POST /rag/search` finds an employee's own documents by meaning.
   The chat screen is connected to it.

4. **Phrasing** — the last step, and the only one not on this machine. A
   teammate runs Qwen through Ollama; `backend/services/llm.py` is the single
   door to it and `LLM_URL` in `.env` is the only thing that needs setting.
   See [LLM-INTEGRATION.md](LLM-INTEGRATION.md).

Every one of those writes into tables that already exist, through endpoints
that already work. Nothing built so far gets rebuilt.
