<h1 align="center">Text-to-SQL Agent</h1>

<p align="center">
  <b>Ask your database a question in plain English. Get an answer you can trust.</b><br>
  A LangGraph agent that writes its own SQL, checks it against a read-only guard it cannot
  bypass, and cites the table or file every answer came from.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-1.x-1C3C3C">
  <img alt="Chroma" src="https://img.shields.io/badge/Chroma-vector%20store-FF6F61">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white">
  <img alt="Size" src="https://img.shields.io/badge/Python-498%20lines-success">
</p>

---

## The problem

Business users cannot write SQL, so every *"how many orders shipped late last quarter?"*
becomes a ticket for an analyst. Bolting an LLM onto a production database solves that and
creates a worse problem: a model that can write `SELECT` can also write `DROP TABLE`, and a
prompt saying *"please only read data"* is a request, not a control.

This project answers the question **and** removes the risk — the guard is compiled code on
the execution path, not an instruction the model is asked to respect.

---

## Request lifecycle

Twelve steps from question to answer. Nothing skips step 10.

![Request lifecycle](docs/pipeline.svg)

As a flow:

```
User question
  → JWT check              reject with 401 unless a valid token is present
  → Agent starts           LangGraph tool-calling loop takes over
  → Business rules         glossary, rules and notes injected into the system prompt
  → Schema search          which of the user's tables could answer this?
  → BM25 + vectors         two independent rankings over the schema cards
  → RRF fusion             merge both rankings, 1/(60+rank) — no score calibration needed
  → Cross-encoder rerank   the top 5 tables that survive
  → Model writes SQL       one SELECT, against only those tables
  → is_safe() guard        SELECT/WITH only · one statement · no DDL/DML  ← fail-closed
  → Execute                read-only session, row cap
  → Stream the answer      token by token, with the source named
→ Answer + chart + citations
```

---

## What it does

| | |
|---|---|
| **Text to SQL** | Ask in English, get an answer from Postgres or SQL Server. The agent picks its own tools and retries a failed query once. |
| **Document Q&A** | Upload PDF, DOCX, XLSX or TXT. Answers name the file they came from. |
| **Hybrid retrieval** | BM25 + embeddings, RRF-fused, cross-encoder reranked. |
| **Read-only guard** | `SELECT`/`WITH` only, single statement, no DDL or DML. Enforced in code. |
| **JWT auth** | `/connect`, `/chat` and `/upload` all require a valid token. |
| **Memory** | Each conversation id keeps its own history, so follow-ups work. |
| **Streaming** | Answers arrive token by token, not after a twenty-second pause. |

---

## Architecture

Four packages, one direction of dependency. No module reaches upward.

![Architecture](docs/architecture.svg)

---

## The read-only guard

This is the file worth reading twice. Every query the model writes passes three checks
before it touches the database, and failing any one of them raises rather than executes.

![Read-only guard](docs/safety-guard.svg)

```python
def is_safe(sql_query):
  cleaned = sql_query.strip().rstrip(";").upper()
  if ";" in cleaned:                              # a second statement
    return False
  if not cleaned.startswith(("SELECT", "WITH")):  # not a read
    return False
  return not re.search(FORBIDDEN_WORDS, cleaned)  # DDL / DML / EXEC
```

Three properties make it worth trusting:

1. **It is code, not a prompt.** No amount of clever phrasing gets past a regex.
2. **It fails closed.** Anything not *provably* a single read-only statement is refused.
   Blocking too much is the safe direction here.
3. **It sits on the execution path**, not beside it. There is no route to the database that
   does not pass through `execute_sql()`.

---

## Hybrid retrieval

A database with 200 tables will not fit in a prompt, so the agent has to find the right five
first. Neither search method is sufficient alone.

![Hybrid retrieval](docs/retrieval.svg)

- **BM25** catches literal identifiers an embedding fumbles — a column genuinely named
  `cust_id_fk`.
- **Vectors** catch meaning BM25 misses — "revenue" finding a table called `sales`.
- **RRF** merges them by *rank*, so two scores measuring completely different things never
  need calibrating against each other.
