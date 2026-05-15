# ONNX — Open Neural Network Exchange
*p8 — Model Registry*

---

## What it is

ONNX is a standard file format for machine learning models. It separates the
model definition from the framework used to train it. A model trained in PyTorch
can be saved as ONNX and run with any ONNX-compatible runtime — without PyTorch
installed.

Think of it like a PDF: the document is independent of the word processor that
created it.

---

## Why it exists

Training frameworks (PyTorch, TensorFlow, JAX) are designed for research —
flexible, Python-heavy, large dependencies. Inference in production has different
requirements: fast, small, portable, hardware-optimised.

ONNX is the handoff point between the two worlds:

```
Research / Training          Production / Inference
─────────────────────────────────────────────────────
PyTorch (flexible, ~1.5GB)  →  ONNX Runtime (~50MB)
TensorFlow                   →  ONNX Runtime
JAX                          →  ONNX Runtime
                             →  TensorRT (NVIDIA GPU)
                             →  OpenVINO (Intel)
                             →  Windows ML
                             →  Mobile (iOS/Android)
```

---

## How a model becomes ONNX

PyTorch traces the model's computation graph by running a forward pass with a
dummy input. The graph — every operation and its shape — is saved to a `.onnx`
file.

```python
import torch
import torch.onnx

model.eval()
dummy_input = torch.randn(1, 3, 96, 96)   # same shape as real input

torch.onnx.export(
    model,
    dummy_input,
    "model.onnx",
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={"input": {0: "batch_size"}},  # allow variable batch size
)
```

The `.onnx` file contains:
- The computation graph (every layer, every operation)
- The weights (the learned parameters)
- Input/output shape definitions

---

## How ONNX Runtime executes it

ONNX Runtime reads the graph and executes it using optimised C++ kernels.
It does not need PyTorch, Python, or any ML framework — just the runtime library.

```
model.onnx
    │
    ▼
onnxruntime.InferenceSession("model.onnx")
    │
    ▼
session.run(["output"], {"input": numpy_array})
    │
    ▼
numpy array output
```

The input and output are plain NumPy arrays. No tensors, no PyTorch, no GPU
required.

---

## Performance characteristics

On CPU inference:

| | PyTorch | ONNX Runtime |
|---|---|---|
| Dependency size | ~1.5 GB | ~50 MB |
| Cold start | ~3s (import torch) | ~0.1s |
| Inference latency | baseline | typically 2–4× faster |
| Memory footprint | higher | lower |

ONNX Runtime is faster because:
- Graph is pre-optimised at load time (operator fusion, constant folding)
- No Python overhead per operation — pure C++ execution
- Compiled for the target CPU's instruction set (AVX2, etc.)

---

## What cannot be converted

Not every PyTorch model converts cleanly to ONNX:

- **Dynamic control flow** — `if` statements that depend on tensor values
- **Python-side logic** — code that runs outside the model's `forward()` method
- **Custom operators** — operations not in the ONNX standard operator set

Transformers (like DistilBERT) have known conversion challenges — variable
sequence length, attention masks. HuggingFace's `optimum` library handles these
correctly via `optimum-cli export onnx`.

---

## Who uses it in production

- **Microsoft Azure ML** — primary driver behind the ONNX standard
- **AWS SageMaker** — supports ONNX as a deployment format
- **NVIDIA TensorRT** — uses ONNX as input, optimises for GPU
- **Intel OpenVINO** — uses ONNX as input, optimises for Intel CPU
- **HuggingFace** — ships ONNX exports for most transformer models via `optimum`
- **Windows ML** — runs ONNX models on Windows devices (on-device AI)
- Any company training in PyTorch but serving in lean production environments

---

## How p8 uses ONNX

ONNX Runtime is consistently faster than PyTorch on CPU inference for standard
architectures — this is well established. The speed and size gains are real.

p8 benchmarks both formats for two specific reasons:

**1. Verify output agreement before switching.**
An ONNX export that produces different predictions than PyTorch is a broken
export — it cannot be used regardless of speed. Running both on identical inputs
confirms the exported model is correct before replacing the production format.

**2. Measure the actual gain on our hardware.**
"2–4× faster" is a general claim across many models and machines. The benchmark
measures the actual number on `quick-thrush` CPU with our specific models —
ResNet-18 (vision) and DistilBERT (text). This is what justifies the decision
to switch the serving container from PyTorch to ONNX Runtime.

The output of the benchmark answers two questions:
- Are the predictions identical? (correctness gate)
- How much faster is ONNX on this hardware? (justification for switching)

See `docs/benchmark-design.md` for the benchmark methodology.
