# Implementation Notes — P1 PCam Deployment
*Last updated: 2026-04-21*

This document describes how the project was built: structure chosen, problems hit during development, and decisions made along the way. For how the finished product works see `how-it-works.md`.

---

## Training (train/)

- ResNet-18, 6 epochs, AUC 0.9657, Acc 90.0%, F1 0.897
- Plan A was Dardel SLURM (`submit_dardel.sh`), fell back to Kaggle T4 (plan B) because Kaggle was faster to set up
- Artifacts produced: `best_model.pt`, `metrics.json`, `config.json`, `threshold.json`
- `push_kaggle_artifacts.py` used to push from Kaggle download → RGW

## Container (serving/Dockerfile)

- Multi-stage: builder stage installs deps, runtime stage uses `distroless/python3-debian12:nonroot`
- Model pulled from RGW at container startup (not baked in)
- `TRANSFORMERS_CACHE` or similar env var not needed here (PyTorch, not HuggingFace) — note for p4

## Helm chart (helm/pcam-inference/)

- Standard structure: deployment, service, configmap, hpa, _helpers, values
- HPA: CPU-based, min 1 / max 4 replicas
- Ingress template exists but gated on `ingress.enabled=false` (DNS step 19 deferred)

## CI/CD

- GitHub Actions: pytest → docker build → push GHCR → update values.yaml tag
- `update-tags` step writes the new SHA back to `values.yaml` — this is the ArgoCD trigger
- ArgoCD Application CR committed and watching `helm/pcam-inference/` on main

## Cluster issues hit during deployment

- API server TLS SAN missing Tailscale IP → kubectl over Tailscale failed with TLS error. Fixed: `kubeadm init phase certs apiserver --apiserver-cert-extra-sans 100.123.23.6`
- NetworkPolicies blocked ArgoCD's internal DNS resolution → removed for stability (security debt noted)
- Sealed Secrets for RGW creds + GHCR pull token — sealed and committed

## Testing

- `/predict` tested with dummy weights to confirm pipeline correctness before real model
- Load test: Locust 20 users → 396% CPU → HPA scaled 1→4 replicas; events in `hpa-watch.log`
- Prometheus + Grafana: kube-prometheus-stack, ServiceMonitor with `release: kube-prom` label, 5-panel dashboard
