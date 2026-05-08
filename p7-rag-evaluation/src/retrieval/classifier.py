"""
Query complexity classifier — routes queries to fast or slow retrieval path.

Uses a rule-based heuristic rather than a trained model. A trained classifier
would require labelled data we don't have. The heuristic captures the signal
that matters: query length, presence of comparative/mechanistic keywords, and
multi-entity structure are reliable proxies for retrieval complexity.

Returns "simple" or "complex".

  simple  → fast path: dense vector search only, no reranking  (< 2s)
  complex → slow path: hybrid search + reranking + agent loop  (30–60s)
"""

import re

# Keywords that signal a complex, multi-hop or comparative query
_COMPLEX_PATTERNS = [
    r"\bcompare\b", r"\bcomparison\b", r"\bdifference\b", r"\bdifferences\b",
    r"\bversus\b", r"\bvs\.?\b",
    r"\bmechanism\b", r"\bmechanistically\b", r"\bhow does\b", r"\bhow do\b",
    r"\bpathway\b", r"\bcascade\b",
    r"\binteract\b", r"\binteraction\b", r"\binteractions\b",
    r"\bregulat\b",   # regulates, regulation, regulatory
    r"\bmulti.hop\b",
    r"\bwhich\b.*\band\b",   # "which X and Y" — multi-entity
    r"\bboth\b",
    r"\bwhat are the\b",
    r"\bwhat is the role\b",
    r"\bwhat is the mechanism\b",
]

_COMPLEX_RE = re.compile("|".join(_COMPLEX_PATTERNS), re.IGNORECASE)

# Simple queries are short and contain a single named entity or fact lookup
_SIMPLE_MAX_WORDS = 8


def classify(query: str) -> str:
    """
    Classify a query as 'simple' or 'complex'.

    Args:
        query: natural language query string

    Returns:
        "simple" or "complex"
    """
    words = query.strip().split()

    if _COMPLEX_RE.search(query):
        return "complex"

    if len(words) > _SIMPLE_MAX_WORDS:
        return "complex"

    return "simple"
