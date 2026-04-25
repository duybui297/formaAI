---
phase: 02-review-ux-glossary
plan: 08
type: execute
wave: 8
depends_on: [02-07]
files_modified:
  - backend/src/app/workers/translate_worker.py
  - backend/tests/workers/test_segment_persistence.py
autonomous: true
gap_closure: true
requirements: [REV-01, REV-02, REV-04, REV-05, GLOS-04, GLOS-05]

must_haves:
  truths:
    - "Translated segments are persisted to the segments DB table so the review page can display them"
    - "Worker recovers gracefully when run_post_check raises so the job transitions to failed (not stuck in running)"
  artifacts:
    - path: "backend/src/app/workers/translate_worker.py"
      provides: "segment persistence before translate loop + session recovery in error handler"
      contains: "session.add_all"
    - path: "backend/tests/workers/test_segment_persistence.py"
      provides: "tests for segment persistence and session recovery"
      exports: ["test_segments_persisted_before_translate", "test_failed_job_does_not_stick_running"]
  key_links:
    - from: "backend/src/app/workers/translate_worker.py"
      to: "backend/src/app/db/models.py Segment"
      via: "session.add_all(orm_segments)"
      pattern: "session\\.add_all"
    - from: "backend/src/app/workers/translate_worker.py"
      to: "backend/src/app/services/job_service.transition_to_failed"
      via: "await session.rollback() before transition_to_failed"
      pattern: "await session\\.rollback"
---

<objective>
Fix the two UAT blockers that prevent the review page from working:

1. Segments never persisted (Gap 1 / T1): `extract_run_segments` returns pipeline dataclass
   objects that were never written to the DB. The review page has no rows to display.

2. Session recovery broken (Gap 2 / T5): When `run_post_check` raises (FK violation from
   missing Segment rows), the SQLAlchemy session enters `PendingRollbackError` state. The
   outer `except` block then calls `transition_to_failed` on the same broken session, which
   also raises. The job stays permanently in `status=running`.

These two bugs share a common root cause: Segment ORM rows must be persisted to the DB
before `run_post_check` tries to UPDATE and INSERT against them. Fixing Gap 1 eliminates
the FK violation, but Gap 2's session-recovery defect is patched defensively regardless.

Purpose: Unblock review page, flag display, inline editing, and glossary violation badges.
Output: Updated `translate_worker.py` + new test file.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

**Key type distinction (critical):**
The pipeline uses TWO different `Segment` types:
- `app.pipeline.segment.Segment` — a pure Python dataclass (in-memory only, no DB)
- `app.db.models.Segment` — the SQLAlchemy ORM model (maps to the `segments` table)

`extract_run_segments` returns `list[app.pipeline.segment.Segment]` (dataclass objects).
The worker must convert these into `app.db.models.Segment` ORM instances and persist them.

**ORM Segment fields required at insert time:**
```python
# from app/db/models.py
class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[str]                    # String(16) — from pipeline_seg.id (D-06 SHA)
    seq_in_job: Mapped[int]            # pipeline_seg.seq_in_job
    job_id: Mapped[str]                # FK to jobs.id
    source_text: Mapped[str]           # pipeline_seg.source_text
    translated_text: Mapped[str|None]  # None at insert; updated after translation
    structural_position: Mapped[str]   # pipeline_seg.structural_position
    is_comment: Mapped[bool]           # pipeline_seg.is_comment
    is_inserted: Mapped[bool]          # pipeline_seg.is_inserted
    is_deleted: Mapped[bool]           # pipeline_seg.is_deleted
    # Phase 2:
    edited_text: Mapped[str|None]      # None at insert
    expansion_ratio: Mapped[float|None]  # None at insert; updated by run_post_check
```

**run_post_check signature (from glossary_service.py):**
```python
async def run_post_check(
    session: AsyncSession,
    batch_segs: list,           # list of pipeline dataclass Segments
    translated_map: dict[str, str],
    glossary: dict[str, str] | None,
    source_lang: str,
    target_lang: str,
    expansion_thresholds: dict[str, float],
) -> None:
```
run_post_check does:
1. UPDATE Segment SET expansion_ratio = ratio WHERE id = seg.id
2. session.add_all([SegmentFlag(..., segment_id=seg.id), ...]) + session.flush()

For these to work: ORM Segment rows with matching id values must already exist in the DB.

**session_factory config:**
```python
ctx["session_factory"] = async_sessionmaker(ctx["engine"], expire_on_commit=False)
```
expire_on_commit=False means ORM objects remain usable after commit without re-fetch.

**DB import alias to avoid name collision:**
```python
from app.db.models import Segment as SegmentORM  # alias avoids clash with pipeline Segment
```
</context>

<interfaces>
<!-- Extracted from codebase. Executor should use these directly. -->

