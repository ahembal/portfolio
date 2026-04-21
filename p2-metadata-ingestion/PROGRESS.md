# Project 2 — Metadata Ingestion Service
## Progress Tracker
*Last updated: 2026-04-21*

---

## Steps

### Phase 1 — Local stack
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | docker-compose.yml | ⬜ Todo | Brings up API + Celery worker + Redis + Postgres in one command. Local dev requires all four services running simultaneously — docker compose is the only sane way to orchestrate that without a cluster. |
| 2 | src/storage/db.py | ⬜ Todo | SQLAlchemy async models for FileMetadata (id, filename, content_type, size_bytes, sha256, s3_key, status, timestamps). The schema is the contract between the API and the worker — defining it first prevents mismatches later. |
| 3 | src/storage/s3.py | ⬜ Todo | boto3 wrapper for Ceph RGW. Reuses the pattern from `infra/ceph-rgw/boto3_config.py`. Abstracts bucket/key operations so the worker doesn't care whether the backend is RGW or AWS S3. |
| 4 | src/api/schemas.py | ⬜ Todo | Pydantic models for request/response: IngestRequest, IngestResponse (job_id, status), StatusResponse, FileMetadataOut. These are the API's type contract — wrong schema means wrong client behaviour at every layer. |
| 5 | src/api/main.py | ⬜ Todo | FastAPI app with POST /ingest, GET /status/{job_id}, GET /files, GET /health, GET /metrics. /ingest queues a Celery task and returns immediately (async pattern) — the worker does the heavy lifting so the API stays fast under load. |
| 6 | src/workers/tasks.py | ⬜ Todo | Celery tasks: compute SHA-256 checksum, detect MIME type, upload file to RGW, update Postgres status (pending → processing → done/failed). Processing is in the worker, not the API, so the pipeline scales horizontally by adding worker replicas. |

### Phase 2 — Tests
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 7 | tests/test_ingestion.py skeleton | ⬜ Todo | pytest setup with fixtures for test DB and mock Celery (eager mode) and mock S3. The test infrastructure determines what's testable — define it before writing individual tests. |
| 8 | Test: POST /ingest → job created | ⬜ Todo | Confirms the API creates a DB record, queues a Celery task, and returns a job_id. The most important happy-path test — if this fails, nothing else matters. |
| 9 | Test: worker status transitions | ⬜ Todo | Confirms the worker moves the job through pending → processing → done and writes the sha256 and s3_key to the DB. Validates the async pipeline end-to-end without a real S3 or Redis. |
| 10 | Test: /health returns 200 | ⬜ Todo | /health checks DB connectivity and Redis connectivity — tests that both are reachable in the test environment. Kubernetes probes this endpoint; if it's wrong the pod never gets traffic. |

### Phase 3 — Helm + K8s
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 11 | helm/metadata-ingestion/ chart | ⬜ Todo | Two deployments (api + worker), one service, configmap, HPA on worker CPU. Worker and API scale independently — during a backlog the worker replicas can spike while the API stays at 1. This is why they're separate deployments. |
| 12 | Sealed Secrets | ⬜ Todo | Seal Postgres password and RGW credentials with kubeseal. Same pattern as p1 — plaintext credentials in git is never acceptable even in a homelab portfolio. |
| 13 | Deploy to homelab | ⬜ Todo | `helm install metadata ./helm/metadata-ingestion -n metadata`. Smoke test: port-forward the API and POST a file. |
| 14 | Smoke test | ⬜ Todo | POST /ingest via port-forward → poll /status/{id} until done → verify record in Postgres. End-to-end confirmation that all four services (API, worker, Redis, Postgres) communicate correctly in K8s. |

### Phase 4 — CI/CD
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 15 | GitHub Actions pipeline | ⬜ Todo | pytest → docker build × 2 (api image + worker image) → push GHCR → update values.yaml with new tags. Two images because api and worker have different runtime dependencies and get rebuilt independently. |
| 16 | ArgoCD Application CR | ⬜ Todo | Watches helm/metadata-ingestion/ on main. Auto-deploys when values.yaml tag changes. Reuses the existing ArgoCD instance from p1 — shows GitOps scales to multiple applications on the same cluster. |

### Phase 5 — Observability + Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 17 | Prometheus metrics | ⬜ Todo | Three metrics: ingest_jobs_total (Counter by status), job_duration_seconds (Histogram), queue_depth (Gauge — polled from Redis). queue_depth is the key operational signal: a rising queue means workers can't keep up, which is the trigger for scaling. |
| 18 | Grafana dashboard | ⬜ Todo | Add a ConfigMap dashboard to the existing kube-prom stack. Panels: ingest rate, success/failure rate, job latency p50/p95, queue depth, worker replica count. Same pattern as p1's dashboard. |
| 19 | docs/q6-scalability.md | ⬜ Todo | Answers Q6 with concrete numbers: what happens to queue depth and latency as ingest rate increases, how adding worker replicas reduces queue depth, where the DB becomes the bottleneck. Evidence-based, not theoretical. |

---

## Quick status

```
Phase 1  [░░░░░░] 0/6  ← start here
Phase 2  [░░░░]   0/4
Phase 3  [░░░░]   0/4
Phase 4  [░░]     0/2
Phase 5  [░░░]    0/3
```
