"""
Tests for segment and export endpoints:

GET  /jobs/{id}/segments    — REV-01: list with flags
PATCH /segments/{id}        — REV-02: persist edited_text; 409 gate
POST /segments/{id}/regenerate — REV-04: sync re-translate
POST /jobs/{id}/export      — REV-05/06: idempotent DOCX export
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, FlagSeverity, FlagType, Job, JobStatus, Segment, SegmentFlag

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Shared app fixture
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _fake_lifespan(app, tmp_path_str: str = "/tmp"):
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    app.state.settings = MagicMock(
        database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
        redis_url="redis://localhost:6379/0",
        data_dir=tmp_path_str,
    )
    app.state.engine = engine
    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()
    app.state.llm_client = AsyncMock()
    yield
    await engine.dispose()


def _make_lifespan(tmp_path_str: str):
    @asynccontextmanager
    async def _lifespan(app):
        async with _fake_lifespan(app, tmp_path_str):
            yield
    return _lifespan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_job(session: AsyncSession, status: JobStatus = JobStatus.done, **kwargs) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        status=status,
        source_lang=kwargs.get("source_lang", "en"),
        target_lang=kwargs.get("target_lang", "vi"),
        input_format="docx",
        input_path=kwargs.get("input_path", "/tmp/source.docx"),
        original_filename="test.docx",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def _create_segment(
    session: AsyncSession,
    job_id: str,
    seq: int = 1,
    source_text: str = "Hello",
    translated_text: str | None = "Xin chào",
    edited_text: str | None = None,
) -> Segment:
    seg_id = (job_id.replace("-", "")[:12] + f"{seq:04d}")[:16]
    seg = Segment(
        id=seg_id,
        seq_in_job=seq,
        job_id=job_id,
        source_text=source_text,
        translated_text=translated_text,
        edited_text=edited_text,
        structural_position=f"para.{seq}",
    )
    session.add(seg)
    await session.commit()
    return seg


async def _create_flag(
    session: AsyncSession,
    segment_id: str,
    segment_job_id: str,
    flag_type: FlagType = FlagType.overflow,
) -> SegmentFlag:
    flag = SegmentFlag(
        segment_id=segment_id,
        segment_job_id=segment_job_id,
        flag_type=flag_type,
        severity=FlagSeverity.warn,
        details={"test": True},
    )
    session.add(flag)
    await session.commit()
    return flag


# ---------------------------------------------------------------------------
# GET /jobs/{id}/segments — REV-01
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_segments_returns_200_with_segments(tmp_path):
    """GET /jobs/{id}/segments returns list of segments with flags."""
    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as sess:
            job = await _create_job(sess)
            seg = await _create_segment(sess, job.id, seq=1)
            await _create_flag(sess, seg.id, job.id)

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/jobs/{job.id}/segments")

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    data = response.json()
    assert "segments" in data
    assert data["total"] == 1
    assert len(data["segments"]) == 1
    seg_data = data["segments"][0]
    assert seg_data["source_text"] == "Hello"
    assert seg_data["translated_text"] == "Xin chào"
    assert "flags" in seg_data
    assert len(seg_data["flags"]) == 1
    assert seg_data["flags"][0]["flag_type"] == "overflow"
    assert "flag_counts" in data


@pytest.mark.asyncio
async def test_list_segments_returns_404_for_unknown_job(tmp_path):
    """GET /jobs/{id}/segments returns 404 for unknown job_id."""
    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/jobs/nonexistent-id/segments")

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /segments/{id} — REV-02
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_segment_updates_edited_text(tmp_path):
    """PATCH /jobs/{job_id}/segments/{id} persists edited_text and returns 200."""
    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as sess:
            job = await _create_job(sess, status=JobStatus.done)
            seg = await _create_segment(sess, job.id)

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/jobs/{job.id}/segments/{seg.id}",
                json={"edited_text": "Updated translation"},
            )

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    data = response.json()
    assert data["segment_id"] == seg.id
    assert data["edited_text"] == "Updated translation"


@pytest.mark.asyncio
async def test_patch_segment_clears_edited_text_when_null(tmp_path):
    """PATCH /jobs/{job_id}/segments/{id} with edited_text=null clears the edit."""
    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as sess:
            job = await _create_job(sess, status=JobStatus.needs_review)
            seg = await _create_segment(sess, job.id, edited_text="Old edit")

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/jobs/{job.id}/segments/{seg.id}",
                json={"edited_text": None},
            )

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    data = response.json()
    assert data["edited_text"] is None


@pytest.mark.asyncio
async def test_patch_segment_returns_409_when_job_queued(tmp_path):
    """PATCH /jobs/{job_id}/segments/{id} returns 409 when job status is queued."""
    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as sess:
            job = await _create_job(sess, status=JobStatus.queued)
            seg = await _create_segment(sess, job.id)

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/jobs/{job.id}/segments/{seg.id}",
                json={"edited_text": "Should be blocked"},
            )

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_segment_returns_409_when_job_running(tmp_path):
    """PATCH /jobs/{job_id}/segments/{id} returns 409 when job status is running."""
    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as sess:
            job = await _create_job(sess, status=JobStatus.processing)
            seg = await _create_segment(sess, job.id)

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/jobs/{job.id}/segments/{seg.id}",
                json={"edited_text": "Should be blocked"},
            )

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_segment_returns_404_for_unknown_segment(tmp_path):
    """PATCH /jobs/{job_id}/segments/{id} returns 404 for unknown segment_id."""
    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                "/jobs/nonexistent-job/segments/nonexistent-seg",
                json={"edited_text": "test"},
            )

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_segment_rejects_oversized_edited_text(tmp_path):
    """PATCH /jobs/{job_id}/segments/{id} returns 422 when edited_text exceeds 10000 chars."""
    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as sess:
            job = await _create_job(sess, status=JobStatus.done)
            seg = await _create_segment(sess, job.id)

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/jobs/{job.id}/segments/{seg.id}",
                json={"edited_text": "x" * 10001},
            )

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /jobs/{id}/export — REV-05/06
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_returns_409_for_non_exportable_job(tmp_path):
    """POST /jobs/{id}/export returns 409 when job is in queued state."""
    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as sess:
            job = await _create_job(sess, status=JobStatus.queued)

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(f"/jobs/{job.id}/export")

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_export_returns_file_for_done_job(tmp_path):
    """POST /jobs/{id}/export returns DOCX file for done job."""
    from docx import Document as DocxDocument
    doc = DocxDocument()
    doc.add_paragraph("Test content")
    input_path = str(tmp_path / "source.docx")
    doc.save(input_path)

    lifespan = _make_lifespan(str(tmp_path))
    with patch("app.main.lifespan", lifespan):
        from app.main import app
        from app.db.session import get_session

        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as sess:
            job = await _create_job(sess, status=JobStatus.done, input_path=input_path)
            await _create_segment(sess, job.id)

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(f"/jobs/{job.id}/export")

        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    assert "wordprocessingml" in response.headers.get("content-type", "")
