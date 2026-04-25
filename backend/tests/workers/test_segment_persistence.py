"""
Tests for segment persistence in translate_worker.
Gap 1: segments must be persisted to DB before run_post_check.
Gap 2: session recovery — transition_to_failed must succeed even when session
       enters PendingRollbackError after run_post_check raises.
"""
from __future__ import annotations

import tempfile
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from docx import Document as DocxDocument
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, Job, JobStatus, Segment as SegmentORM
from app.workers.translate_worker import _run_translation


def _make_minimal_docx() -> str:
    """Write a DOCX with one paragraph to a temp file; return path."""
    doc = DocxDocument()
    doc.add_paragraph("Hello world")
    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    doc.save(tmp.name)
    tmp.close()
    return tmp.name


@pytest_asyncio.fixture
async def engine():
    e = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def job(session_factory):
    """Create a queued job row pointing at a real DOCX file."""
    docx_path = _make_minimal_docx()
    async with session_factory() as s:
        j = Job(
            source_lang="en",
            target_lang="vi",
            input_format="docx",
            input_path=docx_path,
            original_filename="test.docx",
            status=JobStatus.queued,
        )
        s.add(j)
        await s.commit()
        await s.refresh(j)
        return j.id, docx_path


@pytest.mark.asyncio
async def test_segments_persisted_before_translate(session_factory, job, tmp_path):
    """Gap 1: ORM Segment rows must exist in DB after _run_translation."""
    job_id, _ = job

    mock_ctx = {
        "settings": _make_settings(tmp_path),
        "redis": _make_redis(),
        "llm_client": None,
    }

    with patch(
        "app.workers.translate_worker.translate_batch_with_retry",
        new_callable=AsyncMock,
        return_value=["Xin chào thế giới"],
    ), patch(
        "app.workers.translate_worker.run_post_check",
        new_callable=AsyncMock,
    ):
        async with session_factory() as session:
            await _run_translation(mock_ctx, session, job_id)

    async with session_factory() as s:
        result = await s.execute(
            select(SegmentORM).where(SegmentORM.job_id == job_id)
        )
        rows = result.scalars().all()
    assert len(rows) >= 1, "No Segment rows persisted — Gap 1 not fixed"
    assert all(r.source_text for r in rows)


@pytest.mark.asyncio
async def test_translated_text_written_after_batch(session_factory, job, tmp_path):
    """Segment.translated_text is set after the translate loop."""
    job_id, _ = job

    mock_ctx = {
        "settings": _make_settings(tmp_path),
        "redis": _make_redis(),
        "llm_client": None,
    }

    with patch(
        "app.workers.translate_worker.translate_batch_with_retry",
        new_callable=AsyncMock,
        return_value=["Xin chào thế giới"],
    ), patch(
        "app.workers.translate_worker.run_post_check",
        new_callable=AsyncMock,
    ):
        async with session_factory() as session:
            await _run_translation(mock_ctx, session, job_id)

    async with session_factory() as s:
        result = await s.execute(
            select(SegmentORM).where(SegmentORM.job_id == job_id)
        )
        rows = result.scalars().all()
    assert any(r.translated_text is not None for r in rows), \
        "translated_text never written to DB"


@pytest.mark.asyncio
async def test_failed_job_not_stuck_running(session_factory, job, tmp_path):
    """Gap 2: job transitions to 'failed' even when run_post_check raises."""
    job_id, _ = job

    mock_ctx = {
        "settings": _make_settings(tmp_path),
        "redis": _make_redis(),
        "llm_client": None,
    }

    with patch(
        "app.workers.translate_worker.translate_batch_with_retry",
        new_callable=AsyncMock,
        return_value=["ok"],
    ), patch(
        "app.workers.translate_worker.run_post_check",
        new_callable=AsyncMock,
        side_effect=Exception("simulated post_check failure"),
    ):
        async with session_factory() as session:
            try:
                await _run_translation(mock_ctx, session, job_id)
            except Exception:
                pass  # _run_translation re-raises; that is expected

    async with session_factory() as s:
        result = await s.execute(
            select(Job).where(Job.id == job_id)
        )
        j = result.scalar_one()
    assert j.status == JobStatus.failed, \
        f"Job stuck in {j.status!r} instead of transitioning to failed — Gap 2 not fixed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(tmp_path):
    """Minimal settings stub sufficient for _run_translation."""
    return SimpleNamespace(
        data_dir=str(tmp_path),
        token_budget=2000,
        worker_concurrency=1,
        expansion_thresholds_dict={"en->vi": 1.5},
    )


def _make_redis():
    """AsyncMock Redis that silently swallows publish() calls."""
    r = AsyncMock()
    r.publish = AsyncMock(return_value=0)
    return r
