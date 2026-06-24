"""
Chunked resumable upload API — US-3.1 AC-4.

All routes are prefixed with /api/v1 (applied at app level).

Flow:
  1. POST /api/v1/upload/init          — create session, return upload_id + chunk_size
  2. POST /api/v1/upload/{id}/chunks/{n}  — upload one 5 MB chunk
  3. GET  /api/v1/upload/{id}/status     — check uploaded chunks progress
  4. POST /api/v1/upload/{id}/complete   — assemble chunks, create Job, enqueue translate
  5. DELETE /api/v1/upload/{id}          — cancel upload

Supports resumable uploads: if a chunk upload fails, the client can retry
the same chunk index without re-uploading already-received chunks.

Entitlement enforcement (file size, monthly quota, feature gates) is applied
at the /upload/init step (same as the single-shot upload).
"""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.params import Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_active_user
from app.api.routes.languages import get_valid_target_codes_async
from app.db.models import User
from app.db.session import db_dependency, get_session
from app.licensing.entitlements import count_monthly_jobs, resolve_entitlements
from app.services.glossary_service import get_glossary
from app.services.upload_session_service import (
    DEFAULT_CHUNK_SIZE,
    SESSION_TTL_HOURS,
    cancel_session,
    complete_session,
    get_session,
    init_session,
    upload_chunk,
)

log = structlog.get_logger()

router = APIRouter()

# Absolute ceiling — same as single-shot upload
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB ENTERPRISE ceiling
_ALLOWED_EXTENSIONS = frozenset({".docx", ".pptx", ".pdf", ".xlsx"})
_SUPPORTED_FORMATS = frozenset({".docx", ".pptx", ".pdf", ".xlsx"})


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InitUploadRequest(BaseModel):
    filename: str
    file_size: int
    source_lang: str
    target_lang: str
    glossary_id: str | None = None
    tracked_changes_action: str | None = None
    is_scanned_override: bool | None = None


class InitUploadResponse(BaseModel):
    upload_id: str
    chunk_size: int
    total_chunks: int
    expires_at: str  # ISO8601


class ChunkStatusResponse(BaseModel):
    upload_id: str
    total_chunks: int
    uploaded_chunks: list[int]
    status: str


class CompleteUploadResponse(BaseModel):
    job_id: str
    has_tracked_changes: bool
    is_scanned: bool


# ---------------------------------------------------------------------------
# POST /upload/init — start a chunked upload session
# ---------------------------------------------------------------------------


