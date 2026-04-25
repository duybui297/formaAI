---
phase: 02-review-ux-glossary
plan: 09
subsystem: ui
tags: [nextjs, react, typescript, fastapi, glossary, review-ux]

# Dependency graph
requires:
  - phase: 02-review-ux-glossary
    provides: glossary pages, review page, SegmentRow, useReviewKeyboard, types.ts, jobs.py
provides:
  - NavBar present on /glossaries and /glossaries/[id] routes
  - Glossary.term_count type field + GlossaryList renders correct count
  - GET /jobs/{id} response includes glossary_id field
  - useReviewKeyboard j/k hotkeys safe when filteredSegments is empty (WR-02)
  - SegmentRow isMountedRef guard prevents stale setSaveState on unmount (WR-03)
  - SegmentsResponse.flag_counts type field (IN-01 type completeness)
affects: [03-pdf-native, phase-03, review-ux]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "isMountedRef pattern for guarding async mutation callbacks in Virtuoso-virtualized rows"
    - "segmentCount === 0 early-return guard before Math.min/max on empty lists"

key-files:
  created: []
  modified:
    - frontend/src/lib/types.ts
    - backend/src/app/api/routes/jobs.py
    - frontend/src/app/glossaries/page.tsx
    - frontend/src/app/glossaries/[id]/page.tsx
    - frontend/src/components/glossary/GlossaryList.tsx
    - frontend/src/hooks/useReviewKeyboard.ts
    - frontend/src/components/SegmentRow.tsx

key-decisions:
  - "Render NavBar in each glossary page component (not root layout) — consistent with review page pattern"
  - "SegmentsResponse.flag_counts added as type-only fix (no runtime change — ReviewFilterBar computes counts client-side)"
  - "isMountedRef initialized to true at declaration, set false in cleanup effect — avoids React 18 Strict Mode double-invoke false positives"

patterns-established:
  - "isMountedRef: guard pattern for mutation callbacks in Virtuoso-virtualized components"

requirements-completed: [GLOS-01, GLOS-05, REV-01, REV-02]

# Metrics
duration: 18min
completed: 2026-04-25
---

# Phase 02 Plan 09: Polish Gaps Summary

**NavBar added to glossary routes, term_count fixes IN-03 dash bug, glossary_id in job response, WR-02/WR-03 defensive guards applied**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-25T06:14:00Z
- **Completed:** 2026-04-25T06:32:48Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- NavBar rendered on /glossaries and /glossaries/[id] (including loading/error states)
- GlossaryList now shows correct term count from `g.term_count` instead of always showing "—"
- `GET /jobs/{id}` response includes `glossary_id` field, enabling frontend to display/route on attached glossary
- `useReviewKeyboard` j/k hotkeys guard `segmentCount === 0` — prevents `Math.min(1, -1) = -1` Virtuoso scroll
- `SegmentRow` `isMountedRef` guard prevents stale `setSaveState` calls when Virtuoso unmounts a row mid-debounce
- `SegmentsResponse.flag_counts` type field added for IN-01 completeness

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix types.ts + backend glossary_id** - `3ea683f` (fix)
2. **Task 2: NavBar on glossary pages + GlossaryList term_count + WR-02/WR-03 guards** - `81da5b9` (fix)

## Files Created/Modified

- `frontend/src/lib/types.ts` - Added `Glossary.term_count`, `SegmentsResponse.flag_counts`, `JobProgress.glossary_id`
- `backend/src/app/api/routes/jobs.py` - Added `"glossary_id": job.glossary_id` to `_job_to_dict`
- `frontend/src/app/glossaries/page.tsx` - Added NavBar import + render
- `frontend/src/app/glossaries/[id]/page.tsx` - Added NavBar to all return paths (loading, not-found, main)
- `frontend/src/components/glossary/GlossaryList.tsx` - Changed `g.terms?.length ?? "—"` to `g.term_count`
- `frontend/src/hooks/useReviewKeyboard.ts` - Added `if (segmentCount === 0) return` guard on j/k hotkeys
- `frontend/src/components/SegmentRow.tsx` - Added `isMountedRef` + cleanup effect + guards in mutation callbacks

## Decisions Made

- NavBar rendered per-page (not in root layout) to match the established pattern in `review/page.tsx`
- `flag_counts` added to `SegmentsResponse` as type-only fix (no runtime change — ReviewFilterBar computes counts client-side from the segments array)
- `isMountedRef` initialized to `true` at declaration (not in effect) so it's immediately safe before the first render completes; the cleanup effect sets it to `false` on unmount

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- A `git stash` check (to verify pre-existing coverage baseline) temporarily reverted working-tree changes; `git stash pop` restored them cleanly. No files were lost.
- Backend test suite reports 79.38% coverage — confirmed to be pre-existing (same result from the baseline before our changes). Our single-line `_job_to_dict` addition adds no new uncovered paths.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All Phase 2 UAT-reported gaps and code-review warnings (WR-02, WR-03, IN-03, IN-01) are now closed
- Phase 3 (PDF native translation) can begin with a clean Phase 2 baseline
- No blockers or concerns carried forward

---
*Phase: 02-review-ux-glossary*
*Completed: 2026-04-25*
