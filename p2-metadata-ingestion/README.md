# P2 — Metadata Ingestion Service

Async file ingestion pipeline: upload a file, get a job ID back immediately,
poll for completion. The worker computes checksums, detects MIME types, uploads
to Ceph RGW object storage, and persists structured metadata to PostgreSQL.

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (async, Python 3.11) |
| Task queue | Celery + Redis |
| Metadata store | PostgreSQL 16 (SQLAlchemy async) |
| File storage | Ceph RGW (S3-compatible) |
| Observability | Prometheus + Grafana (kube-prom stack) |
| Deployment | Docker Compose (local) · Helm + ArgoCD (K8s) |

## Quick start (local)

```bash
# Copy and fill in RGW credentials
cp .env.example .env

docker compose up --build
```

```bash
# Ingest a file
curl -s -X POST http://localhost:8000/ingest \
  -F "file=@README.md" | jq .
# → { "job_id": "...", "status": "pending" }

# Poll for completion
curl -s http://localhost:8000/status/<job_id> | jq .
# → { "status": "done", "sha256": "...", "s3_key": "uploads/..." }

# List all ingested files
curl -s "http://localhost:8000/files?limit=10" | jq .
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ingest` | Upload a file — returns `{job_id, status: pending}` immediately |
| `GET` | `/status/{job_id}` | Job status + full metadata |
| `GET` | `/files` | Paginated list of ingested files (`?limit=50&offset=0&status=done`) |
| `GET` | `/health` | Liveness probe — checks DB + Redis |
| `GET` | `/metrics` | Prometheus text exposition |

## Architecture

```
Client
  │  POST /ingest (file bytes)
  ▼
FastAPI API
  │  1. Write record to Postgres (status=pending)
  │  2. Queue Celery task → return 202 immediately
  ▼
Redis (broker)
  ▼
Celery Worker
  │  1. SHA-256 checksum
  │  2. python-magic MIME detection (from bytes, not upload header)
  │  3. Upload to Ceph RGW → s3://metadata-files/uploads/{date}/{job_id}/
  │  4. Update Postgres → status=done
  ▼
PostgreSQL (metadata store)
```

The API never touches S3 or does heavy I/O — it queues and returns.
Worker replicas scale independently when the queue grows.

## Scalability

This design handles volume and velocity horizontally:

- **More uploads** → add worker replicas (`kubectl scale deployment metadata-worker`)
- **DB bottleneck** → connection pool (10 + 20 overflow) absorbs bursts; read replicas
  for `/files` queries if needed
- **Queue visibility** → `ingest_queue_depth` Prometheus gauge triggers HPA on workers

See `docs/q6-scalability.md` for the full analysis with numbers.

## Project structure

```
p2-metadata-ingestion/
├── src/
│   ├── api/
│   │   ├── main.py       FastAPI app — endpoints and lifespan
│   │   └── schemas.py    Pydantic request/response models
│   ├── storage/
│   │   ├── db.py         SQLAlchemy models + async engine factory
│   │   └── s3.py         S3/RGW upload helpers
│   └── workers/
│       └── tasks.py      Celery task — checksum, MIME, upload, DB update
├── tests/
│   └── test_ingestion.py pytest suite
├── helm/
│   └── metadata-ingestion/  K8s Helm chart
├── docs/
│   └── q6-scalability.md    Scalability analysis
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
