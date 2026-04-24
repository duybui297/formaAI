"""
GET /jobs          — list last 50 jobs, newest first (JOB-01)
GET /jobs/{id}     — job status detail with D-10 fields (JOB-01/04)
GET /jobs/{id}/download — stream translated output file (JOB-04)

T-06b-01: output_path is server-stored in DB, never user-supplied.
          os.path.exists check before FileResponse prevents stale path 404.
"""
from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job
from app.db.session import get_session
from app.services.job_service import get_job

log = structlog.get_logger()

router = APIRouter()

# Terminal statuses that permit file download
_DOWNLOADABLE_STATUSES = frozenset({"done", "needs_review"})


def _job_to_dict(job: Job) -> dict:
    """Serialize Job ORM model to D-10 response dict.

    D-10: payload shape for both REST and SSE events.
    """
    return {
        "id": job.id,
        "status": job.status.value,
        "stage": job.stage.value if job.stage else None,
        "source_lang": job.source_lang,
        "target_lang": job.target_lang,
        "detected_lang": job.detected_lang,
        "input_format": job.input_format,
        "original_filename": job.original_filename,
        "segments_done": job.segments_done,
        "segments_total": job.segments_total,
        "retry_count": job.retry_count,
        "error_msg": job.error_msg,
        "has_tracked_changes": job.has_tracked_changes,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.get("/jobs")
async def list_jobs(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """JOB-01: Return last 50 jobs, newest first (Jobs List Page).

    # TODO(phase-2): add JWT auth + per-user filtering
    """
    result = await session.execute(
        select(Job).order_by(desc(Job.created_at)).limit(50)
    )
    jobs = result.scalars().all()
    return {"jobs": [_job_to_dict(j) for j in jobs]}


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """JOB-01/04: Return job status + progress counters.

    Returns D-10 fields: id, status, stage, source_lang, target_lang,
    detected_lang, input_format, original_filename, segments_done,
    segments_total, retry_count, error_msg, has_tracked_changes,
    created_at, updated_at.

    # TODO(phase-2): add JWT auth
    """
    job = await get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@router.get("/jobs/{job_id}/download")
async def download_translated_file(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """JOB-04: Stream the translated output file for completed jobs.

    T-06b-01: output_path is server-stored in DB (not user-supplied).
              os.path.exists guard prevents 500 on stale path.

    HTTP 404 — job not found or output file missing/deleted
    HTTP 409 — job not yet in a terminal state (done/needs_review)

    # TODO(phase-2): add JWT auth
    """
    job = await get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status.value not in _DOWNLOADABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not yet complete (current status: {job.status.value})",
        )

    if not job.output_path:
        raise HTTPException(status_code=404, detail="Output file not found")

    # T-06b-01: output_path is from DB (server-side), not user-supplied
    if not os.path.exists(job.output_path):
        log.warning("output_file_missing", job_id=job_id, path=job.output_path)
        raise HTTPException(status_code=404, detail="Output file has been deleted")

    download_name = f"translated_{job.original_filename}"
    return FileResponse(
        path=job.output_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
