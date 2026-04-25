"""
Export endpoint — REV-05, REV-06.

POST /jobs/{id}/export  — idempotent DOCX reassembly; returns FileResponse
"""
from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.services.export_service import export_job

log = structlog.get_logger()
router = APIRouter()


@router.post("/jobs/{job_id}/export")
async def export_document(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse | JSONResponse:
    """REV-05/06: Idempotent DOCX export using edited_text ?? translated_text.

    Advisory lock prevents concurrent corrupt-write (D-02-22).
    Atomic write (tmp + os.replace) prevents partial-read race.
    Export does NOT mutate segment rows (REV-06).
    Returns FileResponse for browser download, or JSONResponse on error.
    """
    try:
        output_path = await export_job(session, job_id, settings.data_dir)
    except ValueError as exc:
        # Job not found or wrong state — 409 Conflict
        return JSONResponse(
            status_code=409,
            content={"code": "export_state_error", "detail": str(exc)},
        )
    except AttributeError as exc:
        # run_index / run_group_size missing on ORM model — recoverable after migration
        log.error("export_attribute_error", job_id=job_id, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"code": "export_failed", "detail": f"Export assembly error: {exc}"},
        )
    except Exception as exc:
        # Catch-all for unexpected failures (file I/O, DB error)
        log.error("export_unexpected_error", job_id=job_id, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"code": "export_failed", "detail": f"Export failed: {exc}"},
        )

    return FileResponse(
        path=output_path,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        filename=Path(output_path).name,
    )
