# Training Design — PCam Classifier
*Last updated: 2026-05-06*

Rationale behind dataset, model, and training decisions for the ResNet-18
binary classifier trained on PatchCamelyon. For results see PROGRESS.md.
For serving decisions see `how-it-works.md`.

---

## Dataset

**PatchCamelyon (PCam)** — 327,680 colour images (96×96 px), H&E-stained
lymph node sections. Binary label: tumour tissue present in the central
32×32 region (positive) or not (negative). Balanced classes.

Sourced from Kaggle: `andrewmvd/metastatic-tissue-classification-patchcamelyon`

**Why PCam:**
- Well-established benchmark with published baselines — results are comparable
- Realistic medical imaging task relevant to SciLifeLab's pathology work
- Large enough (327k images) to demonstrate deep learning at scale
- Small enough to fine-tune in a single Kaggle session on a T4 GPU

---

## Model choice — ResNet-18

| Alternative | Why not chosen |
|-------------|---------------|
| ResNet-50/101 | 3-4× more parameters, marginal accuracy gain on PCam, slower CPU inference |
| EfficientNet | More complex training setup, not meaningfully better on this task |
| ViT | Requires more data to converge; overkill for 96×96 patches |
| Custom CNN | No benefit over pretrained ResNet-18 on a well-studied benchmark |

ResNet-18 pretrained on ImageNet gives strong feature extraction from the start.
Fine-tuning the full network (not just the head) for 6 epochs converges reliably
on PCam and keeps the model small (~45 MB) — suitable for CPU serving.

---

## Binary output design — 1 logit + sigmoid

The final fully connected layer outputs **one value** (not two):

```python
model.fc = nn.Linear(512, 1)
loss_fn = nn.BCEWithLogitsLoss()
```

**Why not 2 outputs + softmax:**
With two classes, `P(normal) = 1 - P(tumour)` always — the second output
is fully determined by the first and adds no information. One logit + sigmoid
is the standard practice for binary classification:

- Fewer parameters (512×1 vs 512×2 in the final layer)
- Pairs naturally with `BCEWithLogitsLoss` (numerically stable)
- Threshold is an explicit tunable parameter — not locked at 0.5

For 3+ classes (e.g. p4's 5-class sentence classifier), softmax over
multiple outputs is necessary because the probabilities are independent.

---

## Threshold selection

The model outputs P(tumour). Two operating thresholds are stored in
`artifacts/threshold.json`:

| Threshold | Value | Use case |
|-----------|-------|----------|
| Youden | 0.3694 | Maximises sensitivity + specificity balance |
| 95% sensitivity | 0.2044 | For screening — minimises missed cancers |

The serving API defaults to 0.5. The thresholds are stored separately
so they can be applied externally without retraining.

**Why threshold tuning matters in clinical contexts:**
Missing a tumour (false negative) is far worse than a false alarm (false
positive). The 95% sensitivity threshold trades specificity for recall —
accepting more false positives in exchange for catching more real tumours.

---

## Hyperparameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Epochs | 6 | Validation loss plateaued — diminishing returns beyond 6 |
| Batch size | 128 × N_GPUs | Saturates T4 VRAM; larger batches stabilise gradient estimates |
| Learning rate | 1e-4 → cosine decay | AdamW with cosine schedule — standard for fine-tuning |
| Augmentation | RandomRot90 (D4 group) | PCam patches are rotationally symmetric — D4 is zero-copy |
| Channels-last | NHWC | Faster on T4 GPU than NCHW for this model size |

---

## Evaluation

Final metrics reported on held-out **test set** (not validation set).

| Metric | Value |
|--------|-------|
| AUC | 0.9657 |
| Accuracy | 90.0% |
| F1 | 0.897 |
| Youden threshold sensitivity | 90.6% |
| Youden threshold specificity | 90.4% |

AUC is the primary metric for binary classifiers on balanced datasets —
it measures discrimination ability independently of threshold choice.
Accuracy and F1 are reported at the default 0.5 threshold.

---

## Compute

Plan A (Dardel GPU) was deprioritised due to setup time. Plan B (Kaggle T4)
was used — free, immediate, sufficient for this dataset size. Training took
approximately 45 minutes for 6 epochs.
