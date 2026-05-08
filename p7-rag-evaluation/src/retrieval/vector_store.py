"""
Dense vector store using ChromaDB + sentence-transformers.

Provides index() and search() used by the hybrid retrieval pipeline.
Standalone — no dependency on p6.
"""

import hashlib
import os

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

EMBED_MODEL   = "all-MiniLM-L6-v2"
COLLECTION    = "rag_corpus"
CHUNK_SIZE    = 512
CHUNK_OVERLAP = 64


def _persist_dir() -> str:
    # Read at call time so CHROMADB_DIR can be overridden in tests via env var.
    return os.getenv("CHROMADB_DIR", "/tmp/p7-chromadb")


def _client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path=_persist_dir(),
        settings=Settings(anonymized_telemetry=False),
    )


def _model() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL)


def _chunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def index(documents: list[dict]) -> int:
    """
    Embed and upsert documents into ChromaDB.

    Args:
        documents: list of dicts with keys: text (str), source (str)

    Returns:
        number of chunks indexed
    """
    col   = _client().get_or_create_collection(COLLECTION)
    model = _model()

    chunks, ids, metas = [], [], []
    for doc in documents:
        text   = doc.get("text", "")
        source = doc.get("source", "unknown")
        for i, chunk in enumerate(_chunk(text)):
            chunk_id = hashlib.md5(f"{source}:{i}:{chunk[:64]}".encode()).hexdigest()
            chunks.append(chunk)
            ids.append(chunk_id)
            metas.append({"source": source, "chunk_index": i})

    if not chunks:
        return 0

    embeddings = model.encode(chunks, show_progress_bar=False).tolist()
    col.upsert(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metas)
    return len(chunks)


def search(query: str, k: int = 20) -> list[dict]:
    """
    Return top-k chunks by cosine similarity.

    Returns list of dicts: text, source, score, rank (1-based).
    """
    try:
        col = _client().get_or_create_collection(COLLECTION)
        if col.count() == 0:
            return []

        model = _model()
        qemb  = model.encode([query], show_progress_bar=False).tolist()
        res   = col.query(
            query_embeddings=qemb,
            n_results=min(k, col.count()),
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "text":   chunk,
                "source": meta.get("source", "unknown"),
                "score":  round(1 - dist, 4),
                "rank":   i + 1,
            }
            for i, (chunk, meta, dist) in enumerate(
                zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
            )
        ]
    except Exception as e:
        return [{"error": str(e)}]


def count() -> int:
    """Return number of indexed chunks."""
    try:
        return _client().get_or_create_collection(COLLECTION).count()
    except Exception:
        return 0
