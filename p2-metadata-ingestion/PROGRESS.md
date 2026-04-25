# Project 2 — Metadata Ingestion Service
## Progress Tracker
*Last updated: 2026-04-24*

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
| 11 | helm/metadata-ingestion/ chart | ✅ Done | api + worker deployments, service, configmap, HPA (worker), Postgres StatefulSet + PVC, Redis deployment, ArgoCD Application CR. |
| 12 | k8s/seal-secrets.sh | ✅ Done | Script to generate SealedSecrets for RGW creds + Postgres password. Run once per cluster before deploying. |
| 13 | Deploy to homelab | ⬜ Todo | Apply sealed secrets → `helm install` or ArgoCD sync → verify pods Running. |
| 14 | Smoke test | ⬜ Todo | POST /ingest via port-forward → poll /status/{id} until done. |

### Phase 4 — CI/CD
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 15 | .github/workflows/p2-ci.yml | ✅ Done | lint-and-test (ruff + pytest/testcontainers) → build-api + build-worker in parallel → update-tags writes SHAs back to values.yaml. |
| 16 | k8s/argocd-application.yaml | ✅ Done | Done in Phase 3 — watches helm/metadata-ingestion/ on main, CreateNamespace=true. |

### Phase 5 — Observability + Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 17 | Prometheus metrics | ✅ Done | API: QUEUE_DEPTH Gauge (queried from Redis on /metrics scrape). Worker: JOB_STATUS_TOTAL Counter, JOB_DURATION Histogram. |
| 18 | Grafana dashboard | ✅ Done | monitoring/grafana-dashboard.yaml (ConfigMap, auto-discovered by Grafana sidecar). monitoring/service-monitor.yaml. 7 panels: ingest rate, queue depth, job completion rate, job duration p50/p95/p99, API latency p95, worker replicas, failed jobs. |
| 19 | docs/q6-scalability.md | ✅ Done | Written in Phase 1 — volume/velocity/variety analysis with concrete numbers and Prometheus scaling signals. |
| 20 | docs/architecture.md | ✅ Done | Component roles, full data flow diagram, why Redis + Postgres, failure handling, scaling. |
| 21 | docs/design-decisions.md | ✅ Done | Rationale behind async queue, testcontainers, single Dockerfile, MIME detection from bytes, task_acks_late. |
| 22 | docs/runbook.md | ✅ Done | Debugging guide: stuck jobs, S3 errors, queue depth checks, Prometheus metrics reference. |

---

## Quick status

```
Phase 1  [██████] 6/6  ✅ Done
Phase 2  [████]   4/4  ✅ Done
Phase 3  [██░░]   2/4  ← deploy + smoke test pending
Phase 4  [██]     2/2  ✅ Done
Phase 5  [██████] 6/6  ✅ Done
```
