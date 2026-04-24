---
phase: 02-review-ux-glossary
plan: "03"
subsystem: backend
tags: [glossary, crud, csv-import, tbx-import, post-check, orm]
dependency_graph:
  requires: ["02-02"]
  provides: ["glossary-backend-api", "run_post_check", "load_glossary_terms_for_job"]
  affects: ["02-04", "02-05"]
tech_stack:
  added: []
  patterns:
    - "Pre-fetch dedup for bulk import (avoids per-row rollback greenlet issue on SQLite)"
    - "Response(status_code=204) for FastAPI 204 DELETE endpoints"
    - "Import route declared before /{term_id} routes to prevent literal segment matching"
key_files:
  created:
    - backend/src/app/services/glossary_service.py
    - backend/tests/services/test_glossary_service.py
    - backend/tests/services/test_csv_import.py
    - backend/tests/services/test_tbx_import.py
    - backend/tests/services/test_post_check.py
    - backend/tests/api/test_glossaries.py
  modified:
    - backend/src/app/db/models.py
    - backend/src/app/api/routes/glossaries.py
    - backend/src/app/services/job_service.py
    - backend/src/app/api/routes/upload.py
    - backend/pyproject.toml
decisions:
  - "Pre-fetch dedup approach for import_csv_terms: pre-load existing source_terms as a set, skip in-memory — avoids per-row flush+rollback which corrupts aiosqlite session state"
  - "Response(status_code=204) return type annotation on DELETE endpoints — FastAPI asserts no body allowed for 204 when return type is not Response"
  - "import route declared before /{term_id} PATCH/DELETE routes so FastAPI does not match the literal string 'import' as a term_id path parameter"
  - "Added Phase 2 ORM models directly to models.py (deviation — 02-02 runs in parallel wave but worktree starts from pre-02-02 HEAD)"
  - "session.refresh(g) added in update_glossary_name to avoid MissingGreenlet error when serializer accesses g.terms after commit"
metrics:
  duration: "~72 minutes"
  completed: "2026-04-25"
  tasks_completed: 3
  files_created: 6
  files_modified: 5
---

# Phase 02 Plan 03: Glossary Backend Summary

**One-liner:** Full glossary CRUD REST API (10 endpoints) + CSV/TBX import + post-check flag detector (overflow, glossary_violation, placeholder_mismatch, llm_refusal) with Phase 2 ORM model additions.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| prereq | Phase 2 ORM models (deviation Rule 3) | 9ad04b2 | backend/src/app/db/models.py |
| 1 (RED) | Failing tests for glossary_service | 9d39a50 | tests/services/test_glossary_service.py, test_csv_import.py, test_tbx_import.py, test_post_check.py |
| 1 (GREEN) | glossary_service.py implementation | 9ad04b2 | backend/src/app/services/glossary_service.py |
| 2 (RED) | Failing tests for glossary route | 123169a | tests/api/test_glossaries.py |
| 2 (GREEN) | Full glossaries.py 10-endpoint route | 4163a0d | backend/src/app/api/routes/glossaries.py |
| 3 | upload.py + job_service.py glossary_id extension | 8737aca | upload.py, job_service.py |

## What Was Built

**glossary_service.py** — 13 exported functions:
- CRUD: `create_glossary`, `get_glossary`, `list_glossaries`, `update_glossary_name`, `delete_glossary`
- Terms: `create_term`, `update_term`, `delete_term`
- Import: `parse_csv_glossary` (BOM-strip, 5-alias header variants), `parse_tbx_minimal` (TBX-Core + TBX-Basic), `import_csv_terms` (pre-fetch dedup)
- Worker helpers: `load_glossary_terms_for_job`, `run_post_check`

**glossaries.py** — 10 REST endpoints replacing the Phase 1 stub:
- GET/POST `/glossaries` (list/create), GET/PATCH/DELETE `/glossaries/{id}`
- GET/POST `/glossaries/{id}/terms`, PATCH/DELETE `/glossaries/{id}/terms/{term_id}`
- POST `/glossaries/{id}/terms/import` (CSV/TBX, 25MB cap, 422 on bad format)

