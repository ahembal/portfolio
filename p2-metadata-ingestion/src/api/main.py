"""
p2-metadata-ingestion/src/api/main.py
---------------------------------------
FastAPI metadata ingestion service.

Endpoints:
  POST /ingest          — accept a file upload, create a DB record, queue a Celery task
  GET  /status/{job_id} — return current job status + metadata
  GET  /files           — paginated list of all ingested files
  GET  /health          — liveness probe (checks DB + Redis connectivity)
  GET  /metrics         — Prometheus text exposition

Design principles (same as p1):
  - Dependency injection via lifespan: DB engine and session factory created once
    at startup, injected into handlers via app_state
  - Fail fast: missing env vars raise at startup, not at first request
  - Single responsibility: /ingest queues and returns immediately; the worker
    does the heavy work asynchronously
"""

import os
import time
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
    REGISTRY,
)
from sqlalchemy import func, select

from src.api.schemas import (
    FileListResponse,
    FileMetadataOut,
    HealthResponse,
    IngestResponse,
    JobStatus,
)
from src.storage.db import FileMetadata, create_tables, get_engine, get_session_factory
from src.workers.tasks import process_file

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

INGEST_TOTAL = Counter(
    "ingest_requests_total",
    "Total ingest requests by status",
    ["status"],
)
INGEST_LATENCY = Histogram(
    "ingest_request_latency_ms",
    "Request latency in milliseconds",
    ["endpoint"],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000],
)

# ---------------------------------------------------------------------------
# App state + lifespan
# ---------------------------------------------------------------------------

app_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    await create_tables(engine)
    app_state["session_factory"] = get_session_factory(engine)
    app_state["redis"] = aioredis.from_url(
        os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
    )
    yield
    await app_state["redis"].aclose()
    await engine.dispose()


app = FastAPI(
    title="Metadata Ingestion Service",
    description="Async file ingestion pipeline with Celery workers and Postgres metadata store.",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest(file: UploadFile = File(...)):
    """
    Accept a file upload, persist a metadata record in Postgres (status=pending),
    queue a Celery task for background processing, and return immediately.

    The caller polls GET /status/{job_id} to track progress.
    This keeps the API fast under concurrent uploads — the worker absorbs the
    I/O cost of checksum computation and S3 upload.
    """
    t0 = time.perf_counter()
    content = await file.read()
    job_id = uuid.uuid4()

    async with app_state["session_factory"]() as session:
        record = FileMetadata(
            id=job_id,
            filename=file.filename or "unknown",
            content_type=file.content_type,
            size_bytes=len(content),
            status="pending",
        )
        session.add(record)
        await session.commit()

    process_file.delay(str(job_id), file.filename, file.content_type, content)

    INGEST_TOTAL.labels(status="queued").inc()
    INGEST_LATENCY.labels(endpoint="/ingest").observe(
        (time.perf_counter() - t0) * 1000
    )
    return IngestResponse(job_id=job_id, status="pending")


@app.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: uuid.UUID):
    async with app_state["session_factory"]() as session:
        record = await session.get(FileMetadata, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(
        job_id=record.id,
        status=record.status,
        filename=record.filename,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        sha256=record.sha256,
        s3_key=record.s3_key,
        error_msg=record.error_msg,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@app.get("/files", response_model=FileListResponse)
async def list_files(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
):
    async with app_state["session_factory"]() as session:
        q = select(FileMetadata)
        if status:
            q = q.where(FileMetadata.status == status)
        total_result = await session.execute(
            select(func.count()).select_from(q.subquery())
        )
        total = total_result.scalar_one()
        result = await session.execute(
            q.order_by(FileMetadata.created_at.desc()).limit(limit).offset(offset)
        )
        items = result.scalars().all()

    return FileListResponse(
        items=[FileMetadataOut.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    db_status = "ok"
    redis_status = "ok"

    try:
        async with app_state["session_factory"]() as session:
            await session.execute(select(func.now()))
    except Exception:
        db_status = "error"

    try:
        await app_state["redis"].ping()
    except Exception:
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(status=overall, db=db_status, redis=redis_status)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
