# How It Works
*p8 — Model Registry & Packaging*

---

## The problem this solves

p1 deployed a ResNet-18 model for PCam patch classification. During deployment,
a silent preprocessing mismatch caused wrong predictions for several hours — the
serving container was normalising with ImageNet statistics while the model had
been trained with TIAToolbox's defaults. There was no single place to look up
which preprocessing config was canonical for that model version.

p8 solves three related problems:

1. **Provenance** — which model is running, trained on what, with what metrics,
   expecting what preprocessing?
2. **Packaging** — how to carry preprocessing config, class labels, and metrics
   alongside the weights in a standard format?
3. **Serving format** — PyTorch is the right training format; is it also the right
   serving format for CPU inference?

---

## System overview

```
Registry (YAML in git)
    ├── registry/models/         ← one entry per model
    ├── registry/experiments/    ← one entry per training run
    ├── registry/evaluations/    ← benchmark results, test set scores
    └── registry/deployments/    ← which model is live in which project

Packager (src/exporters/)
    ├── vision.py                ← ResNet → HuggingFace format + ONNX
    └── text.py                  ← DistilBERT → ONNX via optimum

Benchmark pipeline
    ├── src/benchmark.py         ← PyTorch vs ONNX, p50/p95/p99 + memory
    ├── k8s/benchmark-job.yaml   ← K8s Job spec
    └── benchmarks/              ← results committed to git daily
```

---

## The registry

The registry is a set of YAML files in git. No database, no server, no API.

**Why YAML in git:**
- Auditable — every change has a commit, an author, and a timestamp
- Diffable — `registry diff <id-a> <id-b>` shows exactly what changed between
  model versions
- Zero infrastructure — readable on any machine with git, no service to maintain
- Reviewable — registry entries go through the same PR process as code

Each schema enforces required fields. `src/validate.py` checks entries against
schemas before they can be committed.

### Model entry

```yaml
id: resnet18-tiatoolbox-pcam-v1
task: image-classification
architecture: resnet18
source: pretrained-finetuned
dataset: pcam
metrics:
  auc: 0.9901
  accuracy: 0.9512
preprocessing:
  input_size: [96, 96]
  normalisation: tiatoolbox-default
  channel_order: RGB
artifacts:
  huggingface_id: <hf-repo-id>
  rgw_path: s3://pcam-models/resnet18-tiatoolbox-pcam-v1/model.safetensors
  sha256: <hash>
```

The `preprocessing` block is what prevents the p1 incident from recurring. Any
code loading this model reads the normalisation config from the registry entry,
not from memory or documentation.

### Experiment entry

Links training run to model: which dataset, which hyperparameters, which hardware,
which checkpoint produced the registered model.

### Evaluation entry

Benchmark results — test set metrics, benchmark YAML path, serving format
recommendation. This is the output of `src/benchmark.py`.

### Deployment entry

Which registry model is live in which project and environment. Updated when a
new model is deployed, creating a traceable chain: experiment → model → evaluation
→ deployment.

---

## The packager

`src/exporters/` converts a trained PyTorch model to two portable formats.

### HuggingFace format

Produces `config.json` + `model.safetensors`. The config carries preprocessing
parameters, class labels, and architecture metadata alongside the weights.
Compatible with the `timm` and `transformers` loading APIs.

Safetensors is preferred over `.pt` (pickle) because it is safe to load from
untrusted sources — pickle can execute arbitrary Python during deserialization,
safetensors cannot.

### ONNX

Produces a single `.onnx` file containing the full computation graph and weights.
Framework-agnostic — runs with ONNX Runtime (~50 MB) without PyTorch (~1.5 GB).

Both formats are validated against fixed inputs before being committed to the
registry — output agreement between PyTorch and the exported format is a hard
requirement, not optional.

---

## The benchmark pipeline

The benchmark runs automatically when a model registry entry changes, triggered
by CI and orchestrated through ArgoCD:

```
Registry entry updated
        │
        ▼
GitHub Actions (p8-run-benchmark.yml)
  commits k8s/benchmark-job.yaml to cluster/manifests/
        │
        ▼
ArgoCD detects manifest
  applies Job to quick-thrush
        │
        ▼
Job runs on quick-thrush:
  clones repo → runs benchmark → commits benchmarks/<result>.yaml → pushes
        │
        ▼
Result in git, linked from evaluation registry entry
```

**Why Jobs via ArgoCD, not kubectl from CI:**
The cluster is on a private Tailscale network. GitHub Actions runners cannot
reach it. By committing Job manifests to git, CI delegates execution to ArgoCD
which already has cluster access — no cluster credentials leave the cluster.

### What is measured

`src/benchmark.py` loads the same model in PyTorch and ONNX Runtime, runs 100
inferences (10 warmup discarded), and records:

| Metric | Why |
|--------|-----|
| p50 latency | Typical performance — what most requests experience |
| p95 latency | Tail latency — what 1 in 20 requests experiences |
| p99 latency | Extreme tail — what 1 in 100 requests experiences |
| Peak memory | RSS delta — how much additional RAM inference uses |
| Output agreement | Max absolute diff between PyTorch and ONNX outputs |

The verdict uses mean speedup across p50/p95/p99. Using minimum was too
conservative (a slow p99 hidden by a fast p50 would block a genuinely faster
model). Mean balances the three percentiles.

### PCam benchmark results (2026-05-21)

| Format | p50 | p95 | p99 | Memory |
|--------|-----|-----|-----|--------|
| PyTorch | 7.87 ms | 87.86 ms | 283.86 ms | 16.21 MB |
| ONNX | 2.65 ms | 69.54 ms | 69.88 ms | 0.87 MB |
| Speedup | **2.97×** | 1.26× | **4.06×** | **18.6×** |

**Verdict: ONNX recommended** — outputs agree (max diff 2.86e-06), mean speedup
2.76×. The p99 improvement is especially notable: ONNX eliminates the long-tail
latency spikes that appear in PyTorch (283 ms → 70 ms).

Output agreement is within tolerance (1e-4) — the floating point difference
(2.86e-06) is numerical noise from different compute kernels, not a semantic
difference in predictions.

---

## Relationship to other projects

| Project | Connection |
|---------|-----------|
| p1 | Source of ResNet-18 weights. p8 packages and benchmarks them. Registry entry tracks the p1 deployment. |
| p4 | Source of DistilBERT weights. p8 exports to ONNX via HuggingFace optimum. |
| p10 | p10 training runs will produce new model entries in p8. The registry will track BEETLE experiment runs, per-class Dice scores, and Grand Challenge submissions. |
