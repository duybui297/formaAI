---
phase: 02-review-ux-glossary
plan: "04"
type: execute
wave: 1
depends_on: ["02-02", "02-03"]
files_modified:
  - backend/src/app/services/export_service.py
  - backend/src/app/api/routes/segments.py
  - backend/src/app/api/routes/export.py
  - backend/src/app/workers/translate_worker.py
  - backend/src/app/main.py
autonomous: true
requirements:
  - GLOS-03
  - GLOS-04
  - REV-01
  - REV-02
  - REV-03
  - REV-04
  - REV-05
  - REV-06
  - LAYOUT-01

must_haves:
  truths:
    - "GET /jobs/{id}/segments returns all segments with flags and expansion_ratio"
    - "PATCH /segments/{id} persists edited_text; edited_text=null clears the edit"
    - "POST /segments/{id}/regenerate overwrites translated_text only; edited_text untouched"
    - "POST /jobs/{id}/export reassembles DOCX using edited_text ?? translated_text; idempotent"
    - "Worker loads glossary terms from DB before translate loop; passes to translate_batch"
    - "Worker calls run_post_check (imported from glossary_service.py, implemented in Plan 03) per batch"
    - "run_post_check skips terms shorter than 2 chars per D-02-07"
    - "Expansion ratio stored as segments.expansion_ratio per segment"
    - "Export advisory lock prevents concurrent corrupt-write"
    - "Export does NOT mutate segment rows"
    - "Export write is atomic: tmp file written then os.replace to prevent readers seeing partial writes"
    - "PATCH /segments/{id} validates job status is done or needs_review before update"
  artifacts:
    - path: "backend/src/app/services/export_service.py"
      provides: "Idempotent DOCX export with advisory lock and atomic write"
      exports: ["export_job"]
    - path: "backend/src/app/api/routes/segments.py"
      provides: "Segment PATCH + GET list + regenerate endpoints"
      exports: ["router"]
    - path: "backend/src/app/api/routes/export.py"
      provides: "POST /jobs/{id}/export endpoint"
      exports: ["router"]
    - path: "backend/src/app/workers/translate_worker.py"
      provides: "Worker with glossary injection + post-check call + expansion ratio"
  key_links:
    - from: "backend/src/app/api/routes/segments.py PATCH"
      to: "backend/src/app/db/models.py Segment.edited_text"
      via: "SQLAlchemy update"
      pattern: "edited_text"
    - from: "backend/src/app/workers/translate_worker.py"
      to: "backend/src/app/services/glossary_service.py load_glossary_terms_for_job"
      via: "glossary load before batch loop"
      pattern: "load_glossary_terms_for_job"
    - from: "backend/src/app/workers/translate_worker.py"
      to: "backend/src/app/services/glossary_service.py run_post_check"
      via: "imported and called per batch after translation"
      pattern: "run_post_check"
    - from: "backend/src/app/services/export_service.py"
      to: "backend/src/app/pipeline/docx/reassembler.py"
      via: "reassemble_docx_runs(doc, segments, translated_map)"
      pattern: "reassemble_docx_runs"
---

<objective>
Implement the segment and export backend: segments.py route (GET list with flags, PATCH edit with job-state gate, POST regenerate), export_service.py (advisory lock + idempotent atomic reassembly), export.py route, and translate_worker.py extension (glossary injection + post-check call + expansion ratio).

Purpose: This plan delivers REV-01..06, GLOS-03/04, LAYOUT-01 on the backend. Frontend review page (Plan 06) depends on these endpoints. Depends on Plan 03 (depends_on: ["02-02", "02-03"]) — Plan 04 imports run_post_check and load_glossary_terms_for_job from glossary_service.py which Plan 03 implements. The depends_on includes "02-03" to prevent parallel execution before glossary_service.py exists.
Output: Full segment management REST surface + export endpoint + worker augmented with glossary injection and post-check.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/02-review-ux-glossary/02-CONTEXT.md
@.planning/phases/02-review-ux-glossary/02-RESEARCH.md
@.planning/phases/02-review-ux-glossary/02-PATTERNS.md

