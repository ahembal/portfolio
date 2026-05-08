"""Unit tests for BM25, vector store, and RRF fusion."""

import pytest
from src.retrieval import bm25, rrf

DOCS = [
    {"text": "TP53 is the most frequently mutated gene in human cancer.", "source": "pubmed:1"},
    {"text": "BRCA1 mutations increase breast cancer risk significantly.", "source": "pubmed:2"},
    {"text": "EGFR targeted therapy improves outcomes in lung cancer.", "source": "pubmed:3"},
    {"text": "DNA repair mechanisms prevent genomic instability.", "source": "pubmed:4"},
    {"text": "Immunotherapy checkpoint inhibitors activate T cells.", "source": "pubmed:5"},
]


class TestBM25:
    def setup_method(self):
        bm25.build(DOCS)

    def test_exact_match_ranks_first(self):
        results = bm25.search("TP53 cancer mutation", k=5)
        assert results[0]["source"] == "pubmed:1"

    def test_no_match_returns_empty(self):
        results = bm25.search("quantum physics neutron star", k=5)
        assert results == []

    def test_is_ready_after_build(self):
        assert bm25.is_ready()

    def test_returns_at_most_k(self):
        results = bm25.search("cancer", k=2)
        assert len(results) <= 2


class TestRRF:
    def _make_results(self, sources: list[str]) -> list[dict]:
        return [
            {"text": f"text {s}", "source": s, "score": 1.0, "rank": i + 1}
            for i, s in enumerate(sources)
        ]

    def test_document_in_both_lists_ranks_highest(self):
        bm25_res  = self._make_results(["A", "B", "C"])
        dense_res = self._make_results(["A", "D", "E"])
        merged = rrf.fuse(bm25_res, dense_res)
        assert merged[0]["source"] == "A"

    def test_fuse_returns_union(self):
        bm25_res  = self._make_results(["A", "B"])
        dense_res = self._make_results(["C", "D"])
        merged = rrf.fuse(bm25_res, dense_res)
        sources = {r["source"] for r in merged}
        assert sources == {"A", "B", "C", "D"}

    def test_rrf_score_decreases_with_rank(self):
        bm25_res  = self._make_results(["A", "B", "C"])
        dense_res = self._make_results(["B", "A", "C"])
        merged = rrf.fuse(bm25_res, dense_res)
        scores = [r["rrf_score"] for r in merged]
        assert scores == sorted(scores, reverse=True)
