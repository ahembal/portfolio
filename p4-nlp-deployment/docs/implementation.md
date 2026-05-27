# Implementation Notes — P4 NLP Deployment
*Last updated: 2026-04-28*

This document describes how the project was built: structure chosen, problems hit during development, and decisions made along the way. For how the finished product works see `how-it-works.md`. For training design rationale see `training-design.md`.

---

## notebooks/train_pubmed_rct.ipynb

### Dataset choice
- Initial attempt used pietrolesci/pubmed-200k-rct: 2.27M rows, ~6 hours per epoch on T4 — too slow for iterative development
- Switched to armanc/pubmed-rct20k: ~177k rows, ~45 minutes per 3 epochs on T4 — correct choice
- DatasetNotFoundError on joolsa/pubmed_rct_200k (dataset does not exist) — had to find correct dataset name

### Training setup
- Model: distilbert-base-uncased, fine-tuned for sequence classification (5 labels)
- Labels: BACKGROUND, METHODS, RESULTS, CONCLUSIONS, OBJECTIVE (strings, not ints — DatasetDict uses string labels)
- Tokenizer: processing_class= parameter (not tokenizer=) — HuggingFace Trainer API changed in transformers>=4.47
- 3 epochs, batch_size=32, T4 GPU, ~45 min total

### Kaggle dependency issues fixed
- boto3==1.34.0 pinned → broke aiobotocore 3.3.0 (needs botocore>=1.42.62,<1.42.71). Fixed: removed boto3 pin (Kaggle has a compatible version pre-installed)
- transformers==4.40.0 pinned → Kaggle's sentence-transformers 5.2.3 requires >=4.41.0. Fixed: pin to >=4.41.0
- datasets==2.19.0 → installed fsspec==2024.3.1, conflicted with Kaggle's s3fs and gcsfs. Fixed: unpinned datasets

### Model upload
- RGW upload from Kaggle failed: Kaggle runs in Google Cloud, Tailscale IP (192.168.x.x) not routable externally
- Workaround: push to HuggingFace Hub from Kaggle → pull to laptop → push to RGW (s3://nlp-models/pubmed-rct/v1/)
- HF token stored in pass homelab/huggingface/kaggle-token

---

## serving/main.py — post-review fixes (2026-05-27)

### Sentence splitting

**Problem:** `req.text.split(".")` splits on every period — including decimals
(`2.5 mg/kg` → `["2", "5 mg/kg"]`), abbreviations (`Dr. Smith` → `["Dr", "Smith"]`),
and p-values (`p < 0.05` → `["p < 0", "05"]`). Each fragment is classified
independently, producing nonsense labels.

**Fix:** regex `(?<=[.!?])\s+(?=[A-Z])` — splits on sentence-ending punctuation
followed by whitespace and a capital letter. Handles 95%+ of PubMed RCT prose
correctly because scientific sentences reliably start with a capital letter.

**Production consideration:** `nltk.sent_tokenize` with the `punkt_tab` model
handles edge cases (abbreviations, initialisms) correctly and is the standard
for biomedical text. Requires adding `nltk` to requirements and downloading the
model at image build time (~13 MB). Worth doing if the API is extended to
handle arbitrary clinical notes rather than structured abstracts.

### Confidence scores

The `confidence` field in `SentenceResult` is the raw softmax probability of
the predicted class — not a calibrated probability. "confidence: 0.97" means
the logit for this class was much higher than the others; it does not mean
the model is correct 97% of the time.

**What calibration means:** a calibrated model with confidence 0.8 is correct
~80% of the time. An uncalibrated softmax can be systematically overconfident
(outputs near 1.0 even when uncertain) or underconfident depending on the
training distribution.

**Production fix:** fit temperature scaling on the validation set. Divide logits
by a scalar T before softmax; T is chosen to minimise NLL on held-out data.
~30 lines of code. See `docs/model-limitations.md §3`.

**Current state:** documented in the schema comment and in `docs/model-limitations.md`.
Callers should not treat the confidence value as a true probability.

### Boto3 error handling in _load_model()

**Problem:** if RGW is unreachable at startup (wrong endpoint, missing credentials,
network partition), boto3 raises an exception that propagates through the FastAPI
lifespan with no log output. The pod CrashLoopBackOff with no useful diagnostic.

**Fix:** wrapped the S3 block in try/except. On failure, logs `model_load_failed`
with endpoint, bucket, prefix, exception type, and message — then re-raises so
the pod still fails fast (correct behaviour) but now with a useful log entry.

### Prometheus metrics added

Two new histograms:
- `nlp_model_load_duration_seconds` — total startup time from entering `_load_model()`
  to model ready. Useful for tuning `readinessProbe.initialDelaySeconds`.
- `nlp_rgw_download_latency_seconds` — per-file S3 download time. Signals RGW
  performance degradation independently of model load time.

### Results
- accuracy=86.8%, macro F1=0.806
- Per-class F1: METHODS=0.937, RESULTS=0.915, CONCLUSIONS=0.833, BACKGROUND=0.706, OBJECTIVE=0.640
- Within expected DistilBERT range (86-88% on PubMed RCT)
