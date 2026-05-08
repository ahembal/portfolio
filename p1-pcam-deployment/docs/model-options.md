# Model Options
*p1-pcam-deployment — PCam binary classification*

This document tracks model options for the tumour/normal classification task.
Each entry records what the model is, where it comes from, what it needs to run,
and whether we have tried it.

---

## Currently in use

### TIAToolbox ResNet-18
- **Source:** `1aurent/resnet18.tiatoolbox-pcam` (HuggingFace)
- **Architecture:** ResNet-18, 11.2M parameters, 2-class softmax
- **Input:** 96×96 RGB patch
- **Class mapping:** class 0 = tumour, class 1 = normal
- **Metrics:** AUC ~0.96 (Pocock et al. 2022, Communications Medicine)
- **License:** CC0 1.0
- **Compute:** CPU-compatible (~500ms/image on homelab)
- **How to load:** `timm.create_model("hf-hub:1aurent/resnet18.tiatoolbox-pcam", pretrained=True)`
- **Status:** ✅ In production — replaced our trained weights (2026-05-08)
- **Notes:** Class index is inverted vs PyTorch convention — see `model-issues.md` §3

---

## Candidates to try

### TIAToolbox MobileNetV2
- **Source:** `1aurent/mobilenetv2_100.tiatoolbox-pcam` (HuggingFace)
- **Architecture:** MobileNetV2, 2.26M parameters — 5× smaller than ResNet-18
- **Input:** 96×96 RGB patch
- **Metrics:** Not published separately — part of Pocock et al. 2022
- **License:** CC0 1.0
- **Compute:** Faster than ResNet-18 on CPU — better for demo latency
- **How to load:** `timm.create_model("hf-hub:1aurent/mobilenetv2_100.tiatoolbox-pcam", pretrained=True)`
- **Status:** ⬜ Not tried — worth benchmarking for latency vs accuracy tradeoff

### TIAToolbox Wide ResNet-50
- **Source:** `1aurent/wide_resnet50_2.tiatoolbox-pcam` (HuggingFace)
- **Architecture:** Wide ResNet-50-2, 66.9M parameters
- **Input:** 96×96 RGB patch
- **License:** CC0 1.0
- **Compute:** Needs more RAM — may be slow on CPU
- **Status:** ⬜ Not tried — higher capacity but likely overkill for this task

### TIAToolbox ResNet-50 (kaczmarj)
- **Source:** `kaczmarj/lymphnodes-tiatoolbox-resnet50.patchcamelyon` (HuggingFace)
- **Architecture:** ResNet-50, ~25M parameters
- **License:** CC-BY 4.0
- **Status:** ⬜ Not tried

---

## Foundation models (require fine-tuning + GPU)

These are large pretrained backbones trained on broad pathology data. They are not
drop-in replacements — they need a classification head and fine-tuning on PCam.
Not suitable for CPU inference at demo scale.

| Model | Source | Parameters | Notes |
|-------|--------|-----------|-------|
| UNI | Harvard MIL-VIT | ~300M | Vision transformer, 100k+ pathology slides |
| CONCH | HuggingFace | ~400M | Contrastive learning, text+image |
| Prov-GigaPath | Microsoft/Providence | ~1B | Whole-slide foundation model |

---

## Our trained model

- **Architecture:** ResNet-18, 1-class sigmoid (BCEWithLogitsLoss)
- **Training:** 6 epochs on PCam, Kaggle T4 GPU
- **Metrics:** AUC 0.9657, accuracy 90.0% on test set
- **Status:** ⚠️ Weights in RGW (`pcam/kaggle-001/best_model.pt`) but produced no class
  separation in serving — see `model-issues.md` §2. Replaced by TIAToolbox for now.
- **Next step:** Retrain with full dataset and validated preprocessing pipeline, then
  benchmark against TIAToolbox ResNet-18 before replacing it.

---

## How to benchmark

To compare two models on the same demo patches:

```python
import timm, torch
from PIL import Image

def load_tia(model_id):
    model = timm.create_model(f"hf-hub:{model_id}", pretrained=True).eval()
    cfg = timm.data.resolve_model_data_config(model)
    transform = timm.data.create_transform(**cfg, is_training=False)
    return model, transform

def predict(model, transform, img_path):
    img = Image.open(img_path).convert("RGB")
    tensor = transform(img).unsqueeze(0)
    with torch.no_grad():
        probs = torch.softmax(model(tensor), dim=1).squeeze()
    return float(probs[0])  # P(tumour) for TIAToolbox models
```
