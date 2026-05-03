# How the Serving API Works — P1 PCAM
*Last updated: 2026-05-03*

This document explains every part of the p1 serving layer — what each endpoint
does, what data flows in and out, how the model is loaded, and where the
limitations are.

---

## The big picture

```
Pathologist / researcher uploads a tissue patch
        │
        ▼
FastAPI serving container
        │  receives image bytes
        │  resize → normalise → tensor
        │  model inference
        ▼
ResNet-18 model (loaded from Ceph RGW at startup)
        │
        ▼
{"label": "tumour", "confidence": 0.91, "latency_ms": 18}
```

---

## What the model does

The model classifies 96×96 pixel histopathology patches from the PatchCamelyon
(PCam) dataset. Each patch is a small crop of a whole-slide tissue image.

**Binary classification:**
- `normal` — no tumour tissue in the central 32×32 region
- `tumour` — tumour tissue present in the central 32×32 region

The model is ResNet-18 fine-tuned on PCam. It outputs a single probability
(P(tumour)) via sigmoid activation. If P(tumour) ≥ 0.5, the label is `tumour`.

---

## How the model gets into the container

At container startup, the API downloads model weights from Ceph RGW:

```
s3://ml-artifacts/pcam/<job_id>/
  └── best_model.pt     trained ResNet-18 weights (~45 MB)
```

Downloaded to `/tmp/best_model.pt`. If RGW is unreachable, the container
fails immediately — it does not start in a broken state.

**Why not bake weights into the Docker image?**
The image stays ~50 MB instead of ~500 MB. Model and code have different
change rates — a code fix should not require re-uploading 45 MB of weights.

---

## Endpoints

### POST /predict

**Purpose:** Classify a histopathology patch as tumour or normal.

**Request:** multipart/form-data with one field:
- `file` — image file (JPEG or PNG, any size — resized automatically to 96×96)

```bash
# Example curl
curl -X POST http://localhost:8000/predict \
  -F "file=@patch_001.png"
```

**Response:**
```json
{
  "label": "tumour",
  "confidence": 0.91,
  "latency_ms": 18.4
}
```

**What happens inside:**
1. Image bytes decoded with PIL → RGB format
2. Resized to 96×96 pixels
3. Normalised with ImageNet mean/std: `mean=[0.485, 0.456, 0.406]`, `std=[0.229, 0.224, 0.225]`
4. Converted to tensor of shape `(1, 3, 96, 96)`
5. Fed to ResNet-18 → single logit output
6. `sigmoid(logit)` → probability of tumour
7. Threshold at 0.5 → label
8. Confidence = P(tumour) if tumour, else 1 - P(tumour)

**Limitations:**
- Input images are always resized to 96×96. A high-resolution patch is downsampled — fine detail is lost. For best results, submit 96×96 crops.
- Only RGB images are supported. Grayscale images are converted to RGB (3-channel) automatically, which may affect accuracy.
- The threshold 0.5 is a conservative default. The optimal Youden threshold from training is 0.37 — at 0.5 the model is more conservative (lower sensitivity, fewer false positives).
- Confidence is not a calibrated probability. 0.91 does not mean 91% of similar patches are tumour.
- Single patch only. No batch endpoint in v1.
- No spatial localisation — the model says tumour/normal for the whole patch, not which region contains tumour.

---

### GET /health

**Purpose:** Kubernetes liveness probe. Checks the model is loaded.

**Response (ready):**
```json
{"status": "ok", "device": "cpu"}
```

**Response (model not loaded — 503):**
```json
{"detail": "Model not loaded"}
```

**Why it matters:** Kubernetes sends `/health` before routing traffic to a pod.
If the model is still downloading from RGW (~5 seconds), the pod returns 503
and Kubernetes waits. This prevents requests hitting the container before it
is ready.

---

### GET /metrics

**Purpose:** Prometheus scrape endpoint.

**Metrics exposed:**

| Metric | Type | Description |
|--------|------|-------------|
| `pcam_requests_total{endpoint, status}` | Counter | Requests by endpoint + HTTP status |
| `pcam_request_latency_ms{endpoint}` | Histogram | Inference latency in ms |
| `pcam_model_info{model_key, bucket, device}` | Info | Static model metadata (value=1) |

**In Grafana:**
- `rate(pcam_requests_total[1m])` → requests per second
- `histogram_quantile(0.95, pcam_request_latency_ms)` → p95 latency

---

## The preprocessing step in detail

```
Raw JPEG/PNG bytes (any size, any format)
        │
        ▼  PIL.Image.open → convert("RGB")
96×96 RGB image (3 channels, values 0-255)
        │
        ▼  transforms.Resize((96, 96))
        ▼  transforms.ToTensor()          → values now 0.0-1.0
        ▼  transforms.Normalize(mean, std) → values now centred around 0
Tensor shape: (3, 96, 96)
        │
        ▼  .unsqueeze(0)                  → add batch dimension
Tensor shape: (1, 3, 96, 96)   ← ready for model
```

**Why normalise?** ResNet-18 was pretrained on ImageNet with those specific
mean and std values. Using the same normalisation at inference ensures the
pixel value distribution matches what the model was trained on. Using wrong
normalisation silently degrades accuracy.

---

## Limitations summary

| Limitation | Impact | Note |
|-----------|--------|------|
| 96×96 input (auto-resize) | Detail lost in large images | Submit crops, not whole slides |
| Binary output only | No confidence distribution | Confidence ≠ calibrated probability |
| Default threshold 0.5 | More conservative than optimal 0.37 | Adjust threshold externally |
| CPU inference ~15-20ms | Not suitable for whole-slide scanning | GPU serving needed at scale |
| No batch endpoint | One patch per request | v1 limitation |
| RGW required at startup | Container fails if RGW unreachable | Kubernetes restart policy handles recovery |
