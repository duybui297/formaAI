---
phase: 02-review-ux-glossary
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - backend/src/app/db/models.py
  - backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py
  - backend/src/app/workers/translate_worker.py
  - backend/src/app/services/glossary_service.py
  - backend/src/app/api/routes/segments.py
  - backend/src/app/api/routes/export.py
  - backend/tests/workers/test_segment_pk_collision.py
  - frontend/src/hooks/useReviewKeyboard.ts
  - frontend/src/components/ReviewPageHeader.tsx
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 02 Gap-Closure: Code Review Report (02-10/02-11/02-12)

**Reviewed:** 2026-04-25
**Depth:** standard
**Files Reviewed:** 9 (gap-closure plans 02-10 compound PK + run fields, 02-11 structured export error, 02-12 keyboard fix)
**Status:** issues_found

## Summary

The three gap-closure plans are coherently implemented. The compound PK migration
(`0003_segment_compound_pk_run_fields.py`) is correctly sequenced: drop FK, drop PK,
create compound PK, backfill `segment_job_id`, create compound FK, add run columns. The
ORM model aligns with the migration schema. The worker correctly scopes all
compound-PK WHERE clauses with `(job_id, id)`. The export endpoint returns structured
JSON on error (02-11). The keyboard hook is correctly typed and the hotkeys are correct
(02-12).

No critical issues found. Four warnings cover real logic bugs or crash risks:

1. `patch_segment` / `regenerate_segment` use `.limit(1)` without `job_id` scoping,
   so edits silently land on a randomly chosen job when the same document is uploaded twice.
2. The migration backfill is non-deterministic when a `segment_flags.segment_id` maps
   to multiple `segments` rows.
3. Worker segment insertion is not idempotent — crash-restart causes `IntegrityError`
   and prevents job recovery.
4. `URL.revokeObjectURL` races the browser download on Safari/Firefox.

---

## Warnings

### WR-01: `patch_segment` / `regenerate_segment` silently target wrong job on duplicate segment hash

**File:** `backend/src/app/api/routes/segments.py:121-123` and `169-170`

**Issue:** Both endpoints query `Segment` by `id` alone with `.limit(1)` to suppress
`MultipleResultsFound`. When the same document is uploaded twice, the same content hash
`id` exists under two different `job_id` values. `.limit(1)` returns whichever the DB
returns first (insertion order), so an edit from the review page for Job B can
silently persist against Job A's segment row. The TODO comment acknowledges the issue
but the current code silently misbehaves rather than returning an error.

**Fix:** Until the route path is migrated to `/jobs/{job_id}/segments/{segment_id}`,
require `job_id` as a query parameter and scope the fetch:

```python
# segments.py — patch_segment (same fix applies to regenerate_segment)
@router.patch("/jobs/{job_id}/segments/{segment_id}", status_code=200)
async def patch_segment(
    job_id: str,
    segment_id: str,
    body: SegmentPatchRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    seg_result = await session.execute(
        select(Segment).where(Segment.job_id == job_id, Segment.id == segment_id)
    )
    seg = seg_result.scalar_one_or_none()
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    # ... rest unchanged; remove the .limit(1) workaround
```

---

### WR-02: Migration backfill for `segment_job_id` is non-deterministic when `segment.id` is not unique

**File:** `backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py:51-59`

**Issue:** The backfill query:

```sql
UPDATE segment_flags sf
SET segment_job_id = s.job_id
FROM segments s
WHERE s.id = sf.segment_id
```

This is a one-to-many join when `segments.id` was not yet unique (the old single-column
PK was dropped at step 2 in this same migration). If any PK-colliding rows already
existed in the DB (precisely what this migration is intended to fix), the UPDATE assigns
an arbitrary `job_id` to each affected flag row. For a fresh PoC DB with no prior
collisions this is low-risk, but it is fragile by design.

**Fix:** Use a deterministic subquery, or document the pre-condition in the migration:

```python
# Deterministic backfill — picks lowest created_at job when segment.id maps to multiple jobs
op.execute(
    """
    UPDATE segment_flags sf
    SET segment_job_id = (
        SELECT s.job_id
        FROM segments s
        WHERE s.id = sf.segment_id
        ORDER BY s.created_at
        LIMIT 1
    )
    """
)
```

---

### WR-03: Worker segment insertion is not idempotent — crash-restart causes `IntegrityError`

**File:** `backend/src/app/workers/translate_worker.py:305-324`

