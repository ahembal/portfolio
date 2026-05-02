# How the Serving API Works
*Last updated: 2026-05-02*

This document explains every part of the p4 serving layer — what each endpoint
does, what data flows in and out, how the model is loaded, and where the
limitations are. Read this before reading or writing any code.

---

## The big picture

```
Researcher types a sentence
        │
        ▼
Streamlit UI (browser)
        │  HTTP POST /predict {"text": "Patients were randomly assigned..."}
        ▼
FastAPI serving container
        │  tokenize → model inference → decode output
        ▼
DistilBERT model (loaded from Ceph RGW at startup)
        │
        ▼
{"label": "METHODS", "confidence": 0.94, "latency_ms": 32}
        │
        ▼
Streamlit UI shows result colour-coded by label
```

---

## How the model gets into the container

At container startup, the API downloads the model from Ceph RGW:

```
s3://nlp-models/pubmed-rct/v1/
  ├── config.json           model architecture config
  ├── model.safetensors     trained weights (268 MB)
  ├── tokenizer.json        vocabulary + tokenisation rules
  ├── tokenizer_config.json tokenizer settings
  └── metrics.json          training results (accuracy, F1)
```

The container downloads these files to a local temp directory on startup.
If RGW is unreachable, the container fails immediately with a clear error —
it does not start in a broken state (fail fast).

**Why not bake the weights into the Docker image?**
The image would be ~750 MB vs ~50 MB. More importantly, model and code change
at different rates — a bug fix in the API should not require re-uploading 268 MB.
Separating them keeps the image small and allows model versioning independently.

---

## Endpoints

### POST /predict

**Purpose:** Classify a sentence from a medical abstract into one of 5 categories.

**Request:**
```json
{
  "text": "Patients were randomly assigned to receive either drug A or placebo."
}
```

**Response:**
```json
{
  "label": "METHODS",
  "confidence": 0.94,
  "latency_ms": 32,
  "all_scores": {
    "BACKGROUND": 0.01,
    "OBJECTIVE": 0.01,
    "METHODS": 0.94,
    "RESULTS": 0.03,
    "CONCLUSIONS": 0.01
  }
}
```

**What happens inside:**
1. The text is passed to the tokenizer → converted to token IDs
2. Token IDs are fed to DistilBERT → outputs 5 raw scores (logits)
3. Softmax converts logits to probabilities (sum to 1.0)
4. Argmax picks the highest probability → that is the label
5. Confidence = the highest probability value

**Data structure:**
- Input: plain string, any length
- Output: label (string), confidence (float 0-1), latency_ms (int), all_scores (dict)

**Limitations:**
- Input is truncated at 128 tokens. A typical sentence is 15-30 tokens so this
  is rarely hit — but very long sentences lose their tail. The model never sees
  text beyond token 128.
- Classifies one sentence at a time. Batch input is not supported in v1.
- Language: English only. Non-English text will produce a prediction but it
  will be meaningless.
- Domain: trained on clinical trial (RCT) abstracts. Performance on other
  abstract types (reviews, case reports) is lower.
- Confidence is NOT a calibrated probability. 0.94 does not mean the model
  is correct 94% of the time — it means the model assigns 94% of its
  probability mass to that label. Calibration would require an extra step.

---

### GET /health

**Purpose:** Kubernetes liveness and readiness probe. Checks that the model
is loaded and the service is ready to accept requests.

**Request:** no body

**Response (healthy):**
```json
{
  "status": "ok",
  "model": "distilbert-base-uncased",
  "model_loaded": true
}
```

**Response (not ready — model still loading):**
```json
{
  "status": "loading",
  "model_loaded": false
}
```

**Why this matters:**
Kubernetes sends a `/health` request before routing traffic to a pod. If the
model is still downloading from RGW (takes ~15 seconds), the pod should return
`loading` — Kubernetes waits. Once the model is loaded, it returns `ok` and
traffic starts flowing. Without this, the first requests would fail.

