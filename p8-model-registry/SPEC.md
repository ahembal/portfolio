# P8 — Model Registry & Packaging

## What and why

Production ML systems accumulate models over time — different versions, different
architectures, different training runs. Without a registry you lose track of which
model is deployed, what it was trained on, how to reproduce it, and how it compares
to alternatives.

p8 builds a lightweight model registry for this portfolio and explores model
packaging across formats. It addresses a gap that appeared concretely in p1: we
deployed a model without knowing its preprocessing config, causing silent prediction
errors that took multiple debugging sessions to trace.

---

## Problem statement

Three problems this project solves:

1. **Provenance** — which model is running in production, where did it come from,
   what are its metrics, what preprocessing does it expect? Currently scattered across
   values.yaml, RGW buckets, and docs.

2. **Packaging** — a trained PyTorch model has no standard way to carry its preprocessing
   config, class labels, and evaluation metrics alongside the weights. Different frameworks
   (timm, transformers, ONNX) solve this differently. We need to understand the trade-offs.

3. **Serving format** — PyTorch eager mode, TorchScript, and ONNX have different
   latency and dependency profiles. For CPU inference at demo scale, ONNX may outperform
   native PyTorch and remove the torch dependency from the serving container entirely.

---

## System components

### 1. Model registry

A lightweight registry that tracks every model used in this portfolio:

- Model ID, version, architecture, task
- Source (trained / pretrained / fine-tuned)
- Metrics (AUC, accuracy, F1, threshold)
- Preprocessing config (input size, normalization, class mapping)
- Artifact location (HuggingFace Hub ID or RGW path)
- Deployment status (which project, which environment)

Stored as versioned YAML files in git — no database, no server. Simple and auditable.

### 2. Model packager

A CLI tool that takes a trained PyTorch model and produces:

- **HuggingFace format** — `config.json` + `model.safetensors` compatible with timm
- **ONNX** — single portable file, framework-agnostic
- **Registry entry** — YAML metadata file for the registry

Each format is validated against known inputs before being committed.

### 3. Serving benchmark

A benchmark runner that loads the same model in each format and measures:

- Inference latency (p50, p95, p99) on CPU
- Memory footprint
- Output correctness (same predictions across formats)
- Container image size (ONNX removes PyTorch dependency)

Run against the PCam demo patches and the NLP classifier inputs.

---

## What this builds on

- p1 PCam model — ResNet-18, packaging and benchmarking starting point
- p4 NLP classifier — DistilBERT, tests ONNX for transformer models
- `p1-pcam-deployment/docs/model-options.md` — existing model catalogue, feeds into registry

---

## Out of scope

- A hosted registry server or UI (git + YAML is sufficient)
- Automated retraining pipelines
- Model monitoring in production (separate concern)
- Training a new model from scratch for this project

## Relationship to p10

p8 is downstream of training — it tracks, packages, and benchmarks models that
already exist. p10 (model training) is the upstream project that produces those
models. The output of p10 feeds into p8: trained weights get a registry entry,
an evaluation record, and a serving format benchmark before being deployed.
