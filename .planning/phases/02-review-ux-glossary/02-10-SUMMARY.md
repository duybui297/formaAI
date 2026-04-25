---
phase: 02-review-ux-glossary
plan: 10
subsystem: db-core
tags: [migration, compound-pk, orm, worker, gap-closure]
dependency_graph:
  requires: [02-08, 02-09]
  provides: [compound-pk-segments, run-index-fields, segment-flags-compound-fk]
  affects: [export-service, translate-worker, glossary-service, segments-routes]
tech_stack:
  added: []
  patterns: [compound-primary-key, compound-foreign-key, alembic-backfill-migration]
key_files:
  created:
    - backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py
    - backend/tests/workers/test_segment_pk_collision.py
  modified:
    - backend/src/app/db/models.py
    - backend/src/app/workers/translate_worker.py
    - backend/src/app/services/glossary_service.py
    - backend/src/app/api/routes/segments.py
decisions:
  - "Deferred PATCH URL migration (/segments/{id} -> /jobs/{job_id}/segments/{id}) to plan 02-11; used .limit(1) as safe interim fix"
  - "Used IF EXISTS SQL form for FK drop in migration to be robust to constraint-name variation"
  - "Used segment_job_id filter directly on SegmentFlag table instead of join for flag_counts query"
metrics:
  duration_minutes: 25
  completed_date: "2026-04-25"
  tasks_completed: 3
  files_created: 2
  files_modified: 4
---

# Phase 02 Plan 10: Segment Compound PK + Run Fields Gap Closure Summary

Compound PK migration (job_id, id) on segments + run_index/run_group_size columns, unblocking re-upload PK collision (UAT Test 5) and DOCX export AttributeError (UAT Test 4).

## What Was Built

**Task 1 — Alembic migration 0003:** `0003_segment_compound_pk_run_fields.py` drops the single-column `segments_pkey`, creates compound PK `(job_id, id)`, adds `segment_job_id` to `segment_flags` with compound FK, backfills from segments table, adds `run_index` (nullable) and `run_group_size` (default 1) to segments. `downgrade()` fully reverses all ops.

**Task 2 — Migration applied + ORM + worker + service updates:**
- Migration 0003 applied to live PostgreSQL — `segments_pkey` is now `PRIMARY KEY (job_id, id)`
- `ORM Segment`: compound PK declared (`id` + `job_id` both `primary_key=True`), `run_index` + `run_group_size` mapped columns added
- `ORM SegmentFlag`: single-column `ForeignKey("segments.id")` removed from `mapped_column`; `segment_job_id` column added; compound `ForeignKeyConstraint` in `__table_args__`
- `translate_worker.py`: `SegmentORM(...)` constructor now passes `run_index=seg.run_index` and `run_group_size=seg.run_group_size`
- `glossary_service.py`: `run_post_check` signature gains `job_id` param; expansion_ratio UPDATE uses compound WHERE `(Segment.job_id == job_id, Segment.id == seg.id)`; all 4 `SegmentFlag(...)` constructors pass `segment_job_id=job_id`
- `segments.py` routes: flag_counts query uses `SegmentFlag.segment_job_id == job_id` filter (no join needed); PATCH and regenerate queries use `.limit(1)` and compound WHERE on UPDATEs

**Task 3 — 3 unit tests:**
- `test_same_content_two_jobs_no_pk_collision`: two jobs with same-content segment insert without IntegrityError
- `test_segment_orm_has_run_fields`: run_index=2, run_group_size=3 roundtrip through SQLite ORM
- `test_orm_segment_run_index_no_attribute_error`: accessing `.run_index` on loaded ORM Segment never raises AttributeError

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Migration file not visible to running Docker container**

- **Found during:** Task 2 Step A (apply migration)
- **Issue:** The API container mounts from the main repo at `/backend`, not the worktree. `docker compose exec api alembic upgrade head` found no new migration.
- **Fix:** `docker cp` the migration file directly into the running container at `/backend/src/app/db/migrations/versions/`, then ran `alembic upgrade head` — succeeded.
- **Files modified:** Migration file copied to container (ephemeral — permanent when worktree merges to main)
- **Commit:** b05a9c5

**2. [Rule 3 - Blocking] Test PYTHONPATH picks up main repo models, not worktree models**

- **Found during:** Task 3 (running tests)
- **Issue:** The venv is shared from the main repo; `app.db.models` resolves to the main repo's old `models.py` (no `run_index`), causing TypeError in tests.
- **Fix:** Ran tests with `PYTHONPATH` pointing to the worktree's `src/` directory.
- **Commit:** 0905ef7

### Deferred Items

- **PATCH/regenerate URL migration** (`/segments/{id}` to `/jobs/{job_id}/segments/{id}`): deferred to plan 02-11. Interim fix: `.limit(1)` prevents `MultipleResultsFound`; compound WHERE on UPDATE uses `seg.job_id`. TODO comments added in routes.

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | b05a9c5 | feat(db): add migration 0003 — compound PK (job_id, id) + run fields |
| 2 | 807b66f | feat(core): apply compound PK migration + update ORM, worker, service, routes |
| 3 | 0905ef7 | test(core): compound PK no-collision + run fields roundtrip + no AttributeError |

## Verification Results

| Check | Result |
|-------|--------|
| `run_index` in live DB | PASS — integer, nullable |
| `run_group_size` in live DB | PASS — integer, not null, default 1 |
| `segments_pkey` = compound (job_id, id) | PASS |
| `segment_job_id` in segment_flags | PASS — not null, compound FK |
| Old single-col FK removed from ORM | PASS — 0 matches |
| 4 SegmentFlag constructors with segment_job_id | PASS — count=4 |
| Compound WHERE on expansion_ratio UPDATE | PASS |
| 3 unit tests | PASS — 3 passed |

## Known Stubs

None — all ORM fields are wired to DB columns and worker populates them from the pipeline dataclass.

## Threat Flags

None — no new network endpoints or auth paths introduced. The `segment_job_id` column is internal DB only, not surfaced in API responses.

## Self-Check: PASSED

- Migration file exists: backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py
- Test file exists: backend/tests/workers/test_segment_pk_collision.py
- Commits b05a9c5, 807b66f, 0905ef7 all verified in git log
- Live DB compound PK confirmed via psql
- 3 tests pass
