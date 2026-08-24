# config.py - every setting in one place; only secrets come from the .env file
import os
from dotenv import load_dotenv

# the folder this file lives in - paths built from it work no matter where the server starts
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# llm settings from .env - the key falls back to a placeholder so the app can
# still start without one (real llm calls will then fail with a clear auth error)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "missing-key")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")

# login settings, all from .env. every one of them is empty by default, and an empty
# value disables login completely - so a fresh clone ships with no password to guess
JWT_SECRET = os.getenv("JWT_SECRET", "")
APP_USERNAME = os.getenv("APP_USERNAME", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
JWT_ALGORITHM = "HS256"
JWT_HOURS = 8

# the embedding model for vector search, plus the reranker and where its files are cached
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "ms-marco-TinyBERT-L-2-v2"
RERANK_CACHE_DIR = os.path.join(BASE_DIR, "models")
# how many tables and document chunks search hands to the model
TOP_TABLES = 5
TOP_CHUNKS = 4
# document chunk sizes, in characters
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
# how many past messages the agent remembers, and the row cap on query results
MEMORY_MESSAGES = 5
MAX_ROWS = 50
# largest file the /upload route will accept, in megabytes
MAX_UPLOAD_MB = 20
# odbc driver name used for sql server connections
SQL_SERVER_DRIVER = "ODBC Driver 17 for SQL Server"
