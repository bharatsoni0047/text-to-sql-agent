<h1 align="center">Text-to-SQL Agent</h1>

<p align="center">
  <b>Ask your company's database a question in normal English. Get a straight answer.</b><br>
  No spreadsheets. No waiting for the data team. And it can only ever read your data —
  never change or delete it.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/Web%20server-FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="Databases" src="https://img.shields.io/badge/Works%20with-PostgreSQL%20%7C%20SQL%20Server-336791">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white">
  <img alt="Read only" src="https://img.shields.io/badge/Read--only-guaranteed-success">
</p>

---

## What is this, in one paragraph

Companies keep their information in databases. To get anything out of a database you
normally have to write a special kind of instruction called a query — which almost nobody
outside a technical team can do. So a manager who wants to know *"how many orders arrived
late last month?"* has to ask someone else, and then wait.

This project removes the waiting. You type the question the way you would say it out loud.
The assistant works out where the answer lives, fetches it, and replies in plain English.
You can also upload documents — a policy PDF, a spreadsheet — and ask questions about
those in exactly the same way.

---

## Why this is different from just using ChatGPT on your data

The moment you let a computer program write its own database instructions, you have a
serious problem: **an instruction that can read your data can also delete it.**

Most demos handle this by politely asking the AI not to delete anything. That is not a
safeguard — it is a request, and requests can be ignored, tricked, or misunderstood.

This project handles it differently. **Before any instruction reaches your database, it is
checked by a separate piece of the system that the AI has no control over.** If the
instruction is anything other than a simple read, it is thrown away and never runs.

That check is the most important part of this whole project.

---

## What happens when you ask a question

![What happens when you ask a question](docs/pipeline.svg)

Written out as a list:

```
You ask a question
  → Check you are allowed in        nobody without a login gets past here
  → The assistant wakes up          and starts working on your question
  → It reads your company's terms   so "revenue" means what YOU mean by it
  → It works out where to look      which parts of your data could hold the answer
  → It searches two different ways  once by keyword, once by meaning
  → It combines both results        into a single, better list
  → It keeps only the best few      the most likely places
  → It drafts a request             to fetch exactly what is needed
  → SAFETY CHECK                    read-only, or the request is thrown away
  → It fetches the information      reading only, never changing
  → It writes the reply             in plain English, word by word
→ You get your answer, and where it came from
```

Twelve steps, every single time. The safety check cannot be skipped.

---

## What you can do with it

| | |
|---|---|
| **Ask about your data** | *"Which five customers spent the most last year?"* — answered from your live database. |
| **Ask about your documents** | Upload a policy, a report or a spreadsheet, then ask questions about it. |
| **Follow-up questions** | It remembers the conversation, so *"and the year before?"* works. |
| **See where answers came from** | Every answer names the file or table behind it. |
| **Keep your data safe** | Reading only — always. And your database password is never saved anywhere. |
| **Watch it type** | Answers appear word by word instead of after a long silence. |

---

## The safety check, explained

Every request the assistant writes has to pass three questions before it is allowed to run.
Fail any one, and it is refused.

![The safety check](docs/safety-guard.svg)

The important detail: **this check is part of the program, not an instruction given to the
AI.** The AI cannot argue with it, rephrase around it, or be tricked into skipping it. And
when there is any doubt at all, the answer is no — it would rather refuse a harmless
request than allow a harmful one.

---

## How it finds the right information

Imagine a filing cabinet with two hundred drawers. Before answering anything, the
assistant has to work out which five drawers to open.

![Finding the right data](docs/retrieval.svg)

It searches in two completely different ways at once:

- **By keyword** — good when you use the exact same word the data uses.
- **By meaning** — good when you don't. If you ask about "revenue" and the data calls it
  "sales", only this kind of search finds it.

Each method misses things the other catches, so the results from both are combined and the
best few are kept. If the final ranking step ever fails, the combined list is used instead —
you still get an answer.

---

## How the parts fit together

![How the parts fit together](docs/architecture.svg)

Four layers, each one only talking to the layer below it. That keeps the system simple to
follow and makes the safety check impossible to route around.

---

## Setting it up

You will need Python installed, and a key from an AI provider.

### Step 1 — download it

```bash
git clone https://github.com/bharatsoni0047/text-to-sql-agent.git
cd text-to-sql-agent
```

### Step 2 — install

