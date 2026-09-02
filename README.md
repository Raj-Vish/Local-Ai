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
| **Reading receipts automatically (OCR)** | **Next phase** |
| **Asking questions about your documents (RAG)** | **Next phase** |

The chat screen is built but deliberately not connected — it says so on screen
rather than replying with placeholder text.

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
        +---> File storage    the actual PDFs and photos
        +---> (next phase)    OCR, embeddings, ChromaDB, a local model
```

Three storage systems, three different jobs:

- **MySQL** holds structured facts you query exactly — who, what, how much.
- **The filesystem** holds the actual uploaded files. MySQL stores only the path.
- **ChromaDB** will hold document meaning for search. Not built yet.

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

21 checks covering documents, expenses and reports — reading, editing,
deleting, downloading, listing and totals, plus unauthenticated access.

This test has been verified by breaking the code on purpose: removing the
ownership check from documents makes it fail with `read A's document -> HTTP
200` and `delete A's document -> HTTP 204`. A test never seen failing is not
known to work.

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
│   ├── services/               storage.py (safe files), report_builder.py (Excel)
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
└── storage/                    uploaded files (not in git)
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

1. **Text extraction** — pull text out of digital PDFs, and OCR for photographs.
   This is the hardest part: a crumpled thermal taxi receipt is genuinely
   difficult to read, which is why the review-and-confirm step exists.
2. **Field extraction** — a small local language model reads the text and
   proposes a date, vendor, category and amount. Every figure is then checked
   against the raw text and confirmed by a human before it counts.
3. **Retrieval** — chunk documents, embed them, store them in ChromaDB, and
   connect the chat screen so an employee can ask about their own receipts.

Every one of those writes into tables that already exist, through endpoints
that already work. Nothing built so far gets rebuilt.
