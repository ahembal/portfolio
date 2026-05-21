# How It Works
*p10 — Model Training & Benchmarking*

---

## The problem this solves

p1 deploys a model that classifies 96×96 pixel patches of breast tissue as
tumour or normal. That is a useful starting point, but it is not how
pathologists actually work — they look at entire tissue sections and label
every region: where is the invasive tumour, where is ductal carcinoma in
situ, where is necrosis, where is stroma.

This project builds a model that does pixel-level labelling — semantic
segmentation — across full whole slide images (WSIs). The target is the BEETLE
challenge: multiclass segmentation of H&E breast cancer biopsies scanned on
seven different scanners across multiple clinical centres.

The concrete gap from p1:

| p1 | p10 |
|----|-----|
| 96×96 patch → 1 label | 512×512 patch → 512×512 label map |
| Binary (tumour / normal) | 4 classes (invasive, non-invasive, necrosis, other) |
| Single scanner | 7 scanners, multiple sites |
| No public leaderboard | BEETLE Grand Challenge leaderboard |

---

## What is a whole slide image

A WSI is a gigapixel image — a single slide scanned at 20× or 40× magnification
produces an image that is typically 50,000×70,000 pixels or larger. That is
3.5 billion pixels for one slide.

No GPU can process that directly. The standard approach is patch-based:

```
Full WSI (50k × 70k px)
    │
    ▼ tile at 512×512 with stride 512
Patches (each 512×512 px)
    │
    ▼ model predicts class for every pixel in the patch
Patch segmentation maps (512×512 uint8)
    │
    ▼ reassemble at inference time
Full slide segmentation map
```

Training uses patches. Inference assembles predictions back into the full slide.
The slide never touches GPU memory as a whole.

---

## The BEETLE challenge

**Task:** Given an H&E breast biopsy WSI, produce a pixel-level segmentation
map with four classes:

| Class index | Name | Description |
|-------------|------|-------------|
| 0 | Other | Stroma, fat, background, normal tissue |
| 1 | Invasive epithelium | Invasive tumour |
| 2 | Non-invasive epithelium | DCIS and similar |
| 3 | Necrosis | Necrotic tissue |

**Metric:** Overall Dice coefficient, averaged across classes.

**Submission:** An inference Docker container submitted to Grand Challenge.
The container receives a WSI as input, writes a segmentation mask as output,
and is scored against sequestered test annotations on Grand Challenge's
infrastructure. Training is done locally; only inference is run by GC.

---

## System architecture

```
Grand Challenge
  ├── Training WSIs + masks (downloaded once)
  └── Sequestered test set (never seen; GC runs inference on it)

Local / Dardel cluster
  ├── data/pipeline.py          ← Phase 1: tile, normalise, split
  │   ├── data/tile.py          ← WSI → 512×512 PNG patches
  │   ├── data/masks.py         ← annotation → 4-class uint8 masks
  │   ├── data/normalise.py     ← Macenko stain normalisation
  │   └── data/split.py        ← train/val split by scanner+site
  │
  ├── data/tiles/               ← output: images/ + masks/ + manifest.csv
  │
  ├── src/dataset.py            ← PyTorch Dataset + albumentations augmentation
  ├── src/model.py              ← U-Net / DeepLabV3+ architecture
  ├── src/train.py              ← training loop (Accelerate, fp16)
  └── src/evaluate.py           ← per-class + overall Dice on val set
  │
  └── p8 model registry         ← every run logged with Dice scores + weights

Grand Challenge submission
  └── submission/Dockerfile     ← packages model + src/infer.py
                                   GC runs this against the test WSIs
```

---

## Phase 1 — Data pipeline

### WSI tiling (`data/tile.py`)

Each WSI is opened with TIAToolbox's `WSIReader`, which handles the common
formats transparently (SVS, TIFF, NDPI, MRXS). Patches are extracted at 20×
magnification (the standard clinical viewing magnification for H&E assessment).

Not every 512×512 region contains useful tissue — slides have large white
background areas where no biopsy material was placed. Extracting those wastes
storage and training compute on uninformative patches.

Tissue detection uses Otsu thresholding on a low-resolution thumbnail (8 µm/px):
the thumbnail is fast to compute, Otsu needs no parameters, and H&E slides have
a clear bimodal histogram (stained tissue is dark, background is near-white).
Patches where less than 50% of pixels fall on tissue are skipped.

### Annotation handling (`data/masks.py`)

BEETLE provides pixel-level annotations. Two formats are supported:

**TIFF/PNG masks** — pixel value = class index (0–3). This is the most common
format for Grand Challenge segmentation challenges and the simplest to load.

**GeoJSON** — polygon annotations with a class property per feature. Some
challenges deliver annotations this way from annotation tools like QuPath. The
GeoJSON rasteriser uses OpenCV's `fillPoly` to paint each polygon onto an
initially blank mask, drawing in ascending class order so higher-priority
classes (necrosis, invasive epithelium) overwrite lower-priority background.

