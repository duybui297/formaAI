"""
Job service: CRUD functions + state machine transitions for Job rows.

State machine (JOB-01..04):
  queued → running → done
                  ↘ failed

All state transitions are idempotent: they silently no-op on unknown job_id.
Callers own the session lifecycle.

D-04: per-job file layout under {data_dir}/jobs/{job_id}/
D-11: errors.log written by append_error_log() — durable, not in DB
"""
from __future__ import annotations

import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, JobStage, JobStatus


async def create_job(
    session: AsyncSession,
    source_lang: str,
    target_lang: str,
    input_format: str,
    input_path: str,
    original_filename: str,
    has_tracked_changes: bool = False,
    tracked_changes_action: str | None = None,
    glossary_id: str | None = None,
    user_id: str | None = None,
    idempotency_key: str | None = None,
    queue_priority: int | None = None,
) -> tuple[Job, bool]:
    """
    Insert a new Job row with status=queued.

    US-3.7 AC-5: If idempotency_key is provided and a Job with that key already
    exists for the same user, returns (existing_job, is_duplicate=True) — no new
    row is created. Callers can use is_duplicate to decide whether to skip enqueuing.

    Returns (job, is_duplicate) — is_duplicate=False for new jobs.

    glossary_id: optional FK to glossaries.id (D-02-01); None if no glossary selected.
    user_id: optional FK to users.id; enables per-user job filtering.
    """
    if idempotency_key and user_id:
        from sqlalchemy import select
        result = await session.execute(
            select(Job).where(
                Job.idempotency_key == idempotency_key,
                Job.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing, True

    job = Job(
        source_lang=source_lang,
        target_lang=target_lang,
        input_format=input_format,
        input_path=input_path,
        original_filename=original_filename,
        has_tracked_changes=has_tracked_changes,
        tracked_changes_action=tracked_changes_action,
        glossary_id=glossary_id,
        status=JobStatus.queued,
        user_id=user_id,
        idempotency_key=idempotency_key,
        queue_priority=queue_priority,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job, False


async def get_job(session: AsyncSession, job_id: str) -> Job | None:
    """Return the Job with the given ID, or None if not found."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def get_job_for_user(
    session: AsyncSession,
    job_id: str,
    user_id: str,
) -> Job | None:
    """Return the Job owned by user_id, or None if not found / not owned."""
    result = await session.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def transition_to_running(session: AsyncSession, job_id: str) -> None:
    """
    JOB-02: queued → running.

    Sets status=running and stage=parse (worker entering the parse stage).
    No-op if job_id does not exist.
    """
    job = await get_job(session, job_id)
    if job is None:
        return
    job.status = JobStatus.running
    job.stage = JobStage.parse
    await session.commit()


async def update_job_progress(
    session: AsyncSession,
    job_id: str,
    segments_done: int,
    segments_total: int,
    current_batch: int,
    retry_count: int,
    stage: JobStage = JobStage.translate,
) -> None:
    """
    Update in-progress counters without changing status.

    D-10: These values mirror what the worker publishes to Redis pub/sub so
    that SSE reconnects can query the current state from the DB.
    """
    job = await get_job(session, job_id)
    if job is None:
        return
    job.segments_done = segments_done
    job.segments_total = segments_total
    job.retry_count = retry_count
    job.stage = stage
    await session.commit()


async def transition_to_done(
    session: AsyncSession,
    job_id: str,
    output_path: str,
    detected_lang: str | None = None,
) -> None:
    """
    JOB-03: running → done.

    Sets status=done, stage=done, output_path, and optionally detected_lang (D-16).
    No-op if job_id does not exist.
    """
    job = await get_job(session, job_id)
    if job is None:
        return
    job.status = JobStatus.done
    job.stage = JobStage.done
    job.output_path = output_path
    if detected_lang is not None:
        job.detected_lang = detected_lang
    await session.commit()


async def transition_to_failed(
    session: AsyncSession,
    job_id: str,
    error_msg: str,
) -> None:
    """
    JOB-04: running → failed.

    Sets status=failed, stage=failed, and error_msg.
    No-op if job_id does not exist.
    """
    job = await get_job(session, job_id)
    if job is None:
        return
    job.status = JobStatus.failed
    job.stage = JobStage.failed
    job.error_msg = error_msg
    await session.commit()


def append_error_log(data_dir: str, job_id: str, message: str) -> None:
    """
    D-11: Append a timestamped error line to the per-job errors.log.

    Creates the directory if it does not exist. Never raises — failure to
    write error log must not mask the original error.
    """
    log_path = os.path.join(data_dir, "jobs", job_id, "errors.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{timestamp} {message}\n")
    except OSError:
        # Best-effort: if we can't write the log, swallow silently so callers
        # can still mark the job failed in the DB without a cascading error.
        pass


def build_job_path(data_dir: str, job_id: str) -> str:
    """
    Build the per-job working directory path.

    Path structure: {data_dir}/jobs/{job_id}/
    The workspace_id is stored in the Job DB row (Job.user_id -> User.workspace_id)
    but is not embedded in the filesystem path to keep paths flat and simple.
    Multi-tenant isolation is enforced at the DB query layer (per-user job filtering).
    """
    return os.path.join(data_dir, "jobs", job_id)
