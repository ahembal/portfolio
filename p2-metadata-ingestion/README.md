# P2 — Metadata Ingestion Service

Async file ingestion pipeline. Upload any file, get a job ID back immediately,
poll for completion. Metadata (checksum, MIME type, size, S3 location, status)
is persisted in PostgreSQL so downstream pipelines can discover and process
files by querying the catalog.

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (async, Python 3.11) |
| Task queue | Celery + Redis |
| Metadata store | PostgreSQL 16 (SQLAlchemy async) |
| File storage | Ceph RGW (S3-compatible) |
| Observability | Prometheus + Grafana |
| Deployment | Docker Compose (local) · Helm + ArgoCD (K8s) |

## Quick start

```bash
cp .env.example .env          # fill in RGW credentials
docker compose up --build
```

```bash
# Upload a file
curl -s -X POST http://localhost:8000/ingest \
  -F "file=@README.md" | jq .
# → { "job_id": "3f2a...", "status": "pending" }

# Poll until done
curl -s http://localhost:8000/status/3f2a... | jq .
# → { "status": "done", "sha256": "a1b2...", "s3_key": "uploads/2026/04/24/..." }

# Browse the catalog
curl -s "http://localhost:8000/files?limit=10&status=done" | jq .
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ingest` | Upload a file — returns `{job_id, status: pending}` immediately (202) |
| `GET` | `/status/{job_id}` | Full job status + all metadata fields |
| `GET` | `/files` | Paginated catalog (`?limit=50&offset=0&status=done`) |
| `GET` | `/health` | Liveness probe — checks PostgreSQL and Redis |
| `GET` | `/metrics` | Prometheus text exposition |

## Running tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --tb=short --cov=src --cov-report=term-missing
```

## Docs

- [Architecture](docs/architecture.md) — component roles, data flow, why Redis + Postgres
- [Design decisions](docs/design-decisions.md) — why async queue, why testcontainers, etc.
- [Runbook](docs/runbook.md) — debugging, common issues, queue depth checks
- [Scalability analysis](docs/q6-scalability.md) — volume/velocity/variety with concrete numbers

## Project structure

```
src/api/main.py          FastAPI app — endpoints, Prometheus metrics, lifespan
src/api/schemas.py       Pydantic request/response models (API contract)
src/storage/db.py        SQLAlchemy async models + engine/session factories
src/storage/s3.py        RGWConfig, S3 client factory, upload helpers
src/workers/tasks.py     Celery task: checksum → MIME detect → S3 upload → DB update
tests/conftest.py        Fixtures: Postgres container, mock Redis, mock S3
tests/test_ingestion.py  Full test suite
helm/                    Helm chart: API + worker deployments, HPA, Postgres, Redis
monitoring/              Grafana dashboard + Prometheus ServiceMonitor
docs/                    Architecture, design decisions, runbook, scalability
```
