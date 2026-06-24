"""
GET /api/v1/jobs          — paginated list of user's jobs, newest first (US-4.1)
GET /api/v1/jobs/{id}     — job status detail with D-10 fields (JOB-01/04)
GET /api/v1/jobs/{id}/download — stream translated output file (JOB-04)

T-06b-01: output_path is server-stored in DB, never user-supplied.
          os.path.exists check before FileResponse prevents stale path 404.
"""
from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models import Job, User
from app.db.session import get_session
from app.services.job_service import get_job, get_job_for_user

log = structlog.get_logger()

router = APIRouter()

# Terminal statuses that permit file download
_DOWNLOADABLE_STATUSES = frozenset({"done", "needs_review"})

# US-4.1: pagination defaults and limits
_PAGE_SIZES = frozenset({5, 10, 25})
_DEFAULT_PAGE_SIZE = 10
_MAX_PAGE_SIZE = 100


class PaginatedJobsResponse(BaseModel):
    jobs: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


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
        "glossary_id": job.glossary_id,
        "low_confidence_pages": job.low_confidence_pages,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.get("/jobs", response_model=PaginatedJobsResponse)
async def list_jobs(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE, description="Items per page"),
    sort: str = Query("newest", description='Sort order: "newest" or "oldest"'),
) -> PaginatedJobsResponse:
    """US-4.1: Paginated list of jobs for the current user.

    Columns: filename, lang pair, status, date+time, actions.
    Statuses: done / running / queued / needs_review / failed.
    Pagination: 5 / 10 / 25 per page.
    Default sort: newest first.

    Auth: requires valid JWT (get_current_active_user).
    Per-user filtering via job.user_id FK.
    """
    if page_size not in _PAGE_SIZES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid page_size={page_size}. Must be one of: {sorted(_PAGE_SIZES)}.",
        )
    if sort not in {"newest", "oldest"}:
        sort = "newest"
    if sort == "oldest":
        order_col = Job.created_at
    else:
        # Default: newest first
        order_col = desc(Job.created_at)

    # Count total matching rows
    count_q = select(func.count(Job.id)).where(Job.user_id == current_user.id)
    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    # Paginated data query
    offset = (page - 1) * page_size
    data_q = (
        select(Job)
        .where(Job.user_id == current_user.id)
        .order_by(desc(Job.created_at) if sort != "oldest" else Job.created_at)
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(data_q)
    jobs = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedJobsResponse(
        jobs=[_job_to_dict(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """JOB-01/04: Return job status + progress counters for the current user.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: job must belong to current_user.
    Returns D-10 fields: id, status, stage, source_lang, target_lang,
    detected_lang, input_format, original_filename, segments_done,
    segments_total, retry_count, error_msg, has_tracked_changes,
    created_at, updated_at.
    """
    job = await get_job_for_user(session, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@router.get("/jobs/{job_id}/artifacts")
async def download_artifact(
    job_id: str,
    artifact: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> FileResponse:
    """D-04-22: Download one of three compose-stage artifacts.

    artifact: bilingual_pdf | translated_pdf | translated_docx
    T-04-09: artifact parameter validated against strict allowlist; path computed
             from job_id (UUID from DB), never from user input.
    T-04-11: 409 returned if job not in done/needs_review.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: job must belong to current_user.
    """
    from app.core.config import get_settings  # noqa: PLC0415

    job = await get_job_for_user(session, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status.value not in _DOWNLOADABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not yet complete (current status: {job.status.value})",
        )

    # T-04-09: strict allowlist — no user-controlled path components
    _artifact_map: dict[str, tuple[str, str]] = {
        "bilingual_pdf": (
            "output.pdf",
            "application/pdf",
        ),
        "translated_pdf": (
            "output-translated-only.pdf",
            "application/pdf",
        ),
        "translated_docx": (
            "output.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    }
    if artifact not in _artifact_map:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown artifact '{artifact}'. Use: {', '.join(_artifact_map)}",
        )

    settings = get_settings()
    filename, media_type = _artifact_map[artifact]
    file_path = os.path.join(settings.data_dir, "jobs", job_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Artifact '{artifact}' not found for this job",
        )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=f"job-{job_id[:8]}-{filename}",
    )


@router.get("/jobs/{job_id}/pages/{page_n}.png")
async def serve_page_image(
    job_id: str,
    page_n: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> FileResponse:
    """D-04-10/11: Serve cached page PNG for image-crop preview in review UI.

    T-04-10: page_n is typed as int (FastAPI auto-validates); path constructed
             from job_id (UUID from DB) + page_n (int) — no directory traversal.
    Auth: requires valid JWT. Ownership enforced via job lookup.
    """
    from app.core.config import get_settings  # noqa: PLC0415

    job = await get_job_for_user(session, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    settings = get_settings()
    file_path = os.path.join(
        settings.data_dir, "jobs", job_id, "pages", f"page-{page_n}.png"
    )
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Page {page_n} image not found",
        )
    return FileResponse(path=file_path, media_type="image/png")


@router.get("/jobs/{job_id}/download")
async def download_translated_file(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> FileResponse:
    """JOB-04: Stream the translated output file for completed jobs.

    T-06b-01: output_path is server-stored in DB (not user-supplied).
              os.path.exists guard prevents 500 on stale path.

    HTTP 404 — job not found or output file missing/deleted
    HTTP 409 — job not yet in a terminal state (done/needs_review)

    Auth: requires valid JWT (get_current_active_user).
    Ownership: job must belong to current_user.
    """
    job = await get_job_for_user(session, job_id, current_user.id)
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

    _media_type_map: dict[str, str] = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    media_type = _media_type_map.get(job.input_format, "application/octet-stream")
    return FileResponse(
        path=job.output_path,
        filename=f"{job.original_filename}",
        media_type=media_type,
    )


@router.delete("/jobs/{job_id}", status_code=204, response_model=None)
async def delete_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Delete a job and its associated files.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: job must belong to current_user.

    Returns HTTP 204 on success (no body).
    HTTP 404 if job not found or not owned by user.
    """
    from app.core.config import get_settings

    job = await get_job_for_user(session, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    settings = get_settings()

    # Delete the job's data directory (source + output files)
    job_dir = os.path.join(settings.data_dir, "jobs", job_id)
    if os.path.isdir(job_dir):
        import shutil
        shutil.rmtree(job_dir)

    # Delete the Job row from DB (cascade deletes segments + flags)
    await session.delete(job)
    await session.commit()
