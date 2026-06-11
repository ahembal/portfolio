# p11 — Unified Evaluation Framework

**Status:** raw
**Target:** new project (p11)
**Opened:** 2026-06-11

## What it is

A single automated pipeline that runs quality checks across all portfolio
projects on a schedule and produces a shared report or dashboard showing the
current state of every system.

Without this, each project's evaluation is run manually and in isolation:
p7's LLM judge, p8's benchmark runner, p9's SPARQL comparison, p1/p4's model
metrics. There is no unified view and no regression detection across projects.

## Why it matters for this portfolio

It demonstrates that the portfolio is not a collection of disconnected
experiments — it is a system that is actively monitored. It also answers a
real engineering question: how do you know your models and services are still
performing as expected after you deploy them?

## Connections to existing projects

- **p7 — RAG evaluation:** has `judge_evaluate()` — the LLM-as-judge scorer.
  p11 would call this on a schedule.
- **p8 — model registry / inference server:** has the benchmark runner for
  inference latency and throughput. p11 would trigger it and collect results.
- **p9 — knowledge graph:** has the SPARQL vs RAG vs GraphRAG comparison
  script. p11 would run it and track results over time.
- **p1 — PCam classifier:** ROC-AUC, per-class F1 on a held-out test set.
  No automated runner currently exists.
- **p4 — NLP classifier:** same — per-class F1, calibration. No automated
  runner.
- **HTAP topic (`htap.md`):** the metrics store p11 needs is the exact HTAP
  use case. Every inference logged transactionally; analytical queries
  (drift, latency percentiles, per-class performance over time) run without
  ETL. If p11 gets built, HTAP is the justified infrastructure choice.

## Open questions

- [ ] Is this realistic without production traffic? Offline benchmarks on
      fixed test sets are useful but they do not detect real drift.
- [ ] What is the minimum viable version? A scheduled script that runs each
      project's existing evaluation and writes results to a shared JSON/CSV
      is a start — no dashboard required.
- [ ] Does p11 need a database at all, or is a git-committed results file
      per run sufficient for the portfolio's purposes?
- [ ] Which projects actually have evaluation datasets ready? p1 (Kaggle
      PCam test set), p4 (held-out split), p7/p9 (benchmark questions).
      p8 has synthetic load — is that sufficient?

## Evidence / research

**2026-06-11** — Noted in TODO.local as a future project. All component
pieces exist: p7 has the judge, p8 has the benchmark runner, p9 has the
comparison script. p11 would wire them together.

## Decision

<!-- Pending. Revisit after p8 benchmark and p9 comparison are complete
     and producing stable results — those are the first two inputs p11
     would consume. -->
