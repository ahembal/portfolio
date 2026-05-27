# Portfolio Documentation Index
*Organized by topic. Each project also has its own `docs/` folder — this index is the map.*

---

## Start here — how each project works

| Project | Entry point |
|---------|-------------|
| p1 — PCam Deployment | [how-it-works.md](../p1-pcam-deployment/docs/how-it-works.md) |
| p2 — Metadata Ingestion | [how-it-works.md](../p2-metadata-ingestion/docs/how-it-works.md) |
| p3 — Spark Benchmark | [how-it-works.md](../p3-spark-benchmark/docs/how-it-works.md) |
| p4 — NLP Deployment | [how-it-works.md](../p4-nlp-deployment/docs/how-it-works.md) |
| p5 — Dev Practices | [q10-dev-practices.md](../p5-devpractices-site/docs/q10-dev-practices.md) |
| p6 — Research Agent | [how-it-works.md](../p6-research-agent/docs/how-it-works.md) |
| p7 — RAG Evaluation | [how-it-works.md](../p7-rag-evaluation/docs/how-it-works.md) |
| p8 — Model Registry | [how-it-works.md](../p8-model-registry/docs/how-it-works.md) |
| p9 — Knowledge Graph | [how-it-works.md](../p9-knowledge-graph/docs/how-it-works.md) |

---

## Topic index

### Large-scale data processing & memory

How to handle data that doesn't fit in memory — streaming, chunking, distributed processing.

- [p2 — Scalability analysis](../p2-metadata-ingestion/docs/q6-scalability.md) — connection pool arithmetic under HPA, streaming uploads vs `file.read()`, when to use pre-signed S3 URLs
- [p3 — Scalability](../p3-spark-benchmark/docs/scalability.md) — Spark vs Pandas for large datasets, distributed processing
- [p3 — HPC narrative](../p3-spark-benchmark/docs/q8-hpc-narrative.md) — running ETL at scale on HPC clusters (Dardel/Pelle)

---

### ML deployment

Serving trained models in production — FastAPI, Docker, Kubernetes, autoscaling.

- [p1 — ML deployment design](../p1-pcam-deployment/docs/q5-ml-deploy.md) — why FastAPI, model loading patterns, latency targets
- [p1 — Docker + Helm + K8s](../p1-pcam-deployment/docs/q7-docker-helm-k8s.md) — distroless containers, Helm chart structure, ArgoCD GitOps
- [p4 — NLP deployment](../p4-nlp-deployment/docs/q5-nlp-deploy.md) — same production patterns applied to a text classification model
- [p8 — Benchmark design](../p8-model-registry/docs/benchmark-design.md) — ONNX vs PyTorch latency, format comparison methodology

---

### Agent design & RAG

How LLM agents and retrieval systems are built, evaluated, and grounded.

- [p6 — Agent design rationale](../p6-research-agent/docs/q-agent-design.md) — why LangGraph, tool design, SSE streaming, prompt engineering, FAIR data
- [p6 — Answer quality & provenance](../p6-research-agent/docs/answer-quality.md) — what hallucination checking does and does not catch
- [p6 — Tools](../p6-research-agent/docs/tools.md) — PubMed, UniProt, ChromaDB tool implementations
- [p7 — Retrieval design](../p7-rag-evaluation/docs/retrieval-design.md) — BM25 vs dense retrieval, RRF fusion, reranking
- [p7 — Evaluation design](../p7-rag-evaluation/docs/evaluation-design.md) — LLM-as-judge methodology, benchmark construction
- [p9 — RAG vs knowledge graph comparison](../p9-knowledge-graph/docs/comparison.md) — when structured queries beat vector search

---

### Kubernetes & infrastructure

Deployment patterns, Helm charts, ArgoCD, cluster operations.

- [p2 — Architecture](../p2-metadata-ingestion/docs/architecture.md) — component roles, data flow, why async queue
- [p1 — K8s issues & lessons](../p1-pcam-deployment/docs/k8s-issues.md) — real problems hit during cluster deployment
- [p6 — Deployment troubleshooting](../p6-research-agent/docs/deployment-troubleshooting.md) — ChromaDB client types, seed corpus, Ollama PVC setup
- [p9 — Deployment troubleshooting](../p9-knowledge-graph/docs/deployment-troubleshooting.md) — SPARQL endpoint, graph rebuild issues

---

### Security

Container hardening, secrets management, input validation, data privacy.

- [p1 — Security & compliance](../p1-pcam-deployment/docs/security-compliance.md) — distroless, non-root, SealedSecrets
- [p5 — Privacy](../p5-devpractices-site/docs/privacy.md) — GDPR considerations, data handling
- [p9 — Security](../p9-knowledge-graph/docs/security.md) — SPARQL injection, network policies
- [p5 — Dev practices](../p5-devpractices-site/docs/q10-dev-practices.md) — security section covers patterns used across p1–p4

---

### Observability

Prometheus metrics, Grafana dashboards, structured logging.

- [p5 — Observability](../p5-devpractices-site/docs/observability.md) — metric types (Counter/Histogram/Gauge), what each project exposes
- [p6 — Observability](../p6-research-agent/docs/observability.md) — agent-specific metrics, query latency, tool call tracking
- [p2 — Runbook](../p2-metadata-ingestion/docs/runbook.md) — how to read the Grafana dashboard, queue depth signals

---

### CI/CD & dev practices

GitHub Actions, GitOps, conventional commits, code quality.

- [p5 — Dev practices](../p5-devpractices-site/docs/q10-dev-practices.md) — full synthesis of practices across the portfolio
- [p5 — GitOps image updates](../p5-devpractices-site/docs/gitops-image-updates.md) — how CI pushes images and ArgoCD picks them up
- [p5 — Conventional commits](../p5-devpractices-site/docs/conventional-commits.md) — commit message format used throughout this repo
- [p5 — Coding standards](../p5-devpractices-site/docs/coding-standards.md) — Ruff, Pydantic, type hints, documentation standards

---

### Model training & evaluation

Training decisions, dataset choices, evaluation methodology.

- [p1 — Training design](../p1-pcam-deployment/docs/training-design.md) — ResNet-18 on PCam, why TIAToolbox, Kaggle T4 compute
- [p4 — Training design](../p4-nlp-deployment/docs/training-design.md) — DistilBERT on PubMed RCT, fine-tuning decisions
- [p8 — Trust model](../p8-model-registry/docs/trust-model.md) — SHA verification, registry design rationale
- [p6 — Llama 3.1 8B](../p6-research-agent/docs/llama-3.1-8b.md) — why this model, quantisation, CPU inference constraints

---

### Troubleshooting & runbooks

When things break — how to diagnose and fix.

- [p1 — Deployment troubleshooting](../p1-pcam-deployment/docs/deployment-troubleshooting.md)
- [p2 — Runbook](../p2-metadata-ingestion/docs/runbook.md)
- [p6 — Deployment troubleshooting](../p6-research-agent/docs/deployment-troubleshooting.md)
- [p9 — Deployment troubleshooting](../p9-knowledge-graph/docs/deployment-troubleshooting.md)

