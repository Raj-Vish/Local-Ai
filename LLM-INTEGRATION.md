# Connecting the language model

**Written for: the teammate running Ollama and Qwen.**

The retrieval half of this project is finished and does not need a model to
work. Documents are read, chunked, embedded and searchable today. What is
missing is the last step — turning what was found into a sentence — and that
runs on your machine, not this one.

This document is the whole contract between us. Nothing else is needed.

---

## What you run

Ollama, serving a Qwen model, reachable over the network from my laptop.

```bash
ollama pull qwen2.5:1.5b
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

`OLLAMA_HOST=0.0.0.0` matters: the default binds to localhost only, and I
cannot reach that from another machine.

Check it from *my* machine, not yours — that is the connection that has to work:

```bash
curl http://<your-ip>:11434/api/tags
```

## What I set

One line in `backend/.env`. No code changes, and your address is not in the
repository anywhere:

```ini
LLM_URL=http://<your-ip>:11434
LLM_MODEL=qwen2.5:1.5b
LLM_TIMEOUT_SECONDS=120
```

Blank `LLM_URL` means "not configured", which is the normal state here. Every
endpoint keeps working; answers simply come back with
`answered_by_model: false` and a reason.

---

## The API I call

Standard Ollama. I have not invented a protocol, so if `ollama serve` is
running you already implement this.

**Request** — `POST {LLM_URL}/api/generate`

```json
{
  "model": "qwen2.5:1.5b",
  "prompt": "<assembled by backend/services/llm.py>",
  "stream": false,
  "options": { "temperature": 0.2 }
}
```

**Response** — I read exactly one field, `response`:

```json
{ "model": "qwen2.5:1.5b", "response": "You stayed at Taj Residency...", "done": true }
```

I also call `GET {LLM_URL}/api/tags` as a reachability check. It only needs to
return HTTP 200.

If you serve something other than Ollama, the only file that changes is
`backend/services/llm.py`. Nothing else in the backend knows what you are
running.

---

## The rule that is not negotiable

> **The database calculates. The model only phrases.**

Every prompt I send carries a `FACTS` block containing figures computed by
MySQL, and instructions telling the model to copy them exactly and never to
add anything up. For example:

```
FACTS (computed by the database -- these figures are correct,
copy them exactly, never recompute them):
- Total verified expenses: INR 19609.50 across 7 expense(s).
- Hotel: INR 5000.00 across 1 expense(s).

CONTEXT (extracts from the user's own documents):
[1] TAJ RESIDENCY
    Colaba, Mumbai 400001
    TOTAL                             5000.00

QUESTION: How much did I spend on hotels?
ANSWER:
```

So please **do not** add a system prompt that encourages the model to compute,
estimate or "helpfully" reconcile numbers. If a figure was not given to it,
the correct answer is that the figure is not available.

This is not a style preference. A wrong number in an expense claim is the one
failure this project cannot ship.

---

## What I need from you

1. Your machine's IP or hostname, and confirmation the port is reachable from
   my laptop (same network, firewall open).
2. The exact model tag you are serving, so `LLM_MODEL` matches.
3. Rough response time for a prompt of about 2,000 characters, so I can set a
   sensible timeout.
4. A note if you are *not* using Ollama's `/api/generate` shape, so I can
   adapt the one file that talks to you.

## What you do not need from me

- Nothing to install on your side beyond Ollama and the model.
- No database access. You never see MySQL; I send you text.
- No authentication work. Requests reach you only from my backend, which has
  already checked who the user is and has already scoped retrieval to that
  person's own documents.

---

## How to tell it is working

Once `LLM_URL` is set, this returns a phrased answer instead of a reason:

```bash
curl -s -X POST http://localhost:8000/rag/ask \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"question":"Where did I stay in Mumbai?"}'
```

```jsonc
{
  "answer": "You stayed at Taj Residency in Colaba, Mumbai...",
  "answered_by_model": true,
  "facts": ["Hotel: INR 5000.00 across 1 expense(s)."],
  "sources": [ { "document_id": 76, "filename": "hotel_invoice.pdf", "score": 0.45 } ]
}
```

`facts` and `sources` are returned either way, so the answer can always be
checked against what produced it.
