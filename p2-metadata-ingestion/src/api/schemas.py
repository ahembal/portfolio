"""
p2-metadata-ingestion/src/api/schemas.py
------------------------------------------
Pydantic request/response models for the metadata ingestion API.

These are the API's type contract. Any change here is a breaking change for callers.
Separate from the SQLAlchemy models in db.py — the DB schema and the API schema
are allowed to diverge (e.g. internal fields like error_msg are omitted from
public responses).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IngestResponse(BaseModel):
    job_id: UUID
    status: str
    message: str = "File queued for processing"


class JobStatus(BaseModel):
    job_id: UUID
    status: str                   # pending | processing | done | failed
    filename: str
    content_type: str | None
    size_bytes: int | None
    sha256: str | None
    s3_key: str | None
    error_msg: str | None
    created_at: datetime
    updated_at: datetime


class FileMetadataOut(BaseModel):
    job_id: UUID
    filename: str
    content_type: str | None
    size_bytes: int | None
    sha256: str | None
    s3_key: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    items: list[FileMetadataOut]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