### Stain normalisation (`data/normalise.py`)

H&E staining varies by lab, reagent batch, and scanner. A model trained on
slides from one scanner will systematically fail on slides from a different
scanner — not because the tissue morphology has changed, but because the colour
statistics have.

Macenko normalisation (the default) fits a reference colour basis from a
representative slide and maps each new image into that colour space. It works
by SVD decomposition of the stain matrix, which makes it more robust than
histogram matching.

The normaliser is fitted once on a user-specified reference slide and applied
to every patch at tile-extraction time. This is a one-time cost — the
normalised tiles are stored as PNGs and reused across training runs.

A second line of defence operates at training time: `HueSaturationValue`
augmentation in `src/dataset.py` randomly perturbs colour, simulating residual
staining variation that Macenko does not fully eliminate.

### Train/val split (`data/split.py`)

A random tile-level split would leak information: if slide A is in both train
and val (some patches train, some patches val), the model has seen the tissue
morphology and colour profile of slide A during training. Val Dice would be
optimistic.

Two levels of grouping are enforced:

1. **Slide-level grouping** — all tiles from one WSI go to the same split.
   `GroupShuffleSplit` from scikit-learn handles this by treating each `wsi_id`
   as a group.

2. **Scanner/site stratification** — if a metadata CSV with scanner and site
   columns is provided, groups are defined as (scanner, site) pairs. This
   ensures the val set contains slides from multiple scanners, measuring
   generalisation rather than within-scanner performance.

---

## Phase 2 — Model training

The training loop (`src/train.py`) uses HuggingFace Accelerate for fp16
mixed-precision training. Accelerate handles device placement and gradient
scaling transparently — the same script runs on a single GPU (local) or
multi-GPU (Dardel A100 nodes) without code changes.

**Architecture:** U-Net with a ResNet-50 encoder (ImageNet-pretrained) via
`segmentation-models-pytorch`. The encoder is the part of the network that
extracts features; the decoder upsamples those features back to the input
resolution and predicts class probabilities per pixel.

**Loss:** Dice loss + cross-entropy, weighted equally. Cross-entropy penalises
confident wrong predictions; Dice loss directly optimises the metric used for
evaluation. Using both prevents the model from hedging on uncertain pixels
(pure cross-entropy) while also learning from the pixel-level class distribution
(pure Dice ignores class balance).

**Augmentation:** Applied at the PyTorch Dataset level (not pre-computed):
random flip, rotation, transpose, stain jitter, brightness/contrast, Gaussian
blur. See `src/dataset.py` for the full albumentations pipeline.

---

## Phase 3 — Foundation model encoders

After the baseline, the ResNet-50 encoder is swapped for a pathology-specific
foundation model:

**UNI** — a ViT-L pretrained on 100,000+ pathology slides (Harvard MIL group).
It encodes tissue morphology from training data that covers the full diversity
of H&E staining, scanner types, and tissue origins. Expected improvement over
ImageNet-pretrained ResNet: +2–5 Dice points on hard classes (necrosis, DCIS).

**CONCH** — a contrastive vision-language model for pathology. Trained to align
image patches with pathology text descriptions. Potentially better at rare
classes where morphological features can be described textually.

Both are drop-in replacements for the encoder in `src/model.py`. Everything
else — loss, augmentation, training loop, evaluation — stays the same. See
`docs/model-options.md` for a detailed comparison.

---

## Phase 4 — WSI inference

At test time, `src/infer.py` runs a sliding window across the full WSI and
assembles patch predictions into a slide-level segmentation map. Patches
overlap by 50% (stride = patch_size / 2) and predictions in overlapping regions
are averaged to reduce boundary artefacts.

The assembled map is saved as a multi-class PNG mask where pixel value = class
index — the format expected by Grand Challenge.

---

## Phase 5 — Grand Challenge submission

The submission container (`submission/Dockerfile`) packages:
- The trained model weights
- `src/infer.py`
- All inference dependencies

Grand Challenge provides the test WSIs at a fixed input path, runs the
container, reads the output mask from a fixed output path, and scores it
against the sequestered annotations. The training pipeline never runs inside
the container — only inference.

This separation means training compute (Dardel GPU nodes) and submission
compute (GC's AWS instances) are fully independent. A failed submission does
not require retraining.

---

## Relationship to the rest of the portfolio

| Project | Connection |
|---------|-----------|
| p1 | p1 deploys a pathology model for serving. p10 produces better weights (segmentation, not just classification) that could replace p1's TIAToolbox model. |
| p8 | Every p10 training run is logged as an experiment in the p8 model registry — hyperparameters, architecture, per-class Dice, weight SHA. |
| p6 / p7 | Shares the PubMed/UniProt data infrastructure; demonstrates the full ML spectrum from data retrieval (p6) to serving (p1) via a reproducible training pipeline (p10). |
