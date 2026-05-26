"""
Export endpoint — REV-05, REV-06.

POST /jobs/{id}/export  — idempotent DOCX reassembly; returns FileResponse
"""
from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_session
from app.services.export_service import export_job
from app.services.job_service import get_job_for_user
from app.api.deps import get_current_active_user

log = structlog.get_logger()
router = APIRouter()


@router.post("/jobs/{job_id}/export", response_model=None)
async def export_document(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse | JSONResponse:
    """REV-05/06: Idempotent DOCX export using edited_text ?? translated_text.

    Advisory lock prevents concurrent corrupt-write (D-02-22).
    Atomic write (tmp + os.replace) prevents partial-read race.
    Export does NOT mutate segment rows (REV-06).
    Returns FileResponse for browser download, or JSONResponse on error.
    """
    # Ownership check
    job = await get_job_for_user(session, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    try:
        output_path = await export_job(session, job_id, settings.data_dir)
    except ValueError as exc:
        return JSONResponse(
            status_code=409,
            content={"code": "export_state_error", "detail": str(exc)},
        )
    except AttributeError as exc:
        log.error("export_attribute_error", job_id=job_id, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"code": "export_failed", "detail": f"Export assembly error: {exc}"},
        )
    except Exception as exc:
        log.error("export_unexpected_error", job_id=job_id, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"code": "export_failed", "detail": f"Export failed: {exc}"},
        )

    suffix = Path(output_path).suffix.lower()
    media_type = {
        ".docx": (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        ".pptx": (
            "application/vnd.openxmlformats-officedocument"
            ".presentationml.presentation"
        ),
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")

    return FileResponse(
        path=output_path,
        media_type=media_type,
        filename=Path(output_path).name,
    )