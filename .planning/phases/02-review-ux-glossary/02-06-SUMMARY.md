---
phase: 02-review-ux-glossary
plan: "06"
subsystem: ui
tags: [react, nextjs, tanstack-query, react-virtuoso, react-hotkeys-hook, typescript]

# Dependency graph
requires:
  - phase: 02-review-ux-glossary/02-04
    provides: segment CRUD endpoints (GET /segments, PATCH /segments/{id}, POST /segments/{id}/regenerate, POST /jobs/{id}/export)
  - phase: 02-review-ux-glossary/02-01
    provides: frontend test scaffolding, react-virtuoso and react-hotkeys-hook installed
provides:
  - useSegments hook (GET segments, PATCH with optimistic update, POST regenerate)
  - useReviewKeyboard hook (j/k/n/e/r/shift+?/escape bindings)
  - SegmentTable component (react-virtuoso virtualized list with scrollIntoView ref)
  - SegmentRow component (debounced 500ms PATCH, inline flag badges, discard edit)
  - ReviewFilterBar component (All + 4 flag chips with live counts, Shortcuts toggle)
  - ReviewPageHeader component (filename, lang pair, glossary chip, Export button)
  - KeyboardHelpPanel component (cheatsheet panel with Fragment key fix)
  - /jobs/[id]/review route (assembles full CAT-tool review page)
  - /jobs/[id] extended with "Review Translation" link on done/needs_review
affects: [02-07, phase-03, phase-04]

# Tech tracking
tech-stack:
  added: []  # react-virtuoso and react-hotkeys-hook were already installed by plan 01
  patterns:
    - "react-virtuoso Virtuoso with forwardRef + useImperativeHandle for scrollIntoView"
    - "TanStack Query v5 optimistic mutation with onMutate/onError/onSettled lifecycle"
    - "500ms debounce pattern with per-call onError to reset local UI state"
    - "react-hotkeys-hook for keyboard shortcuts disabled in form fields by default"
    - "Named Fragment import for .map() key prop (not shorthand <>)"
    - "Parallel-executor type isolation: review-types.ts avoids lib/types.ts conflict"

key-files:
  created:
    - frontend/src/lib/review-types.ts
    - frontend/src/hooks/useSegments.ts
    - frontend/src/hooks/useReviewKeyboard.ts
    - frontend/src/components/SegmentTable.tsx
    - frontend/src/components/SegmentRow.tsx
    - frontend/src/components/ReviewFilterBar.tsx
    - frontend/src/components/ReviewPageHeader.tsx
    - frontend/src/components/KeyboardHelpPanel.tsx
    - frontend/src/app/jobs/[id]/review/page.tsx
  modified:
    - frontend/src/app/jobs/[id]/page.tsx

key-decisions:
  - "Created review-types.ts instead of extending lib/types.ts to avoid parallel-executor merge conflict with plan 05 (which also modifies lib/types.ts)"
  - "Inlined flag badge display in SegmentRow (InlineFlagBadge local component) instead of importing FlagBadge.tsx (plan 05 scope) — avoids missing-file TypeScript error in parallel execution"
  - "jobs/[id]/page.tsx needs_review block upgraded from placeholder text to actual Review link + Download fallback (Rule 2: missing critical functionality)"

patterns-established:
  - "Parallel executor isolation: create separate type files rather than modifying shared files owned by sibling wave executors"
  - "Per-call mutation options (onSuccess/onError) handle local UI state; hook-level options handle shared cache and toasts"

requirements-completed: [REV-01, REV-02, REV-03, REV-04, REV-05, REV-06, LAYOUT-01]

# Metrics
duration: 5min
completed: 2026-04-24
---

# Phase 02 Plan 06: Review Frontend Summary

**Virtualized CAT-tool review page with debounced inline editing, flag-chip filtering, keyboard shortcuts (j/k/n/e/r/?), and idempotent DOCX export — wired to Plan 04 segment/export API**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-24T20:03:04Z
- **Completed:** 2026-04-24T20:07:52Z
- **Tasks:** 3
- **Files modified:** 10 (9 created, 1 modified)

## Accomplishments

- Full review page at `/jobs/[id]/review` with react-virtuoso virtualized segment table (source | editable target | flags), filtering by flag type, and keyboard navigation
- useSegmentPatch implements optimistic update with cache rollback and "Could not save" toast on network error; per-call `onError` resets local `saveState` so UI never sticks on "Saving…"
- Seven keyboard shortcuts (j/k/n/e/r/shift+?/escape) via react-hotkeys-hook, wired to virtuoso `scrollIntoView` for keyboard navigation across thousands of segments
- Export button triggers POST /api/jobs/{id}/export and streams DOCX blob to browser download; visible only on `done`/`needs_review` states

## Task Commits

1. **Task 1: useSegments and useReviewKeyboard hooks** - `a3ce5bf` (feat)
2. **Task 2: SegmentTable, SegmentRow, ReviewFilterBar, ReviewPageHeader, KeyboardHelpPanel** - `42ba4da` (feat)
3. **Task 3: /jobs/[id]/review route + job detail Review link** - `3eebadc` (feat)

