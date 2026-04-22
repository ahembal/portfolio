# Project 2 — Metadata Ingestion Service
## Progress Tracker
*Last updated: 2026-04-22*

---

## Steps

### Phase 1 — Local stack
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | docker-compose.yml | ✅ Done | API + worker + Redis + Postgres with healthchecks — starts in dependency order. |
| 2 | src/storage/db.py | ✅ Done | SQLAlchemy async (asyncpg), FileMetadata with UUID PK, status CHECK constraint, server-side timestamps. |
| 3 | src/storage/s3.py | ✅ Done | boto3 upload wrapper, deterministic key schema `uploads/{yyyy}/{mm}/{dd}/{job_id}/{filename}`. |
| 4 | src/api/schemas.py | ✅ Done | Pydantic v2 — IngestResponse, JobStatus, FileMetadataOut, FileListResponse, HealthResponse. |
| 5 | src/api/main.py | ✅ Done | POST /ingest (202), GET /status/{id}, /files, /health, /metrics. Prometheus counters + histogram. |
| 6 | src/workers/tasks.py | ✅ Done | SHA-256, python-magic MIME detection, RGW upload, status transitions, 3× retry / 30s backoff. |

### Phase 2 — Tests
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 7 | tests/conftest.py | ✅ Done | pytest fixtures: Postgres via testcontainers, async engine, mock Redis, httpx AsyncClient with injected app_state, mock S3, env monkeypatching. |
| 8 | Test: POST /ingest → job created | ✅ Done | 3 tests: 202 + UUID returned, DB record status=pending, Celery .delay called with correct job_id. |
| 9 | Test: worker status transitions | ✅ Done | Worker → done (sha256 written, s3_key set, put_object called); worker → failed (S3 error sets status=failed + error_msg). |
| 10 | Test: /health + /files + /status | ✅ Done | /health ok and degraded paths; /files pagination and status filter; /status 200 and 404. |

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
Phase 1  [██████] 6/6  ✅ Done
Phase 2  [████]   4/4  ✅ Done
Phase 3  [░░░░]   0/4  ← next
Phase 4  [░░]     0/2
Phase 5  [░░░]    0/3
```
