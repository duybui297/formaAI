"""
POST /api/v1/upload — file upload, validation, job creation, arq enqueue.

Requirements:
- UPLD-01: accept file upload
- UPLD-02: restrict to .docx (Phase 1); accept .pptx/.pdf declaration but reject with 422
- UPLD-03: reject > tier-based max_file_bytes with 413 (TASK-3.7-d replaces global 25MB)
- UPLD-05: enqueue translate_job via shared arq pool (W11: no per-request pool creation)
- TASK-3.7: entitlement enforcement (license required, per-tier file size, monthly quota,
            OCR and glossary feature gates)

T-06a-01: extension checked; size guarded; path constructed server-side from data_dir + UUID.
T-06a-03: target_lang validated against _VALID_TARGET_CODES.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_active_user
from app.api.routes.languages import get_valid_target_codes_async
from app.db.models import User
from app.db.session import get_session
from app.licensing.entitlements import count_monthly_jobs, resolve_entitlements
from app.services.glossary_service import get_glossary
from app.services.job_service import create_job

log = structlog.get_logger()

router = APIRouter()

# TASK-3.7: Global cap removed — per-tier limits enforced after entitlement resolution.
# Kept as absolute ceiling to prevent pathological uploads before DB hit.
MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024  # 100 MB (ENTERPRISE ceiling, hard ceiling)
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pptx", ".pdf", ".xlsx"})  # UPLD-02
SUPPORTED_FORMATS: frozenset[str] = frozenset({".docx", ".pptx", ".pdf", ".xlsx"})

_STREAMING_CHUNK = 64 * 1024  # 64 KB per read chunk


@router.post("/upload", status_code=202)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    tracked_changes_action: str | None = Form(None),
    glossary_id: str | None = Form(None),
    is_scanned_override: bool | None = Form(None),
    session: AsyncSession = Depends(get_session),
    arq_pool=Depends(get_arq_pool),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """
    UPLD-01/02/03/05: Upload document, validate, create job row, enqueue translation.

    source_lang / target_lang: language codes (e.g. "auto", "vi", "en").
    Returns: {job_id: str, has_tracked_changes: bool}
    HTTP 202 — job created and queued, not yet complete.

    Auth: requires valid JWT (get_current_active_user).
    TASK-3.7: Entitlement enforcement — license required, per-tier file size,
              monthly quota, OCR and glossary feature gates.
    """
    # --- TASK-3.7: Resolve entitlements (license check + tier limits) ---
    entitlement = await resolve_entitlements(user=current_user, session=session)
    if entitlement is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "LICENSE_REQUIRED", "message": "An active license is required to upload documents."},
        )

    # --- TASK-3.7-f: Feature gate — OCR (is_scanned_override=True requests OCR explicitly) ---
    if is_scanned_override is True and not entitlement.ocr_allowed:
        raise HTTPException(
            status_code=403,
            detail={"error": "FEATURE_NOT_IN_PLAN", "feature": "ocr", "message": "OCR is not available on your current plan."},
        )

    # --- TASK-3.7-f: Feature gate — glossary ---
    if glossary_id is not None and not entitlement.glossary_allowed:
        raise HTTPException(
            status_code=403,
            detail={"error": "FEATURE_NOT_IN_PLAN", "feature": "glossary", "message": "Glossary support is not available on your current plan."},
        )

    # --- Fast path: Content-Length header sanity check using tier limit ---
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > entitlement.max_file_bytes:
        limit_mb = entitlement.max_file_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File too large — your plan allows up to {limit_mb} MB.")

    # --- Extension check (UPLD-02) ---
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a DOCX, PDF, PPTX, or XLSX.",
        )

    # --- Format gate (D-15) — defensive: ALLOWED_EXTENSIONS already filtered above ---
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=422,
            detail=f"{ext.lstrip('.').upper()} translation is not yet supported.",
        )

    # --- Language code validation (T-06a-03) ---
    if target_lang not in await get_valid_target_codes_async(session):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported target language: {target_lang!r}",
        )

    if source_lang != "auto" and source_lang == target_lang:
        raise HTTPException(
            status_code=422,
            detail="Source and target language must be different.",
        )

    # --- Glossary pair validation (D-02-25/26) ---
    if glossary_id is not None:
        g = await get_glossary(session, glossary_id)
        if g is None:
            raise HTTPException(status_code=422, detail="Glossary not found.")
        if g.source_lang != source_lang or g.target_lang != target_lang:
            raise HTTPException(
                status_code=422,
                detail="The selected glossary does not match the language pair.",
            )

    # --- Streaming size guard (TASK-3.7-d: per-tier limit, defence in depth) ---
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_STREAMING_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > entitlement.max_file_bytes:
            limit_mb = entitlement.max_file_bytes // (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"File too large — your plan allows up to {limit_mb} MB.")
        chunks.append(chunk)
    content: bytes = b"".join(chunks)

    # --- TASK-3.7-e: Monthly quota enforcement ---
    if entitlement.monthly_quota is not None:
        quota_used = await count_monthly_jobs(user_id=str(current_user.id), session=session)
        if quota_used >= entitlement.monthly_quota:
            raise HTTPException(
                status_code=403,
                detail={"error": "QUOTA_EXCEEDED", "message": f"Monthly translation quota of {entitlement.monthly_quota} reached."},
            )

    # --- D-04-17: Scanned PDF detection ---
    is_scanned = False
    if ext == ".pdf":
        if is_scanned_override is not None:
            is_scanned = is_scanned_override
        else:
            try:
                import pymupdf  # noqa: PLC0415
                from app.pipeline.scanned_pdf.detector import detect_scanned_pdf  # noqa: PLC0415

                _settings = request.app.state.settings
                _probe_doc = pymupdf.open(stream=content, filetype="pdf")
                is_scanned = detect_scanned_pdf(
                    _probe_doc,
                    threshold=_settings.ocr_text_density_threshold,
                )
                _probe_doc.close()
            except Exception:
                is_scanned = False  # Detection failure → treat as native; worker handles real errors

    # Determine effective input format
    if ext == ".pdf" and is_scanned:
        input_format = "scanned_pdf"
    else:
        input_format = ext.lstrip(".")  # "docx", "pptx", "pdf"

    # --- DOCX tracked-changes probe (DOCX-04 / D-13) ---
    has_tracked = False
    if ext == ".docx":
        try:
            # Write to temp file for python-docx (needs a seekable stream / path)
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                from docx import Document  # noqa: PLC0415
                from app.pipeline.docx.tracked import has_tracked_changes  # noqa: PLC0415

                doc = Document(tmp_path)
                has_tracked = has_tracked_changes(doc)
            finally:
                os.unlink(tmp_path)
        except Exception:
            # Malformed DOCX — let worker report the real error; upload proceeds.
            pass

    # --- Idempotency key (US-3.7 AC-5) ---
    idempotency_key = request.headers.get("Idempotency-Key")

    # --- Create Job row (DB auto-generates job.id via uuid4 default) ---
    settings = request.app.state.settings
    job, is_duplicate = await create_job(
        session=session,
        source_lang=source_lang,
        target_lang=target_lang,
        input_format=input_format,
        input_path="",
        original_filename=filename,
        has_tracked_changes=has_tracked,
        tracked_changes_action=tracked_changes_action,
        glossary_id=glossary_id,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        queue_priority=entitlement.queue_priority,
    )

    # US-3.7 AC-5: idempotent — return existing job if key was already used
    if is_duplicate:
        log.info("upload_idempotent", job_id=job.id, key=idempotency_key)
        return {
            "job_id": job.id,
            "has_tracked_changes": job.has_tracked_changes,
            "is_duplicate": True,
        }

    # --- Persist file to per-job directory (D-04: .data/jobs/{job_id}/source.{ext}) ---
    job_dir = os.path.join(settings.data_dir, "jobs", job.id)
    os.makedirs(job_dir, exist_ok=True)
    input_path = os.path.join(job_dir, f"source{ext}")
    with open(input_path, "wb") as fh:
        fh.write(content)

    # Update input_path on the job row now that we have the final path
    job.input_path = input_path
    await session.commit()

    # --- Enqueue arq job via shared pool (W11: no per-request pool) ---
    # US-3.7 AC-6: priority lanes — ENTERPRISE=1, PRO=5, TRIAL=10
    await arq_pool.enqueue_job(
        "translate_job", job.id,
        priority=job.queue_priority,
    )

    log.info("upload_accepted", job_id=job.id, filename=filename, size_bytes=total)

    return {
        "job_id": job.id,
        "has_tracked_changes": has_tracked,
        "is_scanned": is_scanned,
    }
