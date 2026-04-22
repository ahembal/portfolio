"""
p2-metadata-ingestion/src/storage/db.py
----------------------------------------
SQLAlchemy async models and engine factory for the metadata store.

The FileMetadata table is the single source of truth for every ingestion job:
its status column drives the API responses, and all worker transitions write here.

Design notes:
- async engine (asyncpg) so the FastAPI event loop is never blocked by DB I/O
- UUID primary key — no sequential integer leaks record count to callers
- status as a plain string column with a CHECK constraint rather than a Postgres
  ENUM, so migrations don't require ALTER TYPE when new states are added
- updated_at uses server_default + onupdate so the DB owns the clock, not the app
"""

import os
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FileMetadata(Base):
    __tablename__ = "file_metadata"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','done','failed')",
            name="ck_file_metadata_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    s3_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error_msg: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def get_engine(database_url: str | None = None):
    url = database_url or os.environ["DATABASE_URL"]
    return create_async_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


def get_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
