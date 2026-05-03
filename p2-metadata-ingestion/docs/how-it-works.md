# How the Full Pipeline Works — P2 Metadata Ingestion
*Last updated: 2026-05-03*

This document traces a file from the moment it is uploaded to the moment it
is marked `done` — explaining every component, every data structure, and every
decision point in between.

---

## The big picture

```
Client uploads a file
        │  POST /ingest (file bytes)
        ▼
FastAPI (API container)
        │  1. Writes record to PostgreSQL → status=pending
        │  2. Pushes task message to Redis
        │  3. Returns 202 immediately
        ▼
Redis (message broker — temporary)
        │  holds task message until worker picks it up
        ▼
Celery Worker (worker container)
        │  1. Picks up task from Redis
        │  2. Updates PostgreSQL → status=processing
        │  3. Computes SHA-256 checksum
        │  4. Detects real MIME type
        │  5. Uploads file to Ceph RGW
        │  6. Updates PostgreSQL → status=done
        │  (task message deleted from Redis)
        ▼
Client polls GET /status/{job_id}
        │  reads from PostgreSQL
        ▼
{"status": "done", "sha256": "a1b2...", "s3_key": "uploads/2026/05/03/..."}
```

---

## Why two databases?

Redis and PostgreSQL serve completely different purposes:

| | Redis | PostgreSQL |
|--|-------|-----------|
| What it stores | In-flight task messages (temporary) | File metadata records (permanent) |
| Written when | At ingest — deleted when worker starts | Twice: pending at ingest, done/failed when worker finishes |
| Read by | Celery worker (polling for tasks) | API endpoints, downstream pipelines |
| If lost | Task is re-queued (Celery handles this) | Data loss — this is the permanent catalog |

Redis is the pipe. PostgreSQL is the catalog.

---

## Endpoints

### POST /ingest

**Purpose:** Accept a file upload, create a database record, queue a task,
return immediately without waiting for processing.

**Request:** multipart/form-data
- `file` — any file (no size limit enforced at API level)

```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@data.csv"
```

**Response (202 Accepted):**
```json
{
  "job_id": "9229b73b-d6b5-4d4b-8243-f122dd3d3a60",
  "status": "pending",
  "message": "File queued for processing"
}
```

**What happens inside step by step:**

1. API reads file bytes into memory
2. Generates a UUID (`job_id`) for this upload
3. Writes a record to PostgreSQL:
```sql
INSERT INTO file_metadata (id, filename, size_bytes, status, created_at)
VALUES ('9229b73b...', 'data.csv', 2856, 'pending', NOW())
```
4. Calls `process_file.delay(job_id, filename, content_type, content)` — this
   serialises the task and pushes it to Redis as a JSON message
5. Returns 202 immediately — the file has not been checksummed or uploaded yet

**Why 202 and not 200?**
HTTP 202 means "accepted for processing" — not yet complete. 200 would imply
the work is done. This distinction matters for clients that need to know whether
to poll or not.

**Limitations:**
- The entire file is read into API memory before the record is written. Very
  large files (>1 GB) will spike API container memory. Streaming upload is
  a future improvement.
- No file type validation at this stage — any file is accepted. MIME type is
  detected by the worker from the actual bytes.

---

### GET /status/{job_id}

**Purpose:** Check the current state of an ingestion job.

**Request:** URL parameter only — no body

```bash
curl http://localhost:8000/status/9229b73b-d6b5-4d4b-8243-f122dd3d3a60
```

**Response:**
```json
{
  "job_id": "9229b73b-d6b5-4d4b-8243-f122dd3d3a60",
  "status": "done",
  "filename": "data.csv",
  "content_type": "text/plain",
  "size_bytes": 2856,
  "sha256": "a32a421c7ca43a63c009279d406ecca37005c3b55327763d0c7615139994a874",
  "s3_key": "uploads/2026/05/03/9229b73b-d6b5-4d4b-8243-f122dd3d3a60/data.csv",
  "error_msg": null,
  "created_at": "2026-05-03T10:14:34.606205Z",
  "updated_at": "2026-05-03T10:14:34.951662Z"
}
```

**Status values and what they mean:**

| Status | Meaning | Who sets it |
|--------|---------|------------|
| `pending` | Record created, task queued, worker hasn't started | API at ingest |
| `processing` | Worker picked up the task and is running | Worker at task start |
| `done` | SHA-256 computed, file uploaded to S3, metadata written | Worker on success |
| `failed` | Worker failed after 3 retries; see `error_msg` | Worker on final failure |

**What happens inside:**
Single SQL query: `SELECT * FROM file_metadata WHERE id = $1`
Returns 404 if job_id not found.

---

### GET /files

**Purpose:** Browse the full catalog of ingested files with pagination and
optional status filter.

