# Project 7 — RAG Evaluation & Hybrid Retrieval
## Progress Tracker
*Last updated: 2026-05-08*

---

## Steps

### Phase 1 — Corpus & hybrid search
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | Corpus population script | ✅ Done | `src/corpus/pubmed.py` — fetches PubMed abstracts for seed topics and returns documents ready for indexing. Real content is required to measure retrieval quality. |
| 2 | BM25 implementation | ✅ Done | `src/retrieval/bm25.py` — in-memory lexical index using rank_bm25. Complements dense search for exact matches on gene symbols, accessions, drug names. |
| 3 | RRF fusion | ✅ Done | `src/retrieval/rrf.py` — merges BM25 and dense ranked lists using Reciprocal Rank Fusion (k=60). Parameter-free, consistently outperforms individual rankings. |
| 4 | Cross-encoder reranker | ✅ Done | `src/retrieval/reranker.py` — scores top-20 candidates from hybrid search using cross-encoder/ms-marco-MiniLM-L-6-v2. More accurate than bi-encoder similarity, applied only to top-20 so fast enough for real-time use. |

### Phase 2 — Adaptive retrieval
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 5 | Query complexity classifier | ✅ Done | `src/retrieval/classifier.py` — rule-based heuristic using keyword patterns and query length. Returns "simple" or "complex". Rule-based chosen over trained classifier to avoid need for labelled data. |
| 6 | Fast path | ✅ Done | `src/retrieval/pipeline.py` — dense vector search only for simple queries. Target < 2s. |
| 7 | Slow path | ✅ Done | `src/retrieval/pipeline.py` — hybrid search + reranking for complex queries. Target 30–60s. |

### Phase 3 — Evaluation pipeline
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 8 | Benchmark dataset | ✅ Done | `src/evaluation/benchmark.py` — 20 curated life science questions (simple and complex). Fixed and versioned so results are reproducible across system changes. |
| 9 | LLM-as-judge scoring | ✅ Done | `src/evaluation/judge.py` — context relevance, faithfulness, answer relevance scored via structured JSON prompts. Standard approach (RAGAS-inspired) for evaluating RAG without labelled data. |
| 10 | Evaluation runner | ✅ Done | `src/evaluation/runner.py` — runs benchmark end-to-end, records per-query scores and aggregates. Enables A/B comparison between system versions. |

### Phase 4 — Serving & docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 11 | Evaluation dashboard (Streamlit) | ✅ Done | `streamlit/app.py` — shows aggregate scores, path distribution, per-query table with colour coding, answers inspector. Makes evaluation results tangible. |
| 12 | docs/how-it-works.md | ✅ Done | Explains hybrid search, RRF, reranking, adaptive retrieval with ASCII diagrams and concrete input/output examples. |
| 13 | docs/evaluation-design.md | ✅ Done | Why LLM-as-judge, what each metric measures, framework comparison (RAGAS, TruLens, ARES, DeepEval), honest limitations. |

---

## Quick status

```
Phase 1  [████] 4/4
Phase 2  [███]  3/3
Phase 3  [███]  3/3
Phase 4  [███]  3/3
```
