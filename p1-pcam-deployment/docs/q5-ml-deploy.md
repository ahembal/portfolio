# Q5 — ML Training, Evaluation, and Deployment Pipeline

**Project:** PCam Inference Service — histopathology patch classification
**Model:** ResNet-18, binary classification (tumor / normal)
**Dataset:** PatchCamelyon (PCam) — 327,680 × 96×96 RGB patches from Camelyon16

---

## 1. Training

### Compute

Training ran on a Kaggle T4 GPU notebook (`train/kaggle_train.ipynb`).
The training script (`train/train.py`) is compute-agnostic — the same code
runs on Kaggle, a local GPU, or a SLURM cluster (DARDEL, KTH PDC). The notebook
is a thin wrapper: it calls `train.py` with the Kaggle dataset path and uploads
the resulting artifacts to Ceph RGW.

### Architecture and choices

| Choice | Decision | Reason |
|--------|---------|--------|
| Architecture | ResNet-18, ImageNet pretrained | Strong baseline for small histopathology patches; faster to train than deeper nets with similar AUC on PCam |
| Loss | BCEWithLogitsLoss (`num_classes=1`) | Binary task — single sigmoid output is numerically more stable than 2-class softmax |
| Optimiser | AdamW + cosine LR schedule | Reduces weight decay interaction with momentum; cosine schedule avoids manual LR decay tuning |
| Precision | AMP (automatic mixed precision) | ~1.7× throughput on T4; loss scaling handles gradient underflow |
| Augmentation | RandomRot90 (D4 symmetry group) | Histopathology patches have no canonical orientation; D4 group covers all rotations/flips in one transform; channels-last NHWC avoids a copy |
| Batch size | 128 × N_GPUs, LR scaled linearly | Linear scaling rule: LR ∝ batch size keeps effective gradient step size constant |

### Training run

| Epoch | Train loss | Val loss | Notes |
|-------|-----------|---------|-------|
| 1 | 0.5012 | 0.4231 | |
| 2 | 0.3904 | 0.3891 | |
| 3 | 0.3412 | 0.3742 | |
| 4 | 0.3187 | 0.3671 | |
| 5 | 0.3041 | 0.3589 | |
| 6 | 0.2941 | 0.3566 | ← best checkpoint saved |

6 epochs, best model at epoch 6 (lowest validation loss). Checkpoint saved as
`best_model.pt` and pushed to Ceph RGW at `pcam-models/pcam/kaggle-001/`.

---

## 2. Evaluation

### Metrics

| Metric | Value |
|--------|-------|
| AUC (ROC) | **0.9657** |
| Accuracy | **90.0%** |
| F1 score | **0.897** |
| Train loss (ep 6) | 0.2941 |
| Val loss (ep 6) | 0.3566 |

AUC of 0.9657 is competitive with published ResNet-18 baselines on PCam
(Wang et al. 2019 report ~0.963 with comparable augmentation).

### Threshold selection — two operating points

A sigmoid model outputs a probability, not a label. The decision threshold
determines the sensitivity / specificity trade-off. Two thresholds are stored
in `threshold.json` for different use cases:

| Threshold | Value | Sensitivity | Specificity | Use case |
|-----------|-------|-------------|-------------|---------|
| Youden (J-optimal) | 0.3694 | 90.6% | 90.4% | Balanced: maximises J = sens + spec − 1 |
| 95% sensitivity | 0.2044 | 95.0% | 82.5% | Safety-first: minimise missed tumors |

In a clinical screening context (per EU AI Act Art. 15 — accuracy and robustness),
the 95%-sensitivity threshold is the appropriate operating point: a false negative
(missed tumor) has a worse outcome than a false positive (unnecessary biopsy).

Both thresholds are returned by the `/predict` endpoint so the caller can choose.

---

## 3. Deployment pipeline

### Overview

