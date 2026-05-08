"""
Reciprocal Rank Fusion — merges ranked lists from BM25 and dense search.

RRF score for a document = Σ 1 / (k + rank)  for each list it appears in.
k=60 is the standard constant from the original RRF paper (Cormack et al. 2009).

Documents are identified by their source string. Chunks from the same source
are treated as distinct entries.
"""

K = 60


def fuse(
    bm25_results: list[dict],
    dense_results: list[dict],
    k: int = K,
) -> list[dict]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion.

    Args:
        bm25_results:  ranked list from BM25 search (dicts with text, source, score, rank)
        dense_results: ranked list from vector search (same format)
        k:             RRF constant (default 60)

    Returns:
        merged list sorted by RRF score descending, with keys: text, source, rrf_score
    """
    scores: dict[str, float] = {}
    docs:   dict[str, dict]  = {}

    for result_list in (bm25_results, dense_results):
        for item in result_list:
            key = f"{item['source']}::{item['text'][:64]}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + item["rank"])
            docs[key]   = item

    merged = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    return [
        {
            "text":      docs[key]["text"],
            "source":    docs[key]["source"],
            "rrf_score": round(scores[key], 6),
        }
        for key in merged
    ]
