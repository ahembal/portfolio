# Implementation Notes — P2 Metadata Ingestion
*Last updated: 2026-04-28*

This document describes how the project was built: structure chosen, problems hit during development, and decisions made along the way. For how the finished product works see `how-it-works.md`. For design rationale see `design-decisions.md`.

---

## src/storage/db.py

- `FileMetadata` model: UUID PK (`gen_random_uuid()`), status `CHECK ('pending','processing','done','failed')`, `s3_key` and `sha256` nullable (filled in by worker), `created_at`/`updated_at` server-side defaults
- Async engine via asyncpg, session factory with `async_scoped_session`

## src/storage/s3.py

- Moved from `infra/` to `src/storage/` during development — `infra/` was an accidental extra layer
- `RGWConfig` dataclass holds endpoint, bucket, access_key, secret_key
- `get_s3_client()` returns a boto3 client configured for the RGW endpoint
- Key schema: `uploads/{yyyy}/{mm}/{dd}/{job_id}/{filename}`

## src/api/main.py

- lifespan pattern: DB engine created + Redis connection established at startup, closed on shutdown
- `DATABASE_URL` constructed from split env vars (`DATABASE_URL_HOST`, `DB`, `USER`) + `$(POSTGRES_PASSWORD)` substitution — required because ConfigMap cannot do env var substitution, only Deployment env array can
- Prometheus: `QUEUE_DEPTH` queried from Redis on every `/metrics` scrape (Gauge, not Counter)

## src/workers/tasks.py

- Celery task with `bind=True` (self parameter for retry)
- Status transitions: `pending` → `processing` → `done`/`failed`
- `task_acks_late=True`: task is acknowledged only after completion, preventing loss if the worker crashes mid-execution
- Problem hit: initial import of `get_s3_client` from `infra/` caused `ModuleNotFoundError` — fixed by moving to `src/storage/s3.py`

## tests/conftest.py

- `testcontainers` `PostgreSQLContainer`: starts a real Postgres for each test session, provides connection URL
- `pyproject.toml` needed `pythonpath=["."]` and `asyncio_mode="auto"` for async test functions
- Problem hit: `mock_redis.ping` and `mock_redis.aclose` must be `AsyncMock` (not `MagicMock`) — async context requires awaitable mocks
- Problem hit: `process_file.apply()` (Celery eager mode) requires `throw=True` to propagate task exceptions to the test

## CI/CD

- `.github/workflows/p2-ci.yml`: `lint-and-test` job → `build-api` + `build-worker` jobs (parallel) → `update-tags` job
- Problem hit: initial `values.yaml` stored 7-char short SHA (`GITHUB_SHA[:7]`). GHCR stores images by full SHA. Short SHA lookup returned 404. Fixed: `update-tags` now uses full `$GITHUB_SHA`.
- Problem hit: `DATABASE_URL` with `$(POSTGRES_PASSWORD)` in ConfigMap `data` is a literal string — ConfigMap does not interpolate env vars. Fixed: moved to Deployment env array where K8s does the substitution.

## Cluster deployment issues

- RGW endpoint was `192.168.1.16` (sought-perch, broken) → changed to `192.168.1.200` (quick-thrush)
- Postgres PVC: Ceph RBD ext4 creates `lost+found` directory, Postgres refuses to start in non-empty data dir. Fixed: `subPath: pgdata` in volumeMount
- `ghcr-pull-secret` must be copied to the `metadata-ingestion` namespace before deploying — it lives in `default` namespace by default
