# Q5 — NLP Deployment
*Last updated: 2026-05-01*

> This document covers what is different about deploying an NLP model compared
> to image classification (p1), and the specific engineering decisions made.

## How NLP serving differs from image classification

p1 deployed a CNN for binary image classification (PatchCamelyon).
p4 deploys a transformer for multi-class text classification (PubMed RCT).
Same deployment pattern — FastAPI, Docker, Helm, ArgoCD — different model
characteristics that affect the serving layer.

| Dimension | p1 (image, CNN) | p4 (text, transformer) |
|-----------|----------------|----------------------|
| Model size | ~45 MB | ~250 MB (DistilBERT weights) |
| Input | Fixed-size image tensor (96×96×3) | Variable-length token sequence |
| Preprocessing | Normalise pixel values | Tokenise text (BPE) → pad/truncate |
| Output | Single sigmoid score | 5-class softmax |
| Inference time (CPU) | ~5ms | ~30ms per sentence |
| Memory at startup | ~200 MB | ~600 MB (model + tokeniser + cache) |

---

## Tokenisation pipeline

The most important difference: NLP models require a **tokeniser** that must be
loaded alongside the model weights. The tokeniser converts raw text to integer
token IDs the model understands.

```
Input: "Patients were randomly assigned to drug A."
  ↓ tokenize(text, max_length=128, truncation=True)
Token IDs: [101, 5834, 2020, 6360, 4137, 2000, 2979, 1037, 1012, 102, 0, ...]
Attention mask: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, ...]
  ↓ model(input_ids, attention_mask)
Logits: [-1.2, 0.3, 4.1, -0.8, -2.4]   (one per class)
  ↓ softmax → argmax
Output: "METHODS" (confidence: 0.94)
```

**Variable-length inputs and padding:**
Unlike images (always 96×96), sentences vary in length. The tokeniser truncates
at `max_length=128` and pads shorter sequences with zeros. Padding tokens are
masked out via the attention mask so they don't influence the prediction.

At serving time, batching is straightforward for image models (stack tensors);
for text, batching requires dynamic padding to the longest sequence in the batch
— handled by `DataCollatorWithPadding` during training and manually at inference.

---

## Model artifact management

**Why model weights are stored in Ceph RGW, not baked into the Docker image:**

| Approach | Image size | Model update requires | Startup time |
|----------|-----------|----------------------|--------------|
| Weights in image | ~750 MB | Rebuild + push image | Fast (already on disk) |
| Weights in RGW | ~50 MB | Update RGW only | +15s (download on start) |

We use RGW because:
- Model and code have different change rates — code changes more often
- Decouples model versioning from image versioning
- Multiple versions can coexist in RGW (`pubmed-rct/v1/`, `v2/`, etc.)

The serving container downloads weights at startup via boto3. If RGW is
unreachable, the container fails fast (startup error, not a silent failure).

---

## Distroless container — specific NLP consideration

HuggingFace Transformers writes a cache at import time to store downloaded
models and tokeniser vocabularies. The default cache path is `~/.cache/huggingface/`
— which doesn't exist in a distroless container (no home directory, no writable paths
outside `/tmp`).

**Fix:** Set `TRANSFORMERS_CACHE=/tmp/hf_cache` in the Dockerfile. The container
downloads the tokeniser vocabulary to `/tmp` at startup. This is intentional and safe —
the actual model weights come from RGW, not HuggingFace Hub at serving time.

---

## Deployment architecture

```
GitHub push
  → CI: pytest → docker build (api + streamlit) → push GHCR
    → ArgoCD detects values.yaml tag change
      → Rolling update: api + streamlit deployments
        → API: loads DistilBERT from RGW on startup
        → Streamlit: calls API via in-cluster ClusterIP
```

**Two separate images (api + streamlit):**
- `nlp-api`: FastAPI + PyTorch + transformers (~500 MB)
- `nlp-streamlit`: Streamlit + requests (~150 MB)

Separated because they have different dependencies and update at different rates —
the UI can be updated without rebuilding the model serving image.

**HPA on the API deployment:**
The API is CPU-bound at inference time (CPU inference for DistilBERT).
HPA scales replicas when CPU utilisation > 70%. Unlike p2 (queue depth signal),
here we use the standard CPU metric because inference load is directly reflected
in CPU usage.

---

## Current challenges and known limitations

**Sentence boundary detection:**
The `/predict` endpoint classifies individual sentences. The Streamlit UI splits
input abstracts into sentences using Python's `nltk.sent_tokenize`. This works
for well-formed English medical text but may fail on:
- Abbreviations with periods (e.g., "i.v. injection")
- Numbered lists within abstracts
- Non-English abstracts

**CPU inference latency (~30ms per sentence):**
Acceptable for interactive demo use. For batch processing of PubMed at scale
(millions of abstracts), a batch inference pipeline with GPU acceleration would
be needed — this is a serving demo, not a production batch system.

**Model confidence calibration:**
Transformer softmax outputs are not calibrated probabilities. A confidence of
0.94 does not mean the model is correct 94% of the time. For use in systematic
reviews, proper calibration (e.g., temperature scaling) would be needed.
