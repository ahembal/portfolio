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
seven scanners. Evaluation set: 170 densely annotated ROIs from 54 WSIs
(sequestered on Grand Challenge). Training/resource data publicly available.

**Metric:** Overall Dice coefficient across all classes.

**Leaderboard:** Active as of May 2026. Top score 0.9018.

**Grand Challenge submission:** Inference container submitted to GC; runs on
GC's AWS infrastructure against the sequestered test set. Training is done
locally on Dardel. See `docs/gc-submission.md`.

---

## System components

### 1. Data pipeline

- Download and version the BEETLE training data
- WSI tiling — 512×512 patches at 20× magnification
- Annotation handling — TIFF mask or GeoJSON polygon to 4-class training masks
- Stain normalisation — Macenko (tile-time) + HueSaturationValue (training-time)
- Train/val split respecting scanner and site distribution

### 2. Baseline — nnU-Net

**nnU-Net is the mandatory first baseline.** The BEETLE challenge organisers
used nnU-Net-for-Pathology for technical validation and achieved:

| Set | Overall Dice | Invasive | Non-invasive | Necrosis |
|-----|-------------|----------|-------------|----------|
| Development (5-fold) | **0.92** | 0.78 | 0.83 | 0.75 |
| External test | **0.87** | 0.78 | 0.65 | 0.51 |

This is the most relevant published baseline for BEETLE, trained on the exact
data regime we are targeting. Any custom model must beat these numbers to justify
the added complexity.

nnU-Net self-configures its architecture, preprocessing, and training schedule
from the dataset properties. For BEETLE: RGB patches at 512×512, 0.5 µm/px,
with balanced class sampling and 5-fold cross-validation ensemble.

nnU-Net is run as a separate training environment (its own conda env and config)
rather than integrated into `src/train.py`. Results are logged to the p8 registry.

### 3. Custom segmentation model (post-baseline)

After nnU-Net establishes a baseline, a custom PyTorch model is trained using
`src/train.py`. Architecture: **FM encoder + conservative decoder** (not an
end-to-end foundation model). The decoder is U-Net or UPerNet; the encoder is
one of:

| Encoder | Pretraining | Evidence |
|---------|-------------|---------|
| ResNet-50 | ImageNet | Reference point — establishes cost of ImageNet pretraining |
| **CONCH** (ViT-B) | 1.17M pathology image-caption pairs | Best in Feb 2026 dense segmentation benchmark across 4 histopathology datasets |
| **Virchow2** (ViT-H) | 3.1M pathology slides | Won PUMA Grand Challenge tissue segmentation (Virchow2 + Efficient-UNet) |

UNI (previously listed as primary) is deprioritised: the independent 2026
segmentation benchmark found CONCH and PathDino outperform UNI for dense
prediction. The strongest concrete challenge win (PUMA) uses Virchow2.

### 4. Multi-scanner generalisation

Treating generalisation as only "Macenko + colour jitter" is insufficient for
BEETLE's 7-scanner dataset. Evidence from adjacent challenges (COSAS, SCORPION)
points to three additional strategies:

- **Domain-adaptive convolutions** — content-and-domain adaptive layers that
  adjust feature statistics per scanner at inference time (COSAS winner)
- **Scanner-stratified ensembles** — train separate models or heads per scanner
  group, ensemble at inference time (COSAS runner-up)
- **Consistency regularisation** — penalise prediction drift across scanner
  augmentations of the same patch (SCORPION's SimCons approach)

At minimum, the val set must be scanner-stratified (implemented in `data/split.py`)
so per-scanner Dice is reported alongside overall Dice.

### 5. WSI inference

- Sliding window inference at 50% overlap (stride = patch_size / 2)
- Patch predictions averaged in overlap regions to reduce boundary artefacts
- Full slide segmentation map assembled and saved as uint8 TIFF

### 6. Experiment tracking

All training runs registered in p8 model registry:
- Hyperparameters, architecture, encoder
- Per-class and overall Dice on validation set, per scanner
- Model weights stored in RGW with SHA verification
- Deployment entry when a model is submitted to Grand Challenge

### 7. Grand Challenge submission

- Package inference code as Docker container (non-root, no outbound network)
- Submit to BEETLE leaderboard
- Record result in p8 registry evaluation entry

---

## Model option ranking (research-informed)

Based on the BEETLE-specific evidence and adjacent challenge results:

| Priority | Option | Justification |
|----------|--------|--------------|
| 1 | nnU-Net ensemble (5-fold) | Organiser baseline: 0.92 dev / 0.87 test. Must beat before iterating. |
| 2 | CONCH + U-Net/UPerNet | Best in 2026 dense segmentation benchmark. Independent evidence. |
| 3 | Virchow2 + Efficient-UNet | Won PUMA tissue segmentation. Strongest concrete challenge win. |
| 4 | Domain-adaptive ensemble | COSAS winner pattern. Most relevant for multi-scanner robustness. |
| 5 | ResNet-50 + U-Net | ImageNet baseline. Required for ablation but not competitive. |

---

## Repository layout

```
p10-model-training/
├── SPEC.md
├── PROGRESS.md
├── configs/
│   └── baseline.yaml           ← hyperparameters, paths
├── data/
│   ├── pipeline.py             ← orchestrates data prep
│   ├── tile.py                 ← WSI tiling at 20×
│   ├── masks.py                ← annotation → 4-class mask
│   ├── normalise.py            ← Macenko/Vahadane
│   └── split.py                ← scanner+site stratified split
├── src/
│   ├── dataset.py              ← PyTorch Dataset + augmentation
│   ├── model.py                ← U-Net / UPerNet with swappable encoder
│   ├── train.py                ← training loop (Accelerate, fp16)
│   ├── evaluate.py             ← Dice computation, per-class + per-scanner
│   └── infer.py                ← WSI sliding window inference
├── submission/
│   ├── Dockerfile              ← Grand Challenge submission container
│   └── process.py              ← GC entrypoint
└── docs/
    ├── how-it-works.md
    ├── model-options.md
    ├── data-pipeline.md
    ├── evaluation.md
    ├── implementation.md
    ├── training-on-dardel.md
    ├── gc-submission.md
    ├── security.md
    └── results.md
```

---

## Relationship to other projects

| Project | Connection |
|---------|-----------|
| p1 | p1 deploys the serving pipeline. p10 produces better weights (segmentation) that could replace TIAToolbox in p1. |
| p8 | All p10 training runs logged in p8 registry. Dice scores become evaluation entries. Grand Challenge result recorded. |
| p6/p7 | Same domain (breast pathology, PubMed/UniProt data). Demonstrates full AI stack: literature retrieval (p6) → knowledge graph (p9) → model training (p10) → serving (p1). |

---

## Out of scope

- Instance segmentation (nuclei, gland boundaries)
- WSI inference at 40× magnification
- Multi-task learning (classification + segmentation simultaneously)
- Real-time inference (batch offline inference is sufficient)
- Full clinical validation under MDR (research/benchmarking scope only — see `docs/security.md`)
