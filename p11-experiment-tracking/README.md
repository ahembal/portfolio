# p11 — ML Experiment Tracking

Self-hosted MLflow tracking server deployed on the homelab cluster. Captures
every training run across the portfolio and provides a CI-integrated promotion
gate that enforces metric improvement before any model enters the p8 registry.

---

## Architecture

```
Training script (p4/p13)
        │
        │  via src/tracking.py wrapper
        ▼
MLflow Tracking Server  ←──── MLflow UI (browser)
        │
        │  artifacts (model weights, evaluation reports)
        ▼
Ceph RGW (S3-compatible artifact store)
        │
        │  src/promotion.py — metric comparison
        ▼
CI gate (GitHub Actions)  ──── p8 Model Registry
```

---

## Stack

| Component | Tool | Why |
|-----------|------|-----|
| Experiment tracking | MLflow | Open-source, self-hostable, HuggingFace Trainer native |
| Artifact store | Ceph RGW | Already in homelab; S3-compatible |
| Deployment | Helm on K8s | Consistent with all other portfolio services |
| Promotion logic | `src/promotion.py` | Decouples the pass/fail decision from CI configuration |

---

## Usage

```python
from src.tracking import Tracker

tracker = Tracker(experiment="pubmed-rct")
with tracker.run(name="lora-lr1e-4"):
    for epoch in range(num_epochs):
        tracker.log_metric("val/macro_f1", score, step=epoch)
    tracker.log_params({"lr": 1e-4, "lora_rank": 16})
    tracker.log_artifact("/tmp/model", artifact_path="model")
```

```bash
# CI promotion check — exits 0 (promote) or 1 (reject)
python src/promotion.py \
  --run-id abc123 \
  --metric val/macro_f1 \
  --min-delta 0.01
```

---

## Docs

- [SPEC.md](SPEC.md) — purpose, scope, design decisions
- [docs/how-it-works.md](docs/how-it-works.md) — architecture, instrumentation guide, promotion workflow
