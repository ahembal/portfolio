# Q4 — Personal Abilities
*Last updated: 2026-05-01*

> Numbers in `[brackets]` are filled after training completes.

## What this project demonstrates

End-to-end ownership of an ML task — dataset selection, model choice, training
decisions, evaluation, and production deployment — without scaffolding.

---

## Independent problem framing

**Dataset choice — PubMed RCT 200k:**
Deliberately chosen because it is real biomedical text, not a toy benchmark.
Structured abstract labelling (classifying sentences as BACKGROUND / OBJECTIVE /
METHODS / RESULTS / CONCLUSIONS) maps directly to literature-scale evidence
synthesis — a core workload at SciLifeLab/NBIS. The dataset is small enough to
fine-tune in < 1 hour on a T4 GPU and has published baselines for comparison.

**Model choice — DistilBERT over BERT-base and BioBERT:**
- DistilBERT: 40% fewer parameters than BERT-base, ~97% of performance on GLUE
- Inference latency: ~30ms per sentence vs ~50ms for BERT-base on CPU — matters at scale
- BioBERT would give ~4-6% higher accuracy on this task, but adds complexity
- This reflects a deliberate accuracy/efficiency trade-off, not just picking the "best" model
- A production system would use PubMedBERT — acknowledged in docs

---

## Training decisions

Full rationale in `docs/training-design.md`. Key independent choices:

| Decision | Value | Why |
|----------|-------|-----|
| Learning rate | 2e-5 | Grounded in original BERT paper recommendations |
| Batch size | 64 | Saturates T4 VRAM — not the default 16 |
| Max length | 128 | Empirically appropriate for RCT sentence lengths; default 512 wastes compute |
| Best model selection | `load_best_model_at_end=True` | Saves checkpoint with highest val accuracy, not final epoch |

---

## Evaluation methodology

**Why macro F1 alongside accuracy:**
Accuracy is misleading with imbalanced classes — METHODS sentences are ~37% of
the dataset. A model predicting METHODS for everything achieves 37% accuracy.
Macro F1 weights all classes equally, exposing whether the model learned all
five categories.

**Per-class F1 reported:**
OBJECTIVE (9%) and CONCLUSIONS (11%) are expected to have lower F1 due to fewer
training examples. Reporting this honestly — rather than only overall accuracy —
is the correct scientific practice.

**Test set evaluation:**
Final numbers reported on held-out test set, not the validation set used for
checkpoint selection. Using validation set for final reporting is a common mistake
in published work; this notebook avoids it.

---

## Results

| Metric | Value |
|--------|-------|
| Test accuracy | [X]% |
| Macro F1 | [X] |
| F1 — BACKGROUND | [X] |
| F1 — OBJECTIVE | [X] |
| F1 — METHODS | [X] |
| F1 — RESULTS | [X] |
| F1 — CONCLUSIONS | [X] |

*Context: BioBERT ~92%, general DistilBERT ~86-88% on this task.*

---

## Honest scope boundaries

**Not novel:** This is a known benchmark with known approaches. The contribution
is end-to-end execution and deployment, not a new architecture.

**Not production-scale training:** Kaggle T4 + 200k sentences is a development
environment. Training at SciLifeLab scale (millions of PubMed abstracts) would
require Dardel GPU or equivalent. The approach scales; the infrastructure differs.

**Domain adaptation gap:** General DistilBERT was chosen deliberately for
simplicity. A production system would use PubMedBERT or BioBERT for 4-6%
higher accuracy — this trade-off is documented, not hidden.
