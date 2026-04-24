---
phase: "01"
plan: "06b"
subsystem: jobs-api
tags: [fastapi, sse, redis-pubsub, job-status, download, jobs-list]
dependency_graph:
  requires:
    - "01-05"   # job_service CRUD + state machine
    - "01-06a"  # FastAPI app factory + lifespan + shared dependencies
  provides:
    - GET /jobs (list last 50 newest-first)
    - GET /jobs/{id} (D-10 status detail)
    - GET /jobs/{id}/stream (SSE EventSourceResponse with Redis pub/sub)
    - GET /jobs/{id}/download (FileResponse for done/needs_review jobs)
  affects:
    - frontend job status page (consumes /stream + /jobs/{id})
    - frontend jobs list page (consumes /jobs)
    - frontend download button (consumes /jobs/{id}/download)
tech_stack:
  added:
    - sse-starlette 1.8.2 (EventSourceResponse, AppStatus)
  patterns:
    - Redis pub/sub subscribe/get_message/unsubscribe/aclose lifecycle
    - SSE generator with finally-block cleanup (Pitfall #3 mitigation)
    - FileResponse with server-side output_path validation
    - TDD RED/GREEN with AppStatus event-loop reset fixture for pytest-asyncio
key_files:
  created:
    - backend/src/app/api/routes/jobs.py
    - backend/src/app/api/routes/sse.py
    - backend/tests/api/test_jobs.py
    - backend/tests/api/test_sse.py
  modified:
    - backend/src/app/main.py (added jobs.router + sse.router)
decisions:
  - "AppStatus.should_exit_event reset fixture: sse-starlette 1.x stores anyio.Event as class attribute; pytest-asyncio creates a new loop per test, causing RuntimeError on stale event. Reset AppStatus.should_exit = False / should_exit_event = None in autouse fixture — cleaner than pinning to sse-starlette 2.x which requires FastAPI 0.135+."
  - "aclose() vs close(): used pubsub.aclose() (async) per redis-py asyncio API; PATTERNS.md reference used pubsub.close() (sync). aclose() is correct for async context."
  - "Separate jobs.py and sse.py modules: keeps route files under 200 lines each and separates concerns (REST vs streaming), per CLAUDE.md file organization rule."
metrics:
  duration_minutes: 15
  completed_date: "2026-04-24"
  tasks_completed: 1
  tasks_total: 1
  files_created: 4
  files_modified: 1
  tests_added: 10
  tests_total: 131
  coverage_pct: 80.32
---

# Phase 1 Plan 06b: FastAPI Jobs API + SSE Progress Stream Summary

**One-liner:** Jobs REST API (list/detail/download) + Redis pub/sub SSE stream with Pitfall-#3-safe finally-block cleanup using sse-starlette EventSourceResponse.

## What Was Built

Three endpoint groups registered on the FastAPI app:

**`backend/src/app/api/routes/jobs.py`**
- `GET /jobs` — returns `{"jobs": [...]}` with last 50 jobs newest-first; each item is the D-10 shape
- `GET /jobs/{id}` — job detail with all D-10 fields: id, status, stage, source/target/detected lang, input_format, original_filename, segments_done, segments_total, retry_count, error_msg, has_tracked_changes, created_at, updated_at
- `GET /jobs/{id}/download` — streams output file via `FileResponse`; returns 409 for non-terminal jobs; 404 for missing/deleted file; `Content-Disposition: attachment; filename="translated_{original_filename}"`

**`backend/src/app/api/routes/sse.py`**
- `GET /jobs/{id}/stream` — `EventSourceResponse` wrapping an async generator that subscribes to `job:{id}` Redis pub/sub channel
- Generator yields `{"event": "progress", "data": <D-10 JSON>}` for each message
- Breaks on terminal status (`done` / `failed` / `needs_review`) or client disconnect (`request.is_disconnected()`)
- `finally` block always calls `pubsub.unsubscribe(f"job:{job_id}")` + `pubsub.aclose()` (Pitfall #3)
- Response headers: `ping=15`, `X-Accel-Buffering: no`, `Cache-Control: no-store`

**`backend/src/app/main.py`** — added `jobs.router` and `sse.router` to `include_router` calls.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed sse-starlette AppStatus event-loop binding in pytest**
- **Found during:** Task 1 GREEN phase (3 SSE tests failing with RuntimeError)
- **Issue:** `sse_starlette.AppStatus.should_exit_event` is a class-level attribute set to an `anyio.Event()` instance during the first SSE test. When pytest-asyncio creates a new event loop for subsequent tests, `event.wait()` raises `RuntimeError: Event is bound to a different event loop`.
- **Fix:** Added `autouse=True` pytest fixture `reset_sse_app_status` in `test_sse.py` that resets `AppStatus.should_exit = False` and `AppStatus.should_exit_event = None` before and after each test, forcing a fresh `anyio.Event` to be created per test loop.
- **Files modified:** `backend/tests/api/test_sse.py`
- **Commit:** 0161b43

**2. [Rule 2 - Missing functionality] Used `pubsub.aclose()` instead of `pubsub.close()`**
- **Found during:** Task 1 implementation review
- **Issue:** PATTERNS.md reference shows `pubsub.close()` (sync); redis-py asyncio pubsub requires `aclose()` for async cleanup.
- **Fix:** Used `await pubsub.aclose()` in the finally block — correct for async context.
- **Files modified:** `backend/src/app/api/routes/sse.py`

## TDD Gate Compliance

- RED gate: commit `aaf86a3` — `test(jobs): add failing tests for jobs + SSE endpoints (RED)` (8 failures confirmed)
- GREEN gate: commit `0161b43` — `feat(jobs): add GET /jobs, GET /jobs/{id}, GET /jobs/{id}/download` (all 10 pass)
- REFACTOR: no structural changes needed — code met quality bar after GREEN

## Known Stubs

None — all endpoints are fully wired. `/jobs/{id}/download` returns real `FileResponse`, `/jobs/{id}/stream` reads real Redis pub/sub, `/jobs` and `/jobs/{id}` query real DB via `get_session` + `get_job`.

## Threat Surface Scan

No new threat surface beyond what is documented in the plan's threat register:

| Flag | File | Description |
|------|------|-------------|
| T-06b-01 mitigated | `routes/jobs.py` | `output_path` is DB-stored (server-side); `os.path.exists` check before `FileResponse` |
| T-06b-02 mitigated | `routes/sse.py` | `finally` block always unsubscribes; `CancelledError` caught |
| T-06b-03 accepted | `routes/jobs.py` | `error_msg` in GET /jobs/{id} — internal PoC; no stack traces |
| T-06b-04 accepted | `routes/sse.py` | Unlimited SSE connections per job_id — internal PoC, Phase 1 |

## Self-Check

### Files created exist
- `backend/src/app/api/routes/jobs.py` — FOUND
- `backend/src/app/api/routes/sse.py` — FOUND
- `backend/tests/api/test_jobs.py` — FOUND
- `backend/tests/api/test_sse.py` — FOUND

### Commits exist
- `aaf86a3` — test(jobs): RED phase tests
- `0161b43` — feat(jobs): GREEN implementation

### Test results
- 131 passed, 0 failed
- Coverage: 80.32% (threshold: 80%)

## Self-Check: PASSED
