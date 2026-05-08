"""
Retrieval pipeline — adaptive fast/slow routing.

Fast path (simple queries):
  dense vector search only → top-5 results
  Target latency: < 2s

Slow path (complex queries):
  BM25 + dense search → RRF fusion (top-20) → cross-encoder reranking → top-5
  Target latency: varies by corpus size and reranker speed

Both paths return the same output schema so callers are path-agnostic.
"""

from src.retrieval import bm25, rrf, vector_store
from src.retrieval.classifier import classify
from src.retrieval.reranker import rerank


def retrieve(query: str, top_n: int = 5) -> dict:
    """
    Retrieve the most relevant passages for a query using adaptive routing.

    Args:
        query: natural language query
        top_n: number of final results to return

    Returns:
        dict with keys:
          results  — list of dicts: text, source, rerank_score (slow) or score (fast)
          path     — "fast" or "slow"
          query    — the original query
    """
    path = classify(query)

    if path == "simple":
        results = vector_store.search(query, k=top_n)
        return {"results": results, "path": "fast", "query": query}

    # Slow path — hybrid + rerank
    bm25_results  = bm25.search(query, k=20)
    dense_results = vector_store.search(query, k=20)
    fused         = rrf.fuse(bm25_results, dense_results)
    reranked      = rerank(query, fused, top_n=top_n)

    return {"results": reranked, "path": "slow", "query": query}
