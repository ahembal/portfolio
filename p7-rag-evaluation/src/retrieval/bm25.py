"""
BM25 lexical search index.

Wraps rank_bm25 with the same interface as vector_store.search() so the
hybrid pipeline can treat both uniformly.

The index is in-memory — rebuilt from the corpus on startup. BM25 does not
need persistence: it is fast to build (seconds for thousands of documents)
and has no large model weights to load.
"""

import re
from rank_bm25 import BM25Okapi

_index: BM25Okapi | None = None
_corpus: list[dict] = []   # [{text, source}]


def _tokenise(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def build(documents: list[dict]) -> int:
    """
    Build the BM25 index from a list of documents.

    Args:
        documents: list of dicts with keys: text (str), source (str)

    Returns:
        number of documents indexed
    """
    global _index, _corpus
    _corpus = [{"text": d.get("text", ""), "source": d.get("source", "unknown")} for d in documents]
    tokenised = [_tokenise(d["text"]) for d in _corpus]
    _index = BM25Okapi(tokenised)
    return len(_corpus)


def search(query: str, k: int = 20) -> list[dict]:
    """
    Return top-k documents by BM25 score.

    Returns list of dicts: text, source, score, rank (1-based).
    Returns [] if index has not been built.
    """
    if _index is None or not _corpus:
        return []

    scores  = _index.get_scores(_tokenise(query))
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

    return [
        {
            "text":   _corpus[i]["text"],
            "source": _corpus[i]["source"],
            "score":  round(float(scores[i]), 4),
            "rank":   rank + 1,
        }
        for rank, i in enumerate(top_idx)
        if scores[i] > 0
    ]


def is_ready() -> bool:
    return _index is not None