---

### GET /metrics

**Purpose:** Prometheus scrape endpoint — exposes counters and histograms
for the monitoring dashboard.

**Response:** Prometheus text format (not JSON)

```
# HELP nlp_requests_total Total prediction requests by label
# TYPE nlp_requests_total counter
nlp_requests_total{label="METHODS"} 142.0
nlp_requests_total{label="RESULTS"} 89.0
...

# HELP nlp_request_latency_ms Prediction latency in milliseconds
# TYPE nlp_request_latency_ms histogram
nlp_request_latency_ms_bucket{le="10.0"} 0.0
nlp_request_latency_ms_bucket{le="25.0"} 12.0
nlp_request_latency_ms_bucket{le="50.0"} 187.0
...
```

**Metrics tracked:**
- `nlp_requests_total{label}` — how many times each label was predicted
- `nlp_request_latency_ms` — histogram of inference time
- `nlp_model_load_duration_seconds` — how long model download took at startup

---

## The tokenisation step in detail

This is the most important difference from image classification (p1).

**For images (p1):** input is always 96×96 pixels → fixed-size tensor → model

**For text (p4):** input is a sentence of unknown length → must be converted:

```
Input:  "Patients were randomly assigned to drug A."

Step 1 — Tokenise (split into subwords):
        ["patients", "were", "randomly", "assigned", "to", "drug", "a", "."]
        Note: DistilBERT uses WordPiece — rare words split into subwords:
        "randomisation" → ["random", "##isation"]

Step 2 — Add special tokens:
        [CLS] patients were randomly assigned to drug a . [SEP]
        [CLS] = start of sequence marker
        [SEP] = end of sequence marker

Step 3 — Convert to IDs (vocabulary lookup):
        [101, 5834, 2020, 6360, 4137, 2000, 2979, 1037, 1012, 102]

Step 4 — Pad or truncate to max_length=128:
        [101, 5834, 2020, 6360, 4137, 2000, 2979, 1037, 1012, 102,
         0, 0, 0, ..., 0]   ← padding zeros

Step 5 — Create attention mask (1=real token, 0=padding):
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, ..., 0]
        The model ignores padding positions

Step 6 — Feed to DistilBERT → get logits → softmax → label
```

The tokenizer is loaded from RGW alongside the model weights. They must
always match — using a different tokenizer with the model produces garbage output.

---

## What the Streamlit UI does

The Streamlit app is a thin wrapper around the API — it does not run the model itself.

```
User pastes an abstract:
"Background: HIV is a chronic condition...
 Objective: To investigate the efficacy...
 Methods: Patients were randomly assigned..."

Streamlit splits into sentences:
  → ["HIV is a chronic condition...",
     "To investigate the efficacy...",
     "Patients were randomly assigned..."]

For each sentence → POST /predict → get label + confidence

Display colour-coded:
  BACKGROUND  → blue
  OBJECTIVE   → purple
  METHODS     → green
  RESULTS     → orange
  CONCLUSIONS → red
```

The sentence splitting uses `nltk.sent_tokenize`. It works well for standard
English but can fail on abbreviations with periods (e.g. "i.v. injection" →
split into two sentences) or numbered lists.

---

## Limitations summary

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| Max 128 tokens per sentence | Very long sentences truncated | Rarely hit in practice (~30 tokens avg) |
| English only | Wrong predictions for other languages | Document clearly |
| RCT-specific training data | Lower accuracy on non-RCT abstracts | Document scope |
| Uncalibrated confidence scores | 0.94 ≠ 94% correct | Use for ranking, not as probability |
| Single sentence, no context | Adjacent sentences affect meaning | Known limitation of the dataset |
| CPU inference ~30ms | Not suitable for bulk processing | GPU serving or batch pipeline for scale |
| Model download at startup (~15s) | Cold start delay | Kubernetes readiness probe handles this |
