# AgenticRAG

A read-only chat assistant over your own database **and** your own documents.

Ask a question in plain English. A LangGraph agent decides for itself whether the
answer lives in the database or in an uploaded file, writes a `SELECT` if it needs
one, and replies in plain English — streamed word by word.

Under 500 lines of Python, and every file is small enough to read in one sitting.

```
POST /chat  {"message": "which 5 customers spent the most last year?"}

  agent -> get_business_context   (glossary + rules it must follow)
        -> get_schema             (hybrid search picks the right tables)
        -> run_sql                (one SELECT, checked before it runs)
        -> answer, streamed back
```

## What it does

| | |
|---|---|
| **Text to SQL** | Ask in English, get an answer from Postgres or SQL Server. Only `SELECT` ever runs. |
| **Document Q&A** | Upload PDF, DOCX, XLSX or TXT files and ask about them. Answers name the file they came from. |
| **Hybrid retrieval** | BM25 keyword search + vector similarity, fused with RRF, then reranked by a cross-encoder. |
| **Agentic routing** | No keyword rules. The model picks its own tools and can retry when a query fails. |
| **Login** | JWT. `/connect`, `/chat` and `/upload` all require a valid token. |
| **Memory** | Each conversation id keeps its own history, so follow-up questions work. |

## Quickstart

```bash
git clone https://github.com/bharatsoni0047/GenAI-Secure-Agentic-GenAI-Knowledge-System.git
cd GenAI-Secure-Agentic-GenAI-Knowledge-System

python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env              # then fill in the values (see below)

uvicorn api.main:app --reload
```

Open <http://127.0.0.1:8000> for the chat page, or `/docs` for the API.

### Filling in `.env`

```
OPENAI_API_KEY=your-key
JWT_SECRET=a-long-random-string
APP_USERNAME=admin
APP_PASSWORD=pick-something-strong
```

Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Leaving all three login values **empty** turns login off entirely — fine for local
testing, never for anything reachable from outside your machine.

Database credentials are **not** in `.env`. They are sent to `/connect` at runtime
and held in memory only, so they are never written to disk.

## Docker

```bash
docker build -t agenticrag .
docker run -p 8000:8000 --env-file .env agenticrag
```

## API

| Route | Auth | What it does |
|---|---|---|
| `POST /login` | — | Username + password in, token out |
| `POST /connect` | token | Connect a database and index its schema |
| `POST /chat` | token | Ask a question, answer streams back as plain text |
| `POST /upload` | token | Add a PDF / DOCX / XLSX / TXT file to the document index |
| `GET /status` | — | What is connected and how much is indexed |
| `GET /` | — | The chat page |

## How it is put together

```
config.py                      every setting in one place
api/
  main.py                      the routes
  auth.py                      password login + the token check
ingestion/
  connect.py                   Postgres / SQL Server, in memory only
  schema.py                    reads tables and columns
  documents.py                 PDF, DOCX, XLSX, TXT -> chunks
  business_context.py          glossary, rules and notes the model must follow
retrieval/
  search.py                    BM25 + vectors + RRF + reranker
generation/
  agent.py                     the LangGraph loop
  tools.py                     the five tools the model can call
  sql.py                       the read-only guard and the query runner
  prompts.py                   the system prompt
frontend/chat.html             the whole UI in one file
```

### The safety guard

`generation/sql.py` is the one file worth reading twice. Every query the model
writes goes through `is_safe()` before it touches the database:

- must start with `SELECT` or `WITH`
- one statement only — a second `;` is rejected
- any of `INSERT UPDATE DELETE DROP ALTER CREATE TRUNCATE GRANT REVOKE EXEC MERGE INTO WAITFOR` fails it

This is code, not a prompt instruction, so the model cannot talk its way past it.

## Built with

Python 3.11 · FastAPI · LangGraph · LangChain · Chroma · BGE embeddings ·
flashrank · rank-bm25 · SQLAlchemy

## Known limits

Honest list, so nothing here surprises you:

- The vector stores are in memory — uploaded documents are lost when the server restarts.
- `/chat` is synchronous, so one long answer holds up other requests. Fine for a demo or a small team, not for many users at once.
- The BM25 index is rebuilt on every search. Fast for hundreds of chunks, slow for tens of thousands.
- Login is a single user from `.env`. There are no roles and no user database.
