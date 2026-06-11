# HTAP — Hybrid Transactional/Analytical Processing

**Status:** raw
**Target:** p11 (unified evaluation framework)?
**Opened:** 2026-06-11

## What it is

HTAP systems handle both OLTP (high-frequency, low-latency writes — the kind
a transactional application produces) and OLAP (complex aggregation and
analytical queries) over the same data, in the same system, without an ETL
step between them.

Traditional stacks separate these: writes go to Postgres/MySQL (OLTP), then a
nightly batch job exports to a warehouse (Snowflake, BigQuery) for analytics.
HTAP eliminates that boundary — analytical queries run on live data.

Prominent implementations: TiDB, SingleStore, YugabyteDB, Google Spanner,
Snowflake Hybrid Tables.

## Why it matters for this portfolio

The portfolio is ML-heavy but light on database systems depth. HTAP would
demonstrate that depth. More importantly, there is a natural use case: the ML
projects (p1, p4, p8) produce continuous prediction data. A production system
needs to both log those predictions transactionally and query performance
metrics analytically — without waiting for a batch job.

A toy HTAP demo (insert rows, run an aggregate) has no value. The value is in
the architecture argument: why HTAP over ETL, under what latency and freshness
requirements, and what the trade-offs are.

## Connections to existing projects

- **p11 — unified evaluation framework:** the most natural landing zone.
  Instead of running offline benchmarks, p11 could maintain a live metrics
  store where every inference request from p1/p4/p8 is written transactionally
  and analytical queries (drift, latency percentiles, per-class performance)
  run over the same table in real time. HTAP is the infrastructure choice that
  makes this possible without ETL.
- **p8 — model registry / inference server:** produces the prediction stream
  that HTAP would ingest.
- **p1, p4 — classifiers:** the models whose per-class performance would be
  tracked live.

## Open questions

- [ ] Is TiDB the right choice or is a simpler option (DuckDB in-process OLAP
      + Postgres OLTP + a view) sufficient to demonstrate the concept without
      the operational overhead of running TiDB on the homelab?
- [ ] What is the minimum viable demo? A dashboard showing live inference
      latency + accuracy drift, updated without a batch job, is probably enough.
- [ ] Does p11 actually need HTAP, or is a time-series store (InfluxDB,
      TimescaleDB) a better fit for the metrics use case?

## Evidence / research

**2026-06-11** — Discussed as a potential portfolio addition. Agreed that a
standalone HTAP project without a real use case has no value. The p11
evaluation framework is the justified use case. Parked until p11 is scoped.

## Decision

<!-- Pending p11 scope decision. -->
