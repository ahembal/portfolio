# Runbook

## Check service health

```bash
curl -s http://localhost:8000/health | jq .
# { "status": "ok", "db": "ok", "redis": "ok" }
# If status=degraded, one of the dependencies is unreachable.
```

## Check queue depth

The queue depth shows how many tasks are waiting for a worker to pick them up.
A growing queue means workers are slower than the upload rate.

```bash
# Via API metrics
curl -s http://localhost:8000/metrics | grep ingest_queue_depth

# Directly in Redis
redis-cli LLEN celery
```

## Check a specific job

```bash
curl -s http://localhost:8000/status/<job_id> | jq .
```

Status values:
- `pending` — record created, task queued, worker hasn't started yet
- `processing` — worker picked it up and is running
- `done` — checksum computed, file uploaded to S3, metadata written
- `failed` — worker failed after 3 retries; see `error_msg` field

## List failed jobs

```bash
curl -s "http://localhost:8000/files?status=failed" | jq .
```

## Common issues

### Jobs stuck in `pending`

Worker is not running or not connected to Redis.

```bash
# Check worker is up
docker compose ps

# Check Redis connectivity from worker
docker compose exec worker redis-cli -u $REDIS_URL PING
```

### Jobs stuck in `processing`

Worker started the task but crashed mid-flight. The task will be re-queued
automatically because `task_acks_late=True` — the message stays in Redis
until the worker explicitly acknowledges completion.

Check worker logs:
```bash
docker compose logs worker --tail=50
```

### Jobs failing with S3 error

Check RGW credentials in `.env` and that the RGW endpoint is reachable:

```bash
docker compose exec worker env | grep RGW
curl -s $RGW_ENDPOINT
```

### Database connection errors

Check Postgres is running and DATABASE_URL is correct:

```bash
docker compose ps postgres
docker compose exec api env | grep DATABASE_URL
```

## Prometheus metrics

| Metric | Type | Description |
|--------|------|-------------|
| `ingest_requests_total` | Counter | API ingest requests by status label |
| `ingest_request_latency_ms` | Histogram | API handler latency in milliseconds |
| `ingest_queue_depth` | Gauge | Tasks currently waiting in Redis queue |
| `ingest_jobs_total` | Counter | Completed jobs by status (done/failed) |
| `ingest_job_duration_seconds` | Histogram | End-to-end worker processing time |

## Re-running a failed job

There is no built-in retry endpoint. To re-process a failed file, re-upload it:

```bash
# Get the original filename from the failed job
curl -s http://localhost:8000/status/<job_id> | jq .filename

# Re-upload (creates a new job_id)
curl -s -X POST http://localhost:8000/ingest -F "file=@<filename>" | jq .
```
