# Model Limitations — PCam Classifier
*Last updated: 2026-05-04*

Known failure modes, edge cases, and behavioural limitations of the ResNet-18
model trained on PatchCamelyon. These are observed in practice, not theoretical.

---

## 1. Out-of-distribution inputs produce overconfident predictions

**Observed:** When fed tissue images from a different organ or staining protocol
(e.g. colorectal tissue instead of breast lymph node tissue), the model returns
predictions with very high confidence (e.g. 100% normal) rather than indicating
uncertainty.

**Root cause:** Neural networks with sigmoid output can produce extreme logit
values (very positive or very negative) for inputs far from the training
distribution. Sigmoid maps these to probabilities near 0 or 1 — the model
appears certain even when it has no basis for a reliable prediction.

**Why this matters:** A clinician or downstream system receiving a 100% confidence
score has no signal that the input was out-of-distribution. The model cannot
distinguish between "I am very confident this is normal tissue" and "this input
looks nothing like my training data."

**Mitigation strategies (not implemented in v1):**
- Monte Carlo Dropout: run inference N times with dropout active, use variance
  as an uncertainty estimate
- Temperature scaling: calibrate logit outputs post-hoc to produce better-calibrated
  probabilities
- Out-of-distribution detection: train a separate classifier to flag inputs that
  are unlike the training distribution before passing to the main model
- Input validation: check that input images match expected staining characteristics
  (H&E, 96×96 lymph node patches) before inference

---

## 2. Model is specific to breast lymph node tissue at 96×96 resolution

**Training data:** PatchCamelyon — 96×96 pixel patches from H&E-stained breast
lymph node whole-slide images from the Camelyon16 dataset.

**What this means in practice:**
- Input must be exactly 96×96 pixels (enforced by the preprocessing pipeline)
- The model has not seen colorectal, lung, liver, or other tissue types
- Different staining protocols (IHC, PAS, etc.) will produce unreliable results
- Whole-slide image analysis requires tiling — the model classifies individual
  patches, not full slides

---

## 3. Confidence ≠ calibrated probability

**Observed:** The model's confidence scores are not calibrated probabilities.
A score of 0.91 does not mean "91% of patches with this score are tumour."

**Root cause:** The model was trained with BCEWithLogitsLoss without post-hoc
calibration. Calibration (e.g. Platt scaling, temperature scaling) was not
applied after training.

**Impact:** Threshold selection matters more than the raw confidence value.
The training pipeline produced two thresholds (see `artifacts/threshold.json`):
- Youden threshold (0.37): maximises sensitivity + specificity balance
- 95% sensitivity threshold (0.20): maximises sensitivity at the cost of specificity

The serving API uses 0.5 by default — not the optimal threshold.

---

## 4. Single-patch classification ignores spatial context

**Limitation:** The model classifies one 96×96 patch at a time. It has no
information about neighbouring patches or the broader tissue architecture.

**Clinical context:** In practice, pathologists consider spatial patterns —
the arrangement of cells relative to each other and to tissue boundaries.
A single-patch classifier cannot replicate this reasoning.

---

## 5. Demo images are out-of-distribution

**Note:** The sample images bundled with the Streamlit demo (`streamlit/demo/`)
are from PathMNIST (colorectal tissue sections), not from PatchCamelyon (breast
lymph node tissue). They are present only to demonstrate the UI and API pipeline.
Predictions on these images are unreliable and should not be interpreted as
model performance on real clinical data.

For meaningful predictions, use actual 96×96 breast lymph node patches from the
PatchCamelyon dataset or a compatible source.