From backend/src/app/pipeline/segment.py:
```python
@dataclass
class Segment:
    id: str                       # 16-char hex (D-06 SHA)
    seq_in_job: int
    source_text: str
    structural_position: str
    is_comment: bool = False
    is_inserted: bool = False
    is_deleted: bool = False
    translated_text: str | None = None
    run_index: int | None = None
    run_group_size: int = 1
```

From backend/src/app/db/models.py (SegmentORM — what we persist):
```python
class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[str]               # String(16) primary key
    seq_in_job: Mapped[int]
    job_id: Mapped[str]           # FK to jobs.id
    source_text: Mapped[str]
    translated_text: Mapped[str | None]
    structural_position: Mapped[str]
    is_comment: Mapped[bool]
    is_inserted: Mapped[bool]
    is_deleted: Mapped[bool]
    edited_text: Mapped[str | None]
    expansion_ratio: Mapped[float | None]
```

From backend/src/app/services/job_service.py:
```python
async def transition_to_failed(session, job_id, error_msg) -> None:
    # calls get_job(session, job_id) which issues SELECT — WILL fail if session
    # is in PendingRollbackError state. Must rollback session first.
    job = await get_job(session, job_id)
    ...
    await session.commit()
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add failing tests for segment persistence and session recovery</name>
  <files>backend/tests/workers/test_segment_persistence.py</files>
  <behavior>
    - test_segments_persisted_before_translate: After _run_translation runs on a minimal DOCX
      (or with a mocked translate_batch), SELECT COUNT(*) FROM segments WHERE job_id=? returns
      the same count as extract_run_segments returned. Currently returns 0 (RED).
    - test_translated_text_written_after_batch: After translation, segments.translated_text is
      non-null for at least one row. Currently null because no ORM rows exist (RED).
    - test_failed_job_not_stuck_running: When run_post_check is patched to raise an Exception,
      the job status transitions to "failed" (not remains "running"). Currently the session
      enters PendingRollbackError and transition_to_failed also fails, leaving status=running (RED).
    - Use pytest-asyncio + SQLite in-memory async engine (same pattern as Phase 1 worker tests).
    - Mock translate_batch to return ["<translated text>"] * len(batch) — avoids DashScope calls.
    - Use a real minimal DOCX bytes fixture (one paragraph "Hello world") via io.BytesIO.
  </behavior>
  <action>
Create `backend/tests/workers/test_segment_persistence.py`.

Use this test skeleton:

```python
"""
Tests for segment persistence in translate_worker.
Gap 1: segments must be persisted to DB before run_post_check.
Gap 2: session recovery — transition_to_failed must succeed even when session
       enters PendingRollbackError after run_post_check raises.
"""
from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from docx import Document as DocxDocument
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Job, JobStatus, Segment as SegmentORM
from app.workers.translate_worker import _run_translation


def _make_minimal_docx() -> str:
    """Write a DOCX with one paragraph to a temp file; return path."""
    import tempfile, os
    doc = DocxDocument()
    doc.add_paragraph("Hello world")
    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    doc.save(tmp.name)
    tmp.close()
    return tmp.name


@pytest_asyncio.fixture
async def engine():
    e = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def job(session_factory):
    """Create a queued job row pointing at a real DOCX file."""
    docx_path = _make_minimal_docx()
    async with session_factory() as s:
        j = Job(
            source_lang="en",
            target_lang="vi",
            input_format="docx",
            input_path=docx_path,
            original_filename="test.docx",
            status=JobStatus.queued,
        )
        s.add(j)
        await s.commit()
        await s.refresh(j)
        return j.id, docx_path


@pytest.mark.asyncio
async def test_segments_persisted_before_translate(session_factory, job, tmp_path):
    """Gap 1: ORM Segment rows must exist in DB after _run_translation."""
    job_id, _ = job

    mock_ctx = {
        "settings": _make_settings(tmp_path),
        "redis": _make_redis(),
        "llm_client": None,
    }

    with patch(
        "app.workers.translate_worker.translate_batch_with_retry",
        new_callable=AsyncMock,
        return_value=["Xin chào thế giới"],
    ), patch(
        "app.workers.translate_worker.run_post_check",
        new_callable=AsyncMock,
    ):
        async with session_factory() as session:
            await _run_translation(mock_ctx, session, job_id)

    async with session_factory() as s:
        result = await s.execute(
            select(SegmentORM).where(SegmentORM.job_id == job_id)
        )
        rows = result.scalars().all()
    assert len(rows) >= 1, "No Segment rows persisted — Gap 1 not fixed"
    assert all(r.source_text for r in rows)


