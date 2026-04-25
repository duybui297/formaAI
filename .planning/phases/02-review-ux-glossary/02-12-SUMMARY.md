---
phase: 02-review-ux-glossary
plan: 12
subsystem: frontend/keyboard
tags: [keyboard-shortcuts, hotkeys, bug-fix, ux]
requirements: [REV-03]

dependency_graph:
  requires: []
  provides: [? key toggles help panel]
  affects: [frontend/src/hooks/useReviewKeyboard.ts]

tech_stack:
  added: []
  patterns: [react-hotkeys-hook event.key matching]

key_files:
  modified:
    - frontend/src/hooks/useReviewKeyboard.ts

decisions:
  - "Use '?' string in useHotkeys — matches event.key directly; shift+/ is wrong because Shift+/ sends event.key==='?' not event.key==='/' "
  - "j/k vim navigation kept as-is per 02-09 decision; j/k UX concern deferred to Phase 3"
  - "KeyboardHelpPanel already showed '?' label; no change required there"

metrics:
  duration_minutes: 5
  completed_at: "2026-04-25T08:56:41Z"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 1
---

# Phase 02 Plan 12: Keyboard ? Shortcut Fix Summary

**One-liner:** Fixed ? hotkey to use `event.key==="?"` detection so Shift+/ correctly toggles the help panel.

## What Was Built

Fixed a broken keyboard shortcut in `useReviewKeyboard.ts`: the `shift+/` binding in `react-hotkeys-hook` never fired because pressing Shift+/ on a US keyboard emits `event.key === "?"` (the shifted character) — not `event.key === "/" with shiftKey=true`. Changing the binding string from `"shift+/"` to `"?"` makes react-hotkeys-hook match the actual browser event.

## Tasks

| Task | Name | Status | Commit | Files |
|------|------|--------|--------|-------|
| 1 | Fix ? hotkey detection in useReviewKeyboard.ts | Done | 2642bf6 | frontend/src/hooks/useReviewKeyboard.ts |
| 2 | Update KeyboardHelpPanel help text to show "?" not "Shift+?" | Done (already correct) | — | frontend/src/components/KeyboardHelpPanel.tsx |

## Deviations from Plan

### Task 2 Already Correct

**Found during:** Task 2 read
**Issue:** Plan expected `KeyboardHelpPanel.tsx` to show "Shift+?" and need updating. Actual file already had `{ key: "?", action: "Toggle this panel" }` in the SHORTCUTS array.
**Action:** No change required. Verified acceptance criteria all pass (0 "Shift+?" matches, 1 "?" label, j/k labels intact).
**Classification:** No deviation — plan was written against an assumed state that matched the actual state by the time of execution.

## Verification

All acceptance criteria passed:

```
grep -n '"shift+/"' frontend/src/hooks/useReviewKeyboard.ts  → 0 matches
grep -n '"?"'       frontend/src/hooks/useReviewKeyboard.ts  → 2 matches (comment + binding)
grep -n '"?"'       frontend/src/components/KeyboardHelpPanel.tsx → 1 match (label)
grep -n "Shift+?"   frontend/src/components/KeyboardHelpPanel.tsx → 0 matches
grep -in '"j"\|"k"' frontend/src/components/KeyboardHelpPanel.tsx → 2 matches (j/k preserved)
npx tsc --noEmit → no errors on either file
```

## Known Stubs

None.

## Threat Flags

None — keyboard shortcut change has no security implications; no user data involved.

## Self-Check: PASSED

- [x] `frontend/src/hooks/useReviewKeyboard.ts` modified and committed at 2642bf6
- [x] `frontend/src/components/KeyboardHelpPanel.tsx` verified correct (no change needed)
- [x] Commit 2642bf6 exists in git log
- [x] No unexpected file deletions
- [x] TypeScript compiles clean
