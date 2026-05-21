# Data Pipeline — Design Decisions
*p10 — Model Training & Benchmarking*

This document explains every significant decision in the data pipeline —
why this magnification, why this patch size, why Macenko over Vahadane, and
what each choice costs if you change it.

---

## Why 20×, not 40×

20× (0.5 µm/px) is the standard magnification for H&E tissue assessment. At
20×, cell nuclei are clearly resolved (~10–15 µm diameter = 20–30 pixels),
gland architecture is visible, and the field of view per patch is large enough
to capture tissue context.

40× doubles the resolution but halves the field of view. A 512×512 patch at
40× covers 128 µm × 128 µm — about 3–4 small glands. At 20×, the same patch
covers 256 µm × 256 µm — enough to see a gland in context of surrounding
stroma, which is what distinguishes invasive epithelium from non-invasive.

40× also quadruples the tile count (same tissue area = 4× the patches), which
quadruples storage and compute. For the classes in BEETLE, 20× provides the
right balance of resolution and context.

**If you need to switch to 40×:** change `magnification: 40` in `baseline.yaml`.
The pipeline handles the coordinate maths automatically. Expect 4× more tiles
and ~4× more training time per epoch. Reduce batch size or patch size to stay
within GPU memory.

---

## Why 512×512, not 256×256 or 1024×1024

**256×256 at 20×:** 128 µm field of view. Sufficient to see individual cells
but marginal for gland architecture. Would double the tile count compared to
512×512.

**512×512 at 20×:** 256 µm field of view. Can resolve gland structure, tumour
nests, and surrounding stroma simultaneously. Standard in the pathology
segmentation literature.

**1024×1024 at 20×:** 512 µm field of view. Better context, but most encoder
architectures (ResNet, ViT) were designed for 224×224 or 512×512 inputs.
A 1024×1024 input to a ViT-L with 16×16 tokens gives 4096 tokens — 16×
more than the pretraining input. Attention computation scales quadratically with
token count. Memory cost is prohibitive on a single GPU.

512×512 is the correct default. If context problems appear in the results (e.g.
the model misclassifies DCIS because it cannot see enough duct structure), the
right fix is to add multi-scale inference at test time, not to increase the
patch size.

---

## Why Macenko, not Vahadane

Both Macenko and Vahadane estimate the haematoxylin and eosin stain basis from
image statistics. The difference is in how they find the stain basis:

**Macenko** uses SVD (singular value decomposition) on the optical density
matrix. Fast and deterministic — same image, same result every time.

**Vahadane** uses SNMF (sparse non-negative matrix factorization) to find a
sparser representation of the stain basis. More accurate when the two stains
are not well separated, but significantly slower (~10–50× slower per image).

For a dataset of 587 WSIs at 20× with 512×512 tiles, Macenko processes a tile
in ~10ms; Vahadane takes ~200ms. At 300 tiles per slide, normalising all tiles
for a single WSI takes 3s (Macenko) vs 60s (Vahadane). Across 587 slides:
~30 minutes vs ~10 hours.

BEETLE's dataset spans 7 scanners but all are clinical H&E scanners with
reasonably clean stain separation. Macenko is sufficient. If normalisation
quality is visually poor on specific slides, switching to Vahadane for those
slides specifically (using the `apply()` function directly) is an option
without reprocessing the full dataset.

---

## Why normalise at tile-extraction time, not at training time

Two strategies:
1. **Pre-compute:** normalise during tiling, store normalised PNGs
2. **On-the-fly:** normalise each tile when the DataLoader loads it

Pre-computation is faster at training time — normalisation runs once, not once
per epoch. On a 300k-tile dataset trained for 50 epochs, that is 300k
normalisations vs 15 million. The cost of pre-computation (disk space for
normalised tiles) is modest (~50 GB for 300k tiles at 512×512).

On-the-fly normalisation allows the reference target to be changed without
re-running the pipeline, and avoids committing to one normalisation during
data preparation. It is better if you want to experiment with different
reference slides.

