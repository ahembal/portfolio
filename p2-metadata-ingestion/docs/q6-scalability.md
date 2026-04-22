# Q6 — Scalability Design

This document explains how the metadata ingestion service is designed to handle
increasing load — more files, faster arrival rates, and larger payloads — and
where the limits are.

---

## The three axes of scale

**Volume** — how many files total the system can store and query.
**Velocity** — how many files per second can be ingested concurrently.
**Variety** — how the system handles different file sizes, types, and metadata schemas.

---

## How the architecture addresses each

### Velocity: the async queue pattern

The API handler does two things: write a record to Postgres and put a message on
the Redis queue. Both are fast (< 5 ms under normal conditions). The heavy work —
SHA-256 checksum, MIME detection, S3 upload — happens in the Celery worker
asynchronously, after the API has already returned 202 to the client.

This means the API's throughput is decoupled from the worker's throughput. Under
a sudden spike of uploads, the queue absorbs the burst and the workers drain it
at their own rate. The API stays fast; clients get their job IDs immediately.

**Horizontal scaling:** worker replicas are stateless. Adding replicas reduces
queue depth linearly until the bottleneck shifts to Postgres or S3:

```
queue_depth / worker_throughput = processing_lag

At 1 worker processing 10 files/s:
  100-file burst → queue drains in ~10 s

At 4 workers processing 40 files/s:
  100-file burst → queue drains in ~2.5 s
```

The `ingest_queue_depth` Prometheus gauge (polled from Redis) is the signal for
the HPA to scale workers. This is the right metric — not CPU, which stays flat
because the bottleneck is I/O, not compute.

### Volume: PostgreSQL + S3 separation of concerns

File bytes live in Ceph RGW (object storage, scales to petabytes).
Metadata lives in PostgreSQL (structured queries, indexing, pagination).

The two scale independently:
- Add more RGW OSDs to grow storage capacity
- Add a Postgres read replica to serve `/files` queries without touching the write path

The `file_metadata` table has straightforward access patterns: insert once, update
status a few times, then mostly read. With indexes on `status` and `created_at`,
query latency stays sub-10 ms up to tens of millions of rows.

### Variety: MIME detection from content, not headers

The upload Content-Type header is client-supplied and untrustworthy. The worker
uses `python-magic` to detect MIME type from the file's actual bytes (libmagic,
the same library used by the `file` command). This means the metadata is correct
regardless of what the client claims.

File size is captured at ingest (`len(content)` before queuing). No special
handling is needed for large files in this design — the entire file is held in
worker memory during processing. For files > 100 MB, the right approach would be
streaming upload to S3 with multipart upload and streaming checksum computation;
that is noted as a future improvement.

---

## Where the limits are

### API layer
The FastAPI event loop handles concurrent connections up to the uvicorn worker
count. Each `/ingest` request holds the file in memory for the duration of the
handler (typically < 5 ms after the `await file.read()`). At 50 MB average file
size and 100 concurrent uploads, peak memory per API pod is ~5 GB — manageable
on the homelab but a hard limit that would drive a move to streaming for larger
files.

### Worker layer
Each worker process holds one file in memory at a time (`worker_prefetch_multiplier=1`).
At 50 MB per file and 4 worker threads per pod, peak memory per worker pod is ~200 MB.
Adding pods is the lever; each pod adds 4 parallel processing slots.

### Database layer
PostgreSQL with a connection pool of 10 + 20 overflow supports ~300 concurrent
connections before queuing. For the `/files` list endpoint (read-heavy), a
PgBouncer connection pooler or a read replica would be the next step.

### S3 / Ceph RGW layer
Ceph RGW handles concurrent PUTs well — the bottleneck is network bandwidth to
the RGW nodes. On the homelab LAN (1 Gbps), the ceiling is roughly 100 MB/s
aggregate upload throughput (~200 × 0.5 MB files/s or ~2 × 50 MB files/s).

---

## Prometheus signals for scaling decisions

| Metric | Type | Scaling signal |
|--------|------|----------------|
| `ingest_requests_total` | Counter | Ingest rate (rate over 1m) |
| `ingest_request_latency_ms` | Histogram | p95 latency > 100 ms → API scaling |
| `ingest_queue_depth` | Gauge | Rising queue → add worker replicas |
| `ingest_jobs_total{status="failed"}` | Counter | Rising failures → investigate worker errors |
| `ingest_job_duration_seconds` | Histogram | p95 processing time > 10 s → worker performance issue |

The HPA is configured on `ingest_queue_depth` via the Prometheus adapter,
not on CPU — because the workers are I/O-bound, not CPU-bound, and CPU utilisation
would be a lagging indicator of the actual bottleneck.
