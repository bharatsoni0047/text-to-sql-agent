# api/main.py - the FastAPI app: the chat page, /login, /connect, /chat, /upload, /status
import os
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from api.auth import create_token, login_is_configured, require_user
from ingestion import business_context, connect, documents, schema
from retrieval import search
from generation.agent import application
import config

app = FastAPI(title="Text-to-SQL Agent")

# what each route expects in its request body
class LoginRequest(BaseModel):
  username: str
  password: str

class ConnectRequest(BaseModel):
  database_type: str  # "postgres" or "sqlserver"
  host: str
  port: int
  database: str
  username: str
  password: str

class ChatRequest(BaseModel):
  message: str
  conversation_id: str = "default"

class ContextRequest(BaseModel):
  text: str

# what this function does: serve the one-file chat page at the root url
@app.get("/")
def home_route():
  return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "chat.html"))

# what this function does: swap a username and password for a token that unlocks the other routes
@app.post("/login")
def login_route(request: LoginRequest):
  token = create_token(request.username, request.password)
  if token is None:
    raise HTTPException(status_code=401, detail="Wrong username or password.")
  return {"access_token": token, "token_type": "bearer"}

# what this function does: connect to the database, then read its schema into the search index
@app.post("/connect")
def connect_route(request: ConnectRequest, user: str = Depends(require_user)):
  error_message = connect.connect_to_database(request.database_type, request.host, request.port,
                                              request.database, request.username, request.password)
  if error_message:
    return {"connected": False, "error": error_message}
  return {"connected": True, "tables": schema.load_schema()}

# what this function does: send the question through the agent and stream the answer back
@app.post("/chat")
def chat_route(request: ChatRequest, user: str = Depends(require_user)):
  graph_input = {"messages": [HumanMessage(content=request.message)]}
  graph_config = {"configurable": {"thread_id": request.conversation_id}}
  # what this function does: yield the answer word by word as the model writes it
  def stream_answer():
    for chunk, details in application.stream(graph_input, graph_config, stream_mode="messages"):
      if details.get("langgraph_node") == "agent" and chunk.content:
        yield chunk.content
  return StreamingResponse(stream_answer(), media_type="text/plain")

# what this function does: read an upload in pieces, refusing it the moment it passes the size cap
async def read_within_limit(file):
  limit, pieces, total = config.MAX_UPLOAD_MB * 1024 * 1024, [], 0
  while True:
    piece = await file.read(1024 * 1024)
    if not piece:
      return b"".join(pieces)
    total += len(piece)
    if total > limit:
      raise HTTPException(status_code=413,
                          detail=f"That file is over the {config.MAX_UPLOAD_MB} MB limit.")
    pieces.append(piece)

# what this function does: accept a pdf, docx, xlsx or txt file and add it to the document index
@app.post("/upload")
async def upload_route(file: UploadFile, user: str = Depends(require_user)):
  file_bytes = await read_within_limit(file)
  return {"uploaded": file.filename, "chunks": documents.add_document(file.filename, file_bytes)}

# what this function does: show the glossary, rules and notes currently in force
@app.get("/context")
def get_context_route():
  return business_context.summary()

# what this function does: replace the glossary from a block of plain text
@app.post("/context")
def set_context_route(request: ContextRequest, user: str = Depends(require_user)):
  return business_context.replace(*business_context.parse_text(request.text))

# what this function does: replace the glossary from an uploaded text file
@app.post("/context/upload")
async def upload_context_route(file: UploadFile, user: str = Depends(require_user)):
  text = (await read_within_limit(file)).decode("utf-8", errors="ignore")
  return business_context.replace(*business_context.parse_text(text))

# what this function does: report what is connected and what has been loaded so far
@app.get("/status")
def status_route():
  return {"login_required": login_is_configured(),
          "connected": connect.active_engine is not None,
          "database": connect.active_database_name,
          "tables": len(schema.tables),
          "document_chunks": len(search.document_chunks),
          "context_entries": business_context.summary()["total"]}
