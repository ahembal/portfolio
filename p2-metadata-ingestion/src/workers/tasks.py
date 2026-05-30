"""
p2-metadata-ingestion/src/workers/tasks.py
--------------------------------------------
Celery tasks for background file processing.

The worker handles everything that would slow down the API response:
  1. Compute SHA-256 checksum of the raw bytes
  2. Detect MIME type (python-magic, not trusted from the upload header)
  3. Upload file to Ceph RGW
  4. Update Postgres record: status → done (or failed with error_msg)

Why a worker and not async in the API handler?
  - S3 uploads and DB writes can take hundreds of milliseconds; keeping them in
    the worker keeps the API fast and responsive under concurrent load
  - Worker replicas can be scaled independently of API replicas as the queue grows
  - Failed tasks are retried automatically by Celery without client involvement

The worker uses a synchronous SQLAlchemy session (not async) — Celery runs its
own event loop per task and mixing asyncio here adds complexity without benefit.
"""

import os
import time

import magic
from celery import Celery
from src.logging_config import setup_logging
from prometheus_client import Counter, Histogram
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sqlalchemy.engine import make_url

from src.storage.db import FileMetadata
from src.storage.s3 import (
    RGWConfig,
    download_bytes,
    get_s3_client,
)

log = setup_logging("p2-metadata-ingestion.worker")

JOB_STATUS_TOTAL = Counter(
    "ingest_jobs_total",
    "Total completed jobs by final status",
    ["status"],
)
JOB_DURATION = Histogram(
    "ingest_job_duration_seconds",
    "End-to-end job processing time from task start to DB update",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

celery_app = Celery(
    "metadata_worker",
    broker=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,        # task stays in queue until explicitly acknowledged
    worker_prefetch_multiplier=1,  # one task at a time per worker thread
    task_reject_on_worker_lost=True,
)

# ---------------------------------------------------------------------------
# Sync DB helper (used inside Celery tasks only)
# ---------------------------------------------------------------------------

def _sync_db_url() -> str:
    # asyncpg driver is async-only; use psycopg2 for the sync Celery context.
    # make_url handles percent-encoded special chars in passwords correctly;
    # a naive .replace() on the raw URL string would not.
    url = make_url(os.environ["DATABASE_URL"])
    return url.set(drivername="postgresql+psycopg2").render_as_string(hide_password=False)


_sync_engine = None


def _get_sync_session() -> Session:
    # Module-level engine singleton — creating a new engine per task would open
    # a new connection pool on every invocation, exhausting Postgres connections
    # under HPA scale-out. Pool size is configurable so operators can tune it
    # relative to the number of worker replicas.
    global _sync_engine
    if _sync_engine is None:
        pool_size = int(os.environ.get("DB_POOL_SIZE", "5"))
        max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
        _sync_engine = create_engine(
            _sync_db_url(),
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )
    return Session(_sync_engine)


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    max_retries=3,
    name="metadata.process_file",
)
def process_file(
    self,
    job_id: str,
    s3_key: str,
    bucket: str,
    storage_cfg: dict,
) -> dict:
    """
    Post-process a single ingestion job:
      pending → processing → done | failed

    The API handler uploads the file to S3 and computes SHA-256 before queuing
    this task — only the S3 key reference is passed through Redis, not the file
    bytes. This avoids Redis message size limits for large files.

    The worker downloads the file once to detect its MIME type (python-magic
    needs raw bytes; the upload Content-Type from the client is not trusted),
    then updates the DB record to done.

    Retried up to 3 times with 30-second backoff on transient errors.
    """
    t0 = time.perf_counter()
    log.info("file_processing_started", extra={"job_id": job_id, "s3_key": s3_key})
    session = _get_sync_session()
    try:
        record = session.get(FileMetadata, job_id)
        if record is None:
            return {"status": "skipped", "reason": "record not found"}
        record.status = "processing"
        session.commit()

        # Download from S3 to detect the true MIME type.
        rgw = RGWConfig(
            endpoint=storage_cfg["endpoint"],
            access_key=storage_cfg["access_key"],
            secret_key=storage_cfg["secret_key"],
        )
        s3 = get_s3_client(rgw)
        content = download_bytes(s3, bucket, s3_key)
        detected_type = magic.from_buffer(content, mime=True)

        record.content_type = detected_type
        record.status = "done"
        session.commit()

        JOB_DURATION.observe(time.perf_counter() - t0)
        JOB_STATUS_TOTAL.labels(status="done").inc()
        log.info("file_processing_done", extra={"job_id": job_id, "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})
        return {"status": "done", "job_id": job_id}

    except Exception as exc:
        session.rollback()
        try:
            record = session.get(FileMetadata, job_id)
            if record:
                record.status = "failed"
                full_msg = str(exc)
                record.error_msg = full_msg[:500]
                if len(full_msg) > 500:
                    log.warning("error_msg_truncated", extra={"job_id": job_id, "full_length": len(full_msg)})
                session.commit()
        except Exception:
            pass

        JOB_DURATION.observe(time.perf_counter() - t0)
        JOB_STATUS_TOTAL.labels(status="failed").inc()
        log.error("file_processing_failed", extra={"job_id": job_id, "exception_type": type(exc).__name__, "exception_message": str(exc)[:200]})
        # Exponential backoff: 30s, 60s, 120s.
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))

    finally:
        session.close()
