# Model Issues Log
*p1-pcam-deployment — model training, weights, and inference issues*

---

## 1. ResNet-18 fc layer shape mismatch — num_classes=2 vs checkpoint num_classes=1

**Symptom:**
```
RuntimeError: Error(s) in loading state_dict for ResNet:
    size mismatch for fc.weight: copying a param with shape torch.Size([1, 512])
    from checkpoint, the shape in current model is torch.Size([2, 512]).
```

**Root cause:** Training used `num_classes=1` (binary BCE: one sigmoid output).
`build_model()` in `main.py` defaulted to `num_classes=2`. These are architecturally
incompatible — the final fully-connected layer has different shapes.

**Fix:** Changed `build_model` default to `num_classes=1` to match the training setup.

---

## 2. Trained model weights produced no class separation

**Symptom:** All demo patches returned `prob_tumour` between 0.37–0.41 regardless of
label. Model was effectively random — normal and tumour patches indistinguishable.

**Root cause:** Unknown. The model showed AUC 0.97 on the Kaggle test set during training,
but weights uploaded to RGW produced near-identical probabilities for all patches when
served. Possible causes: weights from an intermediate checkpoint, upload corruption, or
a discrepancy between training preprocessing and serving preprocessing.

**Fix:** Replaced trained weights with TIAToolbox pretrained ResNet-18
(`1aurent/resnet18.tiatoolbox-pcam`, Pocock et al. 2022). This is a publicly validated
model with clear class separation (prob ~0.0 for normal, ~1.0 for tumour patches).

**Serving code change:** Switched from 1-class sigmoid output to 2-class softmax to match
the TIAToolbox architecture. Added `timm` for model loading.

**Next step:** Retrain from scratch on Kaggle with full dataset and validated preprocessing,
then replace TIAToolbox weights once our model reaches comparable separation.

---

## 3. TIAToolbox class index inverted — class 0 is tumour, not normal

**Symptom:** High-confidence tumour patches (selected by TIAToolbox on Kaggle with
`prob_tumour ≈ 1.0`) were classified as Normal with 100% confidence by the serving API.

**Root cause:** The serving code assumed `class 0 = normal, class 1 = tumour` (standard
PyTorch convention). TIAToolbox ResNet-18 uses the opposite: `class 0 = tumour,
class 1 = normal`. This caused predictions to be exactly inverted.

**Fix:** Changed `prob_tumour = float(probs[1])` to `prob_tumour = float(probs[0])`.

**Lesson:** Always verify the class index mapping when using a third-party model.
Do not assume standard label ordering — check the model card or test with known examples.

---

## 4. Preprocessing mismatch — generic ResNet-18 config vs TIAToolbox config

**Symptom:** Some tumour patches correctly classified, others returned `prob_tumour=0.0`
despite TIAToolbox predicting `prob=1.000` on the same patches on Kaggle.

**Root cause:** The serving code loaded TIAToolbox weights into a generic
`timm.create_model("resnet18", ...)`. timm resolved the preprocessing config for a
standard ResNet-18: input 224×224, mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225).
TIAToolbox expects: input 96×96, mean=(0, 0, 0), std=(1, 1, 1) — no normalization.

The image size happened to be 96×96 already (hardcoded in the old transform), so that
part was accidentally correct. But the normalization was wrong, producing corrupted
inputs for some patches.

**Fix:** Load the model directly from HuggingFace Hub using the full model ID:
```python
timm.create_model("hf-hub:1aurent/resnet18.tiatoolbox-pcam", pretrained=True)
```
timm then resolves the correct preprocessing config from the model card automatically.

**Lesson:** When using a timm model from HuggingFace, always load via `hf-hub:<id>` —
never load weights into a generic architecture. The model card config (input size,
normalization) is part of the model, not just the weights.
