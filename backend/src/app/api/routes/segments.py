"""
Segment endpoints — REV-01, REV-02, REV-04.

GET  /jobs/{id}/segments            — list with flags (REV-01)
PATCH /segments/{id}                — persist edited_text (REV-02); 409 if job not reviewable
POST  /segments/{id}/regenerate     — sync re-translate, overwrite translated_text (REV-04)
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FlagType, Job, JobStatus, Segment, SegmentFlag
from app.db.session import get_session
from app.llm.translator import translate_batch
from app.services.glossary_service import load_glossary_terms_for_job

log = structlog.get_logger()
router = APIRouter()

_REVIEWABLE_STATUSES = frozenset({JobStatus.done, JobStatus.needs_review})


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SegmentPatchRequest(BaseModel, frozen=True):
    # edited_text=None clears the edit; Field(...) makes it required (not optional)
    edited_text: str | None = Field(default=..., max_length=10_000)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _flag_to_dict(f: SegmentFlag) -> dict:
    return {
        "id": f.id,
        "segment_id": f.segment_id,
        "flag_type": f.flag_type.value if hasattr(f.flag_type, "value") else f.flag_type,
        "severity": f.severity.value if hasattr(f.severity, "value") else f.severity,
        "details": f.details,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _segment_to_dict(s: Segment) -> dict:
    return {
        "id": s.id,
        "seq_in_job": s.seq_in_job,
        "source_text": s.source_text,
        "translated_text": s.translated_text,
        "edited_text": s.edited_text,
        "expansion_ratio": s.expansion_ratio,
        "flags": [_flag_to_dict(f) for f in (s.flags or [])],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/jobs/{job_id}/segments")
async def list_segments(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """REV-01: Return all segments with embedded flags for the review UI."""
    job_result = await session.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
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
        "segments": [_segment_to_dict(s) for s in segments],
        "flag_counts": flag_counts,
        "total": len(segments),
    }


@router.patch("/segments/{segment_id}", status_code=200)
async def patch_segment(
    segment_id: str,
    body: SegmentPatchRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """REV-02: Persist edited_text. edited_text=null clears the edit.

    409 if job is not in done/needs_review state — prevents editing during active worker run.
    """
    # gap-closure 02-10: compound PK means segment_id alone is not globally unique.
    # Using .limit(1) prevents MultipleResultsFound when same content was re-uploaded.
    # TODO(02-11): migrate to PATCH /jobs/{job_id}/segments/{segment_id} for unambiguous scoping.
    seg_result = await session.execute(
        select(Segment).where(Segment.id == segment_id).limit(1)
    )
    seg = seg_result.scalars().first()
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Gate: prevent editing while worker is still running (worker race guard)
    job_result = await session.execute(select(Job).where(Job.id == seg.job_id))
    job = job_result.scalar_one_or_none()
    if job is None or job.status not in _REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "Job is not in a reviewable state (done or needs_review). "
                "Edits are only allowed after translation completes."
            ),
        )

    # gap-closure 02-10: use compound WHERE (job_id, id) for the UPDATE — safe since we
    # already fetched seg above and know seg.job_id.
    await session.execute(
        update(Segment)
        .where(Segment.job_id == seg.job_id, Segment.id == segment_id)
        .values(edited_text=body.edited_text)
    )
    await session.commit()

    return {"segment_id": segment_id, "edited_text": body.edited_text}


@router.post("/segments/{segment_id}/regenerate", status_code=200)
async def regenerate_segment(
    segment_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """REV-04: Sync single-segment re-translate.

    D-02-20: overwrites translated_text; edited_text is NOT touched.
    D-02-21: uses job's locked glossary.
    LLM client loaded from app.state (set in lifespan).
    """
    # gap-closure 02-10: .limit(1) prevents MultipleResultsFound with compound PK.
    # TODO(02-11): migrate to POST /jobs/{job_id}/segments/{segment_id}/regenerate.
    seg_result = await session.execute(
        select(Segment).where(Segment.id == segment_id).limit(1)
    )
    seg = seg_result.scalars().first()
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    job_result = await session.execute(select(Job).where(Job.id == seg.job_id))
    job = job_result.scalar_one_or_none()
    if job is None or job.status not in _REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Job is not in a reviewable state (done or needs_review)",
        )

    glossary = await load_glossary_terms_for_job(session, job.glossary_id)

    llm_client = request.app.state.llm_client
    translated_list = await translate_batch(
        client=llm_client,
        segments=[seg.source_text],
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
