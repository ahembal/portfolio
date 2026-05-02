# Training Design — PubMed RCT Sentence Classification
*Last updated: 2026-05-02*

## What we are building and why

This project fine-tunes a transformer model to classify sentences from medical
abstracts. The task is **structured abstract labelling** — given a sentence like
*"Patients were randomly assigned to receive drug A or placebo"*, the model
outputs the section it belongs to: BACKGROUND, OBJECTIVE, METHODS, RESULTS, or
CONCLUSIONS.

This is not a toy task. Automated structured abstract generation is used in
real biomedical NLP pipelines to extract evidence from literature at scale —
for example, identifying which sentences describe outcomes vs. methods in a
systematic review. SciLifeLab processes large volumes of biomedical literature;
this task is representative of that work.

---

## Dataset — PubMed RCT 200k

**Source:** Dernoncourt & Lee (2017), *PubMed 200k RCT: a Dataset for Sequential
Sentence Classification in Medical Abstracts*

**HuggingFace identifier (current):** `armanc/pubmed-rct20k`

### Dataset history and rationale

**First attempt (2026-04-30):** `pietrolesci/pubmed-200k-rct`
- Contains 2.27M sentences (200k abstracts × ~11 sentences each)
- Labels pre-encoded as integers 0–4
- **Problem:** At batch_size=64 on Kaggle T4 (1.55 it/s), one epoch takes ~6 hours.
  Kaggle sessions time out before training completes — not practical.

**Revised choice (2026-05-02):** `armanc/pubmed-rct20k`
- Contains ~177k sentences (20k abstracts), same 5-class label structure
- Labels are lowercase strings: `background, objective, methods, results, conclusions`
- 3 epochs complete in ~90 minutes on T4 — fits within Kaggle session limit
- Same Dernoncourt & Lee (2017) source; 20k split is standard in published experiments

**Why the smaller dataset is still valid:**
177k training sentences gives thousands of examples per class. The accuracy gap
vs. training on the full 2.27M is typically < 2% for BERT-class models on this task.
The goal is a working deployment demo, not a SOTA benchmark — the 20k version is
the appropriate choice for this context.

**Label encoding:**
Labels are lowercase strings mapped to integers 0–4 via `LABEL2ID` in the tokenise
function. `ID2LABEL` stores uppercase names for human-readable output.

**Class distribution (approximate):**

| Label | % of dataset | Challenge |
|-------|-------------|-----------|
| METHODS | ~37% | Most common — model must not over-predict |
| RESULTS | ~30% | Distinct vocabulary (numbers, statistics) |
| BACKGROUND | ~13% | Often short, general sentences |
| CONCLUSIONS | ~11% | Overlap with RESULTS in wording |
| OBJECTIVE | ~9% | Least common — hardest to learn |

The imbalance is real-world — METHODS-heavy abstracts dominate RCTs.
Macro F1 (unweighted average across classes) is the right metric here:
it penalises a model that ignores rare classes.

---

## Model choice — DistilBERT

**Why DistilBERT over BERT-base:**
- 40% fewer parameters (66M vs 110M) → fits on T4 (16 GB VRAM) with batch_size=64
- ~97% of BERT-base performance on GLUE — the efficiency is worth the marginal loss
- Faster inference — critical for serving: DistilBERT processes a sentence in ~30ms
  vs ~50ms for BERT-base on CPU; matters for the `/predict` latency target

**Why not BioBERT or domain-specific models:**
- BioBERT achieves ~92% accuracy on this task vs ~86-88% for DistilBERT
- The gap demonstrates that domain pretraining helps — worth mentioning in docs
- For this portfolio we use DistilBERT to show the general approach;
  a production deployment would use BioBERT or PubMedBERT

**Current SOTA context (as of 2024):**
- BioBERT-base: ~92% accuracy
- DistilBERT: ~86-88% accuracy
- Our target: ≥ 85% (confirms the model learned the task)

---

## Training decisions

### Hyperparameters

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| `learning_rate` | 2e-5 | Standard for BERT fine-tuning (Devlin et al. recommend 2e-5 to 5e-5) |
| `batch_size` | 64 | Fills T4 VRAM; larger batches stabilise gradient estimates for small per-class counts |
| `epochs` | 3 | Typical for BERT fine-tuning — more epochs risks overfitting the task-specific head |
| `max_length` | 128 | Most RCT sentences < 50 tokens; 128 gives headroom with minimal padding cost |
| `weight_decay` | 0.01 | L2 regularisation — prevents the classification head from overfitting |
| `fp16` | True (GPU only) | Mixed precision halves VRAM usage and speeds up training ~1.5× on T4 |

### Why `eval_strategy="epoch"` not steps:
With 200k training examples and batch_size=64 there are ~3,100 steps per epoch.
Evaluating every epoch (not every N steps) is appropriate — the model needs to
see a full pass before meaningful metrics emerge, and frequent eval adds overhead.

### Why `load_best_model_at_end=True`:
The model checkpoint with highest validation accuracy is saved, not the final
epoch. This is important because loss can increase in epoch 3 while accuracy
plateaus — we want the best generalising model, not the most-trained one.

---

## Dependency and API notes (Kaggle-specific)

**Do not reinstall boto3 on Kaggle:**
Kaggle pre-installs `boto3` with a version compatible with its `aiobotocore`.
Pinning `boto3==1.34.0` downgrades `botocore` to 1.34.x, which breaks
`aiobotocore 3.3.0` (requires botocore >=1.42.62). The upload cell uses
Kaggle's pre-installed boto3 — no explicit install needed.

**transformers `Trainer` API change (>=4.47):**
The `tokenizer=` parameter was renamed to `processing_class=` in transformers
v4.47. The notebook uses `processing_class=tokenizer` to work with current
versions installed via `pip install 'transformers>=4.41.0'`.

**scikit-learn required by `evaluate`:**
The `evaluate` library uses `scikit-learn` internally for accuracy and F1
computation. Kaggle has it pre-installed; local environments may need
`pip install scikit-learn`.

---

## Known challenges and limitations

**Sentence boundary sensitivity:**
The model classifies individual sentences. In practice, abstracts have context
dependence — the same sentence may be BACKGROUND or CONCLUSIONS depending on
position. The dataset provides sentences without positional context, which is
a limitation. Sequential models (e.g., with position embeddings over sentence
position) achieve higher accuracy.

**Class confusion:**
RESULTS and CONCLUSIONS are the most commonly confused pair — both contain
outcome language. A confusion matrix (in the notebook output) reveals this
empirically.

**Inference vs. training distribution:**
The model is fine-tuned on structured abstracts from RCTs specifically.
Performance on non-RCT abstracts (e.g., review articles, case reports) is
expected to be lower — this is a domain-specific model, not a general
sentence classifier.

**RGW connectivity from Kaggle:**
Uploading model artifacts to the homelab Ceph RGW requires the Kaggle notebook
to reach `http://100.82.75.34` (quick-thrush via Tailscale). This works if
Tailscale is active on the network where quick-thrush runs. If the endpoint is
unreachable, download the model from `/kaggle/working/` manually and upload
with the local `push_artifacts.py` script.
