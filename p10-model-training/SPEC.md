# P10 — Model Training & Benchmarking

## What and why

p1 deploys a model. p8 tracks and packages models. Neither project trains one.
This project closes that gap — it covers the full training pipeline from data
preparation through reproducible evaluation and public benchmarking.

The concrete target is the BEETLE challenge: multiclass semantic segmentation
of H&E-stained breast cancer whole slide images. This is a deliberate step up
from PCam patch classification (p1) — from predicting a binary label on a 96×96
patch to predicting pixel-level tissue class across a full WSI. Both tasks are
in the same domain (digital pathology, H&E, breast cancer) which makes the
progression coherent.

---

## Problem statement

Three things this project addresses:

1. **No training pipeline in the portfolio** — the models in p1 and p4 were
   trained on Kaggle with ad-hoc notebooks. There is no reproducible, versioned
   training pipeline. p10 builds one.

2. **No public benchmark score** — self-reported metrics on a local test split
   are not independently verifiable. A submission to a public challenge leaderboard
   is a credible, reproducible result.

3. **Classification to segmentation gap** — PCam is a well-known but simple
   benchmark. BEETLE requires spatial reasoning over tissue context, multi-class
   output, and multi-site/multi-scanner generalisation. It is a substantially
   harder problem and more representative of production pathology AI.

---

## Target challenge — BEETLE

**Task:** Pixel-level semantic segmentation of H&E breast cancer WSIs.

**Classes:**
| Class | Description |
|-------|-------------|
| Invasive epithelium | Invasive tumour epithelium |
| Non-invasive epithelium | DCIS and other non-invasive epithelial regions |
| Necrosis | Necrotic tissue |
| Other | Stroma, fat, normal tissue, background |

**Dataset:** 587 biopsies/resections from multiple clinical centres, scanned on
seven scanners. Training/resource data publicly available. Final evaluation
annotations are sequestered — benchmarking handled through Grand Challenge.

**Metric:** Overall Dice coefficient across all classes.

**Leaderboard:** Active as of May 2026. Top score 0.9018. First milestone is
a valid submission with reproducible Dice scores — a competitive baseline
and possibly top-10 are realistic if the leaderboard is not saturated.

**Challenge URL:** beetle.grand-challenge.org

---

## System components

### 1. Data pipeline

- Download and version the BEETLE training data
- WSI tiling — extract fixed-size patches at appropriate magnification
- Annotation handling — map pixel labels to training masks
- Stain normalisation and augmentation — critical for multi-scanner generalisation
- Train/val split respecting site/scanner distribution

### 2. Baseline model

A patch-based semantic segmentation approach:

- **Architecture:** U-Net or DeepLabV3+ with ImageNet-pretrained encoder
  (ResNet-50 or EfficientNet-B4)
- **Input:** 512×512 patches extracted from WSI tiles
- **Output:** 4-class probability map per patch
- **Loss:** combination of cross-entropy and Dice loss
- **Augmentation:** random flip/rotation, stain augmentation (Macenko/Vahadane)

### 3. Foundation model iteration

After baseline: swap encoder for a pathology-specific foundation model:
- UNI (ViT-L pretrained on 100k+ pathology slides, Harvard MIL)
- CONCH (contrastive vision-language model for pathology)

These encoders encode tissue morphology more richly than ImageNet-pretrained
models. Expected improvement: 2-5 Dice points on hard classes (necrosis,
non-invasive epithelium).

### 4. WSI inference

- Sliding window inference across full WSI at test time
- Patch-level predictions assembled into full slide segmentation map
- Post-processing: smoothing, small region removal

### 5. Experiment tracking

All training runs registered in p8 model registry:
- Hyperparameters, architecture, encoder
- Per-class and overall Dice on validation set
- Model weights stored in RGW with SHA verification
- Deployment entry when a model is submitted to Grand Challenge

### 6. Grand Challenge submission

- Package inference code as a Docker container per Grand Challenge requirements
- Submit to BEETLE leaderboard
- Record result in p8 registry evaluation entry

---

## Repository layout

```
p10-model-training/
├── SPEC.md
├── PROGRESS.md
├── data/
│   └── pipeline.py         ← download, tile, augment
├── src/
│   ├── model.py            ← architecture definition
│   ├── train.py            ← training loop
│   ├── evaluate.py         ← Dice computation, per-class metrics
│   └── infer.py            ← WSI sliding window inference
├── configs/
│   └── baseline.yaml       ← hyperparameters, paths
├── submission/
│   └── Dockerfile          ← Grand Challenge submission container
└── docs/
    ├── how-it-works.md
    └── results.md          ← experiment results, leaderboard scores
```

---

## Relationship to other projects

| Project | Connection |
|---------|-----------|
| p1 | p1 deploys the serving pipeline. p10 produces better weights to replace TIAToolbox in p1. |
| p8 | All p10 training runs are registered in p8. Dice scores become evaluation entries. |
| p6/p7 | Demonstrates the broader AI-ready data infrastructure context. |

---

## Out of scope

- Instance segmentation (nuclei, gland boundaries)
- Whole slide inference at 40× magnification (40× requires significantly more compute)
- Multi-task learning (classification + segmentation simultaneously)
- Real-time inference (batch offline inference is sufficient)
