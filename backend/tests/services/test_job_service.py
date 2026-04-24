"""
Unit tests for app.services.job_service.

Uses in-memory SQLite via the db_session fixture from conftest.py.
Tests cover: create, get, state transitions (running/done/failed), progress update.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobStatus, JobStage
from app.services.job_service import (
    create_job,
    get_job,
    transition_to_running,
    transition_to_done,
    transition_to_failed,
    update_job_progress,
    append_error_log,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_create_kwargs() -> dict:
    return {
        "source_lang": "auto",
        "target_lang": "en",
        "input_format": "docx",
        "input_path": "/data/jobs/test-job/source.docx",
        "original_filename": "test.docx",
    }


# ---------------------------------------------------------------------------
# Test: create_job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_job_inserts_row(db_session: AsyncSession):
    """create_job() inserts a Job row with status=queued."""
    job = await create_job(db_session, **_default_create_kwargs())
    assert job.id is not None
    assert job.status == JobStatus.queued
    assert job.source_lang == "auto"
    assert job.target_lang == "en"
    assert job.input_format == "docx"
    assert job.has_tracked_changes is False


@pytest.mark.asyncio
async def test_create_job_with_tracked_changes(db_session: AsyncSession):
    """create_job() records has_tracked_changes and tracked_changes_action."""
    job = await create_job(
        db_session,
        source_lang="vi",
        target_lang="en",
        input_format="docx",
        input_path="/data/jobs/tc-job/source.docx",
        original_filename="doc_with_tc.docx",
        has_tracked_changes=True,
        tracked_changes_action="strip",
    )
    assert job.has_tracked_changes is True
    assert job.tracked_changes_action == "strip"


# ---------------------------------------------------------------------------
# Test: get_job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_job_returns_none_for_unknown_id(db_session: AsyncSession):
    """get_job() returns None for an ID that does not exist."""
    result = await get_job(db_session, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_get_job_returns_existing_job(db_session: AsyncSession):
    """get_job() returns the correct job by ID."""
    job = await create_job(db_session, **_default_create_kwargs())
    fetched = await get_job(db_session, job.id)
    assert fetched is not None
    assert fetched.id == job.id
    assert fetched.status == JobStatus.queued


# ---------------------------------------------------------------------------
# Test: transition_to_running
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transition_to_running_updates_status(db_session: AsyncSession):
    """transition_to_running() sets status=running and stage=parse."""
    job = await create_job(db_session, **_default_create_kwargs())
    await transition_to_running(db_session, job.id)

    updated = await get_job(db_session, job.id)
    assert updated is not None
    assert updated.status == JobStatus.running
    assert updated.stage == JobStage.parse


@pytest.mark.asyncio
async def test_transition_to_running_noop_on_missing_id(db_session: AsyncSession):
    """transition_to_running() is a no-op for unknown job_id (no exception raised)."""
    # Should not raise
    await transition_to_running(db_session, "does-not-exist")


# ---------------------------------------------------------------------------
# Test: transition_to_done
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transition_to_done_sets_output_path(db_session: AsyncSession):
    """transition_to_done() sets status=done, stage=done, and output_path."""
    job = await create_job(db_session, **_default_create_kwargs())
    output_path = "/data/jobs/{id}/output.docx".format(id=job.id)

    await transition_to_done(db_session, job.id, output_path=output_path)

    updated = await get_job(db_session, job.id)
    assert updated is not None
    assert updated.status == JobStatus.done
    assert updated.stage == JobStage.done
    assert updated.output_path == output_path


@pytest.mark.asyncio
async def test_transition_to_done_sets_detected_lang(db_session: AsyncSession):
    """transition_to_done() persists detected_lang when provided (D-16)."""
    job = await create_job(db_session, **_default_create_kwargs())
    await transition_to_done(db_session, job.id, output_path="/out.docx", detected_lang="vi")

    updated = await get_job(db_session, job.id)
    assert updated is not None
    assert updated.detected_lang == "vi"


# ---------------------------------------------------------------------------
# Test: transition_to_failed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transition_to_failed_sets_error_msg(db_session: AsyncSession):
    """transition_to_failed() sets status=failed, stage=failed, and error_msg."""
    job = await create_job(db_session, **_default_create_kwargs())
    error_text = "All 3 retries exhausted for batch 7"

    await transition_to_failed(db_session, job.id, error_msg=error_text)

    updated = await get_job(db_session, job.id)
    assert updated is not None
    assert updated.status == JobStatus.failed
    assert updated.stage == JobStage.failed
    assert updated.error_msg == error_text


# ---------------------------------------------------------------------------
# Test: update_job_progress
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_progress_increments_segments_done(db_session: AsyncSession):
    """update_job_progress() writes segments_done and segments_total to DB."""
    job = await create_job(db_session, **_default_create_kwargs())
    await update_job_progress(
        db_session,
        job.id,
        segments_done=5,
        segments_total=10,
        current_batch=2,
        retry_count=0,
        stage=JobStage.translate,
    )

    updated = await get_job(db_session, job.id)
    assert updated is not None
    assert updated.segments_done == 5
    assert updated.segments_total == 10
    assert updated.retry_count == 0
    assert updated.stage == JobStage.translate


# ---------------------------------------------------------------------------
# Test: append_error_log
# ---------------------------------------------------------------------------

def test_append_error_log_creates_file():
    """append_error_log() creates errors.log at the expected path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        job_id = "test-job-123"
        append_error_log(tmpdir, job_id, "Something went wrong")

        log_path = os.path.join(tmpdir, "jobs", job_id, "errors.log")
        assert os.path.exists(log_path)
        content = open(log_path).read()
        assert "Something went wrong" in content


def test_append_error_log_appends_multiple_lines():
    """append_error_log() appends (not overwrites) on repeated calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        job_id = "test-job-append"
        append_error_log(tmpdir, job_id, "Error A")
        append_error_log(tmpdir, job_id, "Error B")

        log_path = os.path.join(tmpdir, "jobs", job_id, "errors.log")
        content = open(log_path).read()
        assert "Error A" in content
        assert "Error B" in content
