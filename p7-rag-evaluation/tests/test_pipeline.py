"""Tests for query classifier and adaptive retrieval pipeline."""

import pytest
from src.retrieval.classifier import classify
from src.retrieval import bm25, vector_store
from src.retrieval.pipeline import retrieve

DOCS = [
    {"text": "TP53 is the most frequently mutated gene in human cancer.", "source": "pubmed:1"},
    {"text": "BRCA1 mutations increase breast cancer risk significantly.", "source": "pubmed:2"},
    {"text": "EGFR targeted therapy improves outcomes in lung cancer.", "source": "pubmed:3"},
    {"text": "DNA repair mechanisms prevent genomic instability.", "source": "pubmed:4"},
    {"text": "Immunotherapy checkpoint inhibitors activate T cells.", "source": "pubmed:5"},
]


class TestClassifier:
    def test_simple_short_query(self):
        assert classify("What is TP53?") == "simple"

    def test_complex_comparative(self):
        assert classify("Compare BRCA1 and BRCA2 roles in DNA repair") == "complex"

    def test_complex_mechanism(self):
        assert classify("How does TP53 regulate apoptosis?") == "complex"

    def test_complex_long_query(self):
        assert classify("What are the downstream targets of EGFR signalling in lung adenocarcinoma cells") == "complex"

    def test_complex_interaction(self):
        assert classify("Which proteins interact with TP53?") == "complex"


class TestPipeline:
    def setup_method(self):
        bm25.build(DOCS)
        vector_store.index(DOCS)

    def test_fast_path_for_simple_query(self):
        result = retrieve("What is TP53?")
        assert result["path"] == "fast"

    def test_slow_path_for_complex_query(self):
        result = retrieve("How does TP53 regulate apoptosis in cancer cells?")
        assert result["path"] == "slow"

    def test_results_have_required_keys(self):
        result = retrieve("TP53 cancer")
        for r in result["results"]:
            assert "text" in r
            assert "source" in r

    def test_returns_at_most_top_n(self):
        result = retrieve("cancer", top_n=3)
        assert len(result["results"]) <= 3
