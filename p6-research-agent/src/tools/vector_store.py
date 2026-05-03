"""
p6-research-agent/src/tools/vector_store.py
---------------------------------------------
Local RAG (Retrieval-Augmented Generation) using ChromaDB + sentence-transformers.

Two functions:
  index(documents) → embed and store documents in ChromaDB
  search(query, k) → return top-k relevant chunks

Used when PubMed and UniProt don't have sufficient context, or when the agent
needs background from a pre-curated local corpus (e.g. SciLifeLab platform docs,
seed abstracts on key topics).

Why semantic search and not keyword search:
  Keyword search for "tumour suppressor" would miss a document that says
  "inhibits cell proliferation". Sentence-transformers encode meaning — the
  embedding of "tumour suppressor" is close to "inhibits cell proliferation"
  in vector space. This finds relevant documents even when the exact words differ.
"""

import hashlib
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

EMBED_MODEL   = "all-MiniLM-L6-v2"   # 22 MB, fast, good for sentence similarity
COLLECTION    = "research_corpus"
CHUNK_SIZE    = 512    # characters per chunk
CHUNK_OVERLAP = 64     # overlap between consecutive chunks


def _get_client(persist_dir: str = "/tmp/chromadb") -> chromadb.Client:
    """Return a persistent ChromaDB client."""
    return chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False),
    )


def _get_model() -> SentenceTransformer:
    """Load the sentence-transformer model (cached after first load)."""
    return SentenceTransformer(EMBED_MODEL)


def _chunk(text: str) -> list[str]:
    """Split text into overlapping chunks of CHUNK_SIZE characters."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def index(
    documents: list[dict],
    persist_dir: str = "/tmp/chromadb",
) -> int:
    """
    Embed and store documents in ChromaDB.

    Args:
        documents: list of dicts with keys:
                     text   (str) — the document content
                     source (str) — identifier for the source (e.g. filename, URL)
        persist_dir: path where ChromaDB stores its files

    Returns:
        number of chunks indexed

    Example:
        >>> index([
        ...     {"text": "TP53 is the most frequently mutated gene...", "source": "seed.txt"},
        ...     {"text": "SciLifeLab provides national infrastructure...", "source": "scilifelab.txt"},
        ... ])
        12
    """
    client     = _get_client(persist_dir)
    model      = _get_model()
    collection = client.get_or_create_collection(COLLECTION)

    all_chunks, all_ids, all_metas = [], [], []

    for doc in documents:
        text   = doc.get("text", "")
        source = doc.get("source", "unknown")
        chunks = _chunk(text)
        for i, chunk in enumerate(chunks):
            # Stable ID: hash of source + chunk index + chunk content
            chunk_id = hashlib.md5(f"{source}:{i}:{chunk[:64]}".encode()).hexdigest()
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metas.append({"source": source, "chunk_index": i})

    if not all_chunks:
        return 0

    embeddings = model.encode(all_chunks, show_progress_bar=False).tolist()
    collection.upsert(
        ids=all_ids,
        documents=all_chunks,
        embeddings=embeddings,
        metadatas=all_metas,
    )
    return len(all_chunks)


def search(
    query: str,
    k: int = 5,
    persist_dir: str = "/tmp/chromadb",
) -> list[dict]:
    """
    Search the corpus for the k most relevant chunks.

    Args:
        query:       natural language query
        k:           number of results to return (default 5)
        persist_dir: path to ChromaDB storage

    Returns:
        list of dicts with keys: text, source, score
        Returns [] if corpus is empty or an error occurs.

    Example:
        >>> search("tumour suppressor function", k=3)
        [
          {"text": "TP53 acts as a tumour suppressor by...", "source": "seed.txt", "score": 0.87},
          {"text": "Cell cycle arrest is triggered when...", "source": "seed.txt", "score": 0.81},
        ]
    """
    try:
        client     = _get_client(persist_dir)
        model      = _get_model()
        collection = client.get_or_create_collection(COLLECTION)

        if collection.count() == 0:
            return []

        query_embedding = model.encode([query], show_progress_bar=False).tolist()
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=min(k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        chunks    = results["documents"][0]
        metas     = results["metadatas"][0]
        distances = results["distances"][0]

        return [
            {
                "text":   chunk,
                "source": meta.get("source", "unknown"),
                "score":  round(1 - dist, 4),   # convert distance to similarity
            }
            for chunk, meta, dist in zip(chunks, metas, distances)
        ]
    except Exception as e:
        return [{"error": str(e)}]
