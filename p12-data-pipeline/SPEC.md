# p12 — Biomedical Data Pipeline

## Purpose

A production-grade data pipeline that continuously ingests PubMed abstracts,
validates and transforms them, and writes structured features to a persistent
store on Ceph. The feature store is the shared data layer for model training
(p13) and RAG corpus updates (p6/p7).

## Scope

**In scope:**
- `dags/pubmed_pipeline.py` — daily Airflow DAG: extract → validate → transform → load
- `src/extract.py` — incremental PubMed fetch via Entrez API, by date range
- `src/validate.py` — schema checks and quality rules (missing abstracts,
  duplicate PMIDs, abstract length); rejections logged with reason
- `src/transform.py` — sentence tokenisation, label extraction for RCT abstracts,
  structured JSON output per record
- `src/load.py` — Parquet write to Ceph, partitioned by year/month, append-only
- `src/lineage.py` — records source, transformation version, and row counts per run
- Data quality report emitted as Airflow task output

**Out of scope:**
- Streaming ingestion — daily batch is the appropriate cadence for PubMed updates
- dbt transformations — no SQL warehouse in the homelab
- Full Great Expectations suite — the custom validation layer covers the
  quality requirements at this scale

## Design decisions

**Why Airflow?**
Airflow is the standard orchestration platform for batch pipelines in research
and bioinformatics. It provides task-level retries, dependency management, and
a UI for monitoring run history — all necessary for a pipeline that must run
reliably without manual intervention.

**Why Parquet on Ceph instead of a managed feature store?**
Parquet files on S3-compatible object storage are portable, transparent, and
readable by any consumer — pandas, Spark, DuckDB, or Arrow. The homelab
already operates Ceph (p1, p2). Adding a managed feature store (Feast, Tecton)
would introduce operational complexity that the data scale does not justify.
The partition layout (`year=YYYY/month=MM`) follows Hive convention, making
the store compatible with any future move to a cloud data warehouse.

**Why PubMed as the source?**
PubMed provides daily incremental updates via the Entrez API, is openly
accessible, and is the primary literature source for the biomedical domain
shared across p4, p6, p7, and p13. Concentrating on one well-understood
source demonstrates the pipeline pattern clearly.

## Connection to the portfolio

| Project | Role |
|---------|------|
| p4 | Consumes structured abstracts for model retraining |
| p6 | Consumes new abstracts for RAG corpus updates |
| p7 | Evaluation benchmark can be extended with pipeline output |
| p13 | Primary training data source |
