# Benchmark Design
*p8 — Model Registry*

---

## Purpose

Measure whether exporting a registered model to ONNX is worth the conversion
complexity. Two questions must both be answered before switching a serving
container from PyTorch to ONNX Runtime:

1. **Correctness** — do PyTorch and ONNX produce identical predictions?
2. **Performance** — how much faster is ONNX on our specific hardware?

---

## What is measured

For each model × format (PyTorch, ONNX) combination:

| Metric | How measured |
|--------|-------------|
| p50 latency | median of N inference runs |
| p95 latency | 95th percentile of N inference runs |
| p99 latency | 99th percentile of N inference runs |
| Peak memory | RSS delta during inference (psutil) |
| Output agreement | max absolute difference between PyTorch and ONNX outputs |

N = 100 runs. First 10 runs discarded as warmup.

---

## Inputs

Benchmarks run on **synthetic inputs** — randomly generated tensors with the
correct shape and dtype for each model. This ensures:

- Reproducible results (same seed → same inputs)
- No dependency on demo files being present
- Works in CI without external data

For vision models: `torch.randn(1, 3, 96, 96)` — same shape as PCam patches.
For text models: random token IDs with max sequence length.

---

## Framework design

```
benchmark.py
    │
    ├── load_pytorch(registry_entry)     ← loads model via timm or transformers
    ├── export_onnx(model, input_shape)  ← torch.onnx.export
    ├── run_pytorch(model, inputs, N)    ← N inference runs, returns latencies
    ├── run_onnx(session, inputs, N)     ← N inference runs, returns latencies
    └── compare_outputs(pt_out, onnx_out) ← checks agreement within tolerance
```

Each benchmark run produces a YAML result file in `benchmarks/`:

```yaml
id: resnet18-tiatoolbox-pcam-v1-2026-05-15
model_id: resnet18-tiatoolbox-pcam
model_version: v1
date: "2026-05-15"
hardware: quick-thrush-cpu
n_runs: 100
warmup_runs: 10

pytorch:
  p50_ms: 180.4
  p95_ms: 210.3
  p99_ms: 240.1
  memory_mb: 145.2

onnx:
  p50_ms: 52.1
  p95_ms: 61.4
  p99_ms: 70.2
  memory_mb: 48.7

output_agreement:
  max_abs_diff: 0.000012
  tolerance: 0.0001
  passed: true

speedup:
  p50: 3.46x
  p95: 3.42x
  p99: 3.42x

verdict: ONNX recommended — outputs agree, consistent 3.4x speedup
```

---

## Exporters

Different model types require different ONNX export strategies:

**Vision models (ResNet-18):**
Standard `torch.onnx.export` with dynamic batch size axis.

**Transformer models (DistilBERT):**
HuggingFace `optimum` library — handles attention masks, variable sequence
length, and tokenizer integration correctly. Direct `torch.onnx.export` on
transformers produces incorrect graphs.

---

## Verdict criteria

| Condition | Verdict |
|-----------|---------|
| Output agreement fails | ✗ Export broken — do not use ONNX |
| Output agrees, speedup < 1.5× | — Marginal gain, not worth complexity |
| Output agrees, speedup ≥ 1.5× | ✓ ONNX recommended |

The verdict is recorded in the result file and referenced in the deployment
decision.
