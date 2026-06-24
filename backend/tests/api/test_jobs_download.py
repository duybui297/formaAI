"""
API tests for Phase 4 download and page image endpoints (OCR-01, D-04-09/10/11/22).

Tests:
- GET /jobs/{id}/artifacts?artifact=bilingual_pdf  → 200 application/pdf
- GET /jobs/{id}/artifacts?artifact=translated_pdf → 200 application/pdf
- GET /jobs/{id}/artifacts?artifact=translated_docx → 200 correct MIME
- GET /jobs/{id}/artifacts?artifact=unknown → 400
- GET /jobs/{id}/artifacts?artifact=bilingual_pdf (job running) → 409
- GET /jobs/{id}/pages/{n}.png → 200 when file exists
- GET /jobs/{id}/pages/{n}.png → 404 when file missing

NOTE: download_artifact and serve_page_image call `get_settings()` via a local import
inside the function body, so we patch `app.core.config.get_settings` (the canonical
location) rather than `app.api.routes.jobs.get_settings` (which doesn't exist as
a module-level name).
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Job, JobStatus

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_lifespan(factory, tmp_path_str: str = "/tmp"):
    @asynccontextmanager
    async def _lifespan(app):
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir=tmp_path_str,
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        app.state._session_factory = factory
        yield
        await engine.dispose()

    return _lifespan


async def _insert_job(
    factory,
    job_id: str,
    status: JobStatus = JobStatus.done,
    **kwargs,
) -> None:
    """Insert a Job row into the test DB."""
    async with factory() as sess:
        job = Job(
            id=job_id,
            status=status,
            source_lang=kwargs.get("source_lang", "vi"),
            target_lang=kwargs.get("target_lang", "en"),
            input_format=kwargs.get("input_format", "scanned_pdf"),
            input_path="/tmp/source.pdf",
            original_filename="scan.pdf",
        )
        sess.add(job)
        await sess.commit()


# ---------------------------------------------------------------------------
# /artifacts endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_bilingual_pdf_returns_200(tmp_path):
    """GET /jobs/{id}/artifacts?artifact=bilingual_pdf returns 200 with PDF content."""
    job_id = str(uuid.uuid4())
    job_dir = tmp_path / "jobs" / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "output.pdf").write_bytes(b"%PDF-1.4 fake bilingual pdf content")

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _insert_job(factory, job_id, status=JobStatus.done)

    mock_settings = MagicMock(data_dir=str(tmp_path))

    with patch("app.main.lifespan", _make_lifespan(factory, str(tmp_path))):
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.main import app
            from app.db.session import get_session

            async def override_session():
                async with factory() as sess:
                    yield sess

            app.dependency_overrides[get_session] = override_session

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/jobs/{job_id}/artifacts?artifact=bilingual_pdf"
                )

            app.dependency_overrides.clear()

    await engine.dispose()

    assert response.status_code == 200
    assert "application/pdf" in response.headers.get("content-type", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_translated_pdf_returns_200(tmp_path):
    """GET /jobs/{id}/artifacts?artifact=translated_pdf returns 200."""
    job_id = str(uuid.uuid4())
    job_dir = tmp_path / "jobs" / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "output-translated-only.pdf").write_bytes(b"%PDF-1.4 translated only")

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _insert_job(factory, job_id, status=JobStatus.done)

    mock_settings = MagicMock(data_dir=str(tmp_path))

    with patch("app.main.lifespan", _make_lifespan(factory, str(tmp_path))):
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.main import app
            from app.db.session import get_session

            async def override_session():
                async with factory() as sess:
                    yield sess

            app.dependency_overrides[get_session] = override_session

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/jobs/{job_id}/artifacts?artifact=translated_pdf"
                )

            app.dependency_overrides.clear()

    await engine.dispose()

    assert response.status_code == 200
    assert "application/pdf" in response.headers.get("content-type", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_translated_docx_returns_200(tmp_path):
    """GET /jobs/{id}/artifacts?artifact=translated_docx returns 200 with DOCX MIME."""
    job_id = str(uuid.uuid4())
    job_dir = tmp_path / "jobs" / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "output.docx").write_bytes(b"PK fake docx content")

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _insert_job(factory, job_id, status=JobStatus.done)

    mock_settings = MagicMock(data_dir=str(tmp_path))

    with patch("app.main.lifespan", _make_lifespan(factory, str(tmp_path))):
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.main import app
            from app.db.session import get_session

            async def override_session():
                async with factory() as sess:
                    yield sess

            app.dependency_overrides[get_session] = override_session

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/jobs/{job_id}/artifacts?artifact=translated_docx"
                )

            app.dependency_overrides.clear()

    await engine.dispose()

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "wordprocessingml" in content_type or "octet-stream" in content_type


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_unknown_artifact_returns_400(tmp_path):
    """GET /jobs/{id}/artifacts?artifact=unknown returns 400 (T-04-09 allowlist)."""
    job_id = str(uuid.uuid4())
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _insert_job(factory, job_id, status=JobStatus.done)

    mock_settings = MagicMock(data_dir=str(tmp_path))

    with patch("app.main.lifespan", _make_lifespan(factory, str(tmp_path))):
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.main import app
            from app.db.session import get_session

            async def override_session():
                async with factory() as sess:
                    yield sess

            app.dependency_overrides[get_session] = override_session

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/jobs/{job_id}/artifacts?artifact=../../etc/passwd"
                )

            app.dependency_overrides.clear()

    await engine.dispose()

    assert response.status_code == 400


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_artifact_returns_409_when_job_running(tmp_path):
    """GET /jobs/{id}/artifacts returns 409 when job is not in terminal state (T-04-11)."""
    job_id = str(uuid.uuid4())
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _insert_job(factory, job_id, status=JobStatus.processing)

    mock_settings = MagicMock(data_dir=str(tmp_path))

    with patch("app.main.lifespan", _make_lifespan(factory, str(tmp_path))):
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.main import app
            from app.db.session import get_session

            async def override_session():
                async with factory() as sess:
                    yield sess

            app.dependency_overrides[get_session] = override_session

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/jobs/{job_id}/artifacts?artifact=bilingual_pdf"
                )

            app.dependency_overrides.clear()

    await engine.dispose()

    assert response.status_code == 409


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_artifact_returns_404_when_file_missing(tmp_path):
    """GET /jobs/{id}/artifacts returns 404 when artifact file does not exist on disk."""
    job_id = str(uuid.uuid4())
    # No artifact file created — job exists but file is absent
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await _insert_job(factory, job_id, status=JobStatus.done)

    mock_settings = MagicMock(data_dir=str(tmp_path))

    with patch("app.main.lifespan", _make_lifespan(factory, str(tmp_path))):
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.main import app
            from app.db.session import get_session

            async def override_session():
                async with factory() as sess:
                    yield sess

            app.dependency_overrides[get_session] = override_session

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/jobs/{job_id}/artifacts?artifact=bilingual_pdf"
                )

            app.dependency_overrides.clear()

    await engine.dispose()

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /pages/{page_n}.png endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_serve_page_image_returns_200_when_file_exists(tmp_path):
    """GET /jobs/{id}/pages/0.png returns 200 when page PNG exists (D-04-10)."""
    job_id = str(uuid.uuid4())
    pages_dir = tmp_path / "jobs" / job_id / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "page-0.png").write_bytes(b"\x89PNG\r\n\x1a\n fake png")

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    mock_settings = MagicMock(data_dir=str(tmp_path))

    with patch("app.core.config.get_settings", return_value=mock_settings):
        with patch("app.main.lifespan", _make_lifespan(factory, str(tmp_path))):
            from app.main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/jobs/{job_id}/pages/0.png")

    await engine.dispose()

    assert response.status_code == 200
    assert "image/png" in response.headers.get("content-type", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_serve_page_image_returns_404_when_missing(tmp_path):
    """GET /jobs/{id}/pages/99.png returns 404 when page PNG does not exist."""
    job_id = str(uuid.uuid4())

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    mock_settings = MagicMock(data_dir=str(tmp_path))

    with patch("app.core.config.get_settings", return_value=mock_settings):
        with patch("app.main.lifespan", _make_lifespan(factory, str(tmp_path))):
            from app.main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/jobs/{job_id}/pages/99.png")

    await engine.dispose()

    assert response.status_code == 404
