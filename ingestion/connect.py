# ingestion/connect.py - connect to Postgres or SQL Server, keep the connection in memory
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
import config

# the one active database connection - in memory only, never written to disk
active_engine = None
active_database_name = None

# what this function does: build the connection url in the format sqlalchemy expects
def build_connection_url(database_type, host, port, database, username, password):
  # quote_plus makes special characters like @ or # safe to put inside a url
  safe_password = quote_plus(password)
  if database_type == "postgres":
    return f"postgresql+psycopg2://{username}:{safe_password}@{host}:{port}/{database}"
  return (f"mssql+pyodbc://{username}:{safe_password}@{host}:{port}/{database}"
          f"?driver={quote_plus(config.SQL_SERVER_DRIVER)}&TrustServerCertificate=yes")

# what this function does: open the connection, test it with a tiny query, and remember it
def connect_to_database(database_type, host, port, database, username, password):
  global active_engine, active_database_name
  url = build_connection_url(database_type, host, port, database, username, password)
  engine = create_engine(url, pool_pre_ping=True)
  try:
    with engine.connect() as database_connection:
      database_connection.execute(text("SELECT 1"))
  except Exception as error:
    return f"Could not connect: {error}"
  active_engine, active_database_name = engine, database
  return None

# what this function does: hand back the active connection, or fail with a clear message
def get_engine():
  if active_engine is None:
    raise RuntimeError("No database is connected yet - call /connect first.")
  return active_engine
