# p12 — Biomedical Data Pipeline

Daily Airflow pipeline that ingests PubMed abstracts, validates and transforms
them, and writes structured features to a Parquet store on Ceph. The feature
store is the shared data layer for model training (p13) and RAG corpus updates
(p6/p7).

---

## Architecture

```
PubMed Entrez API
        │
        │  daily incremental fetch
        ▼
src/extract.py  ──── raw records (JSON)
        │
        │  schema + quality checks
        ▼
src/validate.py  ──── rejections logged with reason
        │
        │  sentence tokenisation, label extraction
        ▼
src/transform.py  ──── structured records
        │
        │  Parquet, partitioned by year/month
        ▼
Ceph RGW (feature store)
        │
        ├──── p13: training data
        ├──── p6:  RAG corpus updates
        └──── p7:  evaluation benchmark extension
```

Orchestrated by Airflow on K8s. Each stage is a separate retryable task.

---

## Stack

| Component | Tool | Why |
|-----------|------|-----|
| Orchestration | Apache Airflow | Standard for batch pipelines in research bioinformatics |
| Feature store | Parquet on Ceph | Portable, transparent, Hive-compatible partitioning; reuses existing storage |
| Validation | Custom schema rules | Lightweight and auditable; rejections logged with reason |
| Source | PubMed Entrez API | Daily incremental updates; shared domain across p4/p6/p7/p13 |

---

## Feature store layout

```
s3://pipeline-features/
  pubmed/
    year=2024/
      month=01/
        part-2024-01-31.parquet
        ...
  _lineage/
    2026-05-28.json   ← run metadata: source, rows, rejection counts
```

---

## Docs

- [SPEC.md](SPEC.md) — purpose, scope, design decisions
- [docs/how-it-works.md](docs/how-it-works.md) — pipeline stages, feature store schema, backfill guide
