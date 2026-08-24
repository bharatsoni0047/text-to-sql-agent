# generation/sql.py - the safety guard and query runner (never remove the guard)
import re
from sqlalchemy import text
from tenacity import retry, stop_after_attempt
from ingestion import connect
import config

# words that change data - any of these anywhere in the query means we refuse to run it
FORBIDDEN_WORDS = (r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|"
                   r"REVOKE|EXEC|EXECUTE|MERGE|INTO|WAITFOR)\b")

# what this function does: allow only one read-only SELECT statement - reject everything else
def is_safe(sql_query):
  cleaned = sql_query.strip().rstrip(";").upper()
  if ";" in cleaned:
    return False
  if not cleaned.startswith(("SELECT", "WITH")):
    return False
  return not re.search(FORBIDDEN_WORDS, cleaned)

# what this function does: run the query against the database, retrying once if it fails
@retry(stop=stop_after_attempt(2), reraise=True)
def run_query(sql_query):
  with connect.get_engine().connect() as database_connection:
    result = database_connection.execute(text(sql_query))
    return [dict(row) for row in result.mappings().fetchmany(config.MAX_ROWS)]

# what this function does: check the query is safe, run it, and return rows or a friendly error
def execute_sql(sql_query):
  # strip markdown code fences the model sometimes wraps around the query
  sql_query = re.sub(r"```sql|```", "", sql_query, flags=re.IGNORECASE).strip()
  if not is_safe(sql_query):
    return "Blocked: only a single read-only SELECT statement is allowed."
  try:
    return run_query(sql_query)
  except Exception as error:
    return f"SQL error: {error}. Fix the query and try again."
