"""
src/seed.py
-----------
Index the seed corpus into ChromaDB if the collection is empty.

Called once during API startup (lifespan). Safe to call on every restart —
it checks collection.count() before indexing and skips if already populated.

The seed corpus (data/seed_corpus.json) contains curated summaries of the
10 key proteins in the knowledge graph plus SciLifeLab infrastructure context.
It gives the RAG tool useful background on every fresh deployment without
requiring a manual indexing step or live API calls.
"""

import json
import logging
from pathlib import Path

from src.tools.vector_store import _get_client, _get_model, _chunk, COLLECTION

log = logging.getLogger("p6-research-agent.seed")

SEED_FILE = Path(__file__).parent.parent / "data" / "seed_corpus.json"


def seed_if_empty() -> None:
    """Index seed_corpus.json into ChromaDB if the collection is currently empty."""
    if not SEED_FILE.exists():
        log.warning("seed_file_missing", extra={"path": str(SEED_FILE)})
        return

    try:
        client = _get_client()
        collection = client.get_or_create_collection(COLLECTION)

        if collection.count() > 0:
            log.info("seed_skipped", extra={"reason": "collection already populated", "count": collection.count()})
            return

        with open(SEED_FILE) as f:
            documents = json.load(f)

        model = _get_model()
        all_chunks, all_ids, all_metas = [], [], []

        import hashlib
        for doc in documents:
            text   = doc.get("text", "")
            source = doc.get("source", "unknown")
            for i, chunk in enumerate(_chunk(text)):
                chunk_id = hashlib.md5(f"{source}:{i}:{chunk[:64]}".encode()).hexdigest()
                all_chunks.append(chunk)
                all_ids.append(chunk_id)
                all_metas.append({"source": source, "chunk_index": i})

        embeddings = model.encode(all_chunks, show_progress_bar=False).tolist()
        collection.upsert(ids=all_ids, documents=all_chunks, embeddings=embeddings, metadatas=all_metas)

        log.info("seed_complete", extra={"documents": len(documents), "chunks": len(all_chunks)})

    except Exception as exc:
        log.error("seed_failed", extra={"exception_type": type(exc).__name__, "exception_message": str(exc)})
