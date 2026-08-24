# retrieval/search.py - hybrid search: BM25 keywords + vector similarity + RRF + reranker
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi
from flashrank import Ranker, RerankRequest
import config

# loaded once at startup - the embedding model, the reranker and two vector stores
embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
reranker = Ranker(model_name=config.RERANK_MODEL, cache_dir=config.RERANK_CACHE_DIR)
schema_store = Chroma(collection_name="schema_cards", embedding_function=embeddings)
document_store = Chroma(collection_name="document_chunks", embedding_function=embeddings)

# plain text copies of everything indexed, for the BM25 keyword side
schema_cards = []
document_chunks = []
# chunk text -> the file it came from, so an answer can name its source
chunk_sources = {}

# what this function does: replace the schema index with the newly connected database's tables
def index_tables(cards):
  schema_cards.clear()
  schema_cards.extend(cards)
  schema_store.reset_collection()
  if cards:
    schema_store.add_texts(cards)

# what this function does: add freshly uploaded chunks, remembering which file each came from
def add_document_chunks(chunks, source_name):
  document_chunks.extend(chunks)
  for chunk in chunks:
    chunk_sources[chunk] = source_name
  if chunks:
    document_store.add_texts(chunks, metadatas=[{"source": source_name}] * len(chunks))

# what this function does: combine two ranked lists into one using reciprocal rank fusion
def fuse_rankings(keyword_results, vector_results):
  scores = {}
  for ranked_list in (keyword_results, vector_results):
    for rank, text in enumerate(ranked_list):
      scores[text] = scores.get(text, 0) + 1 / (60 + rank)
  return sorted(scores, key=scores.get, reverse=True)

# what this function does: let the reranker pick the best texts; keep the fused order on any error
def rerank(question, candidates, top_count):
  try:
    passages = [{"id": index, "text": text} for index, text in enumerate(candidates)]
    ranked = reranker.rerank(RerankRequest(query=question, passages=passages))
    return [item["text"] for item in ranked[:top_count]]
  except Exception:
    return candidates[:top_count]

# what this function does: run keyword + vector search, fuse the results, then rerank them
def hybrid_search(question, texts, store, top_count):
  if not texts:
    return []
  keyword_index = BM25Okapi([text.lower().split() for text in texts])
  keyword_results = keyword_index.get_top_n(question.lower().split(), texts, n=10)
  vector_results = [match.page_content for match in store.similarity_search(question, k=10)]
  return rerank(question, fuse_rankings(keyword_results, vector_results), top_count)

# what this function does: find the tables most relevant to the question
def search_tables(question):
  return hybrid_search(question, schema_cards, schema_store, config.TOP_TABLES)

# what this function does: find the best document chunks, each paired with its file name
def search_documents(question):
  chunks = hybrid_search(question, document_chunks, document_store, config.TOP_CHUNKS)
  return [(chunk, chunk_sources.get(chunk, "an uploaded file")) for chunk in chunks]
