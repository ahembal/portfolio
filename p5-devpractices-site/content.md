# p5 — Dev Practices Site Content
*All content for the Lovable site. Sections map 1:1 to site sections.*

---

## Hero

**Headline:** Engineering Practices

**Subheadline:** How I design, test, deploy, and observe production software — with evidence from real projects.

**Context line:** Each claim below links to the actual code, config, or commit that proves it.

---

## Section 1 — Testing

**Heading:** Testing

**Philosophy statement:**
Tests are not a formality. They are the spec made executable. The choice of test type — unit, integration, load — is a design decision: what failure mode am I actually guarding against?

**Three pillars:**

### Unit tests — logic in isolation
Validate individual functions with controlled inputs.
Used for: preprocessing (tokenisation input/output shapes), label mapping correctness, edge cases (empty strings, very long inputs).
Example: `p4-nlp-deployment/tests/test_nlp_inference.py`

### Integration tests — real dependencies
The most important category. Tests that pass against a SQLite mock but fail against real PostgreSQL are not useful.
In p2, tests spin up a real `postgres:16-alpine` container via **testcontainers**. UUID types, CHECK constraints, and the asyncpg driver are all exercised exactly as in production.
Example: `p2-metadata-ingestion/tests/test_ingestion.py`

### Why testcontainers, not mocks
A mocked database gives false confidence. p2 learned this explicitly — the test suite uses a real Postgres container with the same schema constraints. If the test fails, it's a real failure. If it passes, the DB layer actually works.

**Evidence links:**
- p1 tests: `p1-pcam-deployment/tests/test_inference.py`
- p2 tests (testcontainers): `p2-metadata-ingestion/tests/test_ingestion.py`
- p2 conftest: `p2-metadata-ingestion/tests/conftest.py`

---

## Section 2 — CI/CD

**Heading:** CI/CD

**Philosophy statement:**
A pipeline is a contract: every merge to main is linted, tested, built, and deployed — automatically, repeatably, with no manual steps. Humans approve changes; machines execute them.

**The full loop (p2 example):**

```
Push to main
  → lint (ruff: imports, line length, unused vars)
  → test (pytest + real Postgres via testcontainers)
  → build-api + build-worker (parallel, separate image tags)
  → push to GHCR
  → update-tags: writes full SHA to values.yaml + commits back
  → ArgoCD detects drift → deploys to homelab cluster
```

**Key decisions:**
- **Two separate images (api + worker)** from the same Dockerfile — different entrypoints, independent deployment. A worker-only fix doesn't rebuild or restart the API.
- **Full SHA image tags** (not `latest`, not short SHA) — `latest` is mutable, short SHA doesn't exist in the registry. Full SHA is immutable and traceable.
- **GitOps via ArgoCD** — the cluster's desired state lives in git. `kubectl apply` by hand is not how deployments happen.

**Evidence links:**
- p2 CI workflow: `.github/workflows/p2-ci.yml`
- p1 CI workflow: `.github/workflows/p1-ci.yml`
- ArgoCD application: `p2-metadata-ingestion/helm/metadata-ingestion/templates/argocd-application.yaml`

---

## Section 3 — Security

**Heading:** Security

**Philosophy statement:**
Security decisions should be deliberate and traceable — not default settings left unchanged. Each choice below maps to a standard.

**Four layers:**

### Distroless container images
No shell, no package manager, no OS utilities in the final image. Attack surface is the application and its dependencies only.
Standard: NIST SP 800-190 — container runtime hardening.
Applied in: p1, p2, p4.

### Sealed Secrets
Credentials (RGW keys, database passwords, GHCR tokens) are never stored in plain text. Encrypted with the cluster's public key via `kubeseal` — safe to commit to git. Only the in-cluster Sealed Secrets controller can decrypt.
Standard: ISO 27001:2022 A.10 (cryptography).
Applied in: p1, p2.

### Non-root containers
All application containers run as UID 1001. Kernel exploits require root to escalate — non-root containers contain the blast radius.
Standard: CIS Kubernetes Benchmark v1.9.
Applied in: p1, p2, p4.

### Local secret management (pass + GPG)
Credentials used in operations (sealing secrets, HPC access, GHCR tokens) are stored encrypted with GPG via `pass`. Never written to plain text files, never committed.

