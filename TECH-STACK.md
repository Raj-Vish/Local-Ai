# Tools, Technology & Setup

What was used, why it was chosen, and how to run this on a different computer.

Written for someone setting the project up for the first time. Every term is
explained where it first appears.

---

# Part 1 — What was used, and why

## Three words that keep appearing

| Word | Plain meaning |
|---|---|
| **Library** | Somebody else's ready-made code you borrow instead of writing it |
| **Framework** | A kit that calls *your* code, rather than the other way round |
| **Runtime** | The thing that actually runs something — a language, or a model |

---

## The backend

### Python 3.12 and FastAPI

**FastAPI is the receptionist.** Every request from the browser arrives here.
It checks who is asking, decides what they may do, talks to the database, and
sends an answer back.

**Why it was chosen:** it validates incoming data automatically, so a route can
trust what it is given without writing checks by hand; it generates its own
interactive documentation at `/docs`, which is genuinely useful during
development and demonstrates well; and it is built around waiting on slow
things, which matters when a local language model is added later.

**What you would write yourself without it:** HTTP parsing, routing, request
validation, error formatting and documentation. Weeks of work.

### SQLAlchemy

Lets Python talk to MySQL in objects instead of hand-written SQL strings.

**The security reason matters more than the convenience.** Building SQL by
pasting user input into a string is how SQL injection happens. SQLAlchemy sends
values separately from the query, so a value can never be read as a command.

### PyMySQL and `cryptography`

The cable between Python and MySQL. `cryptography` is required because MySQL 8
uses an authentication method that needs it — without it you get a confusing
failure that does not mention the missing package.

### bcrypt

Turns a password into a hash that cannot be reversed. The password itself is
never stored, logged or returned anywhere.

**Used directly rather than through `passlib`**, which almost every tutorial
recommends: current `passlib` and `bcrypt` versions produce a confusing
internal error together. Using `bcrypt` on its own is three lines and avoids
the problem entirely.

### PyJWT

Creates and verifies the signed token a browser carries after signing in. The
algorithm is pinned when verifying — without that, a forged token could declare
itself unsigned and be accepted.

### openpyxl

Writes the `.xlsx` report file: header block, table, category subtotals,
grand total, formatted columns.

### filetype

Reads a file's real type from its first bytes, so a text file renamed to
`.pdf` is caught.

**Chosen over `python-magic`**, which is more common but needs a system library
(`libmagic`) installed separately. `filetype` is pure Python, so it installs
anywhere — including a college server where you may not have admin rights.

### python-multipart

Required for file uploads. FastAPI fails at startup without it and the error
does not make the cause obvious.

---

## The frontend

### React 19 and Vite 8

**React draws the screens.** You describe what a screen should look like for
any given data, and React works out how to get there.

**Vite is the workshop.** Save a file and the browser updates in under a
second, without losing your place.

### lucide-react

Around a thousand ready-made icons that adapt to light and dark automatically.
Only the ones actually used end up in the finished build.

### Plain CSS

No Tailwind, no Bootstrap. Five small stylesheets matching the screens, plus a
set of theme variables that both light and dark mode read from.

**Why no framework:** it is an extra language for every contributor to learn,
and this app has one consistent look across a handful of screens. Plain CSS
keeps it approachable.

---

## What was deliberately not used

| Not used | Why |
|---|---|
| **TypeScript** | Real benefit, real learning curve. Worth revisiting if the project grows. |
| **A router** | Four screens, switched by one variable. A router would be more machinery than the problem deserves. |
| **Redux / Zustand** | Built for apps where dozens of components share state. Ours has one owner and short chains. |
| **Tailwind / Bootstrap** | See above. |
| **Celery / Redis** | A task queue and a cache solve load problems this project does not have. |
| **Docker** | Would make deployment easier, but is a whole technology to learn while working solo. Keep as a fallback. |
| **LangChain** | Not part of the AI phase either. It would replace the easy 40% of a retrieval pipeline and hide the 60% worth understanding. |

---