@router.post("/upload/init", status_code=202)
async def init_upload(
    request: Request,
    body: InitUploadRequest,
    session: AsyncSession = Depends(db_dependency),
    current_user: User = Depends(get_current_active_user),
) -> InitUploadResponse:
    """
    Create a chunked upload session.

    Validates entitlement (license, file size, monthly quota, feature gates)
    before creating the session. The session is valid for 2 hours.
    """
    entitlement = await resolve_entitlements(user=current_user, session=session)
    if entitlement is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "LICENSE_REQUIRED", "message": "An active license is required."},
        )

    # Feature gate: OCR
    if body.is_scanned_override is True and not entitlement.ocr_allowed:
        raise HTTPException(
            status_code=403,
            detail={"error": "FEATURE_NOT_IN_PLAN", "feature": "ocr", "message": "OCR is not available on your current plan."},
        )

    # Feature gate: glossary
    if body.glossary_id is not None and not entitlement.glossary_allowed:
        raise HTTPException(
            status_code=403,
            detail={"error": "FEATURE_NOT_IN_PLAN", "feature": "glossary", "message": "Glossary is not available on your current plan."},
        )

    # File size enforcement (hard ceiling + tier limit)
    if body.file_size > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds absolute size limit of {_MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )
    if body.file_size > entitlement.max_file_bytes:
        limit_mb = entitlement.max_file_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large — your plan allows up to {limit_mb} MB.",
        )

    # Extension check
    ext = os.path.splitext(body.filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a DOCX, PDF, PPTX, or XLSX.",
        )

    # Target language validation
    if body.target_lang not in await get_valid_target_codes_async(session):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported target language: {body.target_lang!r}",
        )

    if body.source_lang != "auto" and body.source_lang == body.target_lang:
        raise HTTPException(
            status_code=422,
            detail="Source and target language must be different.",
        )

    # Glossary pair validation
    if body.glossary_id is not None:
        g = await get_glossary(session, body.glossary_id)
        if g is None:
            raise HTTPException(status_code=422, detail="Glossary not found.")
        if g.source_lang != body.source_lang or g.target_lang != body.target_lang:
            raise HTTPException(
                status_code=422,
                detail="The selected glossary does not match the language pair.",
            )

    # Monthly quota check
    if entitlement.monthly_quota is not None:
        quota_used = await count_monthly_jobs(
            user_id=str(current_user.id), session=session
        )
        if quota_used >= entitlement.monthly_quota:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "QUOTA_EXCEEDED",
                    "message": f"Monthly translation quota of {entitlement.monthly_quota} reached.",
                },
            )

    # Determine is_scanned (PDF only)
    is_scanned = False

    settings = request.app.state.settings

    # Create the upload session
    sess = await init_session(
        session=session,
        user_id=str(current_user.id),
        original_filename=body.filename,
        file_size=body.file_size,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
        glossary_id=body.glossary_id,
        has_tracked_changes=False,
        tracked_changes_action=body.tracked_changes_action,
        is_scanned=is_scanned,
        chunk_size=DEFAULT_CHUNK_SIZE,
        data_dir=settings.data_dir,
        queue_priority=entitlement.queue_priority,
    )

    log.info(
        "chunked_upload_init",
        upload_id=sess.id,
        user_id=current_user.id,
        filename=body.filename,
        size_bytes=body.file_size,
        chunks=sess.total_chunks,
    )

    return InitUploadResponse(
        upload_id=sess.id,
        chunk_size=sess.chunk_size,
        total_chunks=sess.total_chunks,
        expires_at=sess.expires_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# POST /upload/{upload_id}/chunks/{n} — upload one chunk
# ---------------------------------------------------------------------------


@router.post("/upload/{upload_id}/chunks/{chunk_index}")
async def upload_chunk_endpoint(
    upload_id: str,
    chunk_index: int,
    request: Request,
    session: AsyncSession = Depends(db_dependency),
    current_user: User = Depends(get_current_active_user),
) -> ChunkStatusResponse:
    """
    Upload a single chunk of the file.

    Idempotent for successfully-uploaded chunks: if a chunk is already
    received, re-sending it returns OK without error.
    """
    settings = request.app.state.settings

    # Read chunk from request body (binary)
    chunk_data = await request.body()
    if not chunk_data:
        raise HTTPException(status_code=400, detail="Empty chunk body.")

    try:
        sess, is_complete = await upload_chunk(
            session=session,
            upload_id=upload_id,
            chunk_index=chunk_index,
            chunk_data=chunk_data,
            user_id=str(current_user.id),
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg or "expired" in msg:
            raise HTTPException(status_code=404, detail=msg)
        if "already uploaded" in msg:
            # Idempotent — return OK
            sess = await get_session(session, upload_id, str(current_user.id))
            if sess is None:
                raise HTTPException(status_code=404, detail="Session not found.")
        else:
            raise HTTPException(status_code=400, detail=msg)

    log.info(
        "chunk_uploaded",
        upload_id=upload_id,
        chunk_index=chunk_index,
        is_complete=is_complete,
        user_id=current_user.id,
    )

    return ChunkStatusResponse(
        upload_id=sess.id,
        total_chunks=sess.total_chunks,
        uploaded_chunks=sess.uploaded_chunks,
        status=str(sess.status),
    )


# ---------------------------------------------------------------------------
# GET /upload/{upload_id}/status — check upload progress
# ---------------------------------------------------------------------------


@router.get("/upload/{upload_id}/status", response_model=ChunkStatusResponse)
async def get_upload_status(
    upload_id: str,
    session: AsyncSession = Depends(db_dependency),
    current_user: User = Depends(get_current_active_user),
) -> ChunkStatusResponse:
    """Return the current upload progress for a session."""
    sess = await get_session(session, upload_id, str(current_user.id))
    if sess is None:
        raise HTTPException(status_code=404, detail="Upload session not found.")

    return ChunkStatusResponse(
        upload_id=sess.id,
        total_chunks=sess.total_chunks,
        uploaded_chunks=sess.uploaded_chunks,
        status=str(sess.status),
    )


# ---------------------------------------------------------------------------
# POST /upload/{upload_id}/complete — assemble chunks and start translation
# ---------------------------------------------------------------------------


@router.post("/upload/{upload_id}/complete", status_code=202)
async def complete_upload(
    upload_id: str,
    request: Request,
    session: AsyncSession = Depends(db_dependency),
    arq_pool=Depends(get_arq_pool),
    current_user: User = Depends(get_current_active_user),
) -> CompleteUploadResponse:
    """
    Assemble all uploaded chunks into the final file, create a Job row,
    and enqueue the translation.

    Returns {job_id, has_tracked_changes, is_scanned}.
    """
    settings = request.app.state.settings

    try:
        sess, job_id = await complete_session(
            session=session,
            upload_id=upload_id,
            user_id=str(current_user.id),
            data_dir=settings.data_dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # US-3.7 AC-6: priority lanes — pass session's priority to arq
    await arq_pool.enqueue_job(
        "translate_job", job_id,
        priority=sess.queue_priority,
    )

    log.info(
        "chunked_upload_complete",
        upload_id=upload_id,
        job_id=job_id,
        user_id=current_user.id,
    )

    return CompleteUploadResponse(
        job_id=job_id,
        has_tracked_changes=sess.has_tracked_changes,
        is_scanned=sess.is_scanned,
    )


# ---------------------------------------------------------------------------
# DELETE /upload/{upload_id} — cancel an upload session
# ---------------------------------------------------------------------------


@router.delete("/upload/{upload_id}", status_code=204, response_model=None)
async def cancel_upload(
    upload_id: str,
    request: Request,
    session: AsyncSession = Depends(db_dependency),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Cancel an active upload session and delete its temp files."""
    settings = request.app.state.settings
    await cancel_session(
        session=session,
        upload_id=upload_id,
        user_id=str(current_user.id),
        data_dir=settings.data_dir,
    )
    log.info("chunked_upload_cancelled", upload_id=upload_id, user_id=current_user.id)
