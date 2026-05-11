# Project 8 — Model Registry & Packaging
## Progress Tracker
*Last updated: 2026-05-11*

---

## Steps

### Phase 1 — Registry
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | Registry schema | ⬜ Todo | Define the YAML schema for a registry entry — what fields are required, what's optional. Schema drives everything else. |
| 2 | Seed registry | ⬜ Todo | Create registry entries for all models currently in use: TIAToolbox ResNet-18 (p1), DistilBERT NLP classifier (p4). Surfaces gaps in our current model metadata. |
| 3 | Registry CLI | ⬜ Todo | `registry list`, `registry show <id>`, `registry diff <id-a> <id-b>`. Simple read-only queries against the YAML files. |

### Phase 2 — Packaging
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | HuggingFace packager | ⬜ Todo | Given a PyTorch model + config, produce `config.json` + `model.safetensors` compatible with timm. Validates preprocessing config is correct before packaging. |
| 5 | ONNX exporter | ⬜ Todo | Export ResNet-18 and DistilBERT to ONNX. Verify predictions match PyTorch output on same inputs. |
| 6 | Validation suite | ⬜ Todo | Run both packaged formats against a fixed set of inputs and assert outputs match within tolerance. Packaging is only complete when validation passes. |

### Phase 3 — Serving benchmark
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 7 | Benchmark runner | ⬜ Todo | Load each format (PyTorch eager, TorchScript, ONNX) and measure latency, memory, container size on the same hardware (quick-thrush CPU). |
| 8 | PCam benchmark | ⬜ Todo | Run benchmark on 8 demo patches. Compare formats on latency and correctness. |
| 9 | NLP benchmark | ⬜ Todo | Run benchmark on NLP classifier inputs. ONNX is especially relevant here — removes the large PyTorch dependency from the serving container. |

### Phase 4 — Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 10 | docs/how-it-works.md | ⬜ Todo | Explain model registry concept, packaging formats, and what the benchmark reveals about format trade-offs. |
| 11 | docs/format-comparison.md | ⬜ Todo | Detailed comparison of PyTorch, HuggingFace, ONNX, TorchScript — when to use each. |

---

## Quick status

```
Phase 1  [░░░] 0/3
Phase 2  [░░░] 0/3
Phase 3  [░░░] 0/3
Phase 4  [░░]  0/2
```
