# Project 1 — PCam ML Deployment Pipeline
## Progress Tracker
*Last updated: 2026-04-17*

---

## Steps

### Model training
| # | Step | Status | Notes |
|---|------|--------|-------|
| 1 | Train on Kaggle (T4 GPU) | ✅ Done | 6 epochs, ResNet-18 — AUC 0.9657, Acc 90.0%, F1 0.897 |
| 2 | Download artifacts from Kaggle | ⬜ Pending | best_model.pt, metrics.json, config.json, threshold.json |
| 3 | Push artifacts to Ceph RGW | ⬜ Pending | `push_kaggle_artifacts.py --zip ... --run-id kaggle-001` |

### Container image
| # | Step | Status | Notes |
|---|------|--------|-------|
| 4 | Write Dockerfile | ✅ Done | Multi-stage, pulls model from RGW at startup |
| 5 | Switch runtime to distroless image | ✅ Done | gcr.io/distroless/python3-debian12:nonroot, no shell |

### Helm chart
| # | Step | Status | Notes |
|---|------|--------|-------|
| 6 | Write Helm chart | ✅ Done | deployment, service, configmap, hpa, _helpers, values |
| 7 | Add Nginx Ingress template to chart | ✅ Done | ingress.yaml gated on ingress.enabled=false |
| 8 | Add FastAPI `/metrics` endpoint | ✅ Done | prometheus-client Counter + Histogram + Info |

### CI/CD
| # | Step | Status | Notes |
|---|------|--------|-------|
| 9 | GitHub Actions CI pipeline | ✅ Done | pytest → docker build → push GHCR → update values.yaml tag |
| 10 | RBAC — dedicated service account for ArgoCD | ✅ Done | k8s/rbac.yaml — namespaced Role, automountToken: false |
| 11 | Install ArgoCD on cluster | ✅ Done | Running on quick-thrush; NetworkPolicies removed for stability |
| 12 | Sealed Secrets for RGW credentials | ⬜ Pending | Install controller → kubeseal RGW creds → commit SealedSecret |
| 13 | Wire ArgoCD Application to Helm chart | ⬜ Pending | ArgoCD Application CR pointing at `helm/pcam-inference` on main |

### Testing & observability
| # | Step | Status | Notes |
|---|------|--------|-------|
| 14 | Test /predict endpoint | ⬜ Pending | curl a real PCam patch image through Nginx Ingress |
| 15 | Load test + HPA demo | ⬜ Pending | locust, `kubectl get hpa -w`, screenshot scaling events |
| 16 | Prometheus + Grafana dashboard | ⬜ Pending | Latency, throughput, error rate — screenshot for portfolio |

### Infra hygiene
| # | Step | Status | Notes |
|---|------|--------|-------|
| 17 | Fix API server TLS SAN | ⬜ Pending | Add Tailscale IP `100.123.23.6` to cert SANs; drop insecure-skip-tls-verify |

### Docs
| # | Step | Status | Notes |
|---|------|--------|-------|
| 18 | Write Q5, Q7, Q9 docs | ⬜ Pending | Answer application questions with evidence from above |

---

## Files created

| File | Purpose |
|------|---------|
| `train/train.py` | Training script — ResNet-18, dependency injection, full metrics |
| `train/kaggle_train.ipynb` | Kaggle notebook — plan B compute (T4 GPU) |
| `train/submit_dardel.sh` | SLURM submit script for PDC Dardel (plan A) |
| `train/push_artifacts.py` | Push artifacts from Dardel → Ceph RGW |
| `train/push_kaggle_artifacts.py` | Push downloaded Kaggle zip → Ceph RGW |
| `serving/main.py` | FastAPI inference service — loads model from RGW |
| `serving/requirements.txt` | Serving dependencies |
| `serving/Dockerfile` | Multi-stage image; model pulled from RGW at startup |
| `helm/pcam-inference/Chart.yaml` | Chart metadata |
| `helm/pcam-inference/values.yaml` | Default config + secret reference |
| `helm/pcam-inference/templates/_helpers.tpl` | fullname, labels, selectorLabels helpers |
| `helm/pcam-inference/templates/configmap.yaml` | Non-sensitive env vars (RGW endpoint, bucket, key) |
| `helm/pcam-inference/templates/deployment.yaml` | Pod spec with probes, resource limits, rolling update |
| `helm/pcam-inference/templates/service.yaml` | ClusterIP service on port 80 → 8080 |
| `helm/pcam-inference/templates/hpa.yaml` | CPU-based autoscaler, min 1 / max 4 replicas |
| `pyproject.toml` | Project packaging + dev tools |
| `requirements.txt` | Pinned deps via pip-compile |

---

## Infrastructure used

| Layer | System | Details |
|-------|--------|---------|
| Compute | Kaggle T4 GPU | Plan B — swappable for Dardel later |
| Storage | Ceph RGW on turtle | `http://192.168.1.16`, bucket: `ml-artifacts` |
| Serving | K8s on turtle | sought-perch + quick-thrush workers |
| Registry | GHCR | `ghcr.io/ahembal/pcam-inference` |
| CD | ArgoCD | Watches `helm/pcam-inference/` on main branch |
| Secrets | Sealed Secrets | RGW credentials encrypted in git |
| Monitoring | Prometheus + Grafana | Latency, throughput, HPA scaling events |

---

## Deployment flow (target)

```
git push
    └── GitHub Actions
            ├── pytest (serving tests)
            ├── docker build + push → ghcr.io/ahembal/pcam-inference:<sha>
            └── update values.yaml image tag → commit back

ArgoCD (running on cluster) detects drift
    └── helm upgrade pcam ./helm/pcam-inference
            └── rolling update → new pods pull model from RGW → /health 200
```

---

## Answers targeted

| Question | How this project answers it |
|----------|-----------------------------|
| Q5 | Train (Kaggle/Dardel) → evaluate (AUC, F1, confusion matrix) → deploy (GitOps: CI + ArgoCD + K8s) |
| Q7 | Real Helm chart, real K8s cluster, GitOps with ArgoCD, Sealed Secrets, HPA, monitoring |
| Q9 | Written reflection on K8s friction for ML — secrets, image pull, probe tuning, GitOps overhead vs benefit |

---

## Kaggle run details

- Dataset: `andrewmvd/metastatic-tissue-classification-patchcamelyon`
- Model: ResNet-18, ImageNet pretrained
- Epochs: 6 (best at epoch 6)
- Batch size: 128 × N_GPUs, LR scaled linearly
- Optimizer: AdamW, cosine LR schedule, AMP
- Augmentation: RandomRot90 (zero-copy D4), channels-last NHWC

## Results

| Metric | Value |
|--------|-------|
| AUC | 0.9657 |
| Accuracy | 90.0% |
| F1 | 0.897 |
| Train loss (ep 6) | 0.2941 |
| Val loss (ep 6) | 0.3566 |
| Youden threshold | 0.3694 (sens 90.6%, spec 90.4%) |
| 95% sensitivity threshold | 0.2044 (spec 82.5%) |
