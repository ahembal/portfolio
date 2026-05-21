# p8 — Model Registry & Packaging

Lightweight model registry (YAML in git), ONNX packaging, and an automated serving format benchmark — triggered by ArgoCD, running on the actual serving node.

## What it demonstrates

- Model provenance: every model in the portfolio has a registry entry tracking source, metrics, preprocessing config, and artifact location
- Format benchmarking: PyTorch vs ONNX Runtime on CPU — p50/p95/p99 latency and memory
- ArgoCD-triggered K8s Jobs: CI commits a Job manifest; ArgoCD applies it; results commit back to git — no cluster credentials in CI
- Output agreement validation: ONNX export is only accepted if predictions match PyTorch within tolerance

## PCam benchmark results (2026-05-21)

| Format | p50 | p95 | p99 | Memory |
|--------|-----|-----|-----|--------|
| PyTorch | 7.87 ms | 87.86 ms | 283.86 ms | 16.21 MB |
| ONNX | 2.65 ms | 69.54 ms | 69.88 ms | 0.87 MB |
| Speedup | **2.97×** | 1.26× | **4.06×** | **18.6×** |

**Verdict: ONNX recommended.** Outputs agree (max diff 2.86e-06). p99 improvement is especially significant — ONNX eliminates the long-tail latency spikes from Python/PyTorch overhead.

## Registry CLI

```bash
# List all registered models
python src/cli.py registry list

# Show a specific entry
python src/cli.py registry show resnet18-tiatoolbox-pcam-v1

# Diff two model versions
python src/cli.py registry diff resnet18-tiatoolbox-pcam-v1 resnet18-tiatoolbox-pcam-v2
```

## Stack

| Component | Choice |
|-----------|--------|
| Registry | YAML files in git (no database) |
| Packaging | `safetensors` (HuggingFace format) + ONNX |
| Benchmark | `onnxruntime`, `psutil`, K8s Job |
| CI trigger | GitHub Actions → ArgoCD → K8s Job |

See [`docs/how-it-works.md`](docs/how-it-works.md) for the full pipeline and [`docs/format-comparison.md`](docs/format-comparison.md) for when to use each serving format.

## Related

- **[p1](../p1-pcam-deployment/)** — the ResNet-18 model packaged and benchmarked here
- **[p4](../p4-nlp-deployment/)** — the DistilBERT model (NLP benchmark pending)
- **[p10](../p10-model-training/)** — future training runs will be logged here