**The choice here is pre-computation.** The pipeline is run once after data
download and the normalised tiles are stored. Re-running is cheap (one
`python data/pipeline.py` invocation). Separating data preparation from
training is cleaner operationally — the training script does not depend on
a normaliser being available.

The dual defence (pre-computed Macenko + HueSaturationValue augmentation) is
deliberate: Macenko handles systematic scanner-level differences, while stain
jitter handles residual variation that Macenko leaves behind.

---

## Tissue detection threshold (50%)

A patch is kept if at least 50% of its pixels fall on tissue in the
low-resolution tissue mask. This threshold removes:
- Pure background patches (glass, slide edges)
- Patches at tissue boundaries where mostly background

At 50%, a patch that is half tissue is included. This is intentional —
boundary patches contain edge effects that the model should learn: where tissue
ends is as diagnostic as where it begins.

**What if the threshold is too aggressive:** slides with sparse tissue
(needle biopsies with narrow cores) may lose many valid patches. Lower to 0.3.

**What if too lenient:** background patches inflate the training set with
uninformative data and slow down training. Raise to 0.7.

The threshold is configurable in `baseline.yaml` (`min_tissue_fraction`).

---

## Train/val split — why scanner+site stratification matters

BEETLE has slides from multiple clinical centres scanned on seven different
scanners. Staining protocols, scanner optics, and preprocessing differ across
sites. A model evaluated only on slides from scanners it has already seen
during training will have inflated Dice scores.

The correct question is: **does the model generalise to a new scanner?**

To answer this, the val set must contain slides from scanner+site combinations
that are distinct from those in the training set — or at minimum, a
representative sample of each combination.

`GroupShuffleSplit` with `groups = (scanner, site)` pairs ensures each WSI goes
to one split and that the split assignment is informed by scanner+site group
identity. This does not guarantee zero scanner overlap between train and val
(the dataset may not be large enough for that), but it ensures that each
scanner+site combination contributes slides to both splits.

**If scanner/site metadata is unavailable:** the split falls back to random
slide-level assignment. Results are still valid (no tile leakage) but may be
optimistic if the val set happens to draw only from well-represented scanners.
Providing a `metadata.csv` with `wsi_id, scanner, site` columns is strongly
recommended.

---

## Annotation format — TIFF mask vs GeoJSON

BEETLE delivers pixel-level annotations. The most likely format is TIFF mask
images where pixel value = class index (0–3), matching the output format the
challenge expects for submission.

GeoJSON is supported as a second format for challenges where annotations are
produced by tools like QuPath or ASAP, which export polygon outlines rather
than rasterised masks. The rasterisation step (masks.py) uses OpenCV fillPoly
to convert polygons to pixel masks.

When the data is downloaded, verify the format by inspecting one annotation
file. Set `annotation_format: mask` or `annotation_format: geojson` in
`baseline.yaml` accordingly. Do not assume the format from the filename
extension alone — `.tiff` files from some tools contain colour-encoded class
labels, not single-channel index masks (see `docs/implementation.md` for
the RGB mask handling).

---

## Storage requirements (estimates)

| Item | Count | Size/item | Total |
|------|-------|-----------|-------|
| Raw BEETLE WSIs | 587 | 1–3 GB | ~1.2 TB |
| Annotation masks | 587 | 50–500 MB | ~100 GB |
| Tiles (512×512 PNG, 20×) | ~300k | 300 KB | ~90 GB |
| Manifest CSV | 1 | 50 MB | 50 MB |

Total: ~1.4 TB. Plan Dardel scratch allocation accordingly. NOBACKUP partition
has no quota but data is deleted after 30 days of inactivity — keep the raw
WSIs on a longer-lived location or re-download from Grand Challenge if needed.

The tiles are the working dataset used for training — they are derived from the
raw WSIs and can be regenerated. If scratch is tight, keep only the tiles and
delete the raw WSIs after tiling is verified.
