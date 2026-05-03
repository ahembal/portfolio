# Project 2 — Metadata Ingestion Service
## Progress Tracker
*Last updated: 2026-04-28*

---

## Steps

### Phase 1 — Local stack
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | docker-compose.yml | ✅ Done | Separating API and worker means HTTP response time is unaffected by file processing duration — the API returns 202 immediately. Healthchecks ensure the worker doesn't connect to Redis before it is ready, preventing crash loops on startup. |
| 2 | src/storage/db.py | ✅ Done | Async SQLAlchemy matches the async FastAPI event loop — a synchronous driver would block the loop during DB writes. Server-side timestamps prevent clock skew when multiple worker instances write concurrently. CHECK constraint on status prevents invalid state transitions from being persisted. |
| 3 | src/storage/s3.py | ✅ Done | Deterministic key schema means the S3 path can be reconstructed from job metadata alone — no secondary lookup needed to locate a file. Date-based prefixes allow lifecycle policies and partitioned listing without scanning the full bucket. |
| 4 | src/api/schemas.py | ✅ Done | Separate response models (not ORM models exposed directly) mean the internal DB schema can change without breaking the API contract. Pydantic validates at the boundary — a missing required field fails at startup, not at the first request. |
| 5 | src/api/main.py | ✅ Done | 202 Accepted is the correct HTTP semantics for an async operation — the request is queued, not yet processed. /health and /metrics must always respond, even under load — they are required by K8s liveness probes and Prometheus respectively. |
| 6 | src/workers/tasks.py | ✅ Done | SHA-256 provides a content fingerprint for integrity verification and deduplication. MIME detection from bytes (not extension) prevents type spoofing. Exponential backoff avoids hammering a temporarily unavailable S3 endpoint — 3 retries covers transient failures without blocking the worker indefinitely. |

### Phase 2 — Tests
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 7 | tests/conftest.py | ✅ Done | testcontainers runs a real Postgres — it catches constraint violations and schema errors that a mock would miss. httpx AsyncClient tests through the full ASGI stack so middleware, dependency injection, and error handlers are all exercised. Mock S3 is sufficient because upload logic is tested separately in worker tests. |
| 8 | Test: POST /ingest → job created | ✅ Done | Three separate assertions because they test three different layers — HTTP, persistence, and queue. Splitting them means a failure pinpoints exactly which layer broke. |
| 9 | Test: worker status transitions | ✅ Done | The failure path is as important as the happy path — a job that fails silently without updating status would appear stuck forever, with no visibility into the cause. |
| 10 | Test: /health + /files + /status | ✅ Done | Testing the degraded /health path matters because monitoring alerts depend on it — a wrong response here would generate false positives or miss real outages. |

### Phase 3 — Helm + K8s
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 11 | helm/metadata-ingestion/ chart | ✅ Done | HPA on the worker (not the API) because ingestion volume is the bottleneck — the API is lightweight HTTP. StatefulSet for Postgres preserves PVC identity across pod restarts — a regular Deployment would lose the volume claim. |
| 12 | k8s/seal-secrets.sh | ✅ Done | The sealed form is encrypted with the cluster's public key and safe to commit to git. Run once per cluster because the sealing key doesn't change between deploys — re-sealing every deploy would be unnecessary. |
| 13 | Deploy to homelab | ✅ Done | The deployment fixes address cluster-specific constraints documented in known-issues.md. Each fix (DATABASE_URL substitution, RGW endpoint, full SHA tags) makes the chart correct for the target cluster, not just locally. |
| 14 | Smoke test | ✅ Done | The smoke test verifies the full data path — from HTTP through Celery to RGW — which cannot be verified by unit tests alone. End-to-end confirmation before closing the phase. |

### Phase 4 — CI/CD
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 15 | .github/workflows/p2-ci.yml | ✅ Done | Parallel builds reduce CI wall time. update-tags writes the full SHA (not short SHA) because short SHAs can collide and GHCR uses the full digest as the authoritative reference. The tag change in values.yaml is the ArgoCD trigger. |
| 16 | k8s/argocd-application.yaml | ✅ Done | The Application CR in git means ArgoCD's own configuration is version-controlled — the cluster state is always derivable from git without manual kubectl commands. |

### Phase 5 — Observability + Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 17 | Prometheus metrics | ✅ Done | Worker metrics use a Counter (not Gauge) for job status because Counters are additive and monotonic — Prometheus rate() and increase() functions work correctly on them. Histogram captures tail latency (p95, p99) that average metrics hide. |
| 18 | Grafana dashboard | ✅ Done | 7 panels cover the three failure modes that matter: queue buildup (queue depth), processing failures (failed jobs), and latency degradation (duration p95/p99). The dashboard is a ConfigMap so it is version-controlled and deployed with the stack. |
| 19 | docs/q6-scalability.md | ✅ Done | Written in Phase 1 — volume/velocity/variety analysis with concrete numbers and Prometheus scaling signals. |
| 20 | docs/architecture.md | ✅ Done | Component roles, full data flow diagram, why Redis + Postgres, failure handling, scaling. |
| 21 | docs/design-decisions.md | ✅ Done | Rationale behind async queue, testcontainers, single Dockerfile, MIME detection from bytes, task_acks_late. |
| 22 | docs/runbook.md | ✅ Done | Debugging guide: stuck jobs, S3 errors, queue depth checks, Prometheus metrics reference. |

---

## Quick status

```
Phase 1  [██████] 6/6  ✅ Done
Phase 2  [████]   4/4  ✅ Done
Phase 3  [████]   4/4  ✅ Done
Phase 4  [██]     2/2  ✅ Done
Phase 5  [██████] 6/6  ✅ Done
```
