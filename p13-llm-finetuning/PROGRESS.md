# p13 — Reproducible LLM Fine-tuning
## Progress Tracker

---

## Steps

### Phase 1 — Data & Config
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | Dataset loader | ⬜ Todo | `src/data.py` — loads PubMed RCT from p12 feature store. Tokenises with DistilBERT tokenizer. Handles class imbalance via weighted sampler. |
| 2 | Training config | ⬜ Todo | `configs/baseline.yaml` — all hyperparameters in one file. No magic numbers in code. |

### Phase 2 — Training
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 3 | LoRA fine-tuning | ⬜ Todo | `src/train.py` — HuggingFace Trainer + PEFT LoRA. Logs every epoch to p11 MLflow. Early stopping on val macro F1. |
| 4 | Evaluation | ⬜ Todo | `src/evaluate.py` — per-class F1, macro F1, confusion matrix. Writes to MLflow and local JSON for promotion gate. |
| 5 | SLURM job | ⬜ Todo | `jobs/dardel_finetune.sh` — submits training to Dardel GPU partition. NAISS 2026/4-384 allocation. |

### Phase 3 — Search & Promotion
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 6 | Hyperparameter sweep | ⬜ Todo | `src/sweep.py` — Optuna study over lr, LoRA rank, batch size. Each trial is a full run logged to MLflow. |
| 7 | Promotion | ⬜ Todo | `src/promote.py` — calls p11 promotion gate. On pass, writes new experiment entry to p8 registry. |
| 8 | Docs | ⬜ Todo | `docs/how-it-works.md` — training design, LoRA rationale, sweep strategy, how to trigger a new run. |

---

## Quick status

```
Phase 1  [░░] 0/2 — Not started
Phase 2  [░░░] 0/3 — Not started
Phase 3  [░░░] 0/3 — Not started
```
