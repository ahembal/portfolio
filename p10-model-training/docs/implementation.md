# Implementation Notes
*p10 — Model Training & Benchmarking*

This document explains how each part was built: structure choices, anticipated
problems, and decisions made along the way. For how the finished system works
see `how-it-works.md`. For model architecture comparisons see `model-options.md`.

---

## data/tile.py

### Tissue detection via Otsu thresholding

The tissue mask is computed at a very low resolution (8 µm/px thumbnail) and
then used to filter tiles extracted at 20× (0.5 µm/px). The resolution
mismatch means the tissue fraction estimate is approximate — a tile might be
20% tissue according to the thumbnail but 35% in reality. The threshold (50%
by default) is conservative enough that this approximation does not cause
problems in practice.

An alternative is to compute the tissue mask at full resolution and sample it
for each tile. That is more accurate but much slower — the thumbnail approach
gives a 1000× speedup with negligible accuracy loss.

**Why Otsu:** H&E slides have a strong bimodal intensity histogram —
haematoxylin/eosin staining produces dark-stained nuclei and eosinophilic
cytoplasm against a near-white glass background. Otsu's threshold reliably
separates the two modes without needing a hand-tuned value. It fails on very
pale or over-stained slides, but these are rare in a controlled dataset like
BEETLE.

### Coordinate spaces

WSIs have multiple coordinate spaces depending on the magnification level.
TIAToolbox's `read_rect` accepts `coord_space="resolution"` — this means
the location and size are specified in pixels at the target resolution (20×),
not at the base level. This is simpler to reason about than converting
coordinates manually between levels.

The annotation mask is resized to the same pixel dimensions as the WSI at 20×
before tiling, using `Image.NEAREST` (no interpolation — class indices must not
be blurred into intermediate values).

### Why PNG, not HDF5

