"""
Export service: idempotent DOCX reassembly with advisory lock and atomic write.

REV-05: Export reassembles using edited_text ?? translated_text.
REV-06: Export is idempotent — re-exporting produces same output; does not mutate segments.

Advisory lock design (D-02-22):
- asyncio.Lock per job_id stored in WeakValueDictionary
- In-process lock is sufficient for single-uvicorn-process PoC
- TODO(v2): upgrade to pg_advisory_lock if deploying multiple API workers

Atomic write: doc.save(tmp_path) then os.replace(tmp_path, output_path)
- Prevents a concurrent reader from seeing a half-written file during reassembly
- os.replace is atomic on POSIX filesystems when src/dst are on same volume
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from weakref import WeakValueDictionary

import structlog
from docx import Document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, JobStatus, Segment
from app.pipeline.docx.reassembler import reassemble_docx_runs

log = structlog.get_logger()

# In-process advisory lock per job_id (sufficient for single-process API)
# TODO(v2): upgrade to pg_advisory_lock if deploying multiple API workers
_export_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
_locks_mutex = asyncio.Lock()

_EXPORTABLE_STATUSES = frozenset({JobStatus.done, JobStatus.needs_review})


async def _get_export_lock(job_id: str) -> asyncio.Lock:
    """Get or create an asyncio.Lock for the given job_id."""
    async with _locks_mutex:
        lock = _export_locks.get(job_id)
        if lock is None:
            lock = asyncio.Lock()
            _export_locks[job_id] = lock
        return lock


async def export_job(
    session: AsyncSession,
    job_id: str,
    data_dir: str,
) -> str:
    """REV-05/06: Idempotent DOCX reassembly.

    Acquires per-job advisory lock, reads a snapshot of segment state,
    reassembles using edited_text ?? translated_text, writes output.docx atomically.
    Does NOT mutate any segment rows.

    Returns the output file path as a string.
    Raises ValueError if job is not in an exportable state.
    """
    lock = await _get_export_lock(job_id)
    async with lock:
        # Load job
        result = await session.execute(
            select(Job).where(Job.id == job_id)
        )
        job: Job | None = result.scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        if job.status not in _EXPORTABLE_STATUSES:
            raise ValueError(
                f"Job {job_id} is in state '{job.status.value}' — "
                "export requires 'done' or 'needs_review'"
            )

        # Load segments ordered by seq_in_job (read snapshot — no mutation)
        seg_result = await session.execute(
            select(Segment)
            .where(Segment.job_id == job_id)
            .order_by(Segment.seq_in_job)
        )
        segments = list(seg_result.scalars().all())

        # REV-05: build translated_map using edited_text ?? translated_text
        # Pitfall 5: use explicit None check, not `or` — empty string edit must be respected
        translated_map: dict[str, str] = {
            seg.id: (
                seg.edited_text
                if seg.edited_text is not None
                else (seg.translated_text or "")
            )
            for seg in segments
        }

        # Reassemble DOCX — reassembler is unchanged from Phase 1 (DOCX-02 invariant preserved)
        doc = Document(job.input_path)
        doc = reassemble_docx_runs(doc, segments, translated_map)

        # Atomic write: tmp file → os.replace → output_path
        # Prevents concurrent reader seeing a half-written file (os.replace is atomic on POSIX)
        output_path = str(Path(data_dir) / "jobs" / job_id / "output.docx")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        tmp_path = output_path + ".tmp"
        doc.save(tmp_path)
        os.replace(tmp_path, output_path)

        log.info(
            "export_complete",
            job_id=job_id,
            output_path=output_path,
            segments=len(segments),
        )
        return output_path
