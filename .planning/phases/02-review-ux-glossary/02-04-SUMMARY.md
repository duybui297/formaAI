---
phase: "02-review-ux-glossary"
plan: "04"
subsystem: backend
tags:
  - export
  - segments
  - glossary-injection
  - post-check
  - advisory-lock
  - tdd
dependency_graph:
  requires:
    - "02-02 (models.py Phase 2 fields — implemented here as parallel executor)"
    - "02-03 (glossary_service.py — implemented here as parallel executor)"
  provides:
    - "GET /jobs/{id}/segments with flags (REV-01)"
    - "PATCH /segments/{id} with job-state gate (REV-02)"
    - "POST /segments/{id}/regenerate sync re-translate (REV-04)"
    - "POST /jobs/{id}/export idempotent DOCX reassembly (REV-05/06)"
    - "Worker glossary injection + post-check per batch (GLOS-03/04, LAYOUT-01)"
  affects:
    - "02-06 (frontend review page — depends on these endpoints)"
    - "02-05 (glossary routes — shares glossary_service.py)"
tech_stack:
  added:
    - "asyncio.Lock + WeakValueDictionary for per-job advisory lock"
    - "os.replace atomic write pattern for DOCX export"
  patterns:
    - "edited_text ?? translated_text (explicit None check, not `or`)"
    - "run_post_check imported from glossary_service — not defined in worker"
    - "glossary loaded once before batch loop (GLOS-03)"
key_files:
  created:
    - backend/src/app/services/export_service.py
    - backend/src/app/services/glossary_service.py
    - backend/src/app/api/routes/segments.py
    - backend/src/app/api/routes/export.py
    - backend/tests/services/test_export_service.py
    - backend/tests/services/test_post_check.py
    - backend/tests/workers/test_worker_glossary.py
  modified:
    - backend/src/app/db/models.py
    - backend/src/app/core/config.py
    - backend/src/app/main.py
    - backend/src/app/workers/translate_worker.py
    - backend/tests/workers/test_translate_worker.py
decisions:
  - "Implemented models.py Phase 2 extension and glossary_service.py here since Plans 02/03 run in the same wave and their output is required"
  - "Patched run_post_check in existing worker tests (Rule 1) — MagicMock settings.expansion_thresholds_dict caused TypeError in float comparison"
  - "Used request.app.state.llm_client for regenerate endpoint instead of adding get_llm_client dependency function — simpler and consistent with how arq_pool is consumed in the regenerate pattern"
metrics:
  duration_minutes: 35
  completed_date: "2026-04-24T19:52:00Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 7
  files_modified: 5
  tests_added: 33
---

# Phase 02 Plan 04: Segment Export Backend Summary

Segment and export backend implementing REV-01..06, GLOS-03/04, and LAYOUT-01. Delivers the full REST surface the frontend review page (Plan 06) depends on: segment list with flags, inline edit with job-state gate, single-segment regenerate, and idempotent DOCX export with advisory lock.

## What Was Built

### Task 1: export_service.py — advisory lock + atomic write (f4df2bf)

`export_job(session, job_id, data_dir) -> str`:
- asyncio.Lock per job_id via WeakValueDictionary (in-process advisory lock, sufficient for single-uvicorn PoC)
- Validates job status is done or needs_review (ValueError if not)
- Builds translated_map using `edited_text if edited_text is not None else translated_text or ""` — explicit None check per Pitfall 5 (empty string edit must not fall back to translated_text)
- Does NOT mutate segment rows (REV-06 invariant)
- Atomic write: doc.save(tmp_path) then os.replace(tmp_path, output_path) — prevents partial reads
- 10 tests: state gate, edited_text selection, Pitfall 5 empty-string, atomic write spy, concurrent lock

Also implemented in this commit (as parallel executor, Plans 02/03 not yet available):
- models.py Phase 2 extension: Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity; edited_text/expansion_ratio on Segment; glossary_id FK on Job
- glossary_service.py: load_glossary_terms_for_job, run_post_check, CSV/TBX import, CRUD helpers
- config.py: expansion_thresholds_dict property

