# Project 9 — Knowledge Graph & Semantic Search
## Progress Tracker
*Last updated: 2026-05-20*

---

## Phase 1 — Graph schema and seed data
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | RDF schema definition | ✅ Done | Namespaces and classes defined in builder.py (P9, SCH, EDAM, UP). Paper, Author, Protein, Disease. |
| 2 | PubMed seed data | ✅ Done | builder.py fetches papers via UniProt-inverted citations — no NLP, deterministic. |
| 3 | UniProt seed data | ✅ Done | 10 canonical proteins (TP53, BRCA1, EGFR, BRCA2, PTEN, MDM2, ATM, KRAS, RB1, APC). Full native Turtle merged. |
| 4 | Serialise to Turtle | ✅ Done | `python src/builder.py` produces `data/seed/graph.ttl`. Run once to generate seed file. |

## Phase 2 — RDF builder
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 5 | builder.py | ✅ Done | UniProt-inverted citation strategy. Fetches protein RDF, extracts PMIDs, adds p9:mentions edges. |
| 6 | aligner.py | ✅ Done | Keyword-based EDAM topic alignment for papers; data type alignment for proteins and diseases. |
| 7 | Validation | ✅ Done | `validate()` in builder.py — checks pmid, schema:name, and that mentions targets have rdf:type. |

## Phase 3 — Fuseki deployment
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 8 | Fuseki config | ✅ Done | `fuseki/config.ttl` — TDB2 dataset, /p9 service, query/update/gsp endpoints. |
| 9 | Helm chart | ✅ Done | `helm/` — Deployment with RGW initContainer (boto3), Service (NodePort 30900), PVC for TDB2. |
| 9a | Builder Job | ✅ Done | `docker/` + `k8s/builder-job.yaml` + `cluster/manifests/p9-builder-job.yaml` — ArgoCD-managed Job that runs builder.py on quick-thrush and uploads graph.ttl to RGW. CI builds image via p9-build-image.yml. |
| 9b | Cluster secrets | ✅ Done | `p9-rgw-credentials` created in default + knowledge-graph namespaces. `p9-builder-ssh-key` created (reuses p8 deploy key). |
| 10 | Deploy Fuseki | ✅ Done | Deployed in knowledge-graph namespace. NodePort 30900 on quick-thrush. 131,023 triples loaded. |
| 11 | Verify endpoint | ✅ Done | `SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }` → 131023. Papers by TP53 query returns real results. |

## Phase 4 — SPARQL queries
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 11 | sparql.py | ✅ Done | SPARQLClient wrapping SPARQLWrapper. Standard prefix injection. query() and ask() methods. |
| 12 | Example queries | ✅ Done | 8 queries in `queries/` — papers by protein, disease paths, top proteins, set intersection, author links, co-mention, temporal filter, full disease subgraph. |
| 13 | Benchmark questions | ✅ Done | `src/benchmark.py` — 10 structured (SPARQL favoured) + 10 open-ended (RAG favoured), each with inline SPARQL and reference answer. |

## Phase 5 — RAG vs SPARQL comparison
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 14 | Run benchmark | ⬜ Todo | `python scripts/run_comparison.py` — needs live Fuseki + p7. Writes results/ and markdown table. |
| 15 | Fill comparison.md | ⬜ Todo | Add benchmark results table to `docs/comparison.md`. |

## Phase 6 — GraphRAG (planned)
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 16 | graphrag.py | ⬜ Planned | Combine SPARQL entity traversal with p7 vector retrieval. LLM synthesises answer from both. |
| 17 | Extend benchmark | ⬜ Planned | Add GraphRAG as third system in the comparison. Add hybrid question type to benchmark. |

## Phase 7 — Imaging facilities domain (planned)
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 18 | Schema extension | ⬜ Planned | Add Facility, Technique, SampleType, AccessCondition classes. |
| 19 | Seed data | ⬜ Planned | Synthetic imaging facility data. 15–20 facilities. |
| 20 | EDAM alignment | ⬜ Planned | Map imaging techniques to EDAM operation terms. |
| 21 | SPARQL examples | ⬜ Planned | Multi-hop queries across facility/technique/access graph. |

---

## Quick status

```
Phase 1  [████] 4/4 — Complete
Phase 2  [███]  3/3 — Complete
Phase 3  [██████] 6/6 ✅
Phase 4  [███]  3/3 — Complete (sparql.py + 8 queries + 20 benchmark questions)
Phase 5  [░░]   0/2 — Needs live Fuseki + p7 to run
Phase 6  [░░]   0/2 — Planned (GraphRAG)
Phase 7  [░░░░] 0/4 — Planned (Imaging facilities)
```

## How to run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Build the knowledge graph (takes ~5–10 min, hits PubMed + UniProt)
python src/builder.py

# 3. Deploy Fuseki on the cluster
helm upgrade --install p9 helm/ \
  --set graphTtlUrl=<URL-to-graph.ttl>

# 4. Query via Python
export P9_SPARQL_ENDPOINT=http://<node-ip>:30900/p9/sparql
python - <<'EOF'
from src.sparql import SPARQLClient
client = SPARQLClient()
rows = client.query(open("queries/03_top_proteins_by_paper_count.sparql").read())
for r in rows[:5]:
    print(r)
EOF
```
