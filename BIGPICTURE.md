# Portfolio — Big Picture
*Last updated: 2026-05-04*

A set of seven projects that together demonstrate end-to-end ML engineering:
training, serving, data pipelines, scale, agents, and evaluation. Each project is
independent but they share the same infrastructure and engineering patterns.

---

## The projects

| # | Project | What it demonstrates | Status |
|---|---------|---------------------|--------|
| p1 | [PCam ML Deployment](p1-pcam-deployment/) | Train a CNN → serve via FastAPI → K8s + GitOps | ✅ Live |
| p2 | [Metadata Ingestion](p2-metadata-ingestion/) | Async file pipeline: HTTP → Celery → Postgres + S3 | ✅ Live |
| p3 | [Spark Benchmark](p3-spark-benchmark/) | Pandas vs Spark vs GPU at scale on real HPC clusters | 🔄 HPC jobs pending |
| p4 | [NLP Deployment](p4-nlp-deployment/) | Fine-tune DistilBERT → serve text classification | 🔄 Model trained, serving in progress |
| p5 | [Dev Practices Site](p5-devpractices-site/) | Cross-project patterns: CI/CD, testing, security, observability | 🔄 Content ready, site not built |
| p6 | [Research Agent](p6-research-agent/) | LangGraph agent with PubMed + UniProt + RAG | ✅ Live |
| p7 | [RAG Evaluation](p7-rag-evaluation/) | Hybrid search, reranking, adaptive retrieval, LLM-as-judge evaluation | 🔄 In progress |

---

## How they relate

```
Training                    Serving                     Infrastructure
──────────────────────────────────────────────────────────────────────
p1: Kaggle T4 (ResNet-18)  → FastAPI on K8s            ← Helm + ArgoCD GitOps
p4: Kaggle T4 (DistilBERT) → FastAPI on K8s (WIP)      ← same pattern as p1

Data pipeline
──────────────
p2: HTTP upload → Redis → Celery worker → Postgres + Ceph RGW
    (the kind of pipeline that feeds model training data)

Scale
──────────────
p3: 1M–40M rows, Pandas vs Spark vs GPU (AMD MI250X on Dardel)
    (benchmarks the compute layer p1/p2 depend on at large scale)

Agents
──────────────
p6: LLM (Llama 3.1 8B via Ollama) + LangGraph + PubMed + UniProt + RAG
    (shows what sits on top of the serving infrastructure)

Cross-cutting (p5 documents all of the above)
──────────────
CI/CD:        GitHub Actions → GHCR → values.yaml tag update → ArgoCD sync
Testing:      unit (mocked) + integration (testcontainers) + e2e (live cluster)
Security:     distroless images, non-root UID, Sealed Secrets, RBAC, seccomp
Observability:Prometheus metrics, Grafana dashboards, liveness/readiness probes
```

---

## Shared infrastructure

All live projects run on a 3-node homelab Kubernetes cluster:

| Node | Role | RAM | Used for |
|------|------|-----|----------|
| `clever-fly` | control-plane | 16 GB | ArgoCD, cluster management |
| `quick-thrush` | worker | 64 GB | All workloads — Ollama (p6), model serving (p1, p4), data pipeline (p2) |
| `sought-perch` | worker (cordoned) | 32 GB | Currently out of service (ISS-009) |

Storage: Ceph RGW (S3-compatible) for model artifacts and file uploads.
Secrets: Bitnami Sealed Secrets — encrypted in git, decrypted by the cluster only.
Registry: GHCR — one image per service, tagged by full commit SHA.

---

## Key design decisions (consistent across projects)

- **GitOps**: CI writes the new image SHA to `values.yaml`; ArgoCD detects drift and applies it. No manual `kubectl apply`.
- **Fail-fast lifespan**: services load their external dependencies (models, DB connections) at startup so a misconfiguration fails immediately, not on the first request.
- **Error-safe tools**: every external call returns a dict — errors are data, not exceptions. The agent or API decides what to do with them.
- **Docs in three layers**: `PROGRESS.md` (why decisions were made), `docs/implementation.md` (how it was built), `docs/how-it-works.md` (how the finished thing works).

---

## What is not here

- p3 HPC benchmark results — jobs submitted, awaiting output from UPPMAX/Dardel
- p4 serving layer — model is trained and stored; FastAPI + Streamlit in progress
- p5 site — content and Lovable prompt are ready; React site not built yet
- Streaming agent responses (p6 shows results after completion, not in real-time)
- Production hardening: no ingress TLS, no multi-tenant RBAC, no image signing

---

## Entry points

| If you want to see... | Go to |
|----------------------|-------|
| A live ML API | `http://100.82.75.34:30080/predict` (p1) |
| A live async data pipeline | p2 — `POST /ingest` with any file |
| A live LLM research agent | `http://100.82.75.34:30651` (p6 Streamlit) |
| The CI/CD pipeline | `.github/workflows/` |
| The Helm charts | `p1-pcam-deployment/helm/`, `p2-metadata-ingestion/helm/`, `p6-research-agent/helm/` |
| Security decisions | `p1-pcam-deployment/docs/security-compliance.md` |
| All deployment issues and fixes | `*/docs/deployment-troubleshooting.md` |
| Cluster runbooks | `runbooks/` |
