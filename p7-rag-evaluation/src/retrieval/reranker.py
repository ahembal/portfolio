"""
Cross-encoder reranker — scores candidate passages against the query.

Applied after hybrid search (BM25 + dense + RRF) to rerank the top-20
candidates and return top-5. More accurate than bi-encoder similarity
because the query and passage are read together as a single input.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  - 22 MB, CPU-friendly
  - Trained on MS MARCO passage ranking (broad domain, transfers well)
  - Scores are logits — higher is more relevant, not bounded to [0,1]
"""

from sentence_transformers import CrossEncoder

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(MODEL_NAME)
    return _model


def rerank(query: str, candidates: list[dict], top_n: int = 5) -> list[dict]:
    """
    Rerank candidates by cross-encoder relevance score.

    Args:
        query:      the search query
        candidates: list of dicts with keys: text, source, rrf_score (from rrf.fuse)
        top_n:      number of results to return after reranking

    Returns:
        top_n candidates sorted by cross-encoder score descending,
        each with an added key: rerank_score (float)
    """
    if not candidates:
        return []

    model  = _get_model()
    pairs  = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs)

    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    return [
        {**candidate, "rerank_score": round(float(score), 4)}
        for candidate, score in ranked[:top_n]
    ]
