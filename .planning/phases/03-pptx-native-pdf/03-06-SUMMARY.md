---
phase: "03-pptx-native-pdf"
plan: "06"
subsystem: frontend
tags: [frontend, flag-badge, breadcrumb, upload-form, pptx, pdf, tdd]
dependency_graph:
  requires: ["03-01", "03-02"]
  provides: ["formatBreadcrumb helper", "FlagBadge smartart/multi_column_degraded", "UploadForm PPTX/PDF accept"]
  affects: ["frontend/src/lib/formatBreadcrumb.ts", "frontend/src/components/FlagBadge.tsx", "frontend/src/components/SegmentRow.tsx", "frontend/src/components/UploadForm.tsx"]
tech_stack:
  added: []
  patterns: ["TDD RED→GREEN", "prefix-based structural position parsing", "M2 overflow auto-adjusted badge differentiation"]
key_files:
  created:
    - frontend/src/lib/formatBreadcrumb.ts
  modified:
    - frontend/src/lib/types.ts
    - frontend/src/lib/review-types.ts
    - frontend/src/components/FlagBadge.tsx
    - frontend/src/components/SegmentRow.tsx
    - frontend/src/components/UploadForm.tsx
    - frontend/src/__tests__/UploadForm.test.tsx
decisions:
  - "Shape index displayed 1-based (raw 0-based) per UI-SPEC D-03-07 and test contract"
  - "M2: overflow + details.auto_adjusted=true renders AUTO-FIT (slate) not OVERFLOW (amber)"
  - "UploadForm.test.tsx Phase 1 tests updated to match Phase 3 behavior (PDF now accepted)"
  - "formatBreadcrumb implemented as pure function — prefix-based, never throws"
metrics:
  duration: "6 minutes"
  completed: "2026-04-25T20:00:29Z"
  tasks_completed: 2
  files_modified: 7
---

# Phase 03 Plan 06: Frontend Phase 3 Changes Summary

Frontend-only plan adding formatBreadcrumb helper, FlagBadge extension for PPTX/PDF flag types, SegmentRow breadcrumb integration, and UploadForm accept list expansion to support PPTX and native PDF uploads.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | formatBreadcrumb + FlagType unions | e41951d | formatBreadcrumb.ts, types.ts, review-types.ts |
| 2 | FlagBadge + SegmentRow + UploadForm | abcbbe8 | FlagBadge.tsx, SegmentRow.tsx, UploadForm.tsx, UploadForm.test.tsx |

## What Was Built

**formatBreadcrumb.ts** — Pure helper that converts raw `structural_position` strings into human-readable breadcrumbs. Detection is prefix-based (no format parameter needed):
- `slide.*` / `master.*` → PPTX format (`Slide N / Shape M / ¶K`, shape 1-indexed)
- `page.*` → PDF format (`Page N / Col C / Block B` or `Page N / Block B`)
- Anything else → raw fallback (never throws, never returns empty for non-empty input)

**FlagType union extensions** — Both `frontend/src/lib/types.ts` and `frontend/src/lib/review-types.ts` now include `"smartart"` and `"multi_column_degraded"`. `Segment` interface in both files gains `structural_position?: string | null`.

**FlagBadge.tsx** — Extended with:
- `smartart`: orange badge, label "SMART" (`text-orange-700 bg-orange-50 border-orange-200`)
- `multi_column_degraded`: slate badge, label "MULTI-COL" (`text-slate-600 bg-slate-100 border-slate-300`)
- M2 rule: `overflow` + `details.auto_adjusted === true` → "AUTO-FIT" info badge (slate); otherwise standard "Overflow" warning (amber)
- Added `details?: Record<string, unknown> | null` prop

**SegmentRow.tsx** — Three records extended (FLAG_BADGE_STYLES, FLAG_LABELS, LEFT_BORDER) with smartart and multi_column_degraded entries. Breadcrumb span added above `source_text` in source cell, rendered only when `structural_position` is non-null/non-empty.

**UploadForm.tsx** — 5 surgical changes:
1. `ALLOWED_EXTS` → `new Set([".docx", ".pptx", ".pdf"])`
2. Error message → `"Unsupported file type. Accepted formats: .docx, .pptx, .pdf"`
3. Drop zone idle text → `"Drop your document here — DOCX, PPTX, or native PDF"`
4. `accept` attribute expanded with PPTX/PDF MIME types
5. TC detection guarded: `ext === ".docx" ? await detectTrackedChanges(f) : false`

## Test Results

```
Test Files  5 passed | 3 skipped (8)
     Tests  48 passed | 20 todo (68)
```

- `formatBreadcrumb.test.ts`: 10/10 tests GREEN (TDD RED→GREEN complete)
- `FlagBadge.test.tsx`: 4 active tests GREEN, 5 todo (pre-existing)
- `UploadForm.test.tsx`: 27/27 tests GREEN (3 Phase 1 tests updated for Phase 3 behavior)
- All other test files unchanged and passing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] UploadForm Phase 1 tests asserting stale copy**
- **Found during:** Task 2 — full test suite run
- **Issue:** 3 UploadForm tests were asserting against Phase 1-only strings: old drop zone text, old `accept` attribute (DOCX-only), and a test that expected PDF to be rejected (Phase 1 behavior). These are pre-existing tests that described Phase 1 behavior, not the TDD scaffolds from plan 03-02.
- **Fix:** Updated the 3 tests to assert Phase 3 behavior: new drop zone text, expanded accept attribute, and PDF acceptance (with no `detectTrackedChanges` call for non-DOCX).
- **Files modified:** `frontend/src/__tests__/UploadForm.test.tsx`
- **Commit:** abcbbe8

## Known Stubs

None — all flag rendering is wired to real data. `structural_position` breadcrumb renders when the field is present; DOCX segments from Phase 1 already have this field populated.

## Threat Flags

None — no new network endpoints, no new auth paths. UploadForm accept expansion is client-side only; server-side validation remains unchanged (existing UPLD-02 guard).

## Self-Check: PASSED

Files verified:
- `frontend/src/lib/formatBreadcrumb.ts` — FOUND
- `frontend/src/lib/types.ts` contains `"smartart"` — FOUND
- `frontend/src/components/FlagBadge.tsx` contains `smartart:` — FOUND
- `frontend/src/components/SegmentRow.tsx` contains `formatBreadcrumb` — FOUND
- `frontend/src/components/UploadForm.tsx` contains `.pptx` — FOUND

Commits verified:
- e41951d — FOUND (Task 1)
- abcbbe8 — FOUND (Task 2)
