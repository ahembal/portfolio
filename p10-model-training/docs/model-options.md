# Model Options
*p10 — Model Training & Benchmarking*

---

## Overview

Three encoder options are evaluated in p10, in order of complexity:

| Encoder | Pretraining data | Parameters | Expected Dice |
|---------|-----------------|------------|---------------|
| ResNet-50 | ImageNet (natural images) | 25M | Baseline |
| UNI (ViT-L) | 100k+ pathology slides | 307M | Baseline + 2–5 pts |
| CONCH (ViT-B) | Pathology image-text pairs | 86M | TBD |

All three are used as encoders in the same U-Net decoder architecture. The
decoder, loss function, augmentation pipeline, and training procedure are
identical — only the encoder changes. This makes results directly comparable.

---

## Architecture — U-Net with swappable encoder

```
Input patch (512×512×3)
        │
        ▼
Encoder (ResNet-50 / UNI / CONCH)
  Extracts hierarchical features at multiple scales:
  ├── scale 1/4:  128×128×256  (fine spatial detail)
  ├── scale 1/8:  64×64×512
  ├── scale 1/16: 32×32×1024
  └── scale 1/32: 16×16×2048  (semantic content)
        │
        ▼
U-Net decoder (skip connections from each encoder scale)
  Progressively upsamples back to input resolution:
  ├── 32×32 → 64×64
  ├── 64×64 → 128×128
  └── 128×128 → 512×512
        │
        ▼
Segmentation head: 1×1 conv → 4 class channels
        │
        ▼
Output: (512×512×4) — per-pixel class logits
        │
        ▼ argmax
Predicted mask: (512×512) uint8, values 0–3
```

Skip connections carry fine-grained spatial information from early encoder
layers directly to the corresponding decoder layers. Without them, the decoder
would have to reconstruct spatial detail from the heavily compressed bottleneck,
losing edge sharpness.

---

## Encoder option 1 — ResNet-50 (baseline)

**Pretraining:** ImageNet-1k (1.2M natural images, 1000 classes).

**Why start here:**
- Standard reference point for all downstream comparison
- Fast to train — no access restrictions, no large model download
- Establishes a Dice baseline before committing GPU time to foundation models
- If the baseline already achieves competitive results, the complexity of
  switching encoders is not justified

**Limitations:**
- ImageNet contains no pathology images. The encoder has learned to recognise
  dogs, cars, and textures — not nuclei, gland structures, or necrotic tissue.
  The features it extracts are generic; the decoder has to compensate.
- Multi-scanner generalisation relies entirely on augmentation and Macenko
  normalisation. There is no prior about staining variability in the weights.

**When to use:**
Always train the baseline first. Use it to validate the data pipeline,
training loop, and evaluation code before investing compute in foundation models.

---

## Encoder option 2 — UNI (ViT-L)

**Pretraining:** Masked image modelling (DINOv2) on 100,000+ pathology slides
from the Mass General Brigham pathology archive (Harvard MIL). The training
data covers a wide range of tissue types, staining protocols, and scanners.

**Architecture:** Vision Transformer Large (ViT-L/16). Patches are 16×16
pixel tokens; the transformer attends globally across all tokens in a patch,
unlike ResNet's local convolutions. This means UNI can relate distant regions
of the image — relevant for tissue structures that are defined by their
relationship to surrounding context.

**Why this matters for BEETLE:**
- UNI has seen H&E slides during pretraining. Its features encode genuine
  tissue morphology — nuclear pleomorphism, gland architecture, stromal
  density — rather than natural image textures.
- Training data includes multi-scanner slides. The encoder has implicit
  robustness to staining variation built into its weights.
- The ViT attention mechanism captures long-range spatial context: a 512×512
  patch of invasive carcinoma is identifiable partly by the surrounding
  desmoplastic stroma, not just the tumour cells themselves.