```
git push (serving/main.py or Dockerfile changed)
  │
  └── GitHub Actions CI (.github/workflows/ci.yml)
        ├── pytest — unit + integration tests
        ├── docker build (multi-stage, distroless)
        ├── docker push → ghcr.io/ahembal/pcam-inference:<git-sha>
        └── update helm/pcam-inference/values.yaml image.tag → commit back
              │
              └── ArgoCD (running on cluster, watches main branch)
                    └── detects values.yaml drift
                          └── helm upgrade pcam ./helm/pcam-inference
                                └── rolling update (maxUnavailable: 0, maxSurge: 1)
                                      └── new pod: lifespan() downloads model from RGW
                                            └── readinessProbe passes → traffic switched
```

### Key design decisions

**Model not baked into the image.**
The model checkpoint is pulled from Ceph RGW at container startup, not
embedded in the Docker image. This means:
- The image tag tracks *code* versions, not *model* versions. Retraining produces
  a new RGW artifact; serving a new model version requires only a ConfigMap change
  (`MODEL_KEY`), not a full image rebuild.
- The image stays ~1.5 GB instead of ~2.5 GB with the 45 MB checkpoint embedded.

**GitOps — single source of truth.**
`helm/pcam-inference/values.yaml` in the `main` branch is the definitive cluster
state. CI writes the image tag; ArgoCD reads it. No manual `kubectl apply` in
production. Every deployment is a reviewed, auditable git commit.

**Secrets never in git as plaintext.**
RGW credentials (`access-key`, `secret-key`) and the GHCR pull token are encrypted
with Bitnami Sealed Secrets (RSA-OAEP + AES-GCM) before committing. Only the
cluster's controller private key can decrypt. Relevant compliance:
ISO/IEC 27001:2022 A.10, NIST SP 800-190 §4.2.
See `docs/security-compliance.md` for the full mapping.

**Zero-downtime rolling updates.**
`maxUnavailable: 0` ensures at least one pod is always serving traffic during an
upgrade. `maxSurge: 1` allows one extra pod to download the model from RGW and
pass readiness before the old pod is terminated.

**HPA for throughput scaling.**
A HorizontalPodAutoscaler (min 1, max 4 replicas) scales on CPU utilisation.
Load test result: 20 concurrent Locust users drove CPU to 396% (880m / 250m request),
triggering scale-up from 1 → 4 replicas within ~90 seconds. After load stopped,
scale-down returned to 1 replica.

### Inference API

`POST /predict` accepts a multipart PNG image (96×96 RGB patch) and returns:
```json
{
  "label": "normal",
  "confidence": 0.94,
  "latency_ms": 347.6
}
```

`GET /metrics` exposes Prometheus-format metrics scraped every 15 seconds:
- `pcam_requests_total{endpoint, status}` — request count
- `pcam_request_latency_ms` — latency histogram (p50/p95/p99 in Grafana)
- `pcam_model_info` — static metadata (model key, bucket, device)

---

## 4. Observability

Prometheus + Grafana (kube-prometheus-stack) deployed in the `monitoring` namespace.
A ServiceMonitor CRD tells the prometheus-operator to scrape the pcam pod's `/metrics`
endpoint. A Grafana ConfigMap (sidecar auto-discovered via `grafana_dashboard: "1"` label)
provides a 5-panel dashboard:

| Panel | Query |
|-------|-------|
| Request rate (req/s) | `sum(rate(pcam_requests_total[1m]))` |
| Error rate (%) | `100 * rate(pcam_requests_total{status="error"}[1m]) / rate(...)` |
| Latency p50/p95/p99 | `histogram_quantile(0.x, sum(rate(pcam_request_latency_ms_bucket[1m])) by (le))` |
| HPA replicas | `kube_horizontalpodautoscaler_status_current_replicas` |
| Pod CPU | `rate(container_cpu_usage_seconds_total{container="pcam-inference"}[1m]) * 1000` |
