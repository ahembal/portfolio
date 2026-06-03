# p13 — Reproducible LLM Fine-tuning

## Purpose

A reproducible, versioned fine-tuning pipeline for the PubMed RCT sentence
classifier. Covers the full training lifecycle: data loading from the p12
feature store, LoRA fine-tuning with HuggingFace Trainer, per-class evaluation,
systematic hyperparameter search with Optuna, and automated promotion to the
p8 registry via the p11 gate.

## Scope

**In scope:**
- `configs/baseline.yaml` — all hyperparameters in one file; no magic numbers
  in code
- `src/data.py` — loads PubMed RCT data from p12 Parquet store; tokenisation;
  weighted sampler for class imbalance
- `src/train.py` — LoRA fine-tuning with HuggingFace Trainer and PEFT; logs
  to p11 MLflow via the tracking wrapper; early stopping on validation macro F1
- `src/evaluate.py` — per-class F1, macro F1, confusion matrix; writes results
  to MLflow and a local JSON for the promotion gate
- `src/sweep.py` — Optuna study over learning rate, LoRA rank, and batch size;
  each trial is a complete training run logged to MLflow
- `src/promote.py` — calls the p11 promotion gate; on pass, writes a new
  experiment entry to the p8 registry
- `jobs/dardel_finetune.sh` — SLURM job for the Dardel GPU partition
  (NAISS 2026/4-384, same allocation used in p3)

**Out of scope:**
- Full BLURB benchmark suite — PubMed RCT sentence classification provides
  a clear, measurable target; additional tasks can be added in future iterations
- Quantisation and ONNX export — covered in the p8 benchmark pipeline
- Instruction fine-tuning and RLHF — distinct paradigm, distinct project scope

## Design decisions

**Why LoRA and not full fine-tuning?**
LoRA (Low-Rank Adaptation) trains a small number of adapter parameters injected
into the attention layers while keeping the base model frozen. For DistilBERT,
this reduces trainable parameters from 66M to approximately 0.5M, cutting GPU
memory and training time proportionally with minimal impact on final metric
quality. On the Dardel GPU allocation, this makes a full hyperparameter sweep
tractable within the project's compute budget.

**Why Optuna and not grid search?**
Optuna uses Bayesian optimisation — each completed trial informs the sampling
of the next. With a fixed compute budget, this finds strong hyperparameter
configurations in far fewer trials than exhaustive search. The Optuna study
is seeded for reproducibility; every trial is logged to MLflow so the full
search history is preserved.

**Why Dardel HPC?**
The homelab cluster does not have a GPU. The NAISS 2026/4-384 allocation on
Dardel (AMD MI250X, ROCm) is already active from p3. Reusing it keeps the
portfolio infrastructure internally consistent and demonstrates that the
training pipeline is not tied to local hardware.

**Why is this a separate project from p4?**
p4 is a serving project — online, latency-sensitive, continuously running.
p13 is a training project — batch, compute-heavy, infrequently executed.
Keeping them separate reflects the standard industry separation between
training and inference workloads.

## Connection to the portfolio

| Project | Role |
|---------|------|
| p11 | Every run logged here; promotion gate called before registry update |
| p12 | Training data sourced from the Parquet feature store |
| p8 | Best run registered as a new versioned model entry |
| p4 | Improved model deployed via the existing serving infrastructure |
