# Experiment Results
*p10 — Model Training & Benchmarking*

---

## BEETLE leaderboard

| Submission | Encoder | Architecture | Overall Dice | Rank | Date |
|------------|---------|-------------|-------------|------|------|
| — | — | — | — | — | — |

*Top score on BEETLE leaderboard as of May 2026: 0.9018.*

---

## Validation results (local, per run)

All runs are logged in the p8 model registry. Dice scores below are
per-class on the held-out val set (20% of training slides, stratified by
scanner and site — see `docs/how-it-works.md` for split details).

| Run | Encoder | Arch | Inv. Epith. | Non-inv. Epith. | Necrosis | Other | Overall | Val loss |
|-----|---------|------|------------|----------------|----------|-------|---------|----------|
| — | — | — | — | — | — | — | — | — |

---

## Class difficulty

Based on published BEETLE baseline results and general pathology segmentation
literature, expected difficulty ordering (hardest first):

1. **Necrosis** — morphologically variable; can resemble stromal tissue or
   ghost cells. Rare relative to other classes, so models see fewer examples.

2. **Non-invasive epithelium (DCIS)** — requires recognising gland architecture
   within a duct rather than individual cells. Context-dependent.

3. **Invasive epithelium** — visually distinctive (sheets of pleomorphic cells,
   desmoplastic stroma). Most models learn this class reliably.

4. **Other** — dominant class by area. High recall but precision errors at
   class boundaries are common.

---

## CLAIM 2024 checklist

CLAIM (Checklist for AI in Medical Imaging) is the reporting standard for
medical imaging AI publications. Key items applicable to p10:

| Item | Status | Notes |
|------|--------|-------|
| Dataset description | ⬜ | Add after downloading — number of slides per scanner/site |
| Train/val/test split | ✅ | GroupShuffleSplit by scanner+site; slide-level groups |
| Preprocessing steps | ✅ | Documented in `docs/how-it-works.md` and `data/` modules |
| Architecture description | ✅ | `docs/model-options.md` |
| Loss function | ✅ | Dice + cross-entropy, weights in `configs/baseline.yaml` |
| Augmentation | ✅ | `src/dataset.py` — full albumentations pipeline |
| Evaluation metric | ✅ | Overall Dice (BEETLE challenge metric) |
| Per-class metrics | ⬜ | To be filled after first training run |
| Statistical uncertainty | ⬜ | Report mean ± std across 3 seeds |
| Calibration | ⬜ | Expected confidence vs. actual accuracy |
| Subgroup analysis | ⬜ | Per-scanner Dice — critical for multi-scanner generalisation claim |
| Failure modes | ⬜ | Qualitative examples of systematic errors |
| Leaderboard score | ⬜ | After Grand Challenge submission |

*CLAIM 2024 reference: Mongan et al., Radiology: AI, 2020 (updated 2024).*

---

## How to reproduce a training run

```bash
# 1. Prepare data (once)
python data/pipeline.py --config configs/baseline.yaml --metadata data/raw/metadata.csv

# 2. Train
python src/train.py --config configs/baseline.yaml

# 3. Evaluate on val set
python src/evaluate.py --config configs/baseline.yaml --checkpoint runs/<run_id>/best.pt

# 4. Results are written to runs/<run_id>/metrics.json
#    and logged to the p8 registry automatically.
```

All hyperparameters, architecture choice, and paths are in
`configs/baseline.yaml`. To reproduce a specific run, restore that run's
config from the p8 registry entry.