```bash
python -m venv .venv
.venv\Scripts\activate                 # on Mac or Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3 — add your settings

Copy the example settings file and fill it in:

```bash
cp .env.example .env
```

Then open `.env` and set four things:

```ini
OPENAI_API_KEY=your-key-here
JWT_SECRET=any-long-random-string
APP_USERNAME=admin
APP_PASSWORD=choose-a-strong-password
```

Need a random string? Run this and paste the result:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> Leaving the last three blank turns the login off completely. That is fine while testing
> on your own computer, but never do it for anything other people can reach.

### Step 4 — start it

```bash
uvicorn api.main:app --reload
```

Open **http://127.0.0.1:8000** in your browser.

### Step 5 — log in and connect your database

Log in with the username and password you chose. Then enter your database details in the
form. **These are never saved to disk** — they are held only while the program is running,
so nothing sensitive is left behind.

### Step 6 — ask something

Type a question in normal English and press Enter.

### Step 7 — add documents (optional)

Upload a PDF, Word document, Excel file or text file, then ask questions about it the same
way.

---

## Running it with Docker

If you prefer Docker:

```bash
docker build -t text-to-sql-agent .
docker run -p 8000:8000 --env-file .env text-to-sql-agent
```

---

## For developers

<details>
<summary>Technical details — click to expand</summary>

**Stack:** Python 3.11 · FastAPI · LangGraph · LangChain · Chroma · BGE embeddings ·
flashrank cross-encoder · rank-bm25 · SQLAlchemy · python-jose (JWT)

**Size:** 498 lines of Python across 16 files. Largest file is 92 lines.

**The guard** (`generation/sql.py`):

```python
def is_safe(sql_query):
  cleaned = sql_query.strip().rstrip(";").upper()
  if ";" in cleaned:                              # a second statement
    return False
  if not cleaned.startswith(("SELECT", "WITH")):  # not a read
    return False
  return not re.search(FORBIDDEN_WORDS, cleaned)  # DDL / DML / EXEC
```

Whitelist first, blacklist second, fail-closed, and called by `execute_sql()` itself rather
than by its callers — so there is no unguarded path to the database.

**Retrieval:** BM25 and vector rankings fused with reciprocal rank fusion (`1/(60+rank)`),
then reranked by a cross-encoder. RRF operates on rank rather than score, so two
incomparable scoring scales never need calibrating. The reranker fails **open**; the guard
fails **closed** — deliberately opposite, because one is a quality optimisation and the
other is a safety property.

**Agent:** a LangGraph tool-calling loop with five tools (`get_schema`, `run_sql`,
`find_table`, `search_documents`, `get_business_context`). It sequences them itself and
retries a failed query once using the database's own error message.

**API routes:**

| Route | Auth | Purpose |
|---|---|---|
| `POST /login` | — | Credentials in, bearer token out |
| `POST /connect` | token | Connect a database and index its schema |
| `POST /chat` | token | Ask a question, answer streams back |
| `POST /upload` | token | Add a PDF / DOCX / XLSX / TXT file |
| `GET /status` | — | What is connected and indexed |

**Layout:**

```
config.py                  every setting in one place
api/main.py                routes
api/auth.py                login and the token guard
generation/agent.py        the LangGraph loop
generation/tools.py        the five tools
generation/sql.py          the safety guard and query runner
generation/prompts.py      the system prompt
retrieval/search.py        BM25 + vectors + RRF + reranker
ingestion/connect.py       Postgres / SQL Server, memory only
ingestion/schema.py        reads tables and columns
ingestion/documents.py     PDF / DOCX / XLSX / TXT to chunks
ingestion/business_context.py
frontend/chat.html         the whole UI in one file
```

</details>

---

## Honest limitations

No project is finished. These are the real gaps:

- **Uploaded documents disappear if you restart the program.** They are held in memory, not
  saved. You would re-upload them.
- **One long answer can hold up other people's questions.** Fine for a small team, not for
  hundreds of people at once.
- **Searching gets slower as you add many documents.** Fine for hundreds, slow for tens of
  thousands.
- **There is one login for everyone.** No separate user accounts or permission levels yet.
- **The safety check has no automated test yet.** It is the single most important piece of
  the project, and proving it works automatically is the next thing that should be built.

---

## The story behind this project

A fuller write-up — the problem, the decisions, the trade-offs and what came out of them —
is in **[STAR.md](STAR.md)**.
