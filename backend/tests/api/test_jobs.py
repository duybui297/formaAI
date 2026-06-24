"""
Tests for GET /jobs, GET /jobs/{id}, and GET /jobs/{id}/download endpoints.

JOB-01: list + detail status
JOB-04: download translated DOCX
"""
from __future__ import annotations

import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Job, JobStatus


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def mock_app_state(tmp_path):
    """Patch lifespan so tests run without real Redis/DB/arq."""

    @asynccontextmanager
    async def fake_lifespan(app):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir=str(tmp_path),
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        app.state._session_factory = session_factory
        yield
        await engine.dispose()

    return fake_lifespan


@pytest.fixture
def override_get_session(mock_app_state):
    """Returns a context manager that patches lifespan + overrides get_session."""

    @asynccontextmanager
    async def fake_lifespan(app):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()

        # expose factory so dependency override can use it
        app.state._session_factory = factory
        yield
        await engine.dispose()

    return fake_lifespan


async def _create_test_job(session: AsyncSession, **kwargs) -> Job:
    """Helper: insert a minimal Job row for testing."""
    job = Job(
        id=str(uuid.uuid4()),
        status=kwargs.get("status", JobStatus.queued),
        source_lang=kwargs.get("source_lang", "auto"),
        target_lang=kwargs.get("target_lang", "vi"),
        input_format=kwargs.get("input_format", "docx"),
        input_path=kwargs.get("input_path", "/tmp/source.docx"),
        original_filename=kwargs.get("original_filename", "test.docx"),
        output_path=kwargs.get("output_path", None),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# GET /jobs/{id} — detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_job_status_returns_detail():
    """GET /jobs/{id} returns D-10 fields for an existing job."""

    @asynccontextmanager
    async def fake_lifespan(app):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        app.state._session_factory = factory
        yield
        await engine.dispose()

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.db.session import get_session

        # create test job in the DB that get_session will use
        engine2 = create_async_engine(TEST_DB_URL, echo=False)
        async with engine2.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory2 = async_sessionmaker(engine2, expire_on_commit=False)

        async with factory2() as sess:
            job = await _create_test_job(sess, status=JobStatus.processing)
            job_id = job.id

        async def override_session():
            async with factory2() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/jobs/{job_id}")

        app.dependency_overrides.clear()
        await engine2.dispose()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["status"] == "processing"
    assert "segments_done" in data
    assert "segments_total" in data
    assert "error_msg" in data
    assert "original_filename" in data


@pytest.mark.asyncio
async def test_get_job_status_404_unknown():
    """GET /jobs/{id} returns 404 for an unknown job_id."""

    @asynccontextmanager
    async def fake_lifespan(app):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        app.state._session_factory = factory
        yield
        await engine.dispose()

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.db.session import get_session

        engine2 = create_async_engine(TEST_DB_URL, echo=False)
        async with engine2.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory2 = async_sessionmaker(engine2, expire_on_commit=False)

        async def override_session():
            async with factory2() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/jobs/nonexistent-job-id")

        app.dependency_overrides.clear()
        await engine2.dispose()

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /jobs — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_jobs_returns_array():
    """GET /jobs returns {"jobs": [...]} with up to 50 items."""

    @asynccontextmanager
    async def fake_lifespan(app):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        app.state._session_factory = factory
        yield
        await engine.dispose()

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.db.session import get_session

        engine2 = create_async_engine(TEST_DB_URL, echo=False)
        async with engine2.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory2 = async_sessionmaker(engine2, expire_on_commit=False)

        async with factory2() as sess:
            await _create_test_job(sess)
            await _create_test_job(sess)

        async def override_session():
            async with factory2() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/jobs")

        app.dependency_overrides.clear()
        await engine2.dispose()

    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert len(data["jobs"]) >= 2


# ---------------------------------------------------------------------------
# GET /jobs/{id}/download
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_returns_409_when_not_done():
    """GET /jobs/{id}/download returns 409 when job status is queued/running."""

    @asynccontextmanager
    async def fake_lifespan(app):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        app.state._session_factory = factory
        yield
        await engine.dispose()

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.db.session import get_session

        engine2 = create_async_engine(TEST_DB_URL, echo=False)
        async with engine2.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory2 = async_sessionmaker(engine2, expire_on_commit=False)

        async with factory2() as sess:
            job = await _create_test_job(sess, status=JobStatus.processing)
            job_id = job.id

        async def override_session():
            async with factory2() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/jobs/{job_id}/download")

        app.dependency_overrides.clear()
        await engine2.dispose()

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_download_returns_file_for_done_job(tmp_path):
    """GET /jobs/{id}/download streams the output file for a done job."""
    # Create a real temp file to simulate the translated output
    output_file = tmp_path / "output.docx"
    output_file.write_bytes(b"PK fake docx content")

    @asynccontextmanager
    async def fake_lifespan(app):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir=str(tmp_path),
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        app.state._session_factory = factory
        yield
        await engine.dispose()

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.db.session import get_session

        engine2 = create_async_engine(TEST_DB_URL, echo=False)
        async with engine2.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory2 = async_sessionmaker(engine2, expire_on_commit=False)

        async with factory2() as sess:
            job = await _create_test_job(
                sess,
                status=JobStatus.done,
                output_path=str(output_file),
                original_filename="report.docx",
            )
            job_id = job.id

        async def override_session():
            async with factory2() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/jobs/{job_id}/download")

        app.dependency_overrides.clear()
        await engine2.dispose()

    assert response.status_code == 200
    assert response.content == b"PK fake docx content"
    content_disp = response.headers.get("content-disposition", "")
    assert "translated_report.docx" in content_disp


@pytest.mark.asyncio
async def test_download_404_for_unknown_job():
    """GET /jobs/{id}/download returns 404 when job_id doesn't exist."""

    @asynccontextmanager
    async def fake_lifespan(app):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        app.state._session_factory = factory
        yield
        await engine.dispose()

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.db.session import get_session

        engine2 = create_async_engine(TEST_DB_URL, echo=False)
        async with engine2.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory2 = async_sessionmaker(engine2, expire_on_commit=False)

        async def override_session():
            async with factory2() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/jobs/no-such-job/download")

        app.dependency_overrides.clear()
        await engine2.dispose()

    assert response.status_code == 404
