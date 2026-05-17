# Project 8 — Model Registry & Packaging
## Progress Tracker
*Last updated: 2026-05-17*

---

## Steps

### Phase 1 — Registry
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | Registry schema | ✅ Done | Four YAML schemas: model, experiment, evaluation, deployment. Each has required/optional fields with inline comments. Schemas live in `schemas/`. |
| 2 | Seed registry | ✅ Done | Registry entries for TIAToolbox ResNet-18 (p1) and DistilBERT NLP classifier (p4). Experiment entry for PCam Kaggle training run. Evaluation entry for PCam with partial SHA verification note. Deployment entry for p1 prod. |
| 3 | Registry CLI | ✅ Done | `registry list`, `registry show <id>`, `registry diff <id-a> <id-b>`. Reads YAML files directly. Diff highlights field-level changes between versions. |

### Phase 2 — Packaging
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | HuggingFace packager | ✅ Done | `src/exporters/vision.py` exports ResNet-18 weights to HuggingFace-compatible format (`config.json` + `model.safetensors`). SHA-256 verified on output. |
| 5 | ONNX exporter | ✅ Done | Both ResNet-18 (opset 14) and DistilBERT exported to ONNX via `src/exporters/vision.py` and `src/exporters/text.py`. Output agreement verified against PyTorch with tolerance 1e-4. |
| 6 | Validation suite | ✅ Done | `src/validate.py` runs both packaged formats against fixed inputs and asserts outputs match. Used in benchmark runner as pre-flight check. |

### Phase 3 — Serving benchmark
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 7 | Benchmark runner | ✅ Done | `src/benchmark.py` loads PyTorch and ONNX, measures p50/p95/p99 latency and peak memory over 100 runs (10 warmup). Verdict uses mean speedup across percentiles. |
| 8 | PCam benchmark | ✅ Done | Benchmark Job runs via ArgoCD on quick-thrush. Results in `benchmarks/resnet18-tiatoolbox-pcam-v1-*.yaml`. Latest: p50=16.3× faster, p95=1.15×, p99=1.88×, mean=6.45×. Outputs agree (max diff 2.86e-06). ONNX recommended. |
| 9 | NLP benchmark | ⬜ Todo | Run benchmark on DistilBERT inputs. ONNX is especially relevant — removes the large PyTorch dependency from the serving container. |

### Phase 4 — Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 10 | docs/how-it-works.md | ⬜ Todo | Explain model registry concept, packaging formats, and what the benchmark reveals about format trade-offs. |
| 11 | docs/format-comparison.md | ⬜ Todo | Detailed comparison of PyTorch, HuggingFace, ONNX, TorchScript — when to use each. |

---

## Key decisions

- **SHA verification by source**: HuggingFace models use the platform commit hash (canonical integrity mechanism). RGW models use SHA-256 file hash computed after download. Both verified in `src/verify.py`.
- **Benchmark via ArgoCD**: CI commits a Kubernetes Job manifest to `cluster/manifests/`. ArgoCD applies it. Job runs on quick-thrush and commits results back via SSH deploy key. No cluster credentials in GitHub Secrets, no Tailscale access required from GitHub Actions.
- **Opset 14 for ONNX**: opset 17 caused assertion errors with the ResNet-18 export. Downgraded to 14 which is stable for vision models.
- **Mean of p50/p95/p99 for verdict**: Using minimum was too conservative (a slow p99 hidden by a fast p50 would block a genuinely faster model). Mean balances the three percentiles.

---

## Quick status

```
Phase 1  [███] 3/3 ✅
Phase 2  [███] 3/3 ✅
Phase 3  [██░] 2/3 — NLP benchmark pending
Phase 4  [░░]  0/2 — Docs pending
```
