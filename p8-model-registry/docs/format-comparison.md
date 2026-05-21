# Model Format Comparison
*p8 — Model Registry*

---

## The four formats

| Format | File | Size | Runtime dependency | Use case |
|--------|------|------|--------------------|----------|
| PyTorch (eager) | `.pt` / `.pth` | ~45 MB | PyTorch (~1.5 GB) | Training, research |
| HuggingFace safetensors | `config.json` + `.safetensors` | ~45 MB | timm / transformers | Sharing, versioning |
| ONNX | `.onnx` | ~45 MB | ONNX Runtime (~50 MB) | CPU production serving |
| TorchScript | `.pt` (traced) | ~45 MB | PyTorch (~1.5 GB) | Mobile, embedded |

The weights are the same size in all formats — the difference is the container
format and the runtime required to execute them.

---

## PyTorch (eager mode)

**What it is:** The raw training format. Weights stored as a Python pickle file.
Execution happens in Python via the PyTorch autograd engine.

**Strengths:**
- No conversion step — training output is directly loadable
- Full Python flexibility — custom ops, dynamic control flow, debugging
- Best for research: modify the model at runtime, inspect activations, iterate fast

**Weaknesses:**
- Pickle serialisation is unsafe — `torch.load()` can execute arbitrary code
  if the file comes from an untrusted source
- Requires the full PyTorch installation (~1.5 GB) to load
- No graph-level optimisations at inference time — Python overhead per operation
- Not portable across frameworks

**When to use:**
During training and development. Not recommended as the final serving format for
production CPU inference.

---

## HuggingFace (safetensors)

**What it is:** A packaging convention, not an execution format. `config.json`
carries model architecture and preprocessing metadata; `.safetensors` carries
the weights in a safe, memory-mappable format.

**Strengths:**
- Safetensors cannot execute code during load — safe to use with third-party weights
- Memory-mapped loading — very fast startup, weights paged in on demand
- Standard for sharing models (HuggingFace Hub)
- Config file carries preprocessing parameters alongside weights — prevents
  the normalisation mismatch that occurred in p1

**Weaknesses:**
- Still requires PyTorch (or JAX/TF) to execute — just the weights format is safer,
  not the runtime
- Framework-specific loading API (timm, transformers) rather than universal

**When to use:**
Model distribution and registry. Use safetensors as the canonical storage format
for model weights — more trustworthy than pickle, compatible with HuggingFace Hub.
Not a solution for removing PyTorch from serving.

---

## ONNX

**What it is:** An open standard for the computation graph. The model's forward
pass is traced and serialised as a graph of standard operations. Any ONNX-compatible
runtime can execute it.

**Strengths:**
- ONNX Runtime is ~50 MB vs PyTorch's ~1.5 GB — 30× smaller container image
- Faster CPU inference: graph is pre-optimised at load time (operator fusion,
  constant folding, memory layout optimisation)
- Hardware-independent: the same file runs on CPU, NVIDIA (via TensorRT), Intel
  (via OpenVINO), ARM, and mobile
- No Python required at inference time — pure C++ execution

**Weaknesses:**
- Conversion is required — not every model converts cleanly
- Dynamic control flow (if statements on tensor values) cannot be represented in ONNX
- Custom PyTorch ops require ONNX custom op registration
- Transformers with variable sequence length require careful export (use optimum)

**PCam benchmark results:**

| | p50 | p95 | p99 | Memory |
|---|---|---|---|---|
| PyTorch | 7.87 ms | 87.86 ms | 283.86 ms | 16.21 MB |
| ONNX | 2.65 ms | 69.54 ms | 69.88 ms | 0.87 MB |
| Speedup | **2.97×** | 1.26× | **4.06×** | **18.6×** |

The p99 improvement (283 ms → 70 ms) eliminates the latency spikes that appear
in PyTorch's eager mode — JIT compilation on first seen input shapes, Python GIL
contention, and GC pauses all contribute to tail latency in PyTorch but not in
the pre-compiled ONNX graph.

**When to use:**
Production CPU inference where PyTorch is not already a dependency. The correct
default for any new serving container where the model can be converted cleanly.

---

## TorchScript

**What it is:** PyTorch's own intermediate representation. The model is JIT-compiled
into a graph that can run without Python.

**Strengths:**
- No third-party runtime — same PyTorch installation
- Supports some dynamic control flow that ONNX cannot
- PyTorch Mobile target — runs on iOS/Android without Python

**Weaknesses:**
- Still requires PyTorch (~1.5 GB) — does not reduce container size
- Slower than ONNX Runtime for CPU inference in most benchmarks
- Limited hardware acceleration targets

**When to use:**
Mobile or embedded deployment where PyTorch Mobile is acceptable. Not recommended
for server-side CPU inference where ONNX is available.

---

## Decision guide

```
Do you need to modify the model during inference?
  Yes → PyTorch eager

Are you distributing or storing the model?
  Yes → safetensors (+ config.json for metadata)

Are you serving on CPU in a container?
  Yes → ONNX (if model converts cleanly)
      → PyTorch if conversion fails or custom ops needed

Are you serving on mobile / embedded?
  Yes → TorchScript (PyTorch Mobile)
  Or  → ONNX (if the target runtime supports it)

Are you serving on GPU in production?
  Yes → TensorRT (takes ONNX as input) for NVIDIA
  Or  → ONNX Runtime with CUDA EP for general GPU
```

---

## What p8 actually does

1. **Storage:** Weights stored as safetensors in Ceph RGW. Registry entry records
   the SHA-256 of the stored file.
2. **Export:** `src/exporters/` produces both HuggingFace (for the registry) and
   ONNX (for serving evaluation).
3. **Validation:** Both exports are checked for output agreement against PyTorch
   before being committed.
4. **Benchmark:** p50/p95/p99 latency and memory measured for PyTorch vs ONNX
   on the serving node (quick-thrush CPU).
5. **Verdict:** If ONNX outputs agree and mean speedup > 1.0, ONNX is recommended.
   The p1 serving container should switch from PyTorch to ONNX Runtime.
