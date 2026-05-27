# ML Engineering Portfolio

Ten projects covering the full ML stack: data pipelines, model training, serving, knowledge graphs, agents, and evaluation — all running on a self-managed Kubernetes homelab with production-grade CI/CD.

---

## Projects

| # | Project | What it demonstrates | Stack | Status |
|---|---------|---------------------|-------|--------|
| [p1](p1-pcam-deployment/) | PCam Deployment | CNN → FastAPI → K8s, GitOps, HPA load testing | PyTorch, TIAToolbox, Helm, ArgoCD | ✅ Live |
| [p2](p2-metadata-ingestion/) | Metadata Ingestion | Async file pipeline: HTTP → queue → Postgres + S3 | FastAPI, Celery, Redis, PostgreSQL, Ceph RGW | ✅ Live |
| [p3](p3-spark-benchmark/) | Spark Benchmark | Pandas vs Spark vs GPU at scale on HPC | PySpark, RAPIDS cuDF, Dardel A100 | ✅ Results |
| [p4](p4-nlp-deployment/) | NLP Deployment | DistilBERT fine-tune → serve text classification | HuggingFace Transformers, FastAPI, Helm | 🔄 In progress |
| [p5](p5-devpractices-site/) | Dev Practices | Cross-project patterns: CI/CD, security, observability, compliance | GitHub Actions, Helm, EU AI Act | 🔄 Content ready |
| [p6](p6-research-agent/) | Research Agent | LangGraph agent with PubMed + UniProt + RAG | LangGraph, Ollama, FastAPI, ChromaDB | ✅ Live |
| [p7](p7-rag-evaluation/) | RAG Evaluation | Hybrid retrieval, reranking, LLM-as-judge evaluation | BM25 + dense search, RRF, cross-encoder, Ollama | 🔄 In progress |
| [p8](p8-model-registry/) | Model Registry | Model provenance, ONNX packaging, serving format benchmark | ONNX Runtime, safetensors, K8s Jobs, ArgoCD | 🔄 In progress |
| [p9](p9-knowledge-graph/) | Knowledge Graph | RDF graph over PubMed/UniProt, SPARQL endpoint, RAG vs SPARQL comparison | RDFlib, Apache Jena Fuseki, EDAM/OBI ontologies | ✅ Live |
| [p10](p10-model-training/) | Model Training | WSI segmentation training pipeline, BEETLE Grand Challenge submission | PyTorch, Accelerate, TIAToolbox, nnU-Net | 🔄 In progress |

---

## Architecture

```
                        Kubernetes cluster (quick-thrush, homelab)
                        ┌──────────────────────────────────────────┐
                        │                                          │
  GitHub Actions ──────▶│  ArgoCD (GitOps)                        │
  (CI/CD, GHCR)         │    ├── p1  FastAPI  (PCam inference)    │
                        │    ├── p2  FastAPI + Celery (ingestion) │
                        │    ├── p4  FastAPI  (NLP classifier)    │
                        │    ├── p6  FastAPI + Streamlit (agent)  │
                        │    ├── p7  FastAPI + Streamlit (RAG)    │
                        │    └── p9  Jena Fuseki (SPARQL)         │
                        │                                          │
                        │  Ceph RGW (object storage)              │
                        │    └── model weights, graphs, datasets  │
                        │                                          │
                        │  p8 Benchmark Jobs (ArgoCD-triggered)   │
                        └──────────────────────────────────────────┘

  Dardel (KTH HPC, A100 GPUs)
    └── p3 Spark/GPU benchmarks
    └── p10 model training

  Grand Challenge (AWS)
    └── p10 BEETLE inference evaluation
```

---

## Key technical decisions

**GitOps over direct kubectl** — CI never touches the cluster directly. GitHub Actions commits manifests; ArgoCD applies them. No cluster credentials in CI, no Tailscale access from external runners.

**ONNX for CPU serving** — p8 benchmarks show ONNX Runtime achieves p50=2.97× faster than PyTorch on CPU for ResNet-18 with identical outputs (max diff 2.86e-06). The PyTorch dependency (~1.5 GB) is removed from serving containers entirely.

**Adaptive retrieval in p7** — queries are classified as simple or complex; simple queries take the fast path (dense-only), complex queries take the slow path (BM25 + dense → RRF fusion → cross-encoder reranking). Avoids paying reranking cost on every query.

**UniProt-inverted citations for p9** — graph is seeded from 10 canonical proteins; PubMed papers are discovered by inverting UniProt's citation edges. No NLP, fully deterministic, connects directly into the linked data ecosystem.

**nnU-Net as p10 baseline** — the BEETLE challenge organisers used nnU-Net-for-Pathology for technical validation, achieving 0.92 overall Dice on the development set. It is the correct first baseline before any foundation model experimentation.

---

## Infrastructure

- **Cluster:** 3-node K8s homelab, Ceph RGW for object storage
- **CI/CD:** GitHub Actions → GHCR → ArgoCD GitOps
- **HPC:** Dardel (KTH) — AMD MI250X and NVIDIA A100 nodes
- **Observability:** Prometheus + Grafana, liveness/readiness probes
- **Security:** Non-root containers, Kubernetes Secrets, RBAC, network policies

See [BIGPICTURE.md](BIGPICTURE.md) for a full cross-project dependency map and [PRODUCTION-READINESS.md](PRODUCTION-READINESS.md) for production gap analysis.

---

## How to navigate

- **[docs/INDEX.md](docs/INDEX.md)** — topic-based map of all documentation across projects (large-scale data, ML deployment, security, observability, etc.)
- Each project has its own `SPEC.md` (what and why), `PROGRESS.md` (current status), and `docs/` directory with a table of contents in the README.
- For the research agent (p6) and knowledge graph (p9), `docs/how-it-works.md` is the best entry point.
