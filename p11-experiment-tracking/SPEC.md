# p11 — ML Experiment Tracking

## Purpose

A self-hosted MLflow tracking server that captures every training run across
the portfolio — hyperparameters, per-epoch metrics, and model artifacts. Paired
with a promotion gate that CI invokes before a run is registered in p8,
ensuring that only runs that demonstrably improve on the current production
model are promoted.

## Scope

**In scope:**
- MLflow tracking server deployed on K8s via Helm
- Artifact store backed by Ceph RGW (S3-compatible)
- `src/tracking.py` — thin client wrapper used by all training scripts
- `src/promotion.py` — compares a candidate run against the current production
  run and outputs a pass/fail decision for CI
- Instrumented example for p4 DistilBERT training
- CI job that invokes the promotion gate before any p8 registry commit

**Out of scope:**
- MLflow Model Registry — p8 fills that role; duplicating it would fragment
  the single source of truth for model governance
- Multi-user authentication — single-user homelab
- Hyperparameter search — covered in p13

## Design decisions

**Why MLflow over W&B or Neptune?**
MLflow is open-source and fully self-hostable. The portfolio infrastructure
runs on the homelab cluster and cannot depend on external SaaS for a core
observability layer. MLflow also integrates natively with HuggingFace Trainer
via the `report_to="mlflow"` argument, which is used in p13.

**Why Ceph RGW as the artifact store?**
The homelab runs Ceph for p1 and p2. Reusing it for MLflow artifacts avoids
introducing a new storage system and demonstrates that infrastructure choices
compound across projects.

**Why a thin wrapper (`src/tracking.py`) instead of calling MLflow directly?**
Training scripts should not depend on the tracking backend's API surface.
If the backend changes, one file changes. The wrapper also provides a
consistent interface across all training scripts in the portfolio.

## Connection to the portfolio

| Project | Role |
|---------|------|
| p4 | First consumer — DistilBERT training instrumented as reference example |
| p8 | Promotion gate reads MLflow run metrics before registry update |
| p13 | Primary consumer — every fine-tuning run logged here |
