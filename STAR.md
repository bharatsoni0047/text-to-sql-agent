# STAR — Text-to-SQL Agent

A structured write-up of the problem, the decisions, and what came out of them.
Written for interviews and design reviews rather than for setup — see
[README.md](README.md) to run it.

---

## Situation

Every organisation with a database has the same bottleneck. The people who hold the
business questions — finance, operations, HR, sales — cannot write SQL, and the people who
can write SQL are a shared, finite resource. So a question that takes forty seconds to
answer takes three days to get answered, and most questions simply never get asked.

The obvious fix is to put a language model in front of the database. That fix creates a
worse problem than the one it solves:

1. **A model that can write `SELECT` can write `DROP TABLE`.** Instructing it not to is a
   request, not a control. Prompt injection through a document, a column value, or a
   carelessly worded question is enough to turn a read into a write.
2. **A wrong answer is indistinguishable from a right one.** SQL that runs and returns
   plausible-looking rows still returns the wrong number if it joined the wrong table, and
   the user has no way to tell.
3. **A real schema does not fit in a prompt.** Two hundred tables with their columns is
   well past the context budget, so something has to decide which five matter before the
   model writes a line.
4. **Credentials have to live somewhere.** Most demos put production database credentials
   in a `.env` file, which is precisely the file that ends up committed.

Existing work in this space is mostly notebooks: they demonstrate that text-to-SQL is
possible and quietly ignore all four problems.

---

## Task

Build a text-to-SQL assistant that a business user could actually be given access to, with
three non-negotiable properties:

| Requirement | Why it is non-negotiable |
|---|---|
| **The model cannot modify data — structurally** | A safety property enforced by a prompt is not a safety property. It must hold even against a model actively trying to break it. |
| **Answers must be traceable** | A number with no visible source is not usable for a decision. Every answer names the table or file it came from. |
| **It must work on a schema it has never seen** | Nothing hardcoded to one database. The user connects their own at runtime. |

Two secondary goals shaped the design as much as the primary ones:

- **The whole thing must stay small enough to be read.** A security-relevant system nobody
  reads is a security-relevant system nobody audits. The budget was 500 lines of Python.
- **Documents and the database must live behind one interface.** "What does the leave
  policy say, and how many people took leave last month?" is one question to a user, even
  though it is two systems underneath.

---

## Action

### 1. Made the safety guarantee structural, not behavioural

The core decision. `generation/sql.py` contains `is_safe()`, and every path to the database
runs through it:

```python
def is_safe(sql_query):
  cleaned = sql_query.strip().rstrip(";").upper()
  if ";" in cleaned:                              # a second statement
    return False
  if not cleaned.startswith(("SELECT", "WITH")):  # not a read
    return False
  return not re.search(FORBIDDEN_WORDS, cleaned)  # DDL / DML / EXEC
```

Three properties were designed in deliberately:

- **Whitelist first, blacklist second.** The statement must *start* as a read before the
  keyword blacklist is even consulted. A blacklist alone is a game of thinking of every bad
  word; a whitelist plus a blacklist means a novel attack has to also look like a `SELECT`.
- **Fail-closed.** Anything not provably a single read-only statement is refused. This
  produces occasional false positives — a legitimate query containing the word `INTO` in a
  string literal gets blocked — and that was accepted knowingly. Blocking too much is the
  recoverable failure; blocking too little is not.
- **On the path, not beside it.** `execute_sql()` calls `is_safe()` itself rather than
  trusting callers to check first. There is no "unsafe but fast" variant to reach for.

I chose a regex over a full SQL parser on purpose. A parser is more precise and much more
surface area — and this guard does not need to *understand* the query, only to decide
whether it is provably a single read. The cheapest correct answer to that question is a
whitelist and a blacklist.

### 2. Solved schema selection with hybrid retrieval

Neither search method is sufficient alone, and the failure modes are complementary:

- **Vector search** handles meaning — "revenue" finding a table called `sales` — and fumbles
  literal identifiers, because `cust_id_fk` has no semantic neighbourhood.
- **BM25** handles exactly those literal identifiers and cannot connect a synonym to
  anything.

I fused them with **reciprocal rank fusion** — `1/(60 + rank)`, summed across both lists.
RRF operates on *rank*, not score, which matters more than it sounds: a BM25 score and a
cosine distance are not on the same scale and never will be, so any score-based blend needs
calibration that drifts the moment the corpus changes. Rank-based fusion needs none.

