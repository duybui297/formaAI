"""
Segment endpoints — REV-01, REV-02, REV-04.

All routes are prefixed with /api/v1 (applied at app level).

GET  /api/v1/jobs/{id}/segments            — list with flags (REV-01)
PATCH /api/v1/segments/{id}                — persist edited_text (REV-02); 409 if job not reviewable
POST  /segments/{id}/regenerate     — sync re-translate, overwrite translated_text (REV-04)
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models import FlagType, Job, JobStatus, Segment, SegmentFlag, User
from app.db.session import get_session
from app.llm.translator import translate_batch
from app.schemas.segment import SegmentPatchRequest, segment_to_dict
from app.services.glossary_service import load_glossary_terms_for_job
from app.services.job_service import get_job_for_user

log = structlog.get_logger()
router = APIRouter()

_REVIEWABLE_STATUSES = frozenset({JobStatus.done, JobStatus.needs_review})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/jobs/{job_id}/segments")
async def list_segments(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """REV-01: Return all segments with embedded flags for the review UI.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: job must belong to current_user.
    """
    job = await get_job_for_user(session, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Load all segments for job (flags loaded via selectin relationship on Segment)
    seg_result = await session.execute(
        select(Segment)
        .where(Segment.job_id == job_id)
        .order_by(Segment.seq_in_job)
    )
    segments = list(seg_result.scalars().all())

    # D-02-10: flag counts per type (one GROUP BY query)
    # gap-closure 02-10: filter by segment_job_id directly (compound FK column), avoids cross-job join ambiguity
    count_result = await session.execute(
        select(SegmentFlag.flag_type, func.count(SegmentFlag.id).label("count"))
        .where(SegmentFlag.segment_job_id == job_id)
        .group_by(SegmentFlag.flag_type)
    )
    flag_counts = {
        (row.flag_type.value if hasattr(row.flag_type, "value") else row.flag_type): row.count
        for row in count_result.all()
    }

    return {
        "segments": [segment_to_dict(s) for s in segments],
        "flag_counts": flag_counts,
        "total": len(segments),
    }


@router.patch("/jobs/{job_id}/segments/{segment_id}", status_code=200)
async def patch_segment(
    job_id: str,
    segment_id: str,
    body: SegmentPatchRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """REV-02: Persist edited_text. edited_text=null clears the edit.

    409 if job is not in done/needs_review state — prevents editing during active worker run.
    Scoped by (job_id, segment_id) — compound PK prevents cross-job collision.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: job must belong to current_user.
    """
    job = await get_job_for_user(session, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in _REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "Job is not in a reviewable state (done or needs_review). "
                "Edits are only allowed after translation completes."
            ),
        )

    seg_result = await session.execute(
        select(Segment).where(Segment.job_id == job_id, Segment.id == segment_id)
    )
    seg = seg_result.scalar_one_or_none()
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    values_to_update: dict = {"edited_text": body.edited_text}
    if body.edited_source_text is not None:
        values_to_update["edited_source_text"] = body.edited_source_text

    await session.execute(
        update(Segment)
        .where(Segment.job_id == job_id, Segment.id == segment_id)
        .values(**values_to_update)
    )
    await session.commit()

    return {"segment_id": segment_id, "edited_text": body.edited_text, "edited_source_text": body.edited_source_text}


@router.post("/jobs/{job_id}/segments/{segment_id}/regenerate", status_code=200)
async def regenerate_segment(
    job_id: str,
    segment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """REV-04: Sync single-segment re-translate.

    D-02-20: overwrites translated_text; edited_text is NOT touched.
    D-02-21: uses job's locked glossary.
    LLM client loaded from app.state (set in lifespan).
    Scoped by (job_id, segment_id) — compound PK prevents cross-job collision.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: job must belong to current_user.
    """
    job = await get_job_for_user(session, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in _REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Job is not in a reviewable state (done or needs_review)",
        )

    seg_result = await session.execute(
        select(Segment).where(Segment.job_id == job_id, Segment.id == segment_id)
    )
    seg = seg_result.scalar_one_or_none()
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    glossary = await load_glossary_terms_for_job(session, job.glossary_id)

    # D-04-25: use reviewer-corrected OCR source if available; fall back to original source_text
    source_for_regen = (
        seg.edited_source_text
        if getattr(seg, "edited_source_text", None)
        else seg.source_text
    )

    llm_client = request.app.state.llm_client
    translated_list = await translate_batch(
        client=llm_client,
        segments=[source_for_regen],
        source_lang=job.source_lang,
        target_lang=job.target_lang,
        glossary=glossary,
    )
    new_translated_text = translated_list[0]

    # D-02-20: overwrite translated_text ONLY — never touch edited_text
    # gap-closure 02-10: compound WHERE (job_id, id) for unambiguous UPDATE
    await session.execute(
        update(Segment)
        .where(Segment.job_id == seg.job_id, Segment.id == segment_id)
        .values(translated_text=new_translated_text)
    )
    await session.commit()

    log.info("segment_regenerated", segment_id=segment_id, job_id=seg.job_id)
    return {"segment_id": segment_id, "translated_text": new_translated_text}
