# p11 — ML Experiment Tracking
## Progress Tracker

---

## Steps

### Phase 1 — Infrastructure
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | MLflow Helm chart | ⬜ Todo | Deploy MLflow tracking server on K8s. Artifact store points to Ceph RGW S3. |
| 2 | Tracking wrapper | ⬜ Todo | `src/tracking.py` — thin client that wraps `mlflow.start_run()`. Training scripts import this, not MLflow directly. |
| 3 | Promotion logic | ⬜ Todo | `src/promotion.py` — loads current production run from MLflow, compares macro F1, returns pass/fail. |

### Phase 2 — Integration
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | Instrument p4 training | ⬜ Todo | Add `tracking.log_run()` calls to p4 DistilBERT training notebook as a reference example. |
| 5 | CI promotion gate | ⬜ Todo | GitHub Actions job that calls `promotion.py` before allowing a p8 registry commit. |
| 6 | Docs | ⬜ Todo | `docs/how-it-works.md` — architecture, how to instrument a new training script, how to read the MLflow UI. |

---

## Quick status

```
Phase 1  [░░░] 0/3 — Not started
Phase 2  [░░░] 0/3 — Not started
```