**Expected improvement:** +2–5 Dice points on hard classes (necrosis,
non-invasive epithelium) where morphological context matters most. Invasive
epithelium is visually distinctive enough that ImageNet features often suffice.

**Access:** UNI weights require a HuggingFace gated model agreement (academic
use, non-commercial). Apply at `hf.co/MahmoodLab/UNI`.

**Compute:** ViT-L is ~12× larger than ResNet-50. On a single A100 (40GB),
batch size needs to be reduced to 8 from 16. Gradient checkpointing is
recommended.

---

## Encoder option 3 — CONCH (ViT-B)

**Pretraining:** Contrastive language-image pretraining (CLIP-style) on
pathology image-text pairs — WSI patches paired with diagnostic text from
pathology reports and educational material. Also from Harvard MIL.

**Why this is different from UNI:**
UNI learns from images only (masked image modelling). CONCH learns from
image-text pairs — the encoder is trained to align tissue appearance with
the natural language descriptions used by pathologists.

This gives CONCH different strengths:
- Rare or ambiguous classes may benefit from the textual grounding. A region
  that is visually similar to two classes might be separated by CONCH if those
  classes are described differently in pathology text.
- CONCH features are more aligned with how pathologists verbalise their
  observations, which may help the decoder when labels were created by
  pathologists using text-based criteria.

**When to use CONCH vs UNI:**
Start with UNI — it has more parameters and pure-image pretraining is generally
better for dense prediction tasks (segmentation). Use CONCH as an alternative
if UNI does not improve over baseline on specific classes.

**Access:** Same gated HuggingFace agreement as UNI.
`hf.co/MahmoodLab/CONCH`

---

## Alternative architecture — DeepLabV3+

The config supports `architecture: deeplabv3plus` as an alternative to U-Net.

DeepLabV3+ uses atrous (dilated) convolutions in the encoder to capture
multi-scale context without reducing spatial resolution, and an Atrous Spatial
Pyramid Pooling (ASPP) module to aggregate features at multiple scales. It
was originally designed for natural image segmentation (Pascal VOC, Cityscapes)
but has been applied to pathology with competitive results.

**U-Net vs DeepLabV3+ for pathology:**

| Aspect | U-Net | DeepLabV3+ |
|--------|-------|-----------|
| Skip connections | Full encoder-decoder skip connections | Shallow decoder, fewer skips |
| Edge sharpness | High (fine skip connections) | Moderate |
| Computational cost | Higher decoder | Lower decoder |
| Foundation model compatibility | Any encoder | Any encoder |
| Pathology literature | Dominant standard | Less common |

U-Net is the standard in pathology segmentation and the right default. Switch
to DeepLabV3+ if U-Net overfits and a shallower decoder helps regularise.

---

## Loss function

**Dice loss + cross-entropy (equal weight, configurable):**

Cross-entropy treats each pixel independently — it maximises the log-probability
of the correct class at each location. It is sensitive to class imbalance because
the "other" class (stroma, background) dominates by area.

Dice loss directly optimises the Dice coefficient, the evaluation metric. It is
computed per class as:

```
Dice(class k) = 2 × |pred_k ∩ target_k| / (|pred_k| + |target_k|)
```

Dice loss is naturally normalised by class size, so it is insensitive to class
imbalance — a rare class (necrosis) contributes equally to the loss as a common
class (other).

Using both: cross-entropy provides stable gradients early in training when Dice
loss can be noisy; Dice loss keeps the optimisation aligned with the actual
metric being reported on the leaderboard.

---

## Configuration

Switch encoders and architectures in `configs/baseline.yaml`:

```yaml
model:
  architecture: unet           # unet | deeplabv3plus
  encoder: resnet50            # resnet50 | efficientnet-b4 | uni | conch
  num_classes: 4
  pretrained: true
```

Foundation model encoders (`uni`, `conch`) require the weights to be downloaded
and placed in the location specified in `src/model.py`. They cannot be
auto-downloaded from HuggingFace without authentication.
