---
phase: "01"
plan: "06a"
subsystem: api
tags: [fastapi, upload, languages, cors, arq, lifespan]
dependency_graph:
  requires:
    - "01-05"  # translate_worker (WorkerSettings, translate_job function)
    - "01-03"  # job_service.create_job, db models
    - "01-02"  # pipeline/docx/tracked.has_tracked_changes
  provides:
    - POST /upload (UPLD-01..05)
    - GET /languages (LANG-01)
    - GET /glossaries (stub)
    - GET /health (INFRA-03)
    - FastAPI lifespan with shared arq pool (W11)
  affects:
    - frontend (Next.js upload form consumes /upload + /languages)
    - translate_worker (jobs enqueued here are consumed by worker)
tech_stack:
  added: []
  patterns:
    - FastAPI lifespan context manager (startup/shutdown resource management)
    - Dependency injection via app.state (W11 arq pool pattern)
    - ASGITransport integration tests (httpx + SQLite in-memory)
    - Streaming size guard (defence-in-depth, no Content-Length trust)
key_files:
  created:
    - backend/src/app/main.py
    - backend/src/app/api/__init__.py
    - backend/src/app/api/dependencies.py
    - backend/src/app/api/middleware/__init__.py
    - backend/src/app/api/middleware/cors.py
    - backend/src/app/api/routes/__init__.py
    - backend/src/app/api/routes/health.py
    - backend/src/app/api/routes/upload.py
    - backend/src/app/api/routes/languages.py
    - backend/src/app/api/routes/glossaries.py
    - backend/tests/api/__init__.py
    - backend/tests/api/test_health.py
    - backend/tests/api/test_upload.py
    - backend/tests/api/test_languages.py
  modified: []
decisions:
  - "Used dependency_overrides instead of lifespan patching in tests — app is a module-level singleton; overrides are the correct FastAPI testing pattern for dependencies"
  - "create_job does not accept job_id (DB auto-generates via uuid4 default) — upload route creates job with empty input_path, saves file using job.id, then updates input_path before enqueue"
  - "SUPPORTED_LANGUAGES uses frozenset for _VALID_CODES and _VALID_TARGET_CODES — O(1) lookup vs O(n) list scan for target_lang validation"
  - "Inline CORS config in middleware/cors.py (add_cors_middleware function) rather than direct in main.py — keeps main.py focused on app factory pattern"
metrics:
  duration_minutes: 28
  completed_date: "2026-04-24"
  tasks_completed: 2
  files_created: 14
---

# Phase 1 Plan 06a: FastAPI Core Summary

FastAPI app factory with lifespan resource management, CORS, upload endpoint (size/type/language validation + arq enqueue), languages endpoint (dict-shaped with qwen_code), glossaries stub, and shared dependencies — 18 integration tests, 82% overall coverage.

## Tasks Completed

| # | Name | Commit | Status |
|---|------|--------|--------|
| 1 | App Entry Point + CORS + Dependencies + Health | c4c5aaf | Done |
| 2 | Upload Endpoint + Languages + Glossaries Stub | 1d87da6 | Done |

## Decisions Made

**1. Dependency overrides for test infrastructure**
Used `app.dependency_overrides` + direct `app.state` mutation instead of patching the lifespan context manager. The FastAPI app is a module-level singleton in `main.py`; the lifespan runs only once per process lifetime (the patch would not apply after first import). Dependency overrides are the correct FastAPI testing pattern.

**2. create_job does not accept job_id**
The plan's upload code snippet pre-generated a UUID and passed it to `create_job`. The actual `create_job` service signature doesn't accept `job_id` — the DB model auto-generates it via `default=lambda: str(uuid.uuid4())`. Fixed by creating the job with `input_path=""`, saving the file to `{data_dir}/jobs/{job.id}/source{ext}`, then updating `job.input_path` before committing.

**3. frozenset for language code lookups**
`_VALID_CODES` and `_VALID_TARGET_CODES` use `frozenset` for O(1) membership testing in target_lang validation, rather than set (which is mutable) or list (O(n)).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] create_job signature mismatch — job_id not accepted**
- **Found during:** Task 2 implementation
- **Issue:** Plan's upload.py snippet called `create_job(session=session, job_id=job_id, ...)` but the service function signature is `create_job(session, source_lang, target_lang, input_format, input_path, original_filename, ...)` with no `job_id` parameter (DB auto-generates it)
- **Fix:** Create job first (gets DB-assigned `job.id`), then save file using `job.id` in path, update `job.input_path`, commit. Two-phase approach preserves the per-job directory layout (D-04) while working with the existing service API.
- **Files modified:** `backend/src/app/api/routes/upload.py`
- **Commit:** 1d87da6

**2. [Rule 2 - Security] Streaming guard uses temp file for DOCX probe**
- **Found during:** Task 2 implementation
- **Issue:** Plan's upload snippet called `Document(input_path)` but at the probe point the file hadn't been saved yet (content only in memory). Writing to temp file and unlinking after probe ensures no orphaned files and the probe works on full content.
- **Fix:** Write content to `tempfile.NamedTemporaryFile`, probe, unlink. Final save to `{data_dir}/jobs/{job.id}/source.docx` happens after DB row is created.
- **Files modified:** `backend/src/app/api/routes/upload.py`
- **Commit:** 1d87da6

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `GET /glossaries` returns `{"glossaries": []}` | `backend/src/app/api/routes/glossaries.py:21` | UPLD-04 deferred to Phase 2 per D-15 — glossary CRUD UI ships in Phase 2 |

## Threat Surface

All T-06a threat mitigations from the plan's threat register are implemented:

| Threat ID | Mitigation Status |
|-----------|------------------|
| T-06a-01 (file tampering) | Extension check + streaming size guard + server-side UUID path |
| T-06a-02 (DoS via per-request pool) | W11: single arq pool on app.state, injected via dependency |
| T-06a-03 (lang code tampering) | `target_lang` validated against `_VALID_TARGET_CODES` frozenset |
| T-06a-04 (CORS spoofing) | `allow_origins=["http://localhost:3000"]`, not `"*"` |
| T-06a-05 (info disclosure) | Accepted — internal PoC, HTTPException details are informational |

## Test Results

```
18 integration tests, 0 failures
Coverage: 82% total (exceeds 80% threshold)
```

Key test scenarios:
- 413 on Content-Length > 25MB (fast path)
- 413 on streaming content > 25MB (defence in depth)
- 415 on unsupported extension (.txt)
- 422 on Phase 1 format gate (PDF, PPTX)
- 422 on unknown target_lang code
- 422 on "auto" as target_lang
- 202 + job_id on valid DOCX upload
- arq enqueue_job called with "translate_job" + job_id
- has_tracked_changes=False for plain DOCX
- has_tracked_changes=True for DOCX with `<w:ins>`
- Source file persisted to {data_dir}/jobs/{job_id}/source.docx

## Self-Check: PASSED

Files exist:
- backend/src/app/main.py ✓
- backend/src/app/api/dependencies.py ✓
- backend/src/app/api/middleware/cors.py ✓
- backend/src/app/api/routes/health.py ✓
- backend/src/app/api/routes/upload.py ✓
- backend/src/app/api/routes/languages.py ✓
- backend/src/app/api/routes/glossaries.py ✓
- backend/tests/api/test_upload.py ✓
- backend/tests/api/test_languages.py ✓
- backend/tests/api/test_health.py ✓

Commits exist:
- c4c5aaf — feat(main): add FastAPI app factory + lifespan + CORS + health + deps ✓
- 1d87da6 — feat(api): add POST /upload, GET /languages, GET /glossaries stub ✓