@pytest.mark.asyncio
async def test_translated_text_written_after_batch(session_factory, job, tmp_path):
    """Segment.translated_text is set after the translate loop."""
    job_id, _ = job

    mock_ctx = {
        "settings": _make_settings(tmp_path),
        "redis": _make_redis(),
        "llm_client": None,
    }

    with patch(
        "app.workers.translate_worker.translate_batch_with_retry",
        new_callable=AsyncMock,
        return_value=["Xin chào thế giới"],
    ), patch(
        "app.workers.translate_worker.run_post_check",
        new_callable=AsyncMock,
    ):
        async with session_factory() as session:
            await _run_translation(mock_ctx, session, job_id)

    async with session_factory() as s:
        result = await s.execute(
            select(SegmentORM).where(SegmentORM.job_id == job_id)
        )
        rows = result.scalars().all()
    assert any(r.translated_text is not None for r in rows), \
        "translated_text never written to DB"


@pytest.mark.asyncio
async def test_failed_job_not_stuck_running(session_factory, job, tmp_path):
    """Gap 2: job transitions to 'failed' even when run_post_check raises."""
    job_id, _ = job

    mock_ctx = {
        "settings": _make_settings(tmp_path),
        "redis": _make_redis(),
        "llm_client": None,
    }

    with patch(
        "app.workers.translate_worker.translate_batch_with_retry",
        new_callable=AsyncMock,
        return_value=["ok"],
    ), patch(
        "app.workers.translate_worker.run_post_check",
        new_callable=AsyncMock,
        side_effect=Exception("simulated post_check failure"),
    ):
        async with session_factory() as session:
            try:
                await _run_translation(mock_ctx, session, job_id)
            except Exception:
                pass  # _run_translation re-raises; that is expected

    async with session_factory() as s:
        result = await s.execute(
            select(Job).where(Job.id == job_id)
        )
        j = result.scalar_one()
    assert j.status == JobStatus.failed, \
        f"Job stuck in {j.status!r} instead of transitioning to failed — Gap 2 not fixed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(tmp_path):
    """Minimal settings stub sufficient for _run_translation."""
    from types import SimpleNamespace
    return SimpleNamespace(
        data_dir=str(tmp_path),
        token_budget=2000,
        worker_concurrency=1,
        expansion_thresholds_dict={"en->vi": 1.5},
    )


def _make_redis():
    """AsyncMock Redis that silently swallows publish() calls."""
    r = AsyncMock()
    r.publish = AsyncMock(return_value=0)
    return r
```

Run: `cd backend && uv run pytest tests/workers/test_segment_persistence.py -x -q`
All three tests must FAIL (RED) before proceeding to Task 2.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/workers/test_segment_persistence.py -x -q 2>&1 | tail -15</automated>
  </verify>
  <done>Three tests collected, all FAIL (RED). No import errors or fixture errors.</done>
</task>

<task type="auto">
  <name>Task 2: Persist Segment ORM rows + patch session recovery in translate_worker</name>
  <files>backend/src/app/workers/translate_worker.py</files>
  <action>
Make the three tests from Task 1 GREEN.

**Change 1 — Import ORM Segment with alias** (add after existing imports, near the top of the file):
```python
from app.db.models import Segment as SegmentORM  # Gap 1: ORM model for DB persistence
```
Keep the pipeline import (`from app.pipeline.docx.extractor import extract_run_segments, ...`) unchanged.

**Change 2 — Persist segments before translate loop** (in `_run_translation`, after the
`pack_into_batches(...)` call and before `update_job_progress`, insert this block):

```python
# Gap 1 fix: persist ORM Segment rows so run_post_check can UPDATE/INSERT against them.
# segments here are app.pipeline.segment.Segment dataclass objects (not ORM). We create
# ORM instances from them and commit once before the translate loop.
orm_segments: list[SegmentORM] = [
    SegmentORM(
        id=seg.id,
        job_id=job_id,
        seq_in_job=seg.seq_in_job,
        source_text=seg.source_text,
        structural_position=seg.structural_position,
        is_comment=seg.is_comment,
        is_inserted=seg.is_inserted,
        is_deleted=seg.is_deleted,
        translated_text=None,
        edited_text=None,
        expansion_ratio=None,
    )
    for seg in segments
]
session.add_all(orm_segments)
await session.commit()
log.info("segments_persisted", job_id=job_id, count=segments_total)
```

Place this block immediately after:
```python
batches = pack_into_batches(segments, budget_tokens=settings.token_budget)
```
and before:
```python
await update_job_progress(
    session, job_id, 0, segments_total, 0, 0, JobStage.translate
)
```

**Change 3 — Write translated_text to DB after each batch** (in `_translate_one_batch`,
after the for loop that populates `translated_map`, add):

```python
# Gap 1: write translated_text to the already-persisted ORM rows.
# This updates each segment's translated_text column before run_post_check reads it.
from sqlalchemy import update as sa_update  # import at top of function or module level
await session.execute(
    sa_update(SegmentORM)
    .where(SegmentORM.id.in_([seg.id for seg in batch_segs]))
    .values(translated_text=None)  # placeholder — overridden per-seg below
)
for seg, translated in zip(batch_segs, results):
    await session.execute(
        sa_update(SegmentORM)
        .where(SegmentORM.id == seg.id)
        .values(translated_text=translated)
    )
