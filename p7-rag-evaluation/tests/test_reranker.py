"""Tests for cross-encoder reranker."""

from src.retrieval.reranker import rerank

CANDIDATES = [
    {"text": "TP53 is the most frequently mutated gene in human cancer.", "source": "pubmed:1", "rrf_score": 0.03},
    {"text": "BRCA1 mutations increase breast cancer risk.", "source": "pubmed:2", "rrf_score": 0.02},
    {"text": "Immunotherapy activates T cells against tumours.", "source": "pubmed:3", "rrf_score": 0.01},
]


def test_rerank_returns_top_n():
    results = rerank("TP53 cancer mutation", CANDIDATES, top_n=2)
    assert len(results) == 2


def test_rerank_adds_score():
    results = rerank("TP53 cancer", CANDIDATES, top_n=3)
    assert all("rerank_score" in r for r in results)


def test_rerank_scores_descending():
    results = rerank("TP53 cancer", CANDIDATES, top_n=3)
    scores = [r["rerank_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_rerank_empty_candidates():
    assert rerank("any query", [], top_n=5) == []