A cross-encoder reranker then takes the fused shortlist down to five tables. It is wrapped
in a `try/except` that returns the fused order on failure — **fail-open**, deliberately the
opposite of the SQL guard. A reranker is a quality optimisation; a safety check is not. The
two should not have the same failure behaviour, and it is worth being explicit about which
is which.

### 3. Chose a tool-calling agent over a fixed chain

A fixed chain has to decide up front whether a question needs SQL or a document. That
decision is made before seeing the schema, which is exactly when the least information is
available.

The agent gets five tools — `get_schema`, `run_sql`, `find_table`, `search_documents`,
`get_business_context` — and sequences them itself. Concretely this means it can call
`find_table("cust")` when it only knows part of a name, read the schema that comes back,
and only then write SQL. On a failed query it sees the database's own error message and
retries once, which turns a class of typo-level failures into a non-event.

### 4. Kept credentials out of the repository entirely

Database credentials are sent to `/connect` at runtime and held in a module-level variable —
never written to disk, never in `.env`, never in a config file. `.env` holds only the LLM
key and the JWT secret, and `.env.example` ships with every secret field blank so a fresh
clone cannot accidentally run with a default password.

Login itself is JWT with a real password check. An earlier iteration of this project had a
`/login` endpoint that issued an admin token to anyone who asked — the kind of bug that
looks like security until someone reads it.

### 5. Made answers traceable

Every document chunk is stored with the filename it came from, and the tool returns
`[from policy.pdf]` alongside the text. The system prompt requires the model to name its
source. Without this, an answer drawn from a document is indistinguishable from one the
model invented.

### 6. Held the line on size

The finished system is **498 lines of Python across 16 files** — the largest is 92 lines.
That constraint drove real decisions: it is why business context is injected rather than
fine-tuned, why there is one vector store abstraction rather than three, and why the UI is a
single HTML file. A system that a reviewer can read end to end in twenty minutes gets
reviewed; one that takes two days does not.

---

## Result

### What was delivered

| Outcome | Detail |
|---|---|
| **Structural read-only guarantee** | Three-check, fail-closed guard on the execution path. The model cannot write, regardless of prompt. |
| **Works on any schema** | Postgres and SQL Server, connected at runtime. Nothing hardcoded. |
| **Traceable answers** | Every document answer names its source file. |
| **Two systems, one interface** | SQL and document Q&A behind a single `/chat` endpoint, with the agent routing itself. |
| **498 lines of Python** | Auditable in one sitting. Largest file is 92 lines. |
| **Deployable** | Dockerised, JWT-protected, streaming responses, per-conversation memory. |

### What I would tell an interviewer

The interesting decision in this project is not the agent — it is **deciding which failures
should fail closed and which should fail open**, and being explicit about it.

The SQL guard fails closed: uncertainty means refuse. The reranker fails open: uncertainty
means fall back to a slightly worse ordering and still answer. Both are correct, for
opposite reasons, and getting them the wrong way round produces either a system that
refuses to work or a system that quietly executes a `DELETE`. Most of the security value in
this codebase is in that one distinction being made deliberately rather than by accident.

The second thing worth saying is what I *didn't* do. I did not fine-tune a model, and I did
not build a SQL parser. Both were tempting and both would have made the system larger and
harder to trust for gains I could not have justified.

### What I would do next, and why

Honest gaps, in the order I would fix them:

1. **A test for the guard.** `is_safe()` is the single most important function here and it
   has no automated test. It should have a table of malicious inputs — stacked statements,
   `SELECT ... INTO`, comment-obfuscated `DROP` — asserted to be blocked. That is roughly
   twenty minutes of work and it converts a claim into a guarantee.
2. **A retrieval eval harness.** Right now the hybrid setup is *assumed* to beat vector-only.
   On a sibling project I built exactly this harness, measured it, and found hybrid was
   **worse** on that corpus — so the assumption here deserves the same scrutiny rather than
   the same confidence.
3. **Persistence for the vector stores.** Uploaded documents currently vanish on restart.
4. **Async `/chat`.** One long answer currently blocks other requests.

The order matters: the test comes first because it protects the property the whole project
exists to provide.
