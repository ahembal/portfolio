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

import hashlib
import os
import sys
from pathlib import Path

import magic
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from infra.ceph_rgw.boto3_config import RGWConfig, get_s3_client  # noqa: E402

from src.storage.db import FileMetadata  # noqa: E402
from src.storage.s3 import build_s3_key, ensure_bucket, upload_bytes  # noqa: E402

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
    # asyncpg driver is async-only; use psycopg2 for the sync Celery context
    return os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )


def _get_sync_session() -> Session:
    engine = create_engine(_sync_db_url(), pool_pre_ping=True)
    return Session(engine)


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="metadata.process_file",
)
def process_file(
    self,
    job_id: str,
    filename: str,
    content_type: str | None,
    content: bytes,
) -> dict:
    """
    Process a single ingestion job:
      pending → processing → done | failed

    Retried up to 3 times with 30-second backoff on transient errors
    (S3 timeout, DB connectivity blip). Permanent failures (e.g. corrupt file)
    set status=failed with an error message.
    """
    session = _get_sync_session()
    try:
        # Mark processing
        record = session.get(FileMetadata, job_id)
        if record is None:
            return {"status": "skipped", "reason": "record not found"}
        record.status = "processing"
        session.commit()

        # 1. SHA-256 checksum
        sha256 = hashlib.sha256(content).hexdigest()

        # 2. MIME type — detect from bytes, don't trust the upload header
        detected_type = magic.from_buffer(content, mime=True)

        # 3. S3 upload
        storage_cfg = {
            "endpoint": os.environ.get("RGW_ENDPOINT", "http://192.168.1.16"),
            "access_key": os.environ["RGW_ACCESS_KEY"],
            "secret_key": os.environ["RGW_SECRET_KEY"],
            "bucket": os.environ.get("STORAGE_BUCKET", "metadata-files"),
        }
        rgw = RGWConfig(
            endpoint=storage_cfg["endpoint"],
            access_key=storage_cfg["access_key"],
            secret_key=storage_cfg["secret_key"],
        )
        s3 = get_s3_client(rgw)
        bucket = storage_cfg["bucket"]
        ensure_bucket(s3, bucket)
        s3_key = build_s3_key(job_id, filename)
        upload_bytes(s3, bucket, s3_key, content, detected_type)

        # 4. Update record → done
        record.sha256 = sha256
        record.content_type = detected_type
        record.s3_key = s3_key
        record.status = "done"
        session.commit()

        return {"status": "done", "job_id": job_id, "sha256": sha256}

    except Exception as exc:
        session.rollback()
        try:
            record = session.get(FileMetadata, job_id)
            if record:
                record.status = "failed"
                record.error_msg = str(exc)[:500]
                session.commit()
        except Exception:
            pass

        raise self.retry(exc=exc)

    finally:
        session.close()