**run_post_check** — 4 flag detectors per batch:
1. `overflow`: expansion_ratio > lang-pair threshold → `FlagSeverity.warn`
2. `glossary_violation`: target term absent from translation (case-insensitive, min 2 chars) → `warn`
3. `placeholder_mismatch`: ⟦T{n}⟧ token in source absent from translation → `warn`
4. `llm_refusal`: source > 8 chars AND translated == source → `warn` (no false positives on "AI", "OK")

**Phase 2 ORM additions** (models.py):
- `Glossary`, `GlossaryTerm`, `SegmentFlag` tables + `FlagType`/`FlagSeverity` enums
- `Job.glossary_id` FK (ON DELETE SET NULL)
- `Segment.edited_text`, `Segment.expansion_ratio` columns

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Phase 2 ORM models not in worktree**
- **Found during:** Task 1 setup
- **Issue:** Plan 02-02 (wave 0) adds Glossary/GlossaryTerm/SegmentFlag models, but the worktree starts from 85c7207 (pre-02-02 HEAD) because parallel agents run independently. Without these models, glossary_service.py cannot be implemented.
- **Fix:** Added all Phase 2 model additions (Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity, Job.glossary_id FK, Segment.edited_text + expansion_ratio) directly to models.py in this worktree.
- **Files modified:** `backend/src/app/db/models.py`
- **Commit:** 9ad04b2

**2. [Rule 1 - Bug] import_csv_terms per-row rollback corrupts aiosqlite session**
- **Found during:** Task 1 GREEN — test_import_csv_terms_skips_duplicates failed
- **Issue:** `flush() + rollback()` per row leaves aiosqlite session in a broken state; subsequent operations fail with MissingGreenlet error
- **Fix:** Replaced per-row rollback with pre-fetch dedup: load existing `source_terms` into a set before the loop, skip duplicates in-memory without touching session state
- **Files modified:** `backend/src/app/services/glossary_service.py`
- **Commit:** 9ad04b2

**3. [Rule 1 - Bug] FastAPI 204 DELETE endpoints reject `-> None` return annotation**
- **Found during:** Task 2 GREEN — collection error before any tests ran
- **Issue:** FastAPI asserts `is_body_allowed_for_status_code(204)` fails when return type is `None`
- **Fix:** Changed DELETE endpoint signatures to `-> Response` and return `Response(status_code=204)` explicitly
- **Files modified:** `backend/src/app/api/routes/glossaries.py`
- **Commit:** 4163a0d

**4. [Rule 1 - Bug] update_glossary_name triggers MissingGreenlet on g.terms access**
- **Found during:** Task 2 GREEN — test_patch_glossary_rename failed
- **Issue:** After `session.commit()`, the `g` object is expired; accessing `g.terms` in the serializer (`len(g.terms)`) triggers a lazy reload outside async context
- **Fix:** Added `await session.refresh(g)` after commit in `update_glossary_name`
- **Files modified:** `backend/src/app/services/glossary_service.py`
- **Commit:** 4163a0d

**5. [Rule 2 - Missing Critical Functionality] Test dependencies not installed**
- **Found during:** Initial test execution
- **Issue:** `pytest`, `pytest-asyncio`, `aiosqlite`, `pytest-cov` not installed in worktree venv
- **Fix:** `uv add --optional test` to install test extras from pyproject.toml
- **Files modified:** `backend/pyproject.toml`, `backend/uv.lock`
- **Commit:** 9ad04b2

## Known Stubs

None — all glossary CRUD endpoints are fully implemented and wired to the DB. The `load_glossary_terms_for_job` and `run_post_check` functions are implemented and ready for Plan 04 (worker wiring).

## Threat Flags

No new security surface beyond what is in the plan's threat model. The import endpoint enforces the 25 MB cap (T-02-03-01). ElementTree does not expand external entities (T-02-03-01 XML safety). Glossary pair validation is in place for upload (T-02-03-03). No auth surface added.

## Self-Check: PASSED

All 7 created files exist on disk. All 5 plan commits found in git log:
- 9d39a50 test(02-03): add failing tests for glossary service
- 9ad04b2 feat(02-03): implement glossary_service + Phase 2 ORM models
- 123169a test(02-03): add failing API tests for full glossary route surface
- 4163a0d feat(02-03): replace glossary stub with full 10-endpoint CRUD route
- 8737aca feat(02-03): extend upload + job_service with glossary_id support

Final test run: 203 passed, 0 failed (all non-integration tests).
