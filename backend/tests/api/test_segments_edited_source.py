"""
API tests for PATCH /jobs/{job_id}/segments/{segment_id} edited_source_text field (Phase 4, D-04-12).

Verifies:
- PATCH with edited_source_text returns 200 with updated field in response
- GET /jobs/{job_id}/segments reflects edited_source_text after PATCH
- PATCH with edited_source_text=None does not overwrite existing value
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Job, JobStatus, Segment

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Shared lifespan helper
# ---------------------------------------------------------------------------


def _make_lifespan(engine, factory):
    @asynccontextmanager
    async def _lifespan(app):
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = engine
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        app.state.llm_client = AsyncMock()
        app.state._session_factory = factory
        yield
        await engine.dispose()

    return _lifespan


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def _create_job(session: AsyncSession, status: JobStatus = JobStatus.done) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        status=status,
        source_lang="vi",
        target_lang="en",
        input_format="scanned_pdf",
        input_path="/tmp/source.pdf",
        original_filename="scan.pdf",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def _create_segment(
    session: AsyncSession,
    job_id: str,
    seq: int = 1,
    source_text: str = "Tiêu đề đoạn văn",
    translated_text: str | None = "Paragraph heading",
    edited_source_text: str | None = None,
) -> Segment:
    seg_id = (job_id.replace("-", "")[:12] + f"{seq:04d}")[:16]
    seg = Segment(
        id=seg_id,
        seq_in_job=seq,
        job_id=job_id,
        source_text=source_text,
        translated_text=translated_text,
        structural_position=f"page.0.region.{seq}",
        confidence=0.89,
        edited_source_text=edited_source_text,
    )
    session.add(seg)
    await session.commit()
    return seg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_patch_edited_source_text_returns_200():
    """
    PATCH /jobs/{job_id}/segments/{seg_id} with edited_source_text returns 200
    and the updated value in the response body.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as sess:
        job = await _create_job(sess, status=JobStatus.done)
        seg = await _create_segment(sess, job_id=job.id, seq=1)
        job_id = job.id
        seg_id = seg.id

    with patch("app.main.lifespan", _make_lifespan(engine, factory)):
        from app.main import app
        from app.db.session import get_session

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/jobs/{job_id}/segments/{seg_id}",
                json={
                    "edited_text": None,
                    "edited_source_text": "corrected OCR source text",
                },
            )

        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["segment_id"] == seg_id
    assert data["edited_source_text"] == "corrected OCR source text"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_patch_edited_source_text_persisted_in_list():
    """
    After PATCH with edited_source_text, GET /jobs/{id}/segments reflects the updated value.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as sess:
        job = await _create_job(sess, status=JobStatus.done)
        seg = await _create_segment(sess, job_id=job.id, seq=1)
        job_id = job.id
        seg_id = seg.id

    with patch("app.main.lifespan", _make_lifespan(engine, factory)):
        from app.main import app
        from app.db.session import get_session

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # PATCH first
            patch_resp = await client.patch(
                f"/jobs/{job_id}/segments/{seg_id}",
                json={"edited_text": None, "edited_source_text": "corrected OCR source text"},
            )
            assert patch_resp.status_code == 200

            # GET segments and verify persistence
            list_resp = await client.get(f"/jobs/{job_id}/segments")

        app.dependency_overrides.clear()

    assert list_resp.status_code == 200
    segments = list_resp.json()["segments"]
    assert len(segments) == 1
    assert segments[0]["edited_source_text"] == "corrected OCR source text"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_patch_edited_source_text_null_not_overwrite():
    """
    PATCH with edited_source_text=None (absent from body) does not overwrite
    an existing edited_source_text value.

    The SegmentPatchRequest schema: edited_source_text defaults to None.
    The PATCH handler only writes edited_source_text when body.edited_source_text is not None.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as sess:
        job = await _create_job(sess, status=JobStatus.done)
        # Segment already has edited_source_text set
        seg = await _create_segment(
            sess,
            job_id=job.id,
            seq=1,
            edited_source_text="pre-existing OCR correction",
        )
        job_id = job.id
        seg_id = seg.id

    with patch("app.main.lifespan", _make_lifespan(engine, factory)):
        from app.main import app
        from app.db.session import get_session

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # PATCH with edited_text only (no edited_source_text key)
            patch_resp = await client.patch(
                f"/jobs/{job_id}/segments/{seg_id}",
                json={"edited_text": "reviewer translation edit"},
            )
            assert patch_resp.status_code == 200

            list_resp = await client.get(f"/jobs/{job_id}/segments")

        app.dependency_overrides.clear()

    segments = list_resp.json()["segments"]
    # edited_source_text should remain "pre-existing OCR correction" — not cleared
    assert segments[0]["edited_source_text"] == "pre-existing OCR correction"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_patch_segment_409_when_job_not_reviewable():
    """
    PATCH returns 409 when job is in 'running' state (not done/needs_review).
    """
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as sess:
        job = await _create_job(sess, status=JobStatus.processing)
        seg = await _create_segment(sess, job_id=job.id, seq=1)
        job_id = job.id
        seg_id = seg.id

    with patch("app.main.lifespan", _make_lifespan(engine, factory)):
        from app.main import app
        from app.db.session import get_session

        async def override_session():
            async with factory() as sess:
                yield sess

        app.dependency_overrides[get_session] = override_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/jobs/{job_id}/segments/{seg_id}",
                json={"edited_text": None, "edited_source_text": "attempted edit"},
            )

        app.dependency_overrides.clear()

    assert response.status_code == 409
