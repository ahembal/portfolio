# p13 — Reproducible LLM Fine-tuning

Reproducible fine-tuning pipeline for the PubMed RCT sentence classifier.
Covers the full training lifecycle: data loading, LoRA fine-tuning, systematic
hyperparameter search, and automated promotion to the p8 model registry via
the p11 gate. Training runs on Dardel HPC (AMD MI250X GPU).

---

## Architecture

```
p12 Feature Store (Parquet on Ceph)
        │
        │  src/data.py — tokenise, weighted sampler
        ▼
src/train.py  ──── LoRA fine-tuning (HuggingFace Trainer + PEFT)
        │                │
        │                │  every epoch
        │                ▼
        │          p11 MLflow tracking
        │
        │  src/evaluate.py — per-class F1, confusion matrix
        ▼
src/promote.py  ──── p11 promotion gate
        │
        │  on pass
        ▼
p8 Model Registry  ──── p4 serving (new image via CI)
```

Hyperparameter sweep via `src/sweep.py` (Optuna). Each trial is a complete
training run logged to MLflow. Compute on Dardel GPU via SLURM.

---

## Stack

| Component | Tool | Why |
|-----------|------|-----|
| Fine-tuning | HuggingFace Trainer + PEFT LoRA | Parameter-efficient; tractable on limited GPU budget |
| Hyperparameter search | Optuna | Bayesian optimisation over learning rate, LoRA rank, batch size |
| Experiment logging | MLflow via p11 | Every run captured, reproducible, comparable |
| Compute | Dardel HPC (NAISS 2026/4-384) | AMD MI250X GPU; same allocation active from p3 |
| Config | YAML (`configs/baseline.yaml`) | All hyperparameters in one file; no magic numbers in code |

---

## LoRA in practice

LoRA injects low-rank adapter matrices into the attention layers of DistilBERT.
The base model is frozen; only the adapters (~0.5M parameters vs 66M total) are
trained. This reduces GPU memory by ~60% and training time proportionally, with
well-documented parity in final metric quality (Hu et al. 2021).

---

## Docs

- [SPEC.md](SPEC.md) — purpose, scope, design decisions
- [docs/how-it-works.md](docs/how-it-works.md) — training design, sweep strategy, promotion workflow
- [configs/baseline.yaml](configs/baseline.yaml) — reference hyperparameter configuration
