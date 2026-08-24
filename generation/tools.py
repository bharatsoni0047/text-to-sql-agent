# generation/tools.py - the five tools the model can choose to call
from langchain_core.tools import tool
from ingestion import business_context, schema
from retrieval import search
from generation import sql

# what this function does: give the model the schema of the tables that match the question
@tool
def get_schema(question: str) -> str:
  """Return the schema of the database tables most relevant to the question."""
  tables = search.search_tables(question)
  return "\n".join(tables) if tables else "No tables found - is a database connected?"

# what this function does: run one safe SELECT query and hand the rows back to the model
@tool
def run_sql(sql_query: str) -> str:
  """Run a single read-only SELECT query on the connected database and return the rows."""
  return str(sql.execute_sql(sql_query))

# what this function does: find table names that contain a keyword
@tool
def find_table(keyword: str) -> str:
  """Find table names that contain the given keyword."""
  matches = [name for name in schema.tables if keyword.lower() in name.lower()]
  return ", ".join(matches) if matches else f"No table name contains '{keyword}'."

# what this function does: search the uploaded documents, labelling each result with its file
@tool
def search_documents(question: str) -> str:
  """Search the uploaded PDF, DOCX, XLSX and TXT documents for text relevant to the question."""
  results = search.search_documents(question)
  if not results:
    return "No matching document content found."
  return "\n---\n".join(f"[from {source}]\n{chunk}" for chunk, source in results)

# what this function does: give the model the business glossary, rules and notes
@tool
def get_business_context() -> str:
  """Return the business glossary, rules and notes that apply to every answer."""
  return business_context.get_business_context_text()

# the full toolbox handed to the model - it decides which of these to call and when
all_tools = [get_schema, run_sql, find_table, search_documents, get_business_context]