**Evidence links:**
- Sealed Secrets usage: `p2-metadata-ingestion/k8s/seal-secrets.sh`
- Container security: `p1-pcam-deployment/Dockerfile`
- Security compliance doc: `p1-pcam-deployment/docs/security-compliance.md`

---

## Section 4 — Observability

**Heading:** Observability

**Philosophy statement:**
You cannot improve what you cannot measure. Observability is not an afterthought — it is specified before deployment, not added when something breaks.

**What is instrumented and why:**

### Request rate (Counter)
`ingest_requests_total{status="queued"}` — how many files are being submitted per second. Counter only goes up; rate() over a window gives throughput.

### Latency (Histogram)
`ingest_request_latency_ms` with buckets `[5, 10, 25, 50, 100, 250, 500, 1000]`. Histograms enable `histogram_quantile(0.95, ...)` — p95 latency is the metric that reveals tail behaviour invisible to averages.

### Queue depth (Gauge)
`ingest_queue_depth` — number of tasks waiting in Redis. A Gauge (not a Counter) because queue depth goes up and down. Queried from Redis `LLEN` at scrape time — no background polling loop needed.

### Worker metrics
`ingest_jobs_total{status="done|failed"}` — job completion rate by outcome.
`ingest_job_duration_seconds` — end-to-end processing time per job.

**Grafana dashboard:** 7 panels — ingest rate, queue depth, job completion rate, job duration p50/p95/p99, API latency p95, worker replicas (HPA), failed jobs total.

**Evidence links:**
- Prometheus metrics: `p2-metadata-ingestion/src/api/main.py`
- Worker metrics: `p2-metadata-ingestion/src/workers/tasks.py`
- Grafana dashboard: `p2-metadata-ingestion/monitoring/grafana-dashboard.yaml`

---

## Section 5 — Code Quality

**Heading:** Code Quality

**Philosophy statement:**
Code quality is not aesthetic preference. It is operational necessity. Inconsistent formatting creates noise in diffs. Unsorted imports cause merge conflicts. Unused variables are hidden bugs.

**Tooling:**

### Ruff
Single tool replacing flake8 + isort + black. Runs in CI on every push.
Rules enforced: E (style), F (pyflakes), I (import sort).
Configuration: `p2-metadata-ingestion/pyproject.toml`

### Pydantic models as living schema
API contracts are defined as Pydantic models, not docstrings. The model *is* the documentation — it validates at runtime, generates OpenAPI automatically, and fails loudly on contract violations.
Example: `p2-metadata-ingestion/src/api/schemas.py`

### Type annotations
All public functions are annotated. Type hints serve three purposes: documentation for the reader, input for static analysis, and contract enforcement with Pydantic.

### Documentation standards
- Every project has `SPEC.md` (what and why), `PROGRESS.md` (what was built and why each decision was made), `docs/` with architecture, design decisions, and runbook.
- Timestamps on all docs — so you know when something was written and whether it's stale.
- Operations log (`runbooks/ops-log.md`) — every manual cluster change recorded with date, what was done, and why.

**Evidence links:**
- Ruff config: `p2-metadata-ingestion/pyproject.toml`
- API schemas: `p2-metadata-ingestion/src/api/schemas.py`
- Architecture doc: `p2-metadata-ingestion/docs/architecture.md`

---

## Section 6 — Synthesis

**Heading:** How it fits together

**Narrative:**
These practices are not independent checklists. They compose.

Tests make CI trustworthy — you can merge confidently because the pipeline ran against real dependencies. CI makes deployment safe — every artifact is traceable to a commit, tested, and built deterministically. Security makes deployment auditable — secrets are encrypted, containers are minimal, nothing runs as root. Observability makes production understandable — when something breaks (and it will), you have the metrics to know what broke, when, and why. Code quality makes all of the above maintainable — readable code is debuggable code, and documented decisions survive beyond the person who made them.

The through-line: **reduce the cost of being wrong**. Tests catch mistakes before deployment. Monitoring catches mistakes in production. Documentation ensures mistakes are not repeated.

**Known issues register:**
Every cluster issue encountered during this portfolio is documented in `runbooks/known-issues.md` — with likelihood, impact, detection time, recovery time, and risk score (FMEA methodology). Including the ones that caused hours of debugging.

---

## Footer

GitHub: `https://github.com/ahembal/portfolio`
