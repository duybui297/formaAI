---
phase: "01"
plan: "09"
subsystem: frontend
tags: [job-status, sse, progress, animation, ui]
dependency_graph:
  requires: ["01-07", "01-08"]
  provides: [jobs-status-page, useCounterAnimation, StageIndicator, ProgressBar, ErrorDetails, JobMetaRow]
  affects: [frontend/src/app/jobs]
tech_stack:
  added: ["@radix-ui/react-collapsible (via shadcn collapsible)"]
  patterns: [react-use-hook, requestAnimationFrame-animation, shadcn-collapsible, async-params-react-use]
key_files:
  created:
    - frontend/src/app/jobs/[id]/page.tsx
    - frontend/src/components/StageIndicator.tsx
    - frontend/src/components/ProgressBar.tsx
    - frontend/src/components/ErrorDetails.tsx
    - frontend/src/components/JobMetaRow.tsx
    - frontend/src/hooks/useCounterAnimation.ts
    - frontend/src/components/ui/collapsible.tsx
  modified:
    - frontend/src/__tests__/useCounterAnimation.test.ts
    - frontend/package.json
decisions:
  - "Set<JobStatus> used instead of Set<string> to satisfy TypeScript strict inference on Set constructor"
  - "fromRef.current resets startRef.current to null before RAF loop to prevent carry-over from prior animation"
  - "Test uses t=0 for first RAF call (sets startRef), t=150 for 50% progress, t=300 for 100%"
metrics:
  duration_minutes: 5
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 2
---

# Phase 1 Plan 09: Job Status Page Summary

**One-liner:** SSE-driven `/jobs/[id]` status page with RAF-animated segment counter, 4-stage stepper, collapsible error panel, and terminal-state download button.

## What Was Built

The `/jobs/[id]` page gives users live translation progress via the `useJobProgress` SSE+TanStack Query hybrid from Plan 07. It composes five new components and one new hook:

- **`useCounterAnimation`** — interpolates a numeric display value toward a target using `requestAnimationFrame`. Snaps immediately (`duration=0`) on terminal states so there's no animation lag after completion.
- **`StageIndicator`** — horizontal 4-stage stepper (Parse → Translate → Reassemble → Done). Active=indigo-600, past=emerald-500 + checkmark, future=slate-300, failed=red-600 + X icon.
- **`ProgressBar`** — shadcn `Progress` wrapper at 8px height with indigo-500 fill.
- **`ErrorDetails`** — destructive `Alert` with shadcn `Collapsible` revealing failing segment `source_text` entries. No traceback shown in UI (per D-11).
- **`JobMetaRow`** — 12px metadata strip: source→target lang, format badge, created-at age.
- **`/jobs/[id]/page.tsx`** — composes all of the above. Handles all five job states: queued (skeleton), running (progress + retry chip), done (indigo download button), failed (error banner), needs_review (placeholder card + download).

## Verification

- `npx tsc --noEmit` — zero errors
- `npx vitest run` — 27 tests pass (22 pre-existing + 5 new useCounterAnimation tests)
- TDD gates: RED commit `68ee65d` → GREEN commits `912a593` / `7114fbc`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TypeScript Set<string> vs Set<JobStatus> inference**
- **Found during:** Task 2 TypeScript check
- **Issue:** `new Set(["done", "failed", "needs_review"])` inferred as `Set<string>`, not assignable to `Set<JobStatus>`
- **Fix:** Changed to `new Set<JobStatus>(["done", "failed", "needs_review"])` explicit type parameter
- **Files modified:** `frontend/src/app/jobs/[id]/page.tsx`
- **Commit:** fbd90d1

**2. [Rule 1 - Bug] RAF animation test: incorrect timestamp for first frame**
- **Found during:** Task 1 GREEN phase — test failed at 50% progress assertion
- **Issue:** Test called `rafCallback(150)` as first RAF tick; this sets `startRef.current = 150`, making elapsed=0 at t=150 and progress=0, not 50%
- **Fix:** Added `rafCallback(0)` as first call to initialize `startRef`, then `rafCallback(150)` for 50% and `rafCallback(300)` for 100%
- **Files modified:** `frontend/src/__tests__/useCounterAnimation.test.ts`
- **Commit:** 7114fbc

## Known Stubs

None — all components render real data from `useJobProgress`. No placeholder or hardcoded values flowing to UI.

## Threat Flags

None — no new network endpoints introduced. The `/api/jobs/{jobId}/download` href passes `jobId` from URL params; validated by FastAPI route handler on the backend (T-01-09-03 accepted per plan threat model).

## Self-Check

### Files exist
- `frontend/src/app/jobs/[id]/page.tsx` — FOUND
- `frontend/src/components/StageIndicator.tsx` — FOUND
- `frontend/src/components/ProgressBar.tsx` — FOUND
- `frontend/src/components/ErrorDetails.tsx` — FOUND
- `frontend/src/components/JobMetaRow.tsx` — FOUND
- `frontend/src/hooks/useCounterAnimation.ts` — FOUND
- `frontend/src/__tests__/useCounterAnimation.test.ts` — FOUND

### Commits exist
- `68ee65d` test(jobs-page): add failing tests for useCounterAnimation hook — FOUND
- `912a593` feat(jobs-page): add useCounterAnimation hook, StageIndicator, ProgressBar — FOUND
- `7114fbc` test(jobs-page): fix useCounterAnimation RAF simulation in animation test — FOUND
- `fbd90d1` feat(jobs-page): add job status page, ErrorDetails, JobMetaRow components — FOUND

## Self-Check: PASSED
