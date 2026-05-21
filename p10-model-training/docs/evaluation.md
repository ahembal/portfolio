# Evaluation — Metrics and Validation
*p10 — Model Training & Benchmarking*

---

## The Dice coefficient

The Dice coefficient (also called F1 score for binary classification, or
Sørensen–Dice index) measures the overlap between a predicted segmentation mask
and the ground truth:

```
Dice(class k) = 2 × |pred_k ∩ target_k|
                ─────────────────────────
                 |pred_k| + |target_k|
```

Where `pred_k` is the set of pixels predicted as class k, and `target_k` is
the set of ground truth pixels for class k. The intersection counts pixels
correctly predicted as class k; the denominator is the total predicted + total
true pixels for class k.

- **Dice = 1.0** — perfect overlap, prediction exactly matches ground truth
- **Dice = 0.0** — no overlap at all
- **Dice = 0.5** — the prediction and ground truth are the same size but don't
  overlap at all (or one is empty and the other is not)

### Why Dice, not pixel accuracy

Pixel accuracy = (correctly classified pixels) / (total pixels). For BEETLE,
the "other" class (stroma, fat, background) dominates by area. A model that
predicts everything as "other" would achieve 60–70% pixel accuracy while
completely failing at the actual task.

Dice is computed per class and then averaged. A class that is 5% of the slide
by area contributes equally to the overall Dice score as a class that is 50% of
the slide. This makes Dice appropriate for class-imbalanced segmentation tasks.

### Why Dice, not IoU (Jaccard)

IoU = |pred ∩ target| / |pred ∪ target|

Dice and IoU are monotonically related:
```
Dice = 2 × IoU / (1 + IoU)
IoU = Dice / (2 − Dice)
```

They rank models in the same order. BEETLE uses Dice; IoU is more common in
computer vision challenges (COCO, Pascal VOC). Either is a valid choice — the
difference is scale (Dice values are higher than IoU for the same prediction).

---

## Per-class Dice interpretation

After each val epoch, `src/evaluate.py` reports:

| Metric | What it tells you |
|--------|------------------|
| `dice_invasive` | How well the model finds invasive tumour — usually the easiest class |
| `dice_non_invasive` | DCIS and similar — requires gland architecture context |
| `dice_necrosis` | Hardest class — rare, variable morphology |
| `dice_other` | Background/stroma — easy but large, errors are common at class boundaries |
| `dice_overall` | Mean of the four per-class Dice scores (BEETLE's official metric) |

Low `dice_necrosis` with high `dice_invasive` is the expected failure mode for
a baseline model. Foundation model encoders (UNI, CONCH) are expected to close
this gap because they encode morphological features relevant to necrosis
(ghost cell patterns, karyorrhexis, absence of nuclear staining detail).

---

## Confusion between classes

The most common confusion pairs in H&E breast segmentation:
- Non-invasive epithelium ↔ invasive epithelium — both are epithelial cells;
  the difference is architectural (gland structure vs infiltrative pattern)
- Invasive epithelium ↔ other — tumour cells embedded in stroma can look
  like stromal cells at low confidence
- Necrosis ↔ other — necrotic regions at the periphery resemble adipose or
  loose stroma

`src/evaluate.py` should compute and log the confusion matrix as well as Dice.
The confusion matrix reveals which classes are being swapped and guides the
next training iteration (e.g. if necrosis is being predicted as other,
upweighting the necrosis class in the loss function may help).

---

## Loss function during training vs evaluation metric

The loss is Dice + cross-entropy (50/50 by default). Val Dice is computed with
the *evaluation Dice* (no smoothing, hard argmax predictions), not the loss
Dice (which uses soft probabilities for differentiability).

The two will not match exactly. A model with low training loss should have high
val Dice, but the exact mapping is not linear. Use the evaluation Dice
(argmax predictions, same computation as BEETLE's scoring) to make decisions —
not the loss value.

---

## Calibration

A calibrated model's predicted class probabilities match empirical accuracy:
if the model says 80% confidence on a pixel being invasive epithelium, 80% of
such pixels should indeed be invasive epithelium.

Deep neural networks are often overconfident — they output high-probability
predictions for pixels where they are uncertain. Overconfidence is a problem
for clinical use (a clinician using the model's output cannot trust the
confidence scores to reflect actual uncertainty).

For BEETLE, calibration is less critical than Dice — the leaderboard ranks
by Dice, not calibration. But the CLAIM checklist (`docs/results.md`) includes
calibration as a reporting item because it matters for any downstream clinical
application.

Calibration can be assessed after training by plotting a reliability diagram:
bucket all pixel predictions by confidence interval (0–10%, 10–20%, …), and
compute the actual accuracy in each bucket. A well-calibrated model has bars
that fall near the diagonal.

Temperature scaling (post-hoc calibration) is a simple fix if the model is
systematically overconfident — divide logits by a learned temperature T before
softmax.

---

## Per-scanner Dice

The overall val Dice is averaged across all val slides. If 80% of val slides
are from scanner A and 20% from scanner B, the overall Dice is dominated by
scanner A performance.

After training, `src/evaluate.py` should group val results by scanner and
compute per-scanner Dice. This is the CLAIM subgroup analysis requirement and
the actual test of multi-scanner generalisation.

Expected pattern: higher Dice on scanners well-represented in training, lower
on underrepresented scanners. If a specific scanner shows a large Dice drop,
stain augmentation may need to be increased or a scanner-specific normalisation
target may help.

---

## Grand Challenge evaluation vs local validation

The BEETLE leaderboard uses the sequestered test set — different slides,
possibly different scanners, definitely different annotations. Your local val
Dice will not match the leaderboard Dice exactly, even for the same model.

Typical patterns:
- Local val Dice > leaderboard Dice — the val set is not fully independent of
  the training distribution (could be due to scanner overlap or incomplete
  stratification). Strengthen the split.
- Local val Dice ≈ leaderboard Dice ± 1–2 points — expected variance from
  different slide populations
- Local val Dice << leaderboard Dice — rare; indicates the val set is harder
  than the test set, possibly due to aggressive stratification

Do not over-tune to the leaderboard. Submit infrequently (once per meaningful
change in the training setup) to avoid test set overfitting via hyperparameter
tuning.

---

## Early stopping

Training stops when val Dice does not improve for `early_stopping_patience`
epochs (default: 10). The checkpoint at the best val Dice epoch is saved as
`runs/<run_id>/best.pt`.

The patience of 10 epochs at a typical learning rate schedule means the model
gets roughly 10 epochs to recover from a local dip before stopping. For a
dataset of 300k tiles with batch size 16, one epoch takes ~1 hour on a single
A100 — 10-epoch patience = 10 hours of compute before stopping.

If training is consistently stopping early (at epoch 15–20), the model is
not learning from the data. Common causes:
- Learning rate too high (loss explodes or oscillates)
- Normalisation not applied (model sees raw, unnormalised colour)
- Label encoding error (class indices off-by-one or not matching the mask format)
