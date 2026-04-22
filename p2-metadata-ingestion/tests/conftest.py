"""
tests/conftest.py
------------------
Shared pytest fixtures for the metadata ingestion test suite.

Strategy:
- Real Postgres via testcontainers — avoids the class of bugs where tests pass
  on SQLite but fail on Postgres (UUID types, CHECK constraints, async driver).
- Celery runs in ALWAYS_EAGER mode — tasks execute synchronously in the same
  process, no broker needed.
- S3/RGW is mocked with unittest.mock — we test that the worker calls upload
  correctly, not that Ceph works (that's an integration concern tested separately).
- httpx.AsyncClient with ASGITransport — exercises the full FastAPI stack
  (middleware, lifespan, dependency injection) without a real HTTP server.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer

from src.storage.db import Base, create_tables, get_engine, get_session_factory


# ---------------------------------------------------------------------------
# Postgres container (session-scoped — starts once per test session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_url(postgres_container):
    # testcontainers gives us a psycopg2 URL; swap driver for asyncpg
    return postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )


# ---------------------------------------------------------------------------
# Async DB engine + session factory (function-scoped — fresh tables each test)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine(db_url):
    engine = get_engine(db_url)
    await create_tables(engine)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return get_session_factory(db_engine)


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.ping = MagicMock(return_value=True)
    redis.aclose = MagicMock(return_value=None)
    return redis


# ---------------------------------------------------------------------------
# FastAPI test client — overrides app_state with test fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(session_factory, mock_redis, db_engine):
    from src.api.main import app, app_state

    # Inject test dependencies directly — bypasses lifespan's env-var reads
    app_state["session_factory"] = session_factory
    app_state["redis"] = mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app_state.clear()


# ---------------------------------------------------------------------------
# Mock S3 client (for worker tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_s3():
    s3 = MagicMock()
    s3.list_buckets.return_value = {"Buckets": [{"Name": "metadata-files"}]}
    s3.put_object.return_value = {}
    return s3


# ---------------------------------------------------------------------------
# Environment variables for worker tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def worker_env(db_url, monkeypatch):
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    monkeypatch.setenv("DATABASE_URL", sync_url)
    monkeypatch.setenv("RGW_ACCESS_KEY", "test-key")
    monkeypatch.setenv("RGW_SECRET_KEY", "test-secret")
    monkeypatch.setenv("RGW_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("STORAGE_BUCKET", "metadata-files")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