<interfaces>
<!-- From backend/src/app/db/models.py (after Plan 02) -->
```python
class Segment(Base):
    id: Mapped[str]                 # String(16)
    seq_in_job: Mapped[int]
    job_id: Mapped[str]             # FK jobs.id
    source_text: Mapped[str]
    translated_text: Mapped[str | None]
    edited_text: Mapped[str | None]        # NEW Phase 2
    expansion_ratio: Mapped[float | None]  # NEW Phase 2
    structural_position: Mapped[str]
    is_comment: Mapped[bool]
    flags: Mapped[list[SegmentFlag]]  # relationship selectin

class SegmentFlag(Base):
    id: Mapped[str]
    segment_id: Mapped[str]
    flag_type: Mapped[FlagType]     # overflow / glossary_violation / placeholder_mismatch / llm_refusal
    severity: Mapped[FlagSeverity]  # info / warn / block
    details: Mapped[dict | None]    # JSON

class Job(Base):
    id, status, source_lang, target_lang, input_path, output_path, original_filename
    glossary_id: Mapped[str | None]  # NEW Phase 2
    status: Mapped[JobStatus]  # done / needs_review = reviewable/exportable states

class JobStatus(str, enum.Enum): queued/running/needs_review/failed/done
```

<!-- From backend/src/app/pipeline/docx/reassembler.py -->
```python
def reassemble_docx_runs(doc: Document, segments: list, translated_map: dict[str, str]) -> Document:
    """Reassembler entry point. translated_map: {segment_id: translated_text}."""
    # Phase 2: caller builds map with edited_text ?? translated_text; reassembler unchanged
```

<!-- From translate_worker.py (current, line ~323) -->
```python
glossary=None,  # Phase 1: no glossary (D-15 deferred to Phase 2)
```
<!-- Phase 2 replaces this with real glossary loaded from DB -->

<!-- RESEARCH.md Section 8 — regenerate endpoint -->
```python
# Single-segment batch; uses existing translate_batch function
# D-02-20: overwrites translated_text; never touches edited_text
```

