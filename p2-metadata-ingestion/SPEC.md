# P2 — Metadata Ingestion Service — Spec

> Last updated: 2026-04-21

## What this project is

A production-grade async metadata ingestion pipeline:

- **FastAPI** ingest endpoint accepts file uploads or metadata payloads
- **Celery + Redis** worker queue processes ingestion jobs asynchronously
- **PostgreSQL** stores structured metadata (filename, size, checksum, MIME type, timestamps, status)
- **Ceph RGW (S3)** stores the raw files
- **Docker Compose** for local development (all services in one command)
- **Helm chart** for K8s deployment (reuses homelab cluster from p1)

**Portfolio question answered:** Q6 — Scalability design: how the system handles volume (many concurrent uploads), velocity (real-time processing), and variety (different file types / metadata schemas).

**Why metadata ingestion?**
Data pipelines start with ingestion. A metadata catalog is a prerequisite for any downstream ML or analytics work — it's where you track what data exists, where it lives, and what its quality is. This project demonstrates async Python, database design, and the same GitOps/K8s patterns as p1 in a data-engineering context.

---

## Stack decisions

| Component | Choice | Why |
|-----------|--------|-----|
| API | FastAPI | same stack as p1; async I/O fits upload handling |
| Queue | Celery + Redis | standard Python async task queue; Redis is lightweight |
| DB | PostgreSQL | structured metadata; SQLAlchemy ORM for schema migrations |
| Storage | Ceph RGW (S3) | reuses homelab infra from p1; boto3 client already in `infra/` |
| Local dev | Docker Compose | single `docker compose up` starts API + worker + Redis + Postgres |
| K8s | Helm chart | same pattern as p1; demonstrates reuse of GitOps pipeline |

---

## Data model

```
FileMetadata
  id          UUID PK
  filename    TEXT NOT NULL
  content_type TEXT
  size_bytes  BIGINT
  sha256      TEXT        -- computed by worker
  s3_key      TEXT        -- RGW object key after upload
  status      ENUM(pending, processing, done, failed)
  created_at  TIMESTAMP
  updated_at  TIMESTAMP
  error_msg   TEXT        -- populated on failure
```

---

## API surface

```
POST /ingest
  Body: multipart/form-data (file) OR JSON metadata payload
  Returns: { job_id: uuid, status: "pending" }

GET /status/{job_id}
  Returns: { job_id, status, metadata: {...} | null, error: null | str }

GET /files
  Query params: ?limit=50&offset=0&status=done
  Returns: paginated list of FileMetadata records

GET /health
  Returns: { status: ok, db: ok, redis: ok }

GET /metrics
  Prometheus text exposition (same pattern as p1)
```

---

## Critical path

```
Docker Compose (local)
  → API + worker + DB running locally
    → /ingest → Celery task → metadata in Postgres
      → /status returns done
        → Tests pass (pytest)
          → Helm chart deploys to K8s
            → CI/CD pipeline (build → push → deploy)
              → Q6 doc (scalability analysis with numbers)
```

---

## Phase 1 — Local stack

| # | Task | Status |
|---|------|--------|
| 1 | `docker-compose.yml` — API, worker, Redis, Postgres, Ceph (optional) | ⬜ |
| 2 | `src/storage/db.py` — SQLAlchemy models + async engine | ⬜ |
| 3 | `src/storage/s3.py` — boto3 wrapper (reuse infra/ceph-rgw pattern) | ⬜ |
| 4 | `src/api/schemas.py` — Pydantic request/response models | ⬜ |
| 5 | `src/api/main.py` — FastAPI app with /ingest, /status, /files, /health, /metrics | ⬜ |
| 6 | `src/workers/tasks.py` — Celery tasks: checksum, MIME detection, S3 upload, DB update | ⬜ |

**Done when:** `docker compose up` → `curl -F file=@sample.txt http://localhost:8000/ingest` returns `{job_id, status: pending}` → polling `/status/{id}` eventually returns `done`.

---

## Phase 2 — Tests

| # | Task | Status |
|---|------|--------|
| 7 | `tests/test_ingestion.py` — pytest with testcontainers or mocks for DB + Redis + S3 | ⬜ |
| 8 | Test: POST /ingest → job created | ⬜ |
| 9 | Test: worker processes job → status transitions pending → done | ⬜ |
| 10 | Test: /health returns 200 with all deps healthy | ⬜ |

**Done when:** `pytest` passes with ≥ 80% coverage on API and worker modules.

---

## Phase 3 — Helm chart + K8s

| # | Task | Status |
|---|------|--------|
| 11 | `helm/metadata-ingestion/` — deployment, service, configmap, worker deployment, hpa | ⬜ |
| 12 | Sealed Secrets for Postgres password + RGW credentials | ⬜ |
| 13 | Deploy to homelab cluster | ⬜ |
| 14 | Smoke test: `/ingest` via port-forward | ⬜ |

**Done when:** `kubectl get pods -n metadata` shows API and worker pods Running; ingest smoke test passes.

---

## Phase 4 — CI/CD

| # | Task | Status |
|---|------|--------|
| 15 | GitHub Actions: pytest → docker build → push GHCR → update values.yaml | ⬜ |
| 16 | ArgoCD Application CR for metadata-ingestion | ⬜ |

Reuse p1 CI pattern. Two images: `metadata-api` and `metadata-worker`.

---

## Phase 5 — Observability + Q6 doc

| # | Task | Status |
|---|------|--------|
| 17 | Prometheus metrics: ingest_jobs_total, job_duration_seconds, queue_depth | ⬜ |
| 18 | Grafana dashboard (add to existing kube-prom stack) | ⬜ |
| 19 | Q6 doc — scalability analysis: horizontal scaling (worker replicas), queue backpressure, DB connection pooling | ⬜ |

---

## Acceptance criteria (project complete)

- [ ] `docker compose up` starts all services; ingest → done flow works end-to-end
- [ ] pytest suite passes in CI
- [ ] Deployed to K8s homelab via ArgoCD
- [ ] `/metrics` scraped by Prometheus; Grafana shows queue depth and job latency
- [ ] `docs/q6-scalability.md` written with concrete numbers and architecture diagram
