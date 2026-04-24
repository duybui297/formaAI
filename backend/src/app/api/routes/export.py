"""
Export endpoint — REV-05, REV-06.

POST /jobs/{id}/export  — idempotent DOCX reassembly; returns FileResponse
"""
from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
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
) -> FileResponse:
    """REV-05/06: Idempotent DOCX export using edited_text ?? translated_text.

    Advisory lock prevents concurrent corrupt-write (D-02-22).
    Atomic write (tmp + os.replace) prevents partial-read race.
    Export does NOT mutate segment rows (REV-06).
    Returns FileResponse for browser download.
    """
    try:
        output_path = await export_job(session, job_id, settings.data_dir)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return FileResponse(
        path=output_path,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        filename=Path(output_path).name,
    )
