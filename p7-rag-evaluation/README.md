# p7 — RAG Evaluation & Hybrid Retrieval

Hybrid retrieval system for life science queries (BM25 + dense search → RRF fusion → cross-encoder reranking) with an LLM-as-judge evaluation framework — all without an API key.

## What it demonstrates

- Hybrid retrieval: sparse (BM25) + dense (sentence-transformers) → Reciprocal Rank Fusion
- Adaptive routing: simple queries take the fast path (dense only); complex queries take the slow path (full hybrid + reranking)
- LLM-as-judge evaluation: context relevance, faithfulness, and answer relevance scored by a local LLM (Ollama)
- RAG vs SPARQL comparison: the same questions answered by vector retrieval (p7) and graph traversal (p9)

## Stack

| Component | Choice |
|-----------|--------|
| Sparse retrieval | `rank-bm25` |
| Dense retrieval | `sentence-transformers` (all-MiniLM-L6-v2) + ChromaDB |
| Fusion | Reciprocal Rank Fusion (k=60) |
| Reranking | Cross-encoder (slow path only) |
| Judge LLM | Llama 3.1 8B via Ollama |
| Corpus | PubMed abstracts fetched via E-utilities |

## Why hybrid retrieval

BM25 handles rare technical identifiers (gene accessions, drug names) that dense models miss. Dense search handles conceptual queries that BM25 can't match by vocabulary. Neither alone is best; fusion captures both.

See [`docs/retrieval-design.md`](docs/retrieval-design.md) for BM25 mechanics, RRF formula, and why cross-encoding only the top-20 candidates keeps latency under 3s.

## Evaluation

The judge scores three metrics per query (0.0–1.0):
- **Context relevance** — are the retrieved chunks relevant?
- **Faithfulness** — does the answer contain only claims from the chunks?
- **Answer relevance** — does the answer address what was asked?

See [`docs/evaluation-design.md`](docs/evaluation-design.md) for why token overlap (BLEU/ROUGE) fails for biomedical text and why LLM-as-judge is the correct approach.

## Related

- **[p6](../p6-research-agent/)** — uses the RAG component built here
- **[p9](../p9-knowledge-graph/)** — runs the structured comparison: same questions answered via SPARQL
