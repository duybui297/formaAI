"""
POST /api/v1/translations  — submit a translation job (US-3.7 spec-aligned)
GET  /api/v1/translations  — paginated list of translations, org-scoped (US-4.1)
POST /api/v1/translations/estimate — lightweight word-count + credit cost estimate (US-3.6)

Accepts multipart/form-data with the source file and job metadata.
This is the spec-aligned alternative to POST /upload; both share the same
implementation but this endpoint carries the spec name.

US-3.6: POST /translations/estimate parses the uploaded source, returns wordCount + creditCost.
US-3.7 AC-5: Idempotency key via Idempotency-Key header.
US-3.7 AC-6: Priority lanes per plan (Free/PRO/ENTERPRISE).
US-4.1: paginated list with page/size/sort; org-scoped via workspace_id.

Auth: requires valid JWT.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_arq_pool, get_current_active_user
from app.api.routes.languages import get_valid_target_codes_async
from app.db.models import FailureReason, Job, User
from app.db.session import get_session
from app.licensing.entitlements import count_monthly_jobs, resolve_entitlements
from app.services.estimate_service import count_words_in_file, estimate_credit_cost
from app.services.glossary_service import get_glossary
from app.services.job_service import create_job

log = structlog.get_logger()

router = APIRouter()

MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024  # 100 MB absolute ceiling
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pptx", ".pdf", ".xlsx"})
SUPPORTED_FORMATS: frozenset[str] = frozenset({".docx", ".pptx", ".pdf", ".xlsx"})

_STREAMING_CHUNK = 64 * 1024  # 64 KB per read chunk


# ---------------------------------------------------------------------------
# US-3.6: POST /translations/estimate — word count + credit cost estimate
# ---------------------------------------------------------------------------


class EstimateResponse(BaseModel):
    """US-3.6 response: word count, credit cost, and credit sufficiency flag."""

    word_count: int
    credit_cost: int
    has_sufficient_credits: bool
    is_scanned: bool


@router.post("/translations/estimate", response_model=EstimateResponse)
async def estimate_translation(
    request: Request,
    file: UploadFile = File(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    is_scanned_override: bool | None = Form(None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> EstimateResponse:
    """
    US-3.6: Lightweight word-count + credit-cost estimation.

    Accepts the same file + language inputs as /translations.
    Does NOT create a job or persist the file.
    Does NOT check monthly quota (quota is consumed only on job submission).

    Returns: {word_count, credit_cost, has_sufficient_credits, is_scanned}
    """
    # --- Entitlement check (LICENSE_REQUIRED) ---
    entitlement = await resolve_entitlements(user=current_user, session=session)
    if entitlement is None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "LICENSE_REQUIRED",
                "message": "An active license is required to estimate translation cost.",
            },
        )

    # --- Extension check ---
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Accepted: DOCX, PDF, PPTX, XLSX.",
        )

    # --- Language validation ---
    if target_lang not in await get_valid_target_codes_async(session):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported target language: {target_lang!r}.",
        )
    if source_lang != "auto" and source_lang == target_lang:
        raise HTTPException(
            status_code=422,
            detail="Source and target language must be different.",
        )

    # --- Read file bytes (streaming, capped at absolute max) ---
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_STREAMING_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large for estimation — maximum is 100 MB.",
            )
        chunks.append(chunk)
    content: bytes = b"".join(chunks)

    # --- Detect scanned PDF ---
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
                is_scanned = False

    # --- Word count ---
    word_count = count_words_in_file(content, ext)

    # --- Credit cost ---
    tier_name = entitlement.tier.value  # "TRIAL", "PRO", "ENTERPRISE"
    credit_cost = estimate_credit_cost(word_count, tier_name, is_scanned)

    # --- US-3.6: has_sfficient_credits = sufficient quota ===
    # For the estimate, we check against monthly_quota (not a ledger balance).
    # A user with unlimited quota (None) always has sufficient credits.
    has_sufficient_credits = True
    if entitlement.monthly_quota is not None:
        quota_used = await count_monthly_jobs(
            user_id=str(current_user.id), session=session
        )
        remaining = entitlement.monthly_quota - quota_used
        # "1 job = word_count/1000" rough credit units for quota check.
        # Simplify: if remaining > 0, user can submit.
        # credit_cost is informational; actual debit happens on job completion (US-3.8).
        has_sufficient_credits = remaining > 0

    return EstimateResponse(
        word_count=word_count,
        credit_cost=credit_cost,
        has_sufficient_credits=has_sufficient_credits,
        is_scanned=is_scanned,
    )


# ---------------------------------------------------------------------------
# US-4.1: GET /api/v1/translations — paginated, org-scoped list
# ---------------------------------------------------------------------------
# Spec quote (US-4.1 [BE]):
#   GET /api/v1/translations?page=&size=&sort= (default sort: -created_at)
#   Org-scoped query
#   Response: rows + total + page metadata
#
# Org scoping (matches the workspace model in `User.workspace_id`):
#   - if user.workspace_id is set → all jobs whose owner shares that workspace
#   - else (personal workspace)    → only jobs owned by this user

_ALLOWED_PAGE_SIZES = frozenset({5, 10, 25})
_DEFAULT_PAGE_SIZE = 10


class PaginatedTranslationsResponse(BaseModel):
    """US-4.1 response shape — key is `rows` per spec, not `jobs`."""

    rows: list[dict]
    total: int
    page: int
    size: int
    total_pages: int


def _serialize_translation_row(job: Job) -> dict:
    """Spec-aligned row shape: filename, lang pair, status, date+time.

    Plus job_id (id) and input_format for the FE actions column.
    """
    return {
        "job_id": job.id,
        "filename": job.original_filename,
        "input_format": job.input_format,
        "source_lang": job.source_lang,
        "target_lang": job.target_lang,
        "status": job.status.value,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.get("/translations", response_model=PaginatedTranslationsResponse)
async def list_translations(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(
        _DEFAULT_PAGE_SIZE,
        description="Items per page (must be one of 5, 10, 25)",
    ),
    sort: str = Query(
        "-created_at",
        description=(
            'Field to sort by. Prefix with "-" for descending. '
            'Allowed: "created_at", "-created_at". Default: "-created_at".'
        ),
    ),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedTranslationsResponse:
    """US-4.1 [BE] — list translations for the caller's organization.

    Query parameters (per spec):
      - page: 1-indexed page number, default 1
      - size: items per page, one of {5, 10, 25}, default 10
      - sort: sort field; prefix "-" means descending. Default: "-created_at"

    Org-scoped query: results include jobs owned by the caller AND by every
    user sharing their workspace_id. Falls back to personal scope (caller
    only) when no workspace is set.

    Response: {"rows": [...], "total": N, "page": P, "size": S, "total_pages": T}
    """
    if size not in _ALLOWED_PAGE_SIZES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid size={size}. Must be one of: {sorted(_ALLOWED_PAGE_SIZES)}.",
        )

    sort_prefix, sep, sort_field = sort.partition("-")
    # "created_at"  → prefix="", sep="", field="created_at"  → ascending
    # "-created_at" → prefix="", sep="-", field="created_at" → descending (sep present)
    descending = bool(sep)
    if not descending:
        sort_field = sort_prefix  # plain "created_at": field is the whole string
    if sort_field not in {"created_at"}:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported sort field {sort_field!r}. Allowed: created_at, -created_at.",
        )
    order_col = desc(Job.created_at) if descending else Job.created_at

    # US-4.1 org-scoped query: caller ∪ all users in the same workspace.
    if current_user.workspace_id:
        owner_ids_result = await session.execute(
            select(User.id).where(User.workspace_id == current_user.workspace_id)
        )
        owner_ids = [str(uid) for uid in owner_ids_result.scalars().all()]
    else:
        owner_ids = [str(current_user.id)]

    base_where = Job.user_id.in_(owner_ids)

    count_q = select(func.count(Job.id)).where(base_where)
    total = (await session.execute(count_q)).scalar_one()

    offset = (page - 1) * size
    data_q = (
        select(Job)
        .where(base_where)
        .order_by(order_col)
        .offset(offset)
        .limit(size)
    )
    jobs = list((await session.execute(data_q)).scalars().all())

    total_pages = (total + size - 1) // size if total > 0 else 0

    return PaginatedTranslationsResponse(
        rows=[_serialize_translation_row(j) for j in jobs],
        total=total,
        page=page,
        size=size,
        total_pages=total_pages,
    )


@router.post("/translations", status_code=202)
async def submit_translation(
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
    US-3.7: Submit a translation job.

    Accepts multipart/form-data: file + source_lang + target_lang + optional fields.
    Creates a Job row (status=queued) and enqueues translate_job.

    Returns HTTP 202 with {job_id, has_tracked_changes, is_scanned}.
    HTTP 403 if no active license.
    HTTP 413 if file exceeds plan limit.
    HTTP 415 if file type unsupported.
    HTTP 422 on invalid language pair or glossary mismatch.

    Auth: requires valid JWT (get_current_active_user).
    Idempotency: repeat POST with same Idempotency-Key header → returns existing job.
    """
    # --- Entitlement resolution ---
    entitlement = await resolve_entitlements(user=current_user, session=session)
    if entitlement is None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "LICENSE_REQUIRED",
                "message": "An active license is required to submit a translation.",
            },
        )

    # --- Feature gates ---
    if is_scanned_override is True and not entitlement.ocr_allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "FEATURE_NOT_IN_PLAN",
                "feature": "ocr",
                "message": "OCR is not available on your current plan.",
            },
        )

    if glossary_id is not None and not entitlement.glossary_allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "FEATURE_NOT_IN_PLAN",
                "feature": "glossary",
                "message": "Glossary support is not available on your current plan.",
            },
        )

    # --- Content-length pre-check ---
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > entitlement.max_file_bytes:
        limit_mb = entitlement.max_file_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large — your plan allows up to {limit_mb} MB.",
        )

    # --- Extension validation ---
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Accepted: DOCX, PDF, PPTX, XLSX.",
        )
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=422,
            detail=f"{ext.lstrip('.').upper()} translation is not yet supported.",
        )

    # --- Language pair validation ---
    if target_lang not in await get_valid_target_codes_async(session):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported target language: {target_lang!r}.",
        )
    if source_lang != "auto" and source_lang == target_lang:
        raise HTTPException(
            status_code=422,
            detail="Source and target language must be different.",
        )

    # --- Glossary pair validation ---
    if glossary_id is not None:
        g = await get_glossary(session, glossary_id)
        if g is None:
            raise HTTPException(status_code=422, detail="Glossary not found.")
        if g.source_lang != source_lang or g.target_lang != target_lang:
            raise HTTPException(
                status_code=422,
                detail="The selected glossary does not match the language pair.",
            )

    # --- Streaming file read with per-tier size limit ---
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_STREAMING_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > entitlement.max_file_bytes:
            limit_mb = entitlement.max_file_bytes // (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File too large — your plan allows up to {limit_mb} MB.",
            )
        chunks.append(chunk)
    content: bytes = b"".join(chunks)

    # --- Monthly quota enforcement ---
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

    # --- Scanned PDF detection (PDF only) ---
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
                is_scanned = False

    input_format = "scanned_pdf" if (ext == ".pdf" and is_scanned) else ext.lstrip(".")

    # --- US-3.6: Word count + credit cost for the job row ---
    word_count = count_words_in_file(content, ext)
    tier_name = entitlement.tier.value
    credit_cost = estimate_credit_cost(word_count, tier_name, is_scanned)

    # --- DOCX tracked-changes probe ---
    has_tracked = False
    if ext == ".docx":
        try:
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
            pass

    # --- Idempotency key ---
    idempotency_key = request.headers.get("Idempotency-Key")

    # --- Create Job row ---
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
        estimated_credit_cost=credit_cost,
    )

    # US-3.7 AC-5: idempotent — return existing job
    if is_duplicate:
        log.info("translation_idempotent", job_id=job.id, key=idempotency_key)
        return {
            "job_id": job.id,
            "has_tracked_changes": job.has_tracked_changes,
            "is_duplicate": True,
        }

    # --- Persist source file ---
    job_dir = os.path.join(settings.data_dir, "jobs", job.id)
    os.makedirs(job_dir, exist_ok=True)
    input_path = os.path.join(job_dir, f"source{ext}")
    with open(input_path, "wb") as fh:
        fh.write(content)

    job.input_path = input_path
    await session.commit()

    # --- Enqueue translation (priority lanes per AC-6) ---
    await arq_pool.enqueue_job(
        "translate_job",
        job.id,
        priority=job.queue_priority,
    )

    log.info(
        "translation_submitted",
        job_id=job.id,
        filename=filename,
        size_bytes=total,
        queue_priority=job.queue_priority,
    )

    return {
        "job_id": job.id,
        "has_tracked_changes": has_tracked,
        "is_scanned": is_scanned,
    }
