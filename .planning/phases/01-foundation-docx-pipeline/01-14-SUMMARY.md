---
phase: 01-foundation-docx-pipeline
plan: "14"
subsystem: upload-form
tags: [gap-closure, error-ux, frontend, backend-tests]
dependency_graph:
  requires: []
  provides:
    - upload-form-inline-error-state
    - upload-form-docx-only-accept
    - backend-error-detail-shape-tests
  affects:
    - frontend/src/components/UploadForm.tsx
    - frontend/src/__tests__/UploadForm.test.tsx
    - backend/tests/api/test_upload_error_ux.py
    - backend/tests/api/conftest.py
tech_stack:
  added: []
  patterns:
    - React useState for inline error display below Submit button
    - role=alert for accessible error paragraph
    - pytest conftest.py fixture extraction for shared app_and_tmp across api tests
key_files:
  modified:
    - frontend/src/components/UploadForm.tsx
    - frontend/src/__tests__/UploadForm.test.tsx
  created:
    - backend/tests/api/test_upload_error_ux.py
    - backend/tests/api/conftest.py
decisions:
  - "Error is surfaced both inline (role=alert paragraph) and as a toast for accessibility — neither alone is sufficient"
  - "accept attribute restricted to .docx MIME only for OS file picker; ALLOWED_EXTS set unchanged so drag-and-drop of pdf/pptx still reaches server and gets actionable 422"
  - "app_and_tmp fixture extracted to tests/api/conftest.py (Rule 3 deviation) — was only in test_upload.py; test_upload.py local definition still shadows conftest for that file, no regressions"
metrics:
  duration_seconds: 236
  completed_date: "2026-04-24T08:23:48Z"
  tasks_completed: 3
  files_changed: 4
---

# Phase 1 Plan 14: Invalid Format Rejection (G3 Gap Closure) Summary

**One-liner:** Inline `role=alert` error state in UploadForm surfaces backend `detail` on non-2xx, with DOCX-only OS picker restriction and backend payload-shape tests.

## What Was Built

Gap G3 closed: clicking "Translate Document" with a `.pdf` or `.txt` file previously silently swallowed the server's 415/422 rejection. Users now see a clear inline error message below the Submit button.

Three coordinated changes:

1. **UploadForm.tsx error state** — `const [error, setError] = useState<string | null>(null)` rendered as `<p role="alert">` below Submit. `setError(null)` on file selection and at submit start; `setError(msg)` in the non-2xx branch reading `data.detail`.

2. **File input accept attribute** — Restricted from `.docx,.pdf,.pptx` to `.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document`. OS file picker shows DOCX only. `ALLOWED_EXTS` set unchanged so drag-and-drop of pdf/pptx still reaches the server and gets actionable 422 (server is authoritative per T-14-01).

3. **Backend error detail shape tests** — `test_upload_error_ux.py` tests the `detail` field content that the frontend surfaces: `.txt` → 415 + "supported" in detail; `.pdf` → 422 + "pdf" in detail.

route.ts was verified to already forward `response.status` verbatim via `Response.json(data, { status: response.status })` — no changes needed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add error state to UploadForm + restrict file input accept | 279b304 | UploadForm.tsx, UploadForm.test.tsx |
| 2 | Verify proxy status forwarding + add frontend vitest tests | 432ea3f | UploadForm.test.tsx |
| 3 | Add error detail shape tests in new backend test file | 4a6cc6c | test_upload_error_ux.py, conftest.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing accept-attribute test to match new value**
- **Found during:** Task 1
- **Issue:** Existing test `"hidden file input accepts .docx, .pdf, .pptx"` checked `input?.accept` equals `.docx,.pdf,.pptx`. After changing the accept attribute, this test would fail.
- **Fix:** Updated test name and assertion to match the new DOCX-only accept value.
- **Files modified:** `frontend/src/__tests__/UploadForm.test.tsx`
- **Commit:** 279b304

**2. [Rule 3 - Blocking] Extracted app_and_tmp fixture to tests/api/conftest.py**
- **Found during:** Task 3
- **Issue:** `app_and_tmp` fixture was defined only in `test_upload.py`. `test_upload_error_ux.py` could not use it — pytest reported "fixture 'app_and_tmp' not found".
- **Fix:** Created `tests/api/conftest.py` with the identical fixture definition so both test files can use it. `test_upload.py`'s local definition shadows conftest for that file (standard pytest behavior) — all 12 existing tests still pass.
- **Files modified:** `backend/tests/api/conftest.py` (new)
- **Commit:** 4a6cc6c

## Verification Results

- `backend/tests/api/test_upload.py`: 12/12 passed (unchanged)
- `backend/tests/api/test_upload_error_ux.py`: 2/2 passed
- `frontend/src/__tests__/UploadForm.test.tsx`: 23/23 passed
- `grep "const \[error, setError\]"` UploadForm.tsx: line 32
- `grep 'role="alert"'` UploadForm.tsx: line 247
- `grep "accept="` UploadForm.tsx: `.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `grep "response.status"` route.ts: line 24 — already correct

## Known Stubs

None — all error paths are wired end-to-end.

## Threat Flags

None — changes are additive UI state and test coverage only. No new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- `frontend/src/components/UploadForm.tsx` — exists, contains error state
- `backend/tests/api/test_upload_error_ux.py` — exists, both tests pass
- `backend/tests/api/conftest.py` — exists, app_and_tmp fixture defined
- Commits 279b304, 432ea3f, 4a6cc6c — all present in git log
