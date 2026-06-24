"""
Upload session service — CRUD for chunked upload sessions.

Flow:
  1. init_session()   — create session record + temp directory
  2. upload_chunk()   — write one chunk to disk, update uploaded_chunks
  3. get_session()    — look up session
  4. complete_session() — assemble chunks → move to job dir → create Job → enqueue
  5. cancel_session() — delete temp files + mark cancelled
  6. cleanup_expired() — cron job: mark expired sessions, delete old temp dirs
"""
from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    JobStatus,
    UploadSession,
    UploadSessionStatus,
)


# Default chunk size: 5 MB — large enough to reduce overhead, small enough
# for reliable uploads on typical mobile/WiFi connections.
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB

# Upload session TTL: 2 hours from creation.
SESSION_TTL_HOURS = 2


async def init_session(
    session: AsyncSession,
    user_id: str,
    original_filename: str,
    file_size: int,
    source_lang: str,
    target_lang: str,
    glossary_id: str | None,
    has_tracked_changes: bool,
    tracked_changes_action: str | None,
    is_scanned: bool,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    data_dir: str = "/data",
    queue_priority: int | None = None,
) -> UploadSession:
    """Create an UploadSession and its on-disk temp directory."""
    upload_id = str(uuid.uuid4())
    session_path = os.path.join(data_dir, "uploads", upload_id)
    os.makedirs(session_path, exist_ok=True)

    total_chunks = (file_size + chunk_size - 1) // chunk_size
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)

    record = UploadSession(
        id=upload_id,
        user_id=user_id,
        original_filename=original_filename,
        file_size=file_size,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        uploaded_chunks=[],
        session_path=session_path,
        source_lang=source_lang,
        target_lang=target_lang,
        glossary_id=glossary_id,
        has_tracked_changes=has_tracked_changes,
        tracked_changes_action=tracked_changes_action,
        is_scanned=is_scanned,
        queue_priority=queue_priority,
        expires_at=expires_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_session(
    session: AsyncSession,
    upload_id: str,
    user_id: str,
) -> UploadSession | None:
    """Return the session if it belongs to user_id and is still active."""
    result = await session.execute(
        select(UploadSession).where(
            UploadSession.id == upload_id,
            UploadSession.user_id == user_id,
            UploadSession.status == UploadSessionStatus.active.value,
        )
    )
    return result.scalar_one_or_none()


async def upload_chunk(
    session: AsyncSession,
    upload_id: str,
    chunk_index: int,
    chunk_data: bytes,
    user_id: str,
) -> tuple[UploadSession, bool]:
    """
    Write a single chunk to disk and record it in the session.

    Returns (session, is_complete) — is_complete=True when all chunks received.

    Raises ValueError if chunk_index out of range, already uploaded, or session expired.
    """
    sess = await get_session(session, upload_id, user_id)
    if sess is None:
        raise ValueError("Upload session not found or expired.")

    if datetime.now(timezone.utc) > sess.expires_at:
        sess.status = UploadSessionStatus.expired.value
        await session.commit()
        raise ValueError("Upload session has expired.")

    if chunk_index < 0 or chunk_index >= sess.total_chunks:
        raise ValueError(f"Invalid chunk index {chunk_index} (expected 0-{sess.total_chunks - 1}).")

    if chunk_index in sess.uploaded_chunks:
        raise ValueError(f"Chunk {chunk_index} already uploaded.")

    # Write chunk to disk
    chunk_path = os.path.join(sess.session_path, f"chunk_{chunk_index:06d}")
    with open(chunk_path, "wb") as fh:
        fh.write(chunk_data)

    # Update DB
    sess.uploaded_chunks = sorted(sess.uploaded_chunks + [chunk_index])
    is_complete = len(sess.uploaded_chunks) == sess.total_chunks
    await session.commit()
    await session.refresh(sess)
    return sess, is_complete


async def complete_session(
    session: AsyncSession,
    upload_id: str,
    user_id: str,
    data_dir: str,
) -> tuple[UploadSession, str]:
    """
    Assemble all chunks into the final file, move to job directory,
    create the Job row, and enqueue translate_job.

    Returns (session, job_id).

    Raises ValueError if not all chunks are present or session is invalid.
    """
    sess = await get_session(session, upload_id, user_id)
    if sess is None:
        raise ValueError("Upload session not found or expired.")

    if len(sess.uploaded_chunks) != sess.total_chunks:
        missing = set(range(sess.total_chunks)) - set(sess.uploaded_chunks)
        raise ValueError(f"Not all chunks uploaded. Missing: {sorted(missing)}.")

    # Determine file extension
    original_ext = os.path.splitext(sess.original_filename)[1].lower()
    if not original_ext:
        original_ext = ".bin"

    # Assemble file in temp location first
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=original_ext) as tmp:
        tmp_path = tmp.name

    try:
        with open(tmp_path, "wb") as out_f:
            for i in range(sess.total_chunks):
                chunk_path = os.path.join(sess.session_path, f"chunk_{i:06d}")
                with open(chunk_path, "rb") as in_f:
                    out_f.write(in_f.read())
    except OSError as exc:
        os.unlink(tmp_path)
        raise ValueError(f"Failed to assemble chunks: {exc}") from exc

    # Create job directory and move file there
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(data_dir, "jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)
    final_path = os.path.join(job_dir, f"source{original_ext}")
    shutil.move(tmp_path, final_path)

    # Determine input_format
    fmt = original_ext.lstrip(".")
    if fmt == "pdf" and sess.is_scanned:
        input_format = "scanned_pdf"
    else:
        input_format = fmt

    # Create the Job row
    from app.services.job_service import create_job

    job, _is_dup = await create_job(
        session=session,
        source_lang=sess.source_lang or "auto",
        target_lang=sess.target_lang or "",
        input_format=input_format,
        input_path=final_path,
        original_filename=sess.original_filename,
        has_tracked_changes=sess.has_tracked_changes,
        tracked_changes_action=sess.tracked_changes_action,
        glossary_id=sess.glossary_id,
        user_id=user_id,
        queue_priority=sess.queue_priority,
    )

    # Mark session complete
    sess.status = UploadSessionStatus.completed.value
    sess.job_id = job.id
    await session.commit()

    # Enqueue translation
    from app.api.deps import get_arq_pool

    # Note: arq_pool must be injected by the caller since we can't
    # access FastAPI Depends() from here. The route handler will call this
    # and then enqueue separately.

    return sess, job.id


async def cancel_session(
    session: AsyncSession,
    upload_id: str,
    user_id: str,
    data_dir: str,
) -> None:
    """Cancel an active session: delete temp files and mark cancelled."""
    sess = await get_session(session, upload_id, user_id)
    if sess is None:
        return

    # Delete temp directory
    if os.path.isdir(sess.session_path):
        shutil.rmtree(sess.session_path)

    sess.status = UploadSessionStatus.cancelled.value
    await session.commit()


async def cleanup_expired_sessions(
    session: AsyncSession,
    data_dir: str = "/data",
) -> int:
    """
    Mark expired sessions as expired and delete their temp files.

    Called by the daily reconciliation cron task.

    Returns the number of sessions cleaned up.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(UploadSession).where(
            UploadSession.status == UploadSessionStatus.active.value,
            UploadSession.expires_at < now,
        )
    )
    expired: list[UploadSession] = list(result.scalars().all())

    count = 0
    for sess in expired:
        # Delete temp directory
        if os.path.isdir(sess.session_path):
            shutil.rmtree(sess.session_path)
        sess.status = UploadSessionStatus.expired.value
        count += 1

    if count > 0:
        await session.commit()

    return count
