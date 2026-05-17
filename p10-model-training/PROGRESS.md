# Project 10 — Model Training & Benchmarking
## Progress Tracker
*Last updated: 2026-05-17*

---

## Goal

Train and publicly benchmark a semantic segmentation model for the BEETLE challenge
(multiclass H&E breast cancer WSI segmentation). Produces model weights that feed
into p8 registry and potentially replace the TIAToolbox model in p1.

See [SPEC.md](SPEC.md) for full problem statement and system design.

---

## Steps

### Phase 1 — Data pipeline
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | Download BEETLE training data | ⬜ Todo | Register on Grand Challenge, download training set (587 cases, multi-scanner). |
| 2 | WSI tiling | ⬜ Todo | Extract 512×512 patches at 20× magnification. Store as HDF5 or flat PNG tiles. |
| 3 | Annotation masks | ⬜ Todo | Convert BEETLE pixel annotations to 4-class training masks (invasive epithelium, non-invasive epithelium, necrosis, other). |
| 4 | Stain normalisation | ⬜ Todo | Apply Macenko or Vahadane normalisation to handle multi-scanner variation. |
| 5 | Train/val split | ⬜ Todo | Split respecting site and scanner distribution — random split would leak scanner-specific staining into both sets. |

### Phase 2 — Baseline model
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 6 | Architecture | ⬜ Todo | U-Net or DeepLabV3+ with ResNet-50 or EfficientNet-B4 encoder. ImageNet-pretrained. |
| 7 | Training loop | ⬜ Todo | Combined Dice + cross-entropy loss. fp16 via Accelerate. Early stopping on val Dice. |
| 8 | Validation metrics | ⬜ Todo | Per-class and overall Dice on val set. Log to p8 registry as experiment entry. |
| 9 | Augmentation | ⬜ Todo | Random flip/rotation + stain augmentation. Critical for multi-scanner generalisation. |

### Phase 3 — Foundation model iteration
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 10 | UNI encoder | ⬜ Todo | Swap ResNet encoder for UNI (ViT-L pretrained on 100k+ pathology slides). Expected: +2-5 Dice on hard classes. |
| 11 | CONCH encoder | ⬜ Todo | Try CONCH (contrastive vision-language model for pathology) as alternative. |
| 12 | Encoder comparison | ⬜ Todo | Compare per-class Dice: ImageNet vs UNI vs CONCH. Record all in p8 registry. |

### Phase 4 — WSI inference
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 13 | Sliding window inference | ⬜ Todo | Run patch-level model across full WSI at test time. Handle overlap and boundary artefacts. |
| 14 | Post-processing | ⬜ Todo | Smooth predictions, remove small isolated regions. |
| 15 | Full slide assembly | ⬜ Todo | Assemble patch predictions into WSI-level segmentation map. |

### Phase 5 — Grand Challenge submission
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 16 | Submission container | ⬜ Todo | Package inference code as Docker container per Grand Challenge requirements. |
| 17 | Submit to BEETLE | ⬜ Todo | Submit to leaderboard. Record result in p8 registry as evaluation entry. |
| 18 | Docs | ⬜ Todo | docs/how-it-works.md, docs/results.md with leaderboard score and per-class Dice. |

---

## Quick status

```
Phase 1  [░░░░░] 0/5 — Not started
Phase 2  [░░░░]  0/4 — Not started
Phase 3  [░░░]   0/3 — Not started
Phase 4  [░░░]   0/3 — Not started
Phase 5  [░░░]   0/3 — Not started
```
