"""
tests/test_ingestion.py
------------------------
Test suite for the metadata ingestion service.

Covers:
  - POST /ingest → DB record created, Celery task queued, 202 returned
  - Worker task: status transitions pending → processing → done
  - Worker task: failed path (S3 error) → status = failed, error_msg set
  - GET /status/{job_id} → correct response shape
  - GET /files → pagination works, status filter works
  - GET /health → 200 when DB + Redis are reachable
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.storage.db import FileMetadata


# ---------------------------------------------------------------------------
# POST /ingest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_returns_202_and_job_id(client):
    """POST /ingest with a valid file returns 202 and a UUID job_id."""
    with patch("src.api.main.process_file") as mock_task:
        mock_task.delay = MagicMock()
        response = await client.post(
            "/ingest",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "pending"
    uuid.UUID(body["job_id"])  # raises if not a valid UUID


@pytest.mark.asyncio
async def test_ingest_creates_db_record(client, session_factory):
    """POST /ingest persists a FileMetadata record with status=pending."""
    with patch("src.api.main.process_file") as mock_task:
        mock_task.delay = MagicMock()
        response = await client.post(
            "/ingest",
            files={"file": ("data.csv", b"col1,col2\n1,2", "text/csv")},
        )

    job_id = uuid.UUID(response.json()["job_id"])

    async with session_factory() as session:
        record = await session.get(FileMetadata, job_id)

    assert record is not None
    assert record.filename == "data.csv"
    assert record.status == "pending"
    assert record.size_bytes == len(b"col1,col2\n1,2")
    assert record.sha256 is None      # not yet computed — worker does this


@pytest.mark.asyncio
async def test_ingest_queues_celery_task(client):
    """POST /ingest calls process_file.delay with the correct job_id."""
    with patch("src.api.main.process_file") as mock_task:
        mock_task.delay = MagicMock()
        response = await client.post(
            "/ingest",
            files={"file": ("img.png", b"\x89PNG\r\n", "image/png")},
        )
        job_id = response.json()["job_id"]
        mock_task.delay.assert_called_once()
        call_args = mock_task.delay.call_args[0]
        assert call_args[0] == job_id  # first positional arg is job_id


# ---------------------------------------------------------------------------
# Worker task — status transitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_transitions_to_done(session_factory, mock_s3):
    """Worker sets status=done and writes sha256 + s3_key on success."""
    from src.workers.tasks import process_file

    # Pre-insert a pending record
    job_id = str(uuid.uuid4())
    async with session_factory() as session:
        record = FileMetadata(
            id=uuid.UUID(job_id),
            filename="report.pdf",
            content_type="application/pdf",
            size_bytes=6,
            status="pending",
        )
        session.add(record)
        await session.commit()

    content = b"%PDF-1"

    with patch("src.workers.tasks.get_s3_client", return_value=mock_s3), \
         patch("src.workers.tasks.RGWConfig"):
        process_file(job_id, "report.pdf", "application/pdf", content)

    async with session_factory() as session:
        updated = await session.get(FileMetadata, uuid.UUID(job_id))

    assert updated.status == "done"
    assert updated.sha256 is not None
    assert len(updated.sha256) == 64       # SHA-256 hex digest length
    assert updated.s3_key is not None
    assert job_id in updated.s3_key
    mock_s3.put_object.assert_called_once()


@pytest.mark.asyncio
async def test_worker_sets_failed_on_s3_error(session_factory, mock_s3):
    """Worker sets status=failed and records error_msg when S3 upload fails."""
    from src.workers.tasks import process_file

    job_id = str(uuid.uuid4())
    async with session_factory() as session:
        record = FileMetadata(
            id=uuid.UUID(job_id),
            filename="broken.bin",
            content_type="application/octet-stream",
            size_bytes=4,
            status="pending",
        )
        session.add(record)
        await session.commit()

    mock_s3.put_object.side_effect = Exception("S3 connection refused")

    with patch("src.workers.tasks.get_s3_client", return_value=mock_s3), \
         patch("src.workers.tasks.RGWConfig"), \
         pytest.raises(Exception):
        process_file.apply(
            args=[job_id, "broken.bin", "application/octet-stream", b"\x00\x01\x02\x03"],
            retries=3,  # exhaust retries immediately in test
            throw=True,
        )

    async with session_factory() as session:
        updated = await session.get(FileMetadata, uuid.UUID(job_id))

    assert updated.status == "failed"
    assert updated.error_msg is not None
    assert "S3" in updated.error_msg or "connection" in updated.error_msg.lower()


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_returns_correct_shape(client, session_factory):
    """GET /status/{job_id} returns the full JobStatus schema."""
    job_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(FileMetadata(
            id=job_id,
            filename="sample.txt",
            content_type="text/plain",
            size_bytes=42,
            status="done",
            sha256="a" * 64,
            s3_key=f"uploads/2026/04/21/{job_id}/sample.txt",
        ))
        await session.commit()

    response = await client.get(f"/status/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == str(job_id)
    assert body["status"] == "done"
    assert body["filename"] == "sample.txt"
    assert body["sha256"] == "a" * 64


@pytest.mark.asyncio
async def test_status_404_for_unknown_job(client):
    response = await client.get(f"/status/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /files
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_files_pagination(client, session_factory):
    """GET /files returns paginated results respecting limit and offset."""
    async with session_factory() as session:
        for i in range(5):
            session.add(FileMetadata(
                id=uuid.uuid4(),
                filename=f"file_{i}.txt",
                status="done",
                size_bytes=i * 10,
            ))
        await session.commit()

    r1 = await client.get("/files?limit=3&offset=0")
    r2 = await client.get("/files?limit=3&offset=3")

    assert r1.status_code == 200
    assert len(r1.json()["items"]) == 3
    assert r1.json()["total"] == 5

    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 2


@pytest.mark.asyncio
async def test_files_status_filter(client, session_factory):
    """GET /files?status=done returns only done records."""
    async with session_factory() as session:
        session.add(FileMetadata(id=uuid.uuid4(), filename="done.txt", status="done", size_bytes=1))
        session.add(FileMetadata(id=uuid.uuid4(), filename="fail.txt", status="failed", size_bytes=1))
        await session.commit()

    response = await client.get("/files?status=done")

    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["status"] == "done" for item in items)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_ok(client, mock_redis):
    """GET /health returns status=ok when DB and Redis are reachable."""
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_degraded_when_redis_down(client, mock_redis):
    """GET /health returns status=degraded when Redis is unreachable."""
    mock_redis.ping.side_effect = Exception("Redis connection refused")

    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["redis"] == "error"