- **Reranking fails open** — if the cross-encoder errors, the fused order is used and the
  answer still ships.

---

## Quickstart

```bash
git clone https://github.com/bharatsoni0047/text-to-sql-agent.git
cd text-to-sql-agent

python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                   # then fill in the values below
uvicorn api.main:app --reload
```

Open <http://127.0.0.1:8000> for the chat page, or `/docs` for the API.

### Step 1 — configure `.env`

```ini
OPENAI_API_KEY=your-key
JWT_SECRET=a-long-random-string
APP_USERNAME=admin
APP_PASSWORD=pick-something-strong
```

Generate the secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Leaving all three login values **empty** disables auth entirely — fine on localhost, never
for anything reachable from outside your machine.

### Step 2 — log in

```bash
curl -X POST localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
```

### Step 3 — connect a database

Database credentials are **not** in `.env`. They are sent to `/connect` at runtime and held
in memory only, so they never touch disk.

```bash
curl -X POST localhost:8000/connect \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"database_type":"postgres","host":"localhost","port":5432,
       "database":"shop","username":"readonly","password":"..."}'
```

### Step 4 — ask a question

```bash
curl -X POST localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message":"which 5 customers spent the most last year?"}'
```

### Step 5 — add documents (optional)

```bash
curl -X POST localhost:8000/upload \
  -H "Authorization: Bearer $TOKEN" -F "file=@leave-policy.pdf"
```

---

## Docker

```bash
docker build -t text-to-sql-agent .
docker run -p 8000:8000 --env-file .env text-to-sql-agent
```

---

## API

| Route | Auth | What it does |
|---|---|---|
| `POST /login` | — | Username + password in, bearer token out |
| `POST /connect` | token | Connect a database and index its schema |
| `POST /chat` | token | Ask a question; the answer streams back as plain text |
| `POST /upload` | token | Add a PDF / DOCX / XLSX / TXT file to the document index |
| `GET /status` | — | What is connected and how much is indexed |
| `GET /` | — | The chat page |

---

## Project structure

```
config.py                      every setting in one place
api/
  main.py                      routes
  auth.py                      password login + the token guard
generation/
  agent.py                     the LangGraph loop
  tools.py                     the five tools the model can call
  sql.py                       the read-only guard and the query runner
  prompts.py                   the system prompt
retrieval/
  search.py                    BM25 + vectors + RRF + reranker
ingestion/
  connect.py                   Postgres / SQL Server, in memory only
  schema.py                    reads tables and columns
  documents.py                 PDF, DOCX, XLSX, TXT -> chunks
  business_context.py          glossary, rules and notes
frontend/chat.html             the whole UI in one file
docs/                          the diagrams on this page
```

---

## Design decisions

**Why a tool-calling agent instead of a fixed chain?**
A fixed chain must guess up front whether a question needs SQL or a document. The agent
decides after seeing the schema, and can call `find_table` when it only knows part of a
name — which is what real questions actually look like.

**Why is the guard a regex and not a SQL parser?**
A parser is more precise and far more surface area. This guard has one job — decide whether
a string is *provably* a single read-only statement — and the cheapest correct answer to
that is a whitelist plus a blacklist, with the benefit of the doubt going to "refuse".

**Why hold database credentials in memory only?**
Because a `.env` file containing production credentials is the thing that leaks. The user
supplies them per session; nothing is persisted.

---

## Known limits

Stated plainly, so nothing here surprises you:

- The vector stores are in memory — uploaded documents are lost when the server restarts.
- `/chat` is synchronous, so one long answer holds up other requests. Fine for a team, not
  for hundreds of concurrent users.
- The BM25 index is rebuilt on every search. Fast for hundreds of chunks, slow for tens of
  thousands.
- Login is a single user from `.env`. No roles, no user database.
- There is no automated test for the guard yet. It is the next thing that should be added.

---

## STAR summary

A detailed write-up of the situation, task, actions and results behind this project is in
**[STAR.md](STAR.md)** — written for interviews and design reviews rather than for setup.