### Task 2: segments.py + export.py routes (51ec489)

`GET /jobs/{id}/segments` (REV-01):
- Returns segments with embedded flags and flag_counts per type (one GROUP BY query)
- 404 for unknown job

`PATCH /segments/{id}` (REV-02):
- Job-state gate: 409 if status not in {done, needs_review} — prevents race with active worker
- edited_text=null clears edit; export will fall back to translated_text
- max_length=10,000 enforced by Pydantic Field (T-02-04-01 DoS mitigation)
- Returns {segment_id, edited_text}

`POST /segments/{id}/regenerate` (REV-04):
- Validates job state (409 gate same as PATCH)
- Loads glossary from DB, calls translate_batch synchronously
- Overwrites translated_text ONLY — never touches edited_text (D-02-20)
- LLM client from app.state.llm_client (added to lifespan)

`POST /jobs/{id}/export` (REV-05/06):
- Delegates to export_service.export_job
- 409 for non-exportable state, FileResponse for success

10 tests covering all endpoints, state gates, 422 oversized text.

### Task 3: translate_worker.py extension (c64ab38)

Three surgical additions:
1. Import `load_glossary_terms_for_job, run_post_check` from glossary_service (top of file)
2. Load glossary once before batch loop: `glossary = await load_glossary_terms_for_job(session, job.glossary_id)`
3. Replace `glossary=None` with `glossary=glossary` in translate_batch call
4. Call `run_post_check(...)` per batch after translated_map populated

run_post_check is NOT defined in translate_worker.py — import only from glossary_service.

13 tests: structural checks (def not in worker, imports present), runtime glossary passing, None glossary, post_check called per batch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Phase 2 model fields not yet available**
- **Found during:** Task 1 (pre-implementation scan)
- **Issue:** Plans 02/03 run in the same wave and their outputs (models.py Phase 2 fields, glossary_service.py) are not yet committed to this worktree
- **Fix:** Implemented models.py Phase 2 extension and complete glossary_service.py in this plan's Task 1 commit — includes all fields and functions required by Plans 02/03 plus this plan
- **Files modified:** backend/src/app/db/models.py, backend/src/app/core/config.py, backend/src/app/services/glossary_service.py
- **Commit:** f4df2bf

**2. [Rule 1 - Bug] Existing worker tests broke due to MagicMock settings**
- **Found during:** Task 3 verification
- **Issue:** test_translate_job_happy_path used `MagicMock()` for settings; after wiring `run_post_check`, `settings.expansion_thresholds_dict` returned a MagicMock causing `TypeError: '>' not supported between instances of 'float' and 'MagicMock'`
- **Fix:** Added `patch("app.workers.translate_worker.run_post_check", new_callable=AsyncMock)` to the three existing worker integration tests that use MagicMock settings (not testing post-check behaviour themselves)
- **Files modified:** backend/tests/workers/test_translate_worker.py
- **Commit:** c64ab38

## Known Stubs

None. All endpoint behaviors are fully implemented with real DB writes.

## Threat Flags

All threats from plan's threat register have been mitigated:

| Flag | File | Mitigation |
|------|------|------------|
| T-02-04-01 DoS | segments.py | edited_text max_length=10,000 via Pydantic Field; 422 on exceed |
| T-02-04-02 DoS | segments.py | Job status gate (409) before LLM call in regenerate |
| T-02-04-04 Integrity | export_service.py | asyncio.Lock + atomic os.replace |
| T-02-04-06 Tampering | segments.py | PATCH checks _REVIEWABLE_STATUSES; 409 during active worker run |

## Self-Check: PASSED

All 7 created files exist on disk. All 3 task commits (f4df2bf, 51ec489, c64ab38) verified in git log. 175 non-integration tests pass.
