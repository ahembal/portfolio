# p1 — PCam Deployment

Binary tissue classification (tumour / normal) on 96×96 H&E patches, served via FastAPI on Kubernetes with GitOps CI/CD.

## What it demonstrates

- End-to-end ML deployment: weights → FastAPI → Docker → Kubernetes → live endpoint
- GitOps: GitHub Actions builds image → updates Helm values → ArgoCD syncs cluster
- Production patterns: distroless container, non-root UID, liveness/readiness probes, HPA autoscaling
- Load testing with Locust to validate horizontal scaling under concurrent requests

## Stack

| Component | Choice |
|-----------|--------|
| Model | ResNet-18 via TIAToolbox, trained on PCam (Kaggle T4) |
| Serving | FastAPI — `/predict`, `/health`, `/metrics` |
| Container | `gcr.io/distroless/python3` — no shell, no package manager |
| Orchestration | Helm chart, ArgoCD GitOps |
| Storage | Model weights on Ceph RGW, loaded at pod startup |
| Autoscaling | HPA on CPU utilisation, 1–5 replicas |

## Quick start

```bash
# Predict on a patch image
curl -X POST http://<node-ip>:30100/predict \
  -F "file=@patch.png" | jq .

# Health check
curl http://<node-ip>:30100/health
```

## Key numbers

- PCam test AUC: **0.9901** (accuracy: 95.1%)
- ONNX p50 latency: **2.65 ms** (2.97× faster than PyTorch — see [p8](../p8-model-registry/))
- Container image: ~200 MB (distroless base)

## Related

- **[p8](../p8-model-registry/)** — packages and benchmarks this model (ONNX vs PyTorch, format comparison)
- **[p10](../p10-model-training/)** — trains a segmentation model in the same H&E pathology domain