**Issue:** ORM segments are inserted with `session.add_all(orm_segments)` + `commit()`
before the translate loop. If the worker crashes (process kill, OOM, `job_timeout`)
after this commit and before `transition_to_done`, arq re-enqueues the job. The second
run hits an `IntegrityError` on the compound PK `(job_id, id)` for the same segment
rows, falls into the `except Exception` branch, and marks the job failed — rather than
resuming from where it stopped.

```python
# translate_worker.py:323-324 — not safe to re-run
session.add_all(orm_segments)
await session.commit()
```

**Fix (simplest, cross-DB compatible):** Wrap in a try/except `IntegrityError` to
skip re-insertion on retry:

```python
try:
    session.add_all(orm_segments)
    await session.commit()
except IntegrityError:
    await session.rollback()
    log.warning("segments_already_persisted_skipping", job_id=job_id)
```

For a production-grade fix on PostgreSQL, use `INSERT … ON CONFLICT DO NOTHING`:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = (
    pg_insert(SegmentORM)
    .values([{...} for seg in segments])
    .on_conflict_do_nothing(index_elements=["job_id", "id"])
)
await session.execute(stmt)
await session.commit()
```

---

### WR-04: `URL.revokeObjectURL` called synchronously after `a.click()` races download

**File:** `frontend/src/components/ReviewPageHeader.tsx:43-44`

**Issue:**

```typescript
a.click();
URL.revokeObjectURL(url);
```

`a.click()` schedules the download asynchronously. The browser initiates the blob read
after the current call stack unwinds. `revokeObjectURL` is called immediately before the
browser has started reading from the URL. On Safari and some Firefox versions this causes
a silent download failure — the blob is revoked before navigation occurs.

**Fix:** Use `setTimeout` (standard browser idiom):

```typescript
a.click();
setTimeout(() => URL.revokeObjectURL(url), 100);
```

---

## Info

### IN-01: `SegmentFlag` relationship missing explicit `foreign_keys` for compound FK

**File:** `backend/src/app/db/models.py:247`

**Issue:** The `segment` relationship on `SegmentFlag` has no explicit `foreign_keys` or
`primaryjoin`:

```python
segment: Mapped[Segment] = relationship("Segment", back_populates="flags")
```

SQLAlchemy 2.0 can usually infer the join from the `ForeignKeyConstraint`, but omitting
explicit join conditions is fragile — any future rename of `segment_job_id` or `segment_id`
columns would silently misconfigure the relationship.

**Fix:** Declare `foreign_keys` explicitly:

```python
segment: Mapped[Segment] = relationship(
    "Segment",
    back_populates="flags",
    foreign_keys="[SegmentFlag.segment_job_id, SegmentFlag.segment_id]",
)
```

---

### IN-02: Test functions lack `@pytest.mark.asyncio` decorator

**File:** `backend/tests/workers/test_segment_pk_collision.py:37`, `87`, `122`

**Issue:** All three test functions are `async def` but have no `@pytest.mark.asyncio`
decorator. Whether they execute depends on `asyncio_mode = "auto"` being set in
`pyproject.toml`. If that setting is absent, the tests silently skip rather than run.
Explicit decoration makes intent clear regardless of configuration.

**Fix:**

```python
@pytest.mark.asyncio
async def test_same_content_two_jobs_no_pk_collision(session: AsyncSession) -> None:
    ...
```

Apply to all three test functions.

---

### IN-03: `update_glossary_name` mutates ORM object in-place (breaks immutability convention)

**File:** `backend/src/app/services/glossary_service.py:100-104`

**Issue:**

```python
g.name = name
await session.commit()
```

Per project coding style (CLAUDE.md immutability rule), data updates should use statement
forms rather than attribute mutation. The same service already uses `sa_update()` statements
correctly in `run_post_check` and the worker uses them for segment updates.

**Fix:** Use an `UPDATE` statement:

```python
await session.execute(
    update(Glossary).where(Glossary.id == glossary_id).values(name=name)
)
await session.commit()
g = await get_glossary(session, glossary_id)
return g
```

---

### IN-04: `useReviewKeyboard` — comment on `?` hotkey is slightly misleading

**File:** `frontend/src/hooks/useReviewKeyboard.ts:73-75`

**Issue:** The comment says `"Using shift+/ is wrong: it would match event.key==='/',
but Shift held transforms / to ?"`. This conflates raw DOM behavior with `react-hotkeys-hook`
library behavior and could mislead future maintainers. The hotkey `"?"` itself is correct.

**Fix:** Simplify the comment:

```typescript
// "?" — react-hotkeys-hook matches event.key directly;
// no need to specify "shift+/" explicitly.
useHotkeys("?", () => onToggleHelp(), { preventDefault: true });
```

---

_Reviewed: 2026-04-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