HDF5 gives faster random access for large datasets because tiles are read via
seek operations rather than file system traversal. For a dataset that fits on
a fast SSD or parallel filesystem (Dardel's Lustre), PNG + a CSV manifest is
simpler to inspect, easier to debug, and avoids HDF5's file locking issues with
PyTorch's multi-process DataLoader workers.

If the dataset is on slow NFS storage and DataLoader I/O becomes the training
bottleneck, converting to HDF5 is a meaningful optimisation.

---

## data/masks.py

### GeoJSON rasterisation draw order

Polygons are drawn in ascending class index order (other=0 first, necrosis=3
last). This means a necrosis polygon that overlaps a stromal region will
correctly overwrite the stroma. If drawn in arbitrary order, the result would
depend on the annotation order in the file.

This assumes class indices are assigned in order of specificity — background
first, specific pathological classes last. That matches BEETLE's class scheme.

### RGB mask handling

Some annotation tools export masks as palette-mode PNG where the palette maps
a colour to a class index. When PIL opens these as `mode="P"`, `convert("L")`
gives the palette index, not the RGB value — which is exactly what we want.

For `mode="RGB"` masks (less common), only the red channel is read. This assumes
the mask was created with class index in R, G, B all equal (greyscale-as-RGB)
or in R only. A warning is logged. If the actual encoding is different (e.g.
specific RGB colours per class), the masks.py needs to be extended with a
colour-to-class lookup table.

---

## data/normalise.py

### Why fit on a thumbnail, not the full slide

Fitting Macenko or Vahadane on a full WSI at 20× would require loading gigabytes
of image data. The stain matrix is estimated from a sample of pixels — a 512×512
thumbnail at 20× provides more than enough pixels (262,144) to estimate the
two-component haematoxylin/eosin stain basis reliably.

### Failure modes

Stain normalisation fails on:
- Patches that are mostly background (no stain signal to decompose)
- Patches with unusual tissue types (calcifications, mucin) that do not fit
  the two-component H&E model

The `apply()` function catches all exceptions and returns the unnormalised patch.
This is intentional — a training set with a small number of unnormalised patches
is better than a training set with missing patches.

---

## data/split.py

### GroupShuffleSplit, not StratifiedGroupKFold

`GroupShuffleSplit` assigns each group (WSI) to exactly one split and shuffles
the assignment. It does not guarantee that the fraction of each (scanner, site)
combination in val is exactly `val_fraction` — some groups may be over- or
under-represented.

`StratifiedGroupKFold` would give more even stratification but requires the
dataset to have enough groups per stratum. With 587 slides across ~7 scanners
and ~20 sites, some (scanner, site) combinations have only 2–3 slides.
`StratifiedGroupKFold` fails when a stratum has fewer groups than the number
of folds.

`GroupShuffleSplit` handles this gracefully — it treats the full set of groups
as the population and assigns them without per-stratum constraints.

### What "slide-level grouping" prevents

If tile 001 of slide A is in train and tile 002 of slide A is in val, the model
has seen the H&E colour profile, morphological features, and annotation style
of slide A during training. The val Dice score measures in-distribution
performance on that slide, not generalisation.

The `GroupShuffleSplit` groups by `wsi_id` — all tiles from one slide go to
the same split. This is the minimum requirement for a valid val set.

---

## src/dataset.py

### Albumentations target type for masks

Albumentations treats `mask` as a 2D integer array by default. The `ToTensorV2`
transform converts it to a `torch.LongTensor` (int64) — the type expected by
PyTorch's cross-entropy and Dice loss functions. The image becomes a float32
tensor normalised to ImageNet statistics.

The mask is loaded as `dtype=np.int64` explicitly — if loaded as uint8 and
converted later, values are correct (class indices 0–3 fit in uint8), but the
explicit dtype makes the intent clear.

### HueSaturationValue limits

`hue_shift_limit=10, sat_shift_limit=20, val_shift_limit=10` are conservative
values relative to what albumentations allows. Too-aggressive colour jitter
causes the model to become insensitive to staining differences that are actually
diagnostically meaningful (e.g. eosin intensity correlates with cytoplasmic
maturity). The values chosen are typical for pathology augmentation in the
literature.

`GaussianBlur(blur_limit=(3, 5))` is applied at p=0.2 — low probability because
nuclear detail is important for segmentation and excessive blur harms that.

### Why not random crop

The patch size (512×512) is fixed at tile-extraction time, not at training time.
Random cropping during training (e.g. extracting 256×256 subregions from 512×512
tiles) would give more augmentation diversity at the cost of losing spatial
context.

For a 512×512 patch at 20×, the field of view is 256 µm × 256 µm — enough to
see gland architecture, tumour nests, and stromal context. Cropping to 256×256
would halve this to 128 µm × 128 µm, which is borderline for gland-level
structural assessment.

---

## configs/baseline.yaml

### Why a YAML config and not argparse

Every hyperparameter is in one file. A training run is reproducible by keeping
that config alongside the checkpoint. The p8 registry stores the config as part
of each experiment entry — a future run can be reproduced by restoring the
config, not by remembering 15 command-line arguments.

`argparse` for hyperparameters means reproducibility requires either shell
history or a wrapper script. Neither is as reliable as a committed YAML.

### val_fraction: 0.2

20% of 587 slides = ~117 val slides. With an average of ~300 tiles per slide
(depends on tissue coverage), the val set contains ~35,000 tiles. This is
enough for stable Dice estimation. A smaller val fraction would give more
training data but noisier val metrics; a larger fraction wastes training data
on a stat problem that is already well-determined at 35k tiles.

---

## Accelerate integration (src/train.py — to be written)

HuggingFace Accelerate wraps the training loop to handle:
- Mixed precision (fp16 / bf16): `accelerate.autocast()` wraps the forward pass;
  GradScaler handles gradient overflow for fp16
- Multi-GPU: `accelerator.prepare(model, optimiser, train_loader)` distributes
  across GPUs without changes to the training loop logic
- Device placement: all `.to(device)` calls are removed; Accelerate places
  tensors on the correct device

On Dardel, the same script runs on one A100 (for debugging) or four A100s
(for production training) without code changes — only the Accelerate config
(set via `accelerate config` or `accelerate launch`) changes.

---

## Relationship between modules

```
configs/baseline.yaml
    │
    ├── data/pipeline.py  ←  reads config, orchestrates
    │       ├── data/tile.py
    │       ├── data/masks.py
    │       ├── data/normalise.py
    │       └── data/split.py
    │
    └── src/train.py  ←  reads config, trains model
            ├── src/dataset.py   ←  reads manifest.csv from tiles_dir
            ├── src/model.py     ←  architecture
            └── src/evaluate.py  ←  Dice computation
```

The only shared state between the data pipeline and training is
`data/tiles/manifest.csv` and the tiles on disk. There is no runtime
coupling — pipeline runs once, training reads the output.
