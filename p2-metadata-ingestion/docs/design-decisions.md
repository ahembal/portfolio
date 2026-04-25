# Design Decisions

## Async queue instead of synchronous processing

**Decision**: API returns immediately after queuing; worker does the heavy work.

**Why**: S3 uploads and SHA-256 on large files are slow (seconds). Doing them
synchronously in the API handler would block the event loop and make latency
proportional to file size. Queuing decouples intake speed from processing speed.

## Real PostgreSQL in tests (testcontainers), not SQLite

**Decision**: Tests spin up a real `postgres:16-alpine` container via testcontainers.

**Why**: SQLite behaves differently from PostgreSQL in several ways that matter here:
- UUID column types behave differently
- CHECK constraints are not enforced by default in SQLite
- Async driver (asyncpg) only works with PostgreSQL

Using SQLite in tests would give false confidence — tests could pass while the
same code fails against the real database. Testcontainers adds ~10 seconds to
the test run; that's an acceptable tradeoff.

## One Dockerfile for both API and worker

**Decision**: The API and worker share a single Dockerfile and base image.
The entrypoint differs: API runs `uvicorn`, worker runs `celery worker`.

**Why**: They share all the same Python code (`src/`). Separate Dockerfiles
would duplicate the entire dependency install layer. CI builds two separate
image tags (`metadata-api`, `metadata-worker`) from the same Dockerfile using
`--target` or different CMD overrides.

## MIME type detection from bytes, not upload header

**Decision**: Worker uses `python-magic` to detect MIME type from file bytes,
ignoring the `Content-Type` header sent by the caller.

**Why**: The upload header is caller-controlled and cannot be trusted. A file
named `data.csv` with `Content-Type: text/csv` could contain executable bytes.
Detecting from the actual bytes (using libmagic, the same library as the `file`
command) gives the real content type.

## SHA-256 in the worker, not the API

**Decision**: Checksum is computed by the Celery worker, not the API handler.

**Why**: For large files this is CPU-intensive. The API handler runs in the
async event loop — CPU-bound work there blocks all concurrent requests.
The worker runs in a separate process where CPU work does not affect API latency.

## Queue depth Gauge updated at scrape time

**Decision**: `ingest_queue_depth` is a Prometheus Gauge queried from Redis
on each `/metrics` request, not a counter updated on every task enqueue/dequeue.

**Why**: A counter only goes up. Queue depth goes up (new tasks) and down
(completed tasks). A Gauge is the correct metric type. Querying Redis `LLEN`
at scrape time is accurate, cheap (O(1) Redis command), and requires no
background polling loop.

## `task_acks_late=True` and `worker_prefetch_multiplier=1`

**Decision**: Celery workers acknowledge tasks only after completion, and fetch
one task at a time.

**Why**: The default behaviour acknowledges tasks on receipt, before processing.
If the worker crashes mid-task, the task is lost. `task_acks_late=True` keeps
the message in Redis until the task finishes, enabling automatic re-queuing on
worker failure. `worker_prefetch_multiplier=1` ensures tasks are distributed
evenly across worker replicas under HPA scale-out.
