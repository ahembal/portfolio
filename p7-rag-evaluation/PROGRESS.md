# Project 7 — RAG Evaluation & Hybrid Retrieval
## Progress Tracker
*Last updated: 2026-05-06*

---

## Steps

### Phase 1 — Corpus & hybrid search
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | Corpus population script | ⬜ Todo | Fetch and index PubMed abstracts for a defined topic set at startup. An empty corpus makes the RAG tool useless — real retrieval quality can only be measured with real content. |
| 2 | BM25 implementation | ⬜ Todo | Add lexical search alongside dense vector search. BM25 excels at exact matches — gene symbols, accession numbers, drug names — where semantic similarity gives poor results. |
| 3 | RRF fusion | ⬜ Todo | Combine BM25 and dense rankings with Reciprocal Rank Fusion. RRF is parameter-free and consistently outperforms individual rankings on hybrid tasks. |
| 4 | Cross-encoder reranker | ⬜ Todo | Score top-20 retrieved passages against the query with a cross-encoder. More accurate than bi-encoder similarity but only feasible on a small candidate set — applied after initial retrieval, not on the full corpus. |

### Phase 2 — Adaptive retrieval
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 5 | Query complexity classifier | ⬜ Todo | Classify queries as simple (factual, single-hop) or complex (comparative, multi-hop) before retrieval starts. This determines which retrieval path to use — routing is the right abstraction because it separates the latency/quality tradeoff from the retrieval logic itself. |
| 6 | Fast path | ⬜ Todo | Dense vector search only, no reranking. For factual single-hop queries, hybrid search adds latency without meaningfully improving results. Target < 2s end-to-end. |
| 7 | Slow path | ⬜ Todo | Hybrid search + reranking + multi-step agent loop. For complex queries where retrieval quality determines answer quality. Target 30–60s. |

### Phase 3 — Evaluation pipeline
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 8 | Benchmark dataset | ⬜ Todo | 50 curated life science questions with expected PMIDs and reference answers. A fixed versioned benchmark is necessary — without it, "improvement" cannot be distinguished from noise. |
| 9 | LLM-as-judge scoring | ⬜ Todo | Context relevance, faithfulness, answer relevance scored by an LLM without labelled data. This is the standard approach for evaluating RAG systems in production where manual labelling is infeasible at scale. |
| 10 | Evaluation runner | ⬜ Todo | Run benchmark against the full system, record scores per query, aggregate. Enables A/B comparison between system versions (e.g. vector-only vs hybrid). |

### Phase 4 — Serving & docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 11 | Evaluation dashboard (Streamlit) | ⬜ Todo | Show benchmark scores per query, retrieval path distribution, per-metric breakdown. Makes evaluation results tangible — a number in a JSON file is less convincing than a dashboard showing which queries improved and which didn't. |
| 12 | docs/how-it-works.md | ⬜ Todo | Explain hybrid search, RRF, reranking, and adaptive retrieval. |
| 13 | docs/evaluation-design.md | ⬜ Todo | Why LLM-as-judge, what each metric measures, honest limitations of automated evaluation. |

---

## Quick status

```
Phase 1  [░░░░] 0/4
Phase 2  [░░░]  0/3
Phase 3  [░░░]  0/3
Phase 4  [░░░]  0/3
```