<!-- From glossary_service.py (Plan 03 output) -->
```python
async def load_glossary_terms_for_job(
    session: AsyncSession, glossary_id: str | None
) -> dict[str, str] | None: ...

async def run_post_check(
    session: AsyncSession,
    batch_segs: list,
    translated_map: dict[str, str],
    glossary: dict[str, str] | None,
    source_lang: str,
    target_lang: str,
    expansion_thresholds: dict[str, float],
) -> None: ...
# Writes SegmentFlag rows for overflow, glossary_violation, placeholder_mismatch, llm_refusal
# Updates Segment.expansion_ratio
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement export_service.py with advisory lock and atomic write</name>
  <files>
    backend/src/app/services/export_service.py
  </files>
  <read_first>
    - backend/src/app/services/job_service.py (module header pattern, service function style)
    - backend/src/app/pipeline/docx/reassembler.py (reassemble_docx_runs signature)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Section 7 (advisory lock pattern, export_job function, Pitfall 5)
    - .planning/phases/02-review-ux-glossary/02-PATTERNS.md §export_service.py (advisory lock + read-snapshot pattern)
    - .planning/phases/02-review-ux-glossary/02-CONTEXT.md D-02-22 (idempotent, overwrite output.docx), D-02-20 (edited_text ?? translated_text)
  </read_first>
  <behavior>
    - export_job(session, job_id, data_dir) → str (output file path)
    - Acquires asyncio.Lock per job_id before reassembly
    - Raises ValueError if job not in done/needs_review state
    - Builds translated_map using: `edited_text if edited_text is not None else translated_text or ""`
    - Does NOT mutate any Segment row during export
    - Writes atomically: doc.save(tmp_path) then os.replace(tmp_path, output_path) — prevents partial reads
    - output_path is {data_dir}/jobs/{job_id}/output.docx
    - get_export_lock uses WeakValueDictionary to avoid memory leak
    - Concurrent exports on same job_id: second waits, then produces same output (idempotent)
  </behavior>
  <action>
Create `backend/src/app/services/export_service.py`:

```python
"""
Export service: idempotent DOCX reassembly with advisory lock and atomic write.

REV-05: Export reassembles using edited_text ?? translated_text.
REV-06: Export is idempotent — re-exporting produces same output; does not mutate segments.

Advisory lock design (D-02-22):
- asyncio.Lock per job_id stored in WeakValueDictionary
- In-process lock is sufficient for single-uvicorn-process PoC
- TODO(v2): upgrade to pg_advisory_lock if deploying multiple API workers

Atomic write: doc.save(tmp_path) then os.replace(tmp_path, output_path)
- Prevents a concurrent reader from seeing a half-written file during reassembly
- os.replace is atomic on POSIX filesystems when src/dst are on same volume
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from weakref import WeakValueDictionary

import structlog
from docx import Document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, JobStatus, Segment
from app.pipeline.docx.reassembler import reassemble_docx_runs

log = structlog.get_logger()

# In-process advisory lock per job_id (sufficient for single-process API)
# TODO(v2): upgrade to pg_advisory_lock if deploying multiple API workers
_export_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
_locks_mutex = asyncio.Lock()

_EXPORTABLE_STATUSES = frozenset({JobStatus.done, JobStatus.needs_review})


async def _get_export_lock(job_id: str) -> asyncio.Lock:
    """Get or create an asyncio.Lock for the given job_id."""
    async with _locks_mutex:
        lock = _export_locks.get(job_id)
        if lock is None:
            lock = asyncio.Lock()
            _export_locks[job_id] = lock
        return lock


async def export_job(
    session: AsyncSession,
    job_id: str,
    data_dir: str,
) -> str:
    """REV-05/06: Idempotent DOCX reassembly.

    Acquires per-job advisory lock, reads a snapshot of segment state,
    reassembles using edited_text ?? translated_text, writes output.docx atomically.
    Does NOT mutate any segment rows.

    Returns the output file path as a string.
    Raises ValueError if job is not in an exportable state.
    """
    lock = await _get_export_lock(job_id)
    async with lock:
        # Load job
        result = await session.execute(
            select(Job).where(Job.id == job_id)
        )
        job: Job | None = result.scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        if job.status not in _EXPORTABLE_STATUSES:
            raise ValueError(
                f"Job {job_id} is in state '{job.status.value}' — "
                "export requires 'done' or 'needs_review'"
            )

        # Load segments ordered by seq_in_job (read snapshot — no mutation)
        seg_result = await session.execute(
            select(Segment)
            .where(Segment.job_id == job_id)
            .order_by(Segment.seq_in_job)
        )
        segments = list(seg_result.scalars().all())

        # REV-05: build translated_map using edited_text ?? translated_text
        # Pitfall 5: use explicit None check, not `or` — empty string edit must be respected
        translated_map: dict[str, str] = {
            seg.id: (
                seg.edited_text
                if seg.edited_text is not None
                else (seg.translated_text or "")
            )
            for seg in segments
        }

        # Reassemble DOCX — reassembler is unchanged from Phase 1 (DOCX-02 invariant preserved)
        doc = Document(job.input_path)
        doc = reassemble_docx_runs(doc, segments, translated_map)

        # Atomic write: tmp file → os.replace → output_path
        # Prevents concurrent reader seeing a half-written file (os.replace is atomic on POSIX)
        output_path = str(Path(data_dir) / "jobs" / job_id / "output.docx")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        tmp_path = output_path + ".tmp"
        doc.save(tmp_path)
        os.replace(tmp_path, output_path)

        log.info(
            "export_complete",
            job_id=job_id,
            output_path=output_path,
            segments=len(segments),
        )
        return output_path
```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend pytest backend/tests/services/test_export_service.py -x -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    - export_service.py imports cleanly
    - test_export_service.py tests pass (xfail → pass/xpass)
    - `export_job` raises ValueError for job in 'queued' state
    - Concurrent exports on same job_id do not corrupt output (advisory lock)
    - segment.edited_text="" (empty string) produces "" in output, not translated_text (Pitfall 5)
    - Atomic write pattern: `tmp_path = output_path + ".tmp"` + `os.replace` visible in file
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement segments.py route (GET list, PATCH with job-state gate, POST regenerate) and export.py route</name>
  <files>
    backend/src/app/api/routes/segments.py
    backend/src/app/api/routes/export.py
    backend/src/app/main.py
  </files>
  <read_first>
    - backend/src/app/api/routes/jobs.py (full file — import pattern, Depends pattern, serializer pattern, FileResponse pattern)
    - backend/src/app/api/dependencies.py (get_session, get_settings — check if get_llm_client exists or needs adding)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Section 8 (regenerate endpoint pattern)
    - .planning/phases/02-review-ux-glossary/02-PATTERNS.md §segments.py (PATCH + regenerate patterns), §export.py (FileResponse pattern)
    - .planning/phases/02-review-ux-glossary/02-CONTEXT.md D-02-20 (regenerate: overwrite translated_text, preserve edited_text)
    - backend/src/app/main.py (router includes — need to add segments + export routers)
  </read_first>
  <behavior>
    - GET /jobs/{id}/segments → list of segments with flags embedded (REV-01)
    - PATCH /segments/{id} → validates job status is done/needs_review (409 if not); update edited_text (max 10000 chars), return {segment_id, edited_text} (REV-02)
    - PATCH /segments/{id} with edited_text=null → clears edit; export will use translated_text (D-02-20)
    - POST /segments/{id}/regenerate → re-translate synchronously; overwrite translated_text; return new translated_text (REV-04)
    - POST /jobs/{id}/export → call export_service.export_job; return FileResponse (REV-05/06)
    - GET /jobs/{id}/segments loads flags via selectinload (flags are on Segment relationship)
    - Segment list response bundles flag_counts per flag_type (one GROUP BY query per RESEARCH Section 5)
    - PATCH must check job.status in _REVIEWABLE_STATUSES before update; 409 on worker race
  </behavior>
  <action>
**Create `backend/src/app/api/routes/segments.py`:**

```python
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

from app.db.models import Job, JobStatus, Segment, SegmentFlag, FlagType
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
    count_result = await session.execute(
        select(SegmentFlag.flag_type, func.count(SegmentFlag.id).label("count"))
        .join(Segment, SegmentFlag.segment_id == Segment.id)
        .where(Segment.job_id == job_id)
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
    seg_result = await session.execute(
        select(Segment).where(Segment.id == segment_id)
    )
    seg = seg_result.scalar_one_or_none()
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Gate: prevent editing while worker is still running (worker race guard)
    job_result = await session.execute(select(Job).where(Job.id == seg.job_id))
    job = job_result.scalar_one_or_none()
    if job is None or job.status not in _REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Job is not in a reviewable state (done or needs_review). Edits are only allowed after translation completes.",
        )

    await session.execute(
        update(Segment)
        .where(Segment.id == segment_id)
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
    seg_result = await session.execute(
        select(Segment).where(Segment.id == segment_id)
    )
    seg = seg_result.scalar_one_or_none()
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
    await session.execute(
        update(Segment)
        .where(Segment.id == segment_id)
        .values(translated_text=new_translated_text)
    )
    await session.commit()

    log.info("segment_regenerated", segment_id=segment_id, job_id=seg.job_id)
    return {"segment_id": segment_id, "translated_text": new_translated_text}
```

**Create `backend/src/app/api/routes/export.py`:**

```python
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
```

**Update `backend/src/app/main.py`** — add router includes:
1. Find where `jobs.router` is included (e.g., `app.include_router(jobs.router)`)
2. Add after it:
   ```python
   from app.api.routes import glossaries, segments, export
   app.include_router(glossaries.router)
   app.include_router(segments.router)
   app.include_router(export.router)
   ```

Check backend/src/app/main.py for the exact import style used and match it.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend pytest backend/tests/api/test_segments.py -x -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    - segments.py and export.py route files exist and import cleanly
    - Routers registered in main.py
    - test_segments.py xfail tests pass
    - GET /jobs/{id}/segments returns segments with flags (tested against SQLite)
    - PATCH /segments/{id} updates edited_text and returns 200
    - PATCH /segments/{id} returns 409 when job is in 'queued' or 'running' state
    - POST /jobs/{id}/export returns 409 for non-exportable job state
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Extend translate_worker.py — import run_post_check from glossary_service + wire glossary injection</name>
  <files>
    backend/src/app/workers/translate_worker.py
  </files>
  <read_first>
    - backend/src/app/workers/translate_worker.py (full file — _run_translation function, _translate_one_batch inner function at line ~313)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Section 5 (glossary load + run_post_check + expansion ratio patterns — exact code)
    - .planning/phases/02-review-ux-glossary/02-PATTERNS.md §translate_worker.py (three extension points)
    - .planning/phases/02-review-ux-glossary/02-CONTEXT.md D-02-20 (glossary locked at job submit), D-02-07 (2-char min), D-02-12 (threshold env var)
  </read_first>
  <behavior>
    - Worker loads glossary terms ONCE before the batch loop (not per-batch)
    - glossary=None when job.glossary_id is None
    - translate_batch_with_retry called with real glossary kwarg (not hardcoded None)
    - run_post_check imported from glossary_service.py (implemented in Plan 03) — NOT defined here
    - run_post_check called after each batch completes with batch_segs + translated_map + glossary + expansion_thresholds
    - expansion_ratio stored on segments table (updated inside run_post_check)
    - No change to retry logic, progress publishing, or reassembly
  </behavior>
  <action>
Make three surgical additions to `backend/src/app/workers/translate_worker.py`.

**Addition 1: Import `load_glossary_terms_for_job` and `run_post_check` from glossary_service**

Add to the imports block at the top of the file (after existing app imports):
```python
from app.services.glossary_service import load_glossary_terms_for_job, run_post_check
```

Do NOT define run_post_check here — it is fully implemented in glossary_service.py (Plan 03).

**Addition 2: Load glossary before batch loop in `_run_translation`**

Find the section labeled `# STAGE 2: Batch pack` (or equivalent) and add BEFORE it (after `segments = extract_run_segments(...)` or equivalent segment extraction):

```python
        # GLOS-03: load glossary terms once before translate loop
        # Returns {source_term: target_term} dict or None if no glossary attached
        glossary: dict[str, str] | None = await load_glossary_terms_for_job(
            session, job.glossary_id
        )
        if glossary:
            log.info("glossary_loaded", job_id=job_id, term_count=len(glossary))
```

**Addition 3: Wire glossary into translate call + call run_post_check per batch**

Inside the batch processing logic (the inner function or loop that calls translate_batch_with_retry):

1. Replace the hardcoded `glossary=None` with the loaded glossary variable:
   ```python
   # Before (Phase 1):
   glossary=None,  # Phase 1: no glossary (D-15 deferred to Phase 2)

   # After (Phase 2):
   glossary=glossary,  # GLOS-03: real glossary from DB (or None)
   ```

2. After the per-batch translated results are stored to `translated_map`, add the post-check call:
   ```python
                # GLOS-04 + LAYOUT-01: post-translation check per batch
                # run_post_check is imported from glossary_service (Plan 03)
                # Writes overflow / glossary_violation / placeholder_mismatch / llm_refusal flags
                # Also stores expansion_ratio on each segment
                await run_post_check(
                    session=session,
                    batch_segs=batch_segs,
                    translated_map={seg.id: translated_map[seg.id] for seg in batch_segs if seg.id in translated_map},
                    glossary=glossary,
                    source_lang=job.source_lang,
                    target_lang=job.target_lang,
                    expansion_thresholds=ctx["settings"].expansion_thresholds_dict,
                )
   ```

Read the full worker file first to find the exact variable names (`batch_segs`, `translated_map`, `ctx`) and adjust the call accordingly if they differ. The three points must be wired correctly — do not rename existing variables.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend pytest backend/tests/workers/test_worker_glossary.py backend/tests/services/test_post_check.py -x -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    - translate_worker.py imports run_post_check and load_glossary_terms_for_job without error
    - `glossary=None` line in _translate_one_batch now reads `glossary=glossary`
    - run_post_check is NOT defined in translate_worker.py (import only)
    - test_worker_glossary.py xfail tests pass
    - test_post_check.py xfail tests pass (violation flag written, short terms skipped, overflow flag at ratio>threshold)
    - Existing worker tests still pass: `uv run pytest backend/tests/workers/ -x -q`
    - `grep "def run_post_check" backend/src/app/workers/translate_worker.py` returns empty (not defined here)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client → PATCH /segments/{id} | edited_text is user-supplied; max 10,000 chars; job-state gated |
| client → POST /segments/{id}/regenerate | Triggers LLM call; must validate job state |
| client → POST /jobs/{id}/export | Triggers file reassembly; advisory lock + atomic write prevents race |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-04-01 | DoS | PATCH /segments/{id} | mitigate | `edited_text` max_length=10,000 enforced by Pydantic Field; exceeding returns 422. |
| T-02-04-02 | DoS | POST /segments/{id}/regenerate | mitigate | Validates job status is done/needs_review before calling LLM; 409 on invalid state. Single segment ~1-3s; acceptable for PoC. |
| T-02-04-03 | Tampering | Export file path | accept | output_path is server-computed from job.input_path; not user-supplied. os.makedirs used with job_id from DB, not from request. |
| T-02-04-04 | Integrity | Concurrent exports | mitigate | asyncio.Lock per job_id (WeakValueDictionary) + atomic os.replace write; second export waits, then produces identical output. In-process lock sufficient for single-process PoC. |
| T-02-04-05 | Tampering | Segment text in DOCX reassembly | accept | edited_text stored as TEXT; reassembler writes it as python-docx run text, auto-escaped by OOXML. No HTML injection vector. |
| T-02-04-06 | Integrity | PATCH during active worker run | mitigate | PATCH /segments/{id} checks job.status in _REVIEWABLE_STATUSES; returns 409 if job is queued/running, preventing stale-write race with worker. |
</threat_model>

<verification>
After all tasks in this plan:

1. `uv run pytest backend/tests/services/test_export_service.py -x -q` — tests pass
2. `uv run pytest backend/tests/api/test_segments.py -x -q` — tests pass
3. `uv run pytest backend/tests/workers/test_worker_glossary.py backend/tests/services/test_post_check.py -x -q` — tests pass
4. `grep -n "glossary=glossary" backend/src/app/workers/translate_worker.py` — shows the wired line
5. `grep -n "run_post_check" backend/src/app/workers/translate_worker.py` — shows import + call, NOT definition
6. `grep "def run_post_check" backend/src/app/workers/translate_worker.py` — empty (not defined here)
7. `grep -n "os.replace" backend/src/app/services/export_service.py` — atomic write present
8. `grep -n "_REVIEWABLE_STATUSES" backend/src/app/api/routes/segments.py` — job-state gate present in PATCH
9. `uv run pytest backend/tests/ -m "not integration" -x -q` — all tests green
</verification>

<success_criteria>
- export_service.py: idempotent, advisory-locked DOCX export with atomic write (tmp + os.replace)
- segments.py route: GET list with flags, PATCH with job-state gate (409 when not done/needs_review), POST regenerate
- export.py route: POST with FileResponse
- translate_worker.py: glossary loaded, passed to translate_batch, run_post_check imported from glossary_service and called per batch
- run_post_check NOT defined in translate_worker.py (import-only from Plan 03)
- segments.expansion_ratio populated on each translated segment (written by run_post_check)
- All Phase 2 backend test stubs pass
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-04-SUMMARY.md`
</output>
