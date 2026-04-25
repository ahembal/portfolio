# Architecture

## Components

| Component | Technology | Role |
|-----------|-----------|------|
| **API** | FastAPI | Receives file uploads, writes initial DB record, queues work, returns immediately |
| **Worker** | Celery | Picks up queued tasks, does the heavy I/O (checksum, S3 upload), updates DB |
| **Redis** | Redis | Message broker — holds in-flight task messages between API and worker |
| **PostgreSQL** | PostgreSQL 16 | Permanent metadata catalog — source of truth for all job records |
| **Ceph RGW** | S3-compatible | Object storage — holds the actual file bytes |

## Data flow

```
1. Client: POST /ingest (file bytes)
        │
        ▼
2. API: write record to PostgreSQL
        { id, filename, size_bytes, status="pending", created_at }
   → Record exists immediately so callers can poll /status right away.
        │
        ▼
3. API: push task message into Redis
        "process job_id=abc123, filename=data.csv, bytes=..."
   → Returns 202 to the client. Does not wait for S3 or checksums.
        │
        ▼
4. Worker: picks up task message from Redis
        a. Update PostgreSQL → status="processing"
        b. Compute SHA-256 checksum of the raw bytes
        c. Detect real MIME type from bytes (python-magic)
           — not trusted from the upload Content-Type header
        d. Upload bytes to Ceph RGW
           key: uploads/{yyyy}/{mm}/{dd}/{job_id}/{filename}
        e. Update PostgreSQL → status="done", sha256, s3_key, content_type
        → Task message deleted from Redis.
        │
        ▼
5. Client: GET /status/{job_id} → reads from PostgreSQL
        { status="done", sha256="...", s3_key="uploads/..." }
```

## Why Redis AND PostgreSQL?

They serve completely different purposes:

|  | Redis | PostgreSQL |
|--|-------|-----------|
| **What it stores** | In-flight task messages (temporary) | File metadata records (permanent) |
| **Written when** | At ingest — deleted when worker picks it up | Twice: at ingest (pending) and when worker finishes (done/failed) |
| **Read by** | Celery worker (polling for tasks) | API endpoints, downstream pipelines |
| **If lost** | Task is re-queued (Celery retries handle this) | Data loss — this is the catalog |

Redis is the pipe. PostgreSQL is the catalog.

## Why not process the file synchronously in the API handler?

SHA-256 on a large file plus an S3 upload can take several seconds. If the API
waited for all of that before responding, concurrent uploads would back up and
response latency would grow with file size. The async queue lets the API
respond in milliseconds regardless of file size, and worker replicas absorb
the I/O cost independently.

## Failure handling

- **Worker crash mid-task**: `task_acks_late=True` means the task message stays
  in Redis until the worker explicitly acknowledges it. If the worker dies, the
  message is re-queued and another worker picks it up.
- **S3 error**: Worker retries up to 3 times with 30-second backoff. After 3
  failures it sets `status=failed` and records `error_msg` in PostgreSQL.
- **DB error at ingest**: If the initial Postgres write fails, no task is queued —
  the client gets a 500 and nothing is left in a partial state.

## Scaling

- **More upload throughput**: add worker replicas — they all pull from the same Redis queue.
- **Queue depth signal**: `ingest_queue_depth` Prometheus gauge (queried from Redis on each
  `/metrics` scrape) drives the HPA on the worker deployment.
- **API and worker scale independently**: the API is stateless; the worker is I/O-bound.
  Under a burst of uploads, the queue grows and HPA adds workers automatically.
