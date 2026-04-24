---
phase: 01-foundation-docx-pipeline
plan: "10"
subsystem: ui
tags: [nextjs, tanstack-query, shadcn, tailwind, react]

requires:
  - phase: 01-foundation-docx-pipeline
    plan: "07"
    provides: "JobSummary type, listJobs() API function, JobStatus type in types.ts"

provides:
  - "StatusBadge component with semantic color coding per UI-SPEC"
  - "JobsTable component: full shadcn Table with all required columns"
  - "/jobs page with 5s polling via TanStack Query refetchInterval"
  - "Empty state with copywriting-contract copy and upload CTA"

affects:
  - job-status-page
  - upload-page
  - any future plan using JobStatus display

tech-stack:
  added: []
  patterns:
    - "StatusBadge: Record<JobStatus, string> style maps for type-safe color coding"
    - "Table row click navigation with stopPropagation on action column"
    - "refetchInterval polling pattern for list views (no SSE needed)"

key-files:
  created:
    - frontend/src/components/StatusBadge.tsx
    - frontend/src/components/JobsTable.tsx
    - frontend/src/app/jobs/page.tsx
  modified: []

key-decisions:
  - "Extracted JobsTable into its own component for reusability and testability, with page.tsx handling empty/loading states"
  - "Used Record<JobStatus, string> maps for STATUS_STYLES and STATUS_LABELS — exhaustive type checking catches missing status variants at compile time"
  - "Download action uses window.location.href (browser download) rather than fetch() to trigger file download directly"

patterns-established:
  - "StatusBadge: import and use wherever JobStatus needs visual representation"
  - "Page-level component handles loading/empty/data states; table component receives populated jobs[]"

requirements-completed:
  - JOB-01
  - JOB-02

duration: 10min
completed: 2026-04-24
---

# Phase 1 Plan 10: Jobs List Page Summary

**Polling jobs list page with shadcn Table, semantic StatusBadge component, and empty state — wired to GET /api/jobs every 5s via TanStack Query**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-24T05:25:00Z
- **Completed:** 2026-04-24T05:34:58Z
- **Tasks:** 1
- **Files modified:** 3 created

## Accomplishments

- `StatusBadge` component with `Record<JobStatus, string>` style maps — emerald/red/amber/indigo per UI-SPEC semantic color table
- `JobsTable` component encapsulating shadcn Table with columns: #, Filename, Languages, Format, Status, Created, Actions
- `/jobs` page with 5s polling (`refetchInterval`), empty state ("No translations yet"), loading state, and "New Translation" CTA
- Download button visible only on `done`-status rows; row click navigates to `/jobs/{id}` with action cell `stopPropagation`

## Task Commits

1. **Task 1: StatusBadge component + jobs list page** — `d06f1ac` (feat)

## Files Created/Modified

- `frontend/src/components/StatusBadge.tsx` — Reusable badge with semantic colors per UI-SPEC; exported `StatusBadge`
- `frontend/src/components/JobsTable.tsx` — Extracted table component receiving `JobSummary[]` prop
- `frontend/src/app/jobs/page.tsx` — Page shell with TanStack Query polling, empty/loading/table states

## Decisions Made

- Extracted `JobsTable` into a separate component even though the plan embedded it in `page.tsx` — improves testability and keeps `page.tsx` under 60 lines focused on state management
- `Record<JobStatus, string>` maps for styles and labels ensure TypeScript flags missing status variants at compile time rather than silently falling through

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Extracted JobsTable as separate component**
- **Found during:** Task 1
- **Issue:** Deliverables checklist specified `frontend/src/components/JobsTable.tsx` but plan action embedded table inline in page.tsx
- **Fix:** Created `JobsTable.tsx` and updated `page.tsx` to use it, satisfying both the checklist and improving separation of concerns
- **Files modified:** frontend/src/components/JobsTable.tsx (created), frontend/src/app/jobs/page.tsx (simplified)
- **Verification:** TypeScript clean, 27/27 tests pass
- **Committed in:** d06f1ac

---

**Total deviations:** 1 (missing deliverable from checklist, resolved by creating component)
**Impact on plan:** Additive only — no scope creep, improves testability.

## Issues Encountered

None — shadcn Table was already installed from a prior plan; no new dependencies needed.

## Known Stubs

None — `listJobs()` is wired to a real API endpoint (`GET /api/jobs`). Empty state renders when the array is empty, not as a hardcoded stub.

## Next Phase Readiness

- `StatusBadge` is reusable and can be imported into the job detail page (`/jobs/[id]`) built in plan 09
- `JobsTable` receives `JobSummary[]` — ready to be wrapped with filtering/sorting if needed in a future plan
- All 27 existing tests remain green; no regressions

---
*Phase: 01-foundation-docx-pipeline*
*Completed: 2026-04-24*
