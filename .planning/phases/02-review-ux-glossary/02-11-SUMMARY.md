---
phase: 02-review-ux-glossary
plan: 11
subsystem: export
tags: [error-handling, ux, export, structured-errors]
dependency_graph:
  requires: [02-10]
  provides: [structured-export-errors, export-detail-banner]
  affects: [frontend/src/components/ReviewPageHeader.tsx, backend/src/app/api/routes/export.py]
tech_stack:
  added: []
  patterns: [JSONResponse structured error body, try/catch JSON parse in fetch error path]
key_files:
  created: []
  modified:
    - backend/src/app/api/routes/export.py
    - frontend/src/components/ReviewPageHeader.tsx
decisions:
  - "Use JSONResponse instead of HTTPException so the body can carry both code and detail fields; HTTPException only supports a flat detail string"
  - "Frontend falls back to generic message when body is not JSON (e.g. binary download on an unexpected 2xx path); backend controls user-visible detail text"
metrics:
  duration_minutes: 10
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  completed_date: "2026-04-25T09:16:56Z"
---

# Phase 02 Plan 11: Structured Export Error Response Summary

**One-liner:** Export endpoint returns `{code, detail}` JSON on all failure paths; frontend parses `body.detail` into error banner instead of showing "Unknown error".

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Structured error responses in export endpoint | c9a4aed | backend/src/app/api/routes/export.py |
| 2 | Frontend parses structured export error and displays detail | 7cd8340 | frontend/src/components/ReviewPageHeader.tsx |

## What Was Built

### Task 1 — backend/src/app/api/routes/export.py

Replaced `raise HTTPException(status_code=409, detail=str(exc))` (single catch) with three `return JSONResponse(...)` branches:

- `ValueError` → HTTP 409 `{"code": "export_state_error", "detail": "..."}`
- `AttributeError` → HTTP 500 `{"code": "export_failed", "detail": "Export assembly error: ..."}`
- `Exception` → HTTP 500 `{"code": "export_failed", "detail": "Export failed: ..."}`

The `AttributeError` branch is the belt-and-suspenders catch for any ORM column still missing after the 02-10 migration, if any DB row was created before the migration ran.

### Task 2 — frontend/src/components/ReviewPageHeader.tsx

The export error path previously showed:
```
Export failed — Unknown error. Try again.
```
(when `err.detail` was undefined from the old `HTTPException` 409 body in some cases)

Updated to:
```typescript
let detail = "Could not export document. Try again.";
try {
  const body = await res.json();
  if (body?.detail) { detail = body.detail; }
} catch { /* non-JSON response — keep generic */ }
toast({ title: detail, variant: "destructive" });
```

The backend-provided `detail` string is displayed verbatim — backend controls the user-visible message. The network error catch was also updated to a clearer message.

## Deviations from Plan

None — plan executed exactly as written.

The discovery step in Task 2 found the export logic in `frontend/src/components/ReviewPageHeader.tsx` (not `frontend/src/hooks/useExport.ts` as the plan anticipated). The file `useExport.ts` does not exist; the plan's `read_first` listed it as conditional ("if it exists"). No deviation — this was the expected discovery pattern.

## Verification Results

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| `grep -c "JSONResponse" export.py` | ≥4 | 6 | PASS |
| `grep -c "export_state_error" export.py` | 1 | 1 | PASS |
| `grep -c "export_failed" export.py` | 2 | 2 | PASS |
| `grep "except AttributeError"` | 1 match | 1 | PASS |
| `grep "except Exception"` | 1 match | 1 | PASS |
| `grep -rn "body.detail" frontend/src/` | 1 match | 1 | PASS |
| `grep -rn "Export failed" frontend/src/` | 0 matches | 0 | PASS |
| TypeScript errors in ReviewPageHeader.tsx | 0 | 0 | PASS |
| Python syntax check export.py | OK | OK | PASS |

Pre-existing TS errors in `frontend/src/__tests__/UploadForm.test.tsx` (3× `'res' is of type 'unknown'`) are unrelated to this plan — out of scope.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. Error detail exposure is accepted for internal PoC per T-02-11-01 in the plan's threat model.

## Self-Check: PASSED

- `backend/src/app/api/routes/export.py` — exists, modified
- `frontend/src/components/ReviewPageHeader.tsx` — exists, modified
- Commit c9a4aed exists in git log
- Commit 7cd8340 exists in git log