await session.flush()
```

Wait — the existing loop is:
```python
for seg, translated in zip(batch_segs, results):
    translated_map[seg.id] = translated
```
Replace the `translated_map[seg.id] = translated` loop with:
```python
for seg, translated in zip(batch_segs, results):
    translated_map[seg.id] = translated
    # Gap 1: persist translated_text to DB in the same batch transaction.
    await session.execute(
        sa_update(SegmentORM)
        .where(SegmentORM.id == seg.id)
        .values(translated_text=translated)
    )
await session.flush()
```
Note: `sa_update` must be imported at the module level to avoid repeated imports inside
the closure. Add `from sqlalchemy import update as sa_update` to the module-level imports.

**Change 4 — Session recovery before transition_to_failed** (in the outer `except Exception`
block of `_run_translation`):

Current code:
```python
    except Exception as exc:
        msg = f"Translation failed: {exc}"
        append_error_log(data_dir, job_id, msg)
        await transition_to_failed(session, job_id, error_msg=msg)
        ...
```

Change to:
```python
    except Exception as exc:
        msg = f"Translation failed: {exc}"
        append_error_log(data_dir, job_id, msg)
        # Gap 2: roll back any in-flight transaction before calling transition_to_failed.
        # If run_post_check raised a FK violation (e.g. missing Segment rows), the session
        # is in PendingRollbackError state. transition_to_failed calls get_job() which
        # issues a SELECT — that would also raise. Rollback first.
        try:
            await session.rollback()
        except Exception:
            pass  # best-effort; if rollback itself fails, we still attempt the status update
        await transition_to_failed(session, job_id, error_msg=msg)
        ...
```

Also add `from sqlalchemy import update as sa_update` near the other sqlalchemy imports at
the top of the module if not already present.

After all changes, run the test suite to confirm GREEN:
- `uv run pytest tests/workers/test_segment_persistence.py -x -q` — all 3 pass
- `uv run pytest tests/workers/ -x -q` — no regressions
- `uv run pytest tests/ -x -q --ignore=tests/integration` — full suite passes
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/workers/test_segment_persistence.py tests/workers/test_worker_glossary.py -x -q 2>&1 | tail -15</automated>
  </verify>
  <done>
    All three tests in test_segment_persistence.py pass (GREEN).
    No regressions in tests/workers/.
    Full backend test suite passes: `uv run pytest tests/ -x -q --ignore=tests/integration`.
    `grep "session.add_all" src/app/workers/translate_worker.py` returns at least one match.
    `grep "await session.rollback" src/app/workers/translate_worker.py` returns at least one match.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| worker→DB | Worker writes ORM rows sourced entirely from server-side DOCX parse; no user input reaches Segment content directly |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-08-01 | Tampering | Segment.id (SHA from source_text + structural_position) | accept | IDs are deterministic server-side hashes; no user-supplied IDs enter the insert path |
| T-02-08-02 | Denial | session.add_all on very large documents | accept | token_budget + pack_into_batches already caps batch size; segment count is bounded by document size which is capped at 25 MB at upload |
| T-02-08-03 | Elevation | PendingRollbackError swallowed in session.rollback() try/except | accept | outer catch still calls transition_to_failed; arq re-raises the exception to mark the queue job failed; dual failure path ensures no silent success |
</threat_model>

<verification>
```bash
# 1. All new tests pass
cd /home/thu/dev/projects/ai-translation/backend
uv run pytest tests/workers/test_segment_persistence.py -v 2>&1 | tail -20

# 2. No regressions in full backend suite
uv run pytest tests/ -x -q --ignore=tests/integration 2>&1 | tail -5

# 3. Segment persistence wired
grep "session.add_all" src/app/workers/translate_worker.py

# 4. Session recovery wired
grep "await session.rollback" src/app/workers/translate_worker.py

# 5. ORM import alias present
grep "SegmentORM" src/app/workers/translate_worker.py
```
</verification>

<success_criteria>
- `test_segments_persisted_before_translate` passes: at least 1 Segment ORM row exists in DB after _run_translation
- `test_translated_text_written_after_batch` passes: at least 1 row has non-null translated_text
- `test_failed_job_not_stuck_running` passes: job.status == "failed" when run_post_check raises
- Full backend test suite (excluding integration) remains green
- No new TS or Python type errors introduced
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-08-SUMMARY.md` using the template at `@$HOME/.claude/get-shit-done/templates/summary.md`.
</output>
