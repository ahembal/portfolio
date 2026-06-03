# p12 — Biomedical Data Pipeline
## Progress Tracker

---

## Steps

### Phase 1 — Extract & Validate
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | PubMed extractor | ⬜ Todo | `src/extract.py` — incremental fetch by date range via Entrez API. Returns raw abstract records. |
| 2 | Schema validation | ⬜ Todo | `src/validate.py` — reject records missing abstract, PMID, or publication date. Log rejection reasons. |
| 3 | Transform | ⬜ Todo | `src/transform.py` — sentence tokenisation, structured JSON per abstract. |
| 4 | Feature store load | ⬜ Todo | `src/load.py` — write Parquet to Ceph, partitioned by year/month. Append-only. |
| 5 | Lineage | ⬜ Todo | `src/lineage.py` — record source, extraction date, row counts, and transformation version per run. |

### Phase 2 — Orchestration
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 6 | Airflow DAG | ⬜ Todo | `dags/pubmed_pipeline.py` — daily schedule. Tasks: extract → validate → transform → load → lineage. |
| 7 | Airflow on K8s | ⬜ Todo | Helm deploy. KubernetesExecutor — each task runs in its own pod. |
| 8 | Docs | ⬜ Todo | `docs/how-it-works.md` — pipeline diagram, feature store layout, how to backfill. |

---

## Quick status

```
Phase 1  [░░░░░] 0/5 — Not started
Phase 2  [░░░]   0/3 — Not started
```