# Part 2 — Setting it up on another computer

Tested on Ubuntu 24.04. Roughly 15 minutes, mostly downloading.

## Step 1 — System packages

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv mysql-server
```

Node.js 20 or newer, from https://nodejs.org (take the LTS version).

Check both:

```bash
python3 --version     # 3.11 or newer
node -v               # 20 or newer
```

> **Ubuntu 24.04 note:** `pip install` outside a virtual environment fails with
> `externally-managed-environment`. That is deliberate — Ubuntu protects its own
> Python. Always activate the venv first, and never use
> `--break-system-packages`.

## Step 2 — Database

```bash
sudo systemctl start mysql && sudo systemctl enable mysql
sudo mysql_secure_installation
sudo mysql
```

Then, inside MySQL:

```sql
CREATE DATABASE expense_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'expense_app'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT ALL PRIVILEGES ON expense_db.* TO 'expense_app'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

A dedicated user, not `root`: it can only touch this one database, so a bug can
never reach anything else.

## Step 3 — Backend

```bash
git clone https://github.com/Raj-Vish/Local-Ai.git
cd Local-Ai/backend

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```ini
DATABASE_URL=mysql+pymysql://expense_app:choose-a-password@localhost:3306/expense_db
JWT_SECRET=<paste the command output below>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
STORAGE_ROOT=/absolute/path/to/Local-Ai/storage
MAX_UPLOAD_MB=10
CORS_ORIGINS=http://localhost:5180
```

Generate a proper signing key — a short one is a real weakness, and PyJWT warns
about anything under 32 bytes:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Step 4 — Frontend

```bash
cd ../enterprise-rag-ui
npm install
```

Create `enterprise-rag-ui/.env`:

```ini
VITE_API_URL=http://localhost:8000
```

Only variables starting with `VITE_` reach the browser — and anything that does
is visible in the page source, so never put a secret there.

## Step 5 — Run it

```bash
# terminal 1
cd backend && source venv/bin/activate
uvicorn main:app --reload --port 8000

# terminal 2
cd enterprise-rag-ui && npm run dev
```

Open **http://localhost:5180**. Tables are created automatically on first start.

Load demo data if you want something to look at:

```bash
cd backend && ./venv/bin/python seed_demo.py
```

---

## Commands

| Command | Does |
|---|---|
| `uvicorn main:app --reload --port 8000` | Run the backend |
| `npm run dev` | Run the frontend |
| `npm run build` | Build the frontend for production |
| `npm run lint` | Check the frontend code |
| `./venv/bin/python seed_demo.py` | Reset to demo data |
| `./venv/bin/python test_isolation.py` | Run the data separation test |

---

## When something goes wrong

**`externally-managed-environment`** — pip run outside the venv. Run
`source venv/bin/activate` first.

**`blocked by CORS policy` in the browser** — the frontend's address is not in
`CORS_ORIGINS`. It must match exactly, including the port.

**Vite starts on a different port than 5180** — the port is pinned with
`strictPort`, so this means something else is using it. Free that port; do not
change Vite's, or CORS will block every request.

**`cryptography package is required`** — `pip install cryptography`.

**`RuntimeError: Form data requires python-multipart`** — install it and
restart.

**`Access denied for user 'expense_app'`** — the password in `.env` does not
match the one used in `CREATE USER`.

**Changed a model but the table did not change** — `create_all()` only creates
missing tables, it never alters existing ones. Drop the table and restart, or
add Alembic.

---

## Summary card

```
NEED FIRST   Python 3.11+, Node 20+, MySQL 8

SET UP       git clone https://github.com/Raj-Vish/Local-Ai.git
             cd Local-Ai/backend && python3 -m venv venv
             source venv/bin/activate && pip install -r requirements.txt
             cd ../enterprise-rag-ui && npm install
             create both .env files

RUN          uvicorn main:app --reload --port 8000
             npm run dev
             open http://localhost:5180

DEMO DATA    ./venv/bin/python seed_demo.py
             raj@company.com / demo12345678
```
