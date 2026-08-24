# ingestion/schema.py - read table and column names from the connected database
from sqlalchemy import inspect
from ingestion import connect
from retrieval import search

# every table name mapped to its list of "column (type)" strings - filled by load_schema
tables = {}

# what this function does: read all tables and columns, then hand them to the search index
def load_schema():
  inspector = inspect(connect.get_engine())
  tables.clear()
  for table_name in inspector.get_table_names():
    columns = [f"{column['name']} ({column['type']})" for column in inspector.get_columns(table_name)]
    tables[table_name] = columns
  search.index_tables([f"Table {name} with columns: {', '.join(columns)}"
                       for name, columns in tables.items()])
  return len(tables)