**Request:** query parameters
- `limit` — number of results (default 50, max 500)
- `offset` — pagination offset (default 0)
- `status` — filter by status: `pending`, `processing`, `done`, `failed`

```bash
curl "http://localhost:8000/files?limit=10&offset=0&status=done"
```

**Response:**
```json
{
  "items": [
    {
      "job_id": "9229b73b...",
      "filename": "data.csv",
      "content_type": "text/plain",
      "size_bytes": 2856,
      "sha256": "a32a...",
      "s3_key": "uploads/2026/05/03/.../data.csv",
      "status": "done",
      "created_at": "2026-05-03T10:14:34Z"
    }
  ],
  "total": 142,
  "limit": 10,
  "offset": 0
}
```

**What happens inside:**
Two SQL queries: one COUNT for total, one SELECT for the page.
Results ordered by `created_at DESC` — newest first.

---

### GET /health

**Purpose:** Liveness probe — checks both PostgreSQL and Redis are reachable.

**Response (healthy):**
```json
{"status": "ok", "db": "ok", "redis": "ok"}
```

**Response (degraded — one dependency down):**
```json
{"status": "degraded", "db": "ok", "redis": "error"}
```

**What happens inside:**
- DB check: `SELECT NOW()` — lightweight query, just confirms connectivity
- Redis check: `PING` — returns PONG if Redis is up

Returns 200 even when degraded — Kubernetes uses the status field to alert,
not the HTTP status code.

---

### GET /metrics

**Purpose:** Prometheus scrape endpoint.

**Metrics exposed:**

| Metric | Type | Description |
|--------|------|-------------|
| `ingest_requests_total{status}` | Counter | API requests by outcome |
| `ingest_request_latency_ms{endpoint}` | Histogram | API handler latency |
| `ingest_queue_depth` | Gauge | Tasks waiting in Redis queue |
| `ingest_jobs_total{status}` | Counter | Completed jobs by outcome |
| `ingest_job_duration_seconds` | Histogram | Worker processing time |

**Why a Gauge for queue depth, not a Counter?**
Counters only go up. Queue depth goes up (new tasks arrive) and down (workers
consume them). A Gauge is the correct metric type. It is queried from Redis
`LLEN("celery")` at scrape time — no background polling loop needed.

---

## What the worker does

The worker runs in a separate container. It does not serve HTTP — it only
consumes tasks from Redis.

**Task: `process_file(job_id, filename, content_type, content)`**

Step 1 — Mark processing:
```sql
UPDATE file_metadata SET status='processing' WHERE id = $job_id
```

Step 2 — SHA-256 checksum:
```python
sha256 = hashlib.sha256(content).hexdigest()
# e.g. "a32a421c7ca43a63c009279d406ecca37005c3b55327763d0c7615139994a874"
```

Step 3 — MIME type detection:
```python
detected_type = magic.from_buffer(content, mime=True)
# e.g. "text/plain" — from actual bytes, not the upload header
```
**Why not trust the upload header?**
A caller can claim `Content-Type: text/csv` but upload an executable. `python-magic`
reads the actual bytes (the same way the Unix `file` command works) and returns the
real type. This is a security measure.

Step 4 — S3 upload:
```
s3.put_object(
  Bucket="metadata-files",
  Key="uploads/2026/05/03/9229b73b-.../data.csv",
  Body=content,
  ContentType=detected_type
)
```
The key schema `uploads/{yyyy}/{mm}/{dd}/{job_id}/{filename}` partitions by date —
useful for lifecycle policies and batch processing.

Step 5 — Update record:
```sql
UPDATE file_metadata
SET status='done', sha256=..., s3_key=..., content_type=..., updated_at=NOW()
WHERE id = $job_id
```

**Failure handling:**
If any step fails, the worker retries up to 3 times with 30-second backoff.
After 3 failures:
```sql
UPDATE file_metadata
SET status='failed', error_msg='S3 connection refused', updated_at=NOW()
WHERE id = $job_id
```

**`task_acks_late=True`:**
The task message stays in Redis until the worker explicitly acknowledges it.
If the worker crashes mid-task, the message is re-queued automatically —
no data is lost.

---

## Limitations summary

| Limitation | Impact | Note |
|-----------|--------|------|
| Full file loaded into API memory | Large files spike memory | Streaming upload is a future improvement |
| No file size limit | API can be overwhelmed | Add limit in Helm values |
| No deduplication | Same file uploaded twice creates two records | SHA-256 written after upload, not before |
| S3 upload in worker only | No immediate access to file bytes | Expected — worker is async by design |
| 3 retries then fail | Transient S3 outage > 90s = failed job | Re-upload is the recovery path |
| MIME detection is best-effort | Obfuscated files may fool magic bytes | Not a security boundary |
