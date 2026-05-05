# Project 1 — PCam ML Deployment Pipeline
## Progress Tracker
*Last updated: 2026-04-21*

---

## Steps

### Model training
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | Train on Kaggle (T4 GPU) | ✅ Done | ResNet-18 is small enough for fast iteration and fits on a T4 within Kaggle's time limits, but deep enough for histology patch classification. Kaggle provides free T4 GPU — no HPC allocation needed for a binary classification task at this scale. |
| 2 | Download artifacts from Kaggle | ✅ Done | Separating artifacts from the training environment means serving has no dependency on the training codebase. metrics.json, config.json, and threshold.json are separate files so the serving container can load them at startup without re-running evaluation. |
| 3 | Push artifacts to Ceph RGW | ✅ Done | RGW is the handoff point between training (Kaggle) and serving (K8s). The model is never bundled into the container image — a ~45 MB model would inflate image size and slow every CI build. |

### Container image
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | Write Dockerfile | ✅ Done | Multi-stage keeps the runtime image small by discarding build tools. Pulling the model from RGW at startup means the same image serves any model version — no image rebuild needed for model updates. |
| 5 | Switch runtime to distroless image | ✅ Done | Distroless removes shell, package managers, and tools not needed at runtime, reducing the attack surface. The nonroot UID prevents privilege escalation if the container is compromised. |

### Helm chart
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 6 | Write Helm chart | ✅ Done | Helm parameterises everything that changes between environments — image tag, resource limits, RGW endpoint — so the chart is reusable without editing templates. |
| 7 | Add Nginx Ingress template to chart | ✅ Done | The ingress template is defined but disabled by default. Available when DNS is configured, without requiring a cluster DNS dependency to deploy. |
| 8 | Add FastAPI `/metrics` endpoint | ✅ Done | Histogram (not just Counter) captures latency distribution — p50/p95/p99 distinguish typical from worst-case response times, which a simple average hides. |

### CI/CD
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 9 | GitHub Actions CI pipeline | ✅ Done | Writing the new image SHA back to values.yaml is what triggers ArgoCD — the tag change is the GitOps signal. Tests run before build so broken images are never pushed. |
| 10 | RBAC — dedicated service account for ArgoCD | ✅ Done | A namespaced Role limits ArgoCD's permissions to exactly the resources it needs — it cannot modify other namespaces or cluster-wide resources. automountToken: false prevents the token from being available to pods that don't need it. |
| 11 | Install ArgoCD on cluster | ✅ Done | ArgoCD on the cluster closes the GitOps loop — any drift between the cluster and git is detected and reconciled automatically, without manual kubectl apply. |
| 12 | Sealed Secrets for RGW credentials | ✅ Done | The sealed form is encrypted with the cluster's public key and safe to commit to git. This is what makes GitOps viable for secrets — credentials are version-controlled without being exposed. |
| 13 | Wire ArgoCD Application to Helm chart | ✅ Done | The Application CR in git means ArgoCD's own configuration is version-controlled. DNS was deferred — it does not block the core GitOps pattern. |

### Testing & observability
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 14 | Test /predict endpoint | ✅ Done | A dummy-weights test confirms the inference pipeline (preprocessing → forward pass → threshold → response format) is correct before the real model is available — avoids debugging pipeline issues and model issues simultaneously. |
| 15 | Load test + HPA demo | ✅ Done | HPA requires real load to demonstrate — a unit test cannot prove autoscaling fires. Locust with kubectl watch captures the scaling event as verifiable evidence. |
| 16 | Prometheus + Grafana dashboard | ✅ Done | The dashboard makes the system's behavior visible during load tests — latency percentiles confirm the SLO, HPA replicas confirm autoscaling fired. |

### Infra hygiene
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 17 | Fix API server TLS SAN | ✅ Done | The API server TLS certificate did not include the Tailscale IP as a SAN — kubectl over Tailscale got TLS errors. Adding the SAN is the permanent fix; insecure-skip-tls-verify is a workaround that must never be left in production kubeconfigs. |
| 19 | Fix cluster DNS — MAAS DHCP update | ⬜ Deferred | Update MAAS DHCP to hand out `192.168.1.90` as DNS; unblocks ArgoCD live sync. See docs/deployment-troubleshooting.md §7 |

### Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 18 | Write Q5, Q7, Q9 docs | ✅ Done | Answer application questions with evidence from above |

---

## Future work

| # | Task | Notes |
|---|------|-------|
| F1 | Temperature scaling calibration | The model's confidence scores are not calibrated — "100% normal" means a very negative logit, not a true 100% probability. Fit a temperature parameter T on the validation set (`torch.sigmoid(logit / T)`). T is fitted by minimising NLL. Save T to `artifacts/threshold.json` and apply in the serving API before returning confidence. ~30 lines of code. See `docs/model-limitations.md §3`. |
| F2 | Replace demo patches with real PCam images | Current samples in `streamlit/demo/` are from PathMNIST (colorectal tissue) — out-of-distribution for a breast lymph node model. Use `notebooks/extract_demo_patches.ipynb` on Kaggle to extract real PCam patches and replace them. |
| F3 | Fix cluster DNS (Step 19) | Update MAAS DHCP to hand out `192.168.1.90` as DNS; unblocks ArgoCD live sync. See `docs/deployment-troubleshooting.md §7`. |

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
