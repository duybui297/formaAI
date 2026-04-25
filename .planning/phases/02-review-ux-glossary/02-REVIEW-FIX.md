---
phase: 02-review-ux-glossary
fixed_at: 2026-04-25T00:00:00Z
review_path: .planning/phases/02-review-ux-glossary/02-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-04-25
**Source review:** .planning/phases/02-review-ux-glossary/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (Warnings only — no Criticals)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: `patch_segment` / `regenerate_segment` silently target wrong job on duplicate segment hash

**Files modified:** `backend/src/app/api/routes/segments.py`, `frontend/src/hooks/useSegments.ts`, `backend/tests/api/test_segments.py`
**Commit:** fea0634 (routes), 39bd0b0 (test updates)
**Applied fix:** Migrated both endpoints from `/segments/{segment_id}` to
`/jobs/{job_id}/segments/{segment_id}` (and regenerate to
`/jobs/{job_id}/segments/{segment_id}/regenerate`). Both path parameters are now
declared, `.limit(1)` workaround removed, and the DB query uses a compound
`WHERE (job_id, id)` predicate via `scalar_one_or_none()`. The `patch_segment`
job status gate now queries `Job` by `job_id` directly (no longer via `seg.job_id`).
Frontend `useSegments.ts` fetch URLs updated to match the new paths. All six
test functions in `test_segments.py` updated to use the job-scoped routes.

### WR-02: Migration backfill for `segment_job_id` is non-deterministic when `segment.id` is not unique

**Files modified:** `backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py`
**Commit:** d5b5700
**Applied fix:** Replaced the multi-row `UPDATE … FROM segments … WHERE s.id = sf.segment_id`
join with a correlated subquery that adds `ORDER BY s.created_at LIMIT 1`. When a
`segment_flags.segment_id` maps to more than one job row (the collision scenario this
migration addresses), the backfill now deterministically picks the earliest job by
`created_at` rather than leaving the result to insertion order.

### WR-03: Worker segment insertion is not idempotent — crash-restart causes `IntegrityError`

**Files modified:** `backend/src/app/workers/translate_worker.py`
**Commit:** e7d1972
**Applied fix:** Added `from sqlalchemy.exc import IntegrityError` import. Wrapped
the `session.add_all(orm_segments) / await session.commit()` block in a
`try/except IntegrityError` that rolls back the session and logs a warning at
`WARNING` level instead of propagating. On a crash-restart the worker skips
re-insertion of already-persisted segments and continues to the translate stage,
preserving job recoverability.

### WR-04: `URL.revokeObjectURL` called synchronously after `a.click()` races download

**Files modified:** `frontend/src/components/ReviewPageHeader.tsx`
**Commit:** 2b7a80d
**Applied fix:** Changed `URL.revokeObjectURL(url)` to
`setTimeout(() => URL.revokeObjectURL(url), 100)` so the browser finishes reading
the blob URL before it is revoked. This is the standard idiom for Safari and
Firefox compatibility.

## Skipped Issues

None — all four in-scope findings were fixed.

---

_Fixed: 2026-04-25_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
