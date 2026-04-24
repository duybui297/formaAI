"""
Tests for export_service.export_job.

REV-05/06: Idempotent DOCX export with advisory lock and atomic write.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Job, JobStatus, Segment

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Session fixture local to this module
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def engine():
    e = create_async_engine(TEST_DB_URL, echo=False)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_job(
    session: AsyncSession,
    status: JobStatus = JobStatus.done,
    input_path: str = "/tmp/source.docx",
) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        status=status,
        source_lang="en",
        target_lang="vi",
        input_format="docx",
        input_path=input_path,
        original_filename="test.docx",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def _make_segment(
    session: AsyncSession,
    job_id: str,
    seq: int,
    source_text: str = "Hello world",
    translated_text: str | None = "Xin chào thế giới",
    edited_text: str | None = None,
) -> Segment:
    # Use 8 hex chars from job_id + seq to ensure uniqueness across tests
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_raises_value_error_for_queued_job(session, tmp_path):
    """export_job raises ValueError when job status is queued."""
    from app.services.export_service import export_job

    job = await _make_job(session, status=JobStatus.queued)

    with pytest.raises(ValueError, match="queued"):
        await export_job(session, job.id, str(tmp_path))


@pytest.mark.asyncio
async def test_export_raises_value_error_for_running_job(session, tmp_path):
    """export_job raises ValueError when job status is running."""
    from app.services.export_service import export_job

    job = await _make_job(session, status=JobStatus.running)

    with pytest.raises(ValueError, match="running"):
        await export_job(session, job.id, str(tmp_path))


@pytest.mark.asyncio
async def test_export_raises_for_unknown_job(session, tmp_path):
    """export_job raises ValueError for non-existent job_id."""
    from app.services.export_service import export_job

    with pytest.raises(ValueError, match="not found"):
        await export_job(session, "nonexistent-job-id", str(tmp_path))


@pytest.mark.asyncio
async def test_export_uses_edited_text_when_set(session, tmp_path):
    """Export uses edited_text (not translated_text) when edited_text is not None."""
    from app.services.export_service import export_job

    # Create a minimal DOCX file for the job to open
    from docx import Document as DocxDocument
    doc = DocxDocument()
    doc.add_paragraph("Hello world")
    input_path = str(tmp_path / "source.docx")
    doc.save(input_path)

    job = await _make_job(session, status=JobStatus.done, input_path=input_path)
    await _make_segment(
        session, job.id, 1,
        source_text="Hello world",
        translated_text="Xin chào thế giới",
        edited_text="Xin chào (edited)",
    )

    captured_maps: list[dict] = []

    original_reassemble = None

    def mock_reassemble(doc, segments, translated_map):
        captured_maps.append(dict(translated_map))
        return doc

    with patch("app.services.export_service.reassemble_docx_runs", mock_reassemble):
        output_path = await export_job(session, job.id, str(tmp_path))

    assert len(captured_maps) == 1
    # edited_text should be used instead of translated_text
    assert "Xin chào (edited)" in captured_maps[0].values()
    assert "Xin chào thế giới" not in captured_maps[0].values()


@pytest.mark.asyncio
async def test_export_uses_translated_text_when_edited_text_is_none(session, tmp_path):
    """Export falls back to translated_text when edited_text is None."""
    from app.services.export_service import export_job

    from docx import Document as DocxDocument
    doc = DocxDocument()
    doc.add_paragraph("Hello world")
    input_path = str(tmp_path / "source2.docx")
    doc.save(input_path)

    job = await _make_job(session, status=JobStatus.needs_review, input_path=input_path)
    await _make_segment(
        session, job.id, 1,
        source_text="Hello world",
        translated_text="Xin chào thế giới",
        edited_text=None,
    )

    captured_maps: list[dict] = []

    def mock_reassemble(doc, segments, translated_map):
        captured_maps.append(dict(translated_map))
        return doc

    with patch("app.services.export_service.reassemble_docx_runs", mock_reassemble):
        await export_job(session, job.id, str(tmp_path))

    assert len(captured_maps) == 1
    assert "Xin chào thế giới" in captured_maps[0].values()


@pytest.mark.asyncio
async def test_export_empty_string_edit_is_respected(session, tmp_path):
    """Pitfall 5: edited_text='' (empty string) must NOT fall back to translated_text."""
    from app.services.export_service import export_job

    from docx import Document as DocxDocument
    doc = DocxDocument()
    doc.add_paragraph("Hello world")
    input_path = str(tmp_path / "source3.docx")
    doc.save(input_path)

    job = await _make_job(session, status=JobStatus.done, input_path=input_path)
    await _make_segment(
        session, job.id, 1,
        source_text="Hello world",
        translated_text="Xin chào thế giới",
        edited_text="",  # explicit empty string — MUST be respected, not skipped
    )

    captured_maps: list[dict] = []

    def mock_reassemble(doc, segments, translated_map):
        captured_maps.append(dict(translated_map))
        return doc

    with patch("app.services.export_service.reassemble_docx_runs", mock_reassemble):
        await export_job(session, job.id, str(tmp_path))

    assert len(captured_maps) == 1
    seg_id = list(captured_maps[0].keys())[0]
    # Empty string edit must produce "" in the map, not fall back to translated_text
    assert captured_maps[0][seg_id] == ""


@pytest.mark.asyncio
async def test_export_output_path_structure(session, tmp_path):
    """Export writes to {data_dir}/jobs/{job_id}/output.docx."""
    from app.services.export_service import export_job

    from docx import Document as DocxDocument
    doc = DocxDocument()
    doc.add_paragraph("Test paragraph")
    input_path = str(tmp_path / "source4.docx")
    doc.save(input_path)

    job = await _make_job(session, status=JobStatus.done, input_path=input_path)
    await _make_segment(session, job.id, 1)

    def mock_reassemble(doc, segments, translated_map):
        return doc

    with patch("app.services.export_service.reassemble_docx_runs", mock_reassemble):
        output_path = await export_job(session, job.id, str(tmp_path))

    expected_path = str(tmp_path / "jobs" / job.id / "output.docx")
    assert output_path == expected_path
    assert os.path.exists(output_path)


@pytest.mark.asyncio
async def test_export_does_not_mutate_segments(session, tmp_path):
    """Export must NOT update any segment row (REV-06)."""
    from app.services.export_service import export_job
    from sqlalchemy import select

    from docx import Document as DocxDocument
    doc = DocxDocument()
    doc.add_paragraph("Test paragraph")
    input_path = str(tmp_path / "source5.docx")
    doc.save(input_path)

    job = await _make_job(session, status=JobStatus.done, input_path=input_path)
    await _make_segment(
        session, job.id, 1,
        source_text="Test paragraph",
        translated_text="Đoạn kiểm tra",
        edited_text="Đoạn đã sửa",
    )

    def mock_reassemble(doc, segments, translated_map):
        return doc

    with patch("app.services.export_service.reassemble_docx_runs", mock_reassemble):
        await export_job(session, job.id, str(tmp_path))

    # Verify segment rows unchanged
    result = await session.execute(
        select(Segment).where(Segment.job_id == job.id)
    )
    segs = result.scalars().all()
    assert len(segs) == 1
    assert segs[0].edited_text == "Đoạn đã sửa"  # unchanged
    assert segs[0].translated_text == "Đoạn kiểm tra"  # unchanged


@pytest.mark.asyncio
async def test_export_atomic_write_uses_tmp_file(session, tmp_path):
    """Export writes tmp file then os.replace — atomic write pattern."""
    from app.services.export_service import export_job

    from docx import Document as DocxDocument
    doc = DocxDocument()
    doc.add_paragraph("Atomic write test")
    input_path = str(tmp_path / "source6.docx")
    doc.save(input_path)

    job = await _make_job(session, status=JobStatus.done, input_path=input_path)
    await _make_segment(session, job.id, 1)

    replace_calls: list[tuple] = []
    original_replace = os.replace

    def spy_replace(src, dst):
        replace_calls.append((src, dst))
        return original_replace(src, dst)

    def mock_reassemble(doc, segments, translated_map):
        return doc

    with patch("app.services.export_service.reassemble_docx_runs", mock_reassemble):
        with patch("app.services.export_service.os.replace", spy_replace):
            output_path = await export_job(session, job.id, str(tmp_path))

    assert len(replace_calls) == 1
    tmp_src, final_dst = replace_calls[0]
    assert tmp_src.endswith(".tmp")
    assert final_dst == output_path
    # Final file should exist (tmp was renamed)
    assert os.path.exists(output_path)
    # Tmp file should be gone after atomic replace
    assert not os.path.exists(tmp_src)


@pytest.mark.asyncio
async def test_export_advisory_lock_prevents_concurrent_corruption(session, tmp_path):
    """Concurrent exports on same job_id: second waits, both produce same output."""
    from app.services.export_service import export_job

    from docx import Document as DocxDocument
    doc = DocxDocument()
    doc.add_paragraph("Concurrent test")
    input_path = str(tmp_path / "source7.docx")
    doc.save(input_path)

    job = await _make_job(session, status=JobStatus.done, input_path=input_path)
    await _make_segment(session, job.id, 1)

    def mock_reassemble(doc, segments, translated_map):
        return doc

    with patch("app.services.export_service.reassemble_docx_runs", mock_reassemble):
        results = await asyncio.gather(
            export_job(session, job.id, str(tmp_path)),
            export_job(session, job.id, str(tmp_path)),
        )

    # Both should return the same output path
    assert results[0] == results[1]
    assert os.path.exists(results[0])