## Files Created/Modified

- `frontend/src/lib/review-types.ts` — FlagType, SegmentFlag, Segment, SegmentsResponse types (isolated from lib/types.ts for parallel execution safety)
- `frontend/src/hooks/useSegments.ts` — useSegments (GET), useSegmentPatch (optimistic PATCH), useSegmentRegenerate (POST regenerate)
- `frontend/src/hooks/useReviewKeyboard.ts` — j/k/n/e/r/shift+?/escape bindings via react-hotkeys-hook
- `frontend/src/components/SegmentTable.tsx` — Virtuoso wrapper with VirtuosoHandle ref (scrollIntoView)
- `frontend/src/components/SegmentRow.tsx` — source cell + debounced target textarea + inline flag badges + discard edit button
- `frontend/src/components/ReviewFilterBar.tsx` — All chip + 4 flag-type chips with live counts + Shortcuts toggle
- `frontend/src/components/ReviewPageHeader.tsx` — filename, lang pair, optional glossary chip, Export button
- `frontend/src/components/KeyboardHelpPanel.tsx` — keyboard shortcut cheatsheet with named Fragment key pattern
- `frontend/src/app/jobs/[id]/review/page.tsx` — review page assembling all components with keyboard integration
- `frontend/src/app/jobs/[id]/page.tsx` — extended with "Review Translation" link on done/needs_review

## Decisions Made

- **Parallel-executor type isolation:** Created `review-types.ts` instead of extending `lib/types.ts` because plan 05 (wave 2 sibling) owns `lib/types.ts`. When merged, the orchestrator will consolidate types. Avoids TypeScript errors in parallel execution.
- **Inline flag badges:** Created `InlineFlagBadge` local component inside SegmentRow instead of importing `FlagBadge.tsx` (plan 05 scope). Same visual output; no inter-executor dependency. Plan 07 or merge step can refactor to shared FlagBadge.
- **needs_review upgrade:** The existing `jobs/[id]/page.tsx` `needs_review` block had placeholder text ("Segment-level review will be available in the next release"). Replaced with actual Review link + Download fallback per Rule 2 (missing critical functionality now available).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Isolated Segment types into review-types.ts**
- **Found during:** Task 1 (hook implementation)
- **Issue:** Plan calls for importing types from `@/lib/types`, but `lib/types.ts` is in plan 05's `files_modified` scope. Parallel executor constraint prohibits touching plan 05's files.
- **Fix:** Created `frontend/src/lib/review-types.ts` with FlagType, SegmentFlag, Segment, SegmentsResponse. All plan 06 files import from `@/lib/review-types` instead.
- **Files modified:** frontend/src/lib/review-types.ts (new)
- **Verification:** TypeScript compiles clean; no conflicts with plan 05 scope
- **Committed in:** a3ce5bf (Task 1 commit)

**2. [Rule 2 - Missing Critical] Inlined flag badge to avoid FlagBadge.tsx dependency**
- **Found during:** Task 2 (SegmentRow implementation)
- **Issue:** Plan imports `FlagBadge` from `@/components/FlagBadge` which is plan 05's scope and doesn't exist yet in this worktree.
- **Fix:** Added `InlineFlagBadge` local component inside SegmentRow.tsx with same semantic colors and labels. No import of plan 05 files.
- **Files modified:** frontend/src/components/SegmentRow.tsx
- **Verification:** TypeScript clean; flag badges render correctly from Segment.flags array
- **Committed in:** 42ba4da (Task 2 commit)

**3. [Rule 2 - Missing Critical] Replaced needs_review placeholder with real Review link**
- **Found during:** Task 3 (jobs/[id]/page.tsx update)
- **Issue:** Existing `needs_review` block said "Segment-level review will be available in the next release" — now that review is available, keeping the placeholder would prevent users from accessing the review feature.
- **Fix:** Replaced placeholder block with Review link + Download fallback button.
- **Files modified:** frontend/src/app/jobs/[id]/page.tsx
- **Verification:** Both status branches render Review Translation link
- **Committed in:** 3eebadc (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (3 × Rule 2 — missing critical functionality)
**Impact on plan:** All fixes necessary for parallel execution safety and functional completeness. No scope creep.

## Issues Encountered

- TypeScript compilation runs against the main project's `node_modules` (worktree has no local node_modules). Pre-existing errors in `src/components/ui/command.tsx` (missing cmdk) and `src/__tests__/UploadForm.test.tsx` are unrelated to plan 06. Zero new errors introduced.

## User Setup Required

None — no external service configuration required. Backend endpoints from plan 04 are consumed as-is.

## Next Phase Readiness

- Review UX fully functional: virtualized segment table, inline edit with optimistic update, flag filtering, keyboard shortcuts, export trigger
- Wave 2 merge (plans 05 + 06) will resolve type duplication: plan 07 or orchestrator should consolidate `review-types.ts` into `lib/types.ts` and replace `InlineFlagBadge` with `FlagBadge` from plan 05
- Plan 07 (integration + docs) can reference all plan 06 exports directly

---
*Phase: 02-review-ux-glossary*
*Completed: 2026-04-24*
