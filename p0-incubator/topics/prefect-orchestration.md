# Prefect — Pipeline Orchestration

**Status:** raw
**Target:** p10 (model training pipeline) / p12 (data pipeline)
**Opened:** 2026-05-21

## What it is

Prefect is a Python-native workflow orchestration framework. It wraps existing
Python functions with retry logic, scheduling, observability (run history,
logs, failure alerts), and a UI dashboard — without requiring a DAG-first
design like Airflow.

The key value proposition: you write plain Python, decorate functions with
`@flow` and `@task`, and Prefect handles scheduling, retries, and
observability. It is significantly lighter to operate than Airflow and
integrates naturally with existing Python ML code.

## Why it matters for this portfolio

p10's training pipeline is currently plain Python scripts. A recruiter looking
at a production ML training pipeline expects to see orchestration — not because
the scripts are wrong, but because in production you need retries (Dardel job
failures), run history (which hyperparameters were tried), and alerting (the
job finished / failed). Prefect provides all of this with minimal code changes.

p12 (data pipeline) has the same gap. Prefect would turn it from "scripts that
run in order" to "an observable, retriable pipeline with a run history."

## Connections to existing projects

- **p10 — model training:** `data/pipeline.py` is the natural entry point.
  Wrapping tile → normalise → split as Prefect tasks gives retry logic on
  individual steps and a visible run history. The Dardel SLURM job submission
  could be a Prefect task with a polling loop.
- **p12 — data pipeline:** similar — turn the existing pipeline scripts into
  Prefect flows.
- **p5 — dev practices:** the orchestration vs. workflow automation distinction
  (Prefect for data pipelines, n8n for human-in-the-loop processes) is worth
  documenting as an architectural pattern.

## Open questions

- [ ] Is Prefect Cloud (managed) or self-hosted (Prefect server on homelab)
      the right choice? Self-hosted adds operational overhead; Prefect Cloud
      has a free tier but introduces an external dependency.
- [ ] Does adding Prefect to p10 meaningfully increase the portfolio's value,
      or is it scope creep at a point when p10 Phase 2 (training code) is not
      even written yet?
- [ ] Would Prefect be used to submit the Dardel SLURM job, or only to
      orchestrate the pre-processing steps that run locally?

## Evidence / research

**2026-05-21** — Noted in TODO.local as a potential orchestrator for p10.
Clarification note added: orchestration (Prefect) vs workflow automation (n8n)
are different tools solving different problems.

## Decision

<!-- Pending. Revisit after p10 Phase 2 (training code) is complete. -->
