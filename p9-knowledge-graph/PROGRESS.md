# Project 9 — Knowledge Graph & Semantic Search
## Progress Tracker
*Last updated: 2026-05-19*

---

## Phase 1 — Graph schema and seed data
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | RDF schema definition | ⬜ Todo | Define classes and properties in Turtle. Establish local namespace and EDAM/OBI alignment mappings. |
| 2 | PubMed seed data | ⬜ Todo | Fetch ~500 papers across 5 topics (TP53, BRCA1, EGFR, p53 cancer, DNA repair). Extract entities and relationships. |
| 3 | UniProt seed data | ⬜ Todo | Fetch canonical records for proteins mentioned in seed papers. Extract accessions, gene symbols, disease associations. |
| 4 | Serialise to Turtle | ⬜ Todo | Produce `data/seed/graph.ttl` — the fixed snapshot used for benchmarking. |

## Phase 2 — RDF builder
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 5 | builder.py | ⬜ Todo | Python script using rdflib. Fetches from PubMed and UniProt, constructs graph, serialises to Turtle. |
| 6 | aligner.py | ⬜ Todo | Maps local entity types to EDAM and OBI terms. Adds aligned triples to the graph. |
| 7 | Validation | ⬜ Todo | Assert graph is well-formed: no dangling references, all required properties present. |

## Phase 3 — Fuseki deployment
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 8 | Fuseki config | ⬜ Todo | `fuseki/config.ttl` — dataset name, update endpoint, query endpoint. |
| 9 | Helm chart | ⬜ Todo | Deploy Fuseki on quick-thrush. NodePort 30900. Load graph.ttl on startup. |
| 10 | Verify endpoint | ⬜ Todo | Run a test SPARQL query against the live cluster endpoint. |

## Phase 4 — SPARQL queries
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 11 | sparql.py | ⬜ Todo | Python query interface over Fuseki HTTP endpoint. Used by comparison framework. |
| 12 | Example queries | ⬜ Todo | 8–10 SPARQL queries in `queries/` demonstrating multi-hop reasoning RAG cannot do. |
| 13 | Benchmark questions | ⬜ Todo | 20 questions (10 structured, 10 open-ended) with ground truth for RAG vs SPARQL comparison. |

## Phase 5 — RAG vs SPARQL comparison
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 14 | Run benchmark | ⬜ Todo | Run all 20 questions through SPARQL (p9) and RAG (p7). Record correctness, completeness, hallucination. |
| 15 | Fill comparison.md | ⬜ Todo | Add benchmark results table to `docs/comparison.md`. |

## Phase 6 — GraphRAG (planned)
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 16 | graphrag.py | ⬜ Planned | Combine SPARQL entity traversal with p7 vector retrieval. LLM synthesises answer from both. |
| 17 | Extend benchmark | ⬜ Planned | Add GraphRAG as third system in the comparison. Add hybrid question type to benchmark. |

## Phase 7 — Imaging facilities domain (planned)
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 18 | Schema extension | ⬜ Planned | Add Facility, Technique, SampleType, AccessCondition classes. Once the system exists, adding a second domain is straightforward. |
| 19 | Seed data | ⬜ Planned | Synthetic imaging facility data modelled after public catalogues. 15–20 facilities with techniques, locations, access conditions. |
| 20 | EDAM alignment | ⬜ Planned | Map imaging techniques to EDAM operation terms (e.g. edam:operation_3443 — Image analysis). |
| 21 | SPARQL examples | ⬜ Planned | Multi-hop queries: facilities supporting multiple techniques, filtering by location and access type. |

---

## Quick status

```
Phase 1  [░░░░] 0/4 — Not started
Phase 2  [░░░]  0/3 — Not started
Phase 3  [░░░]  0/3 — Not started
Phase 4  [░░░]  0/3 — Not started
Phase 5  [░░]   0/2 — Not started
Phase 6  [░░]   0/2 — Planned (GraphRAG)
Phase 7  [░░░░] 0/4 — Planned (Imaging facilities)
```
