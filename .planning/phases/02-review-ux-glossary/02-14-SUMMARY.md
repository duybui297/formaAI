---
phase: 02-review-ux-glossary
plan: 14
subsystem: frontend
tags: [fonts, vietnamese, i18n, segment-review]
dependency_graph:
  requires: []
  provides: [vietnamese-font-coverage]
  affects: [frontend/src/app/layout.tsx, CLAUDE.md]
tech_stack:
  added: [JetBrains Mono (via next/font/google)]
  patterns: [CSS variable backwards compat]
key_files:
  modified:
    - frontend/src/app/layout.tsx
    - CLAUDE.md
decisions:
  - "Replace PT Mono with JetBrains Mono: PT Mono has no 'vietnamese' subset on Google Fonts — it only ships cyrillic, cyrillic-ext, latin, latin-ext. JetBrains Mono covers all of those plus greek and vietnamese."
  - "Preserve CSS variable name --font-pt-mono: SegmentRow.tsx uses this var via inline style attribute; renaming would require a separate change with no functional benefit."
metrics:
  duration: 10m
  completed: "2026-04-25"
  tasks: 2
  files: 2
---

# Phase 02 Plan 14: Vietnamese Font Fix (PT Mono → JetBrains Mono) Summary

**One-liner:** Replace PT Mono (no Vietnamese subset) with JetBrains Mono in layout.tsx, preserving the --font-pt-mono CSS variable so SegmentRow.tsx renders VN diacritics without any consumer-side changes.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Swap PT Mono to JetBrains Mono with vietnamese subset | 7f7ab21 | frontend/src/app/layout.tsx |
| 2 | Update CLAUDE.md paper-skill font convention note | 0446ee9 | CLAUDE.md |

## What Was Done

**Task 1 — layout.tsx font swap:**
- Replaced `PT_Mono` import with `JetBrains_Mono` from `next/font/google`
- Renamed internal JS const from `ptMono` to `jetbrainsMono`
- Changed subsets from `["latin"]` to `["latin", "vietnamese"]`
- Kept CSS variable `--font-pt-mono` (backwards compat — SegmentRow.tsx unchanged)
- Updated html className to use `${jetbrainsMono.variable}`
- All four fonts (Inter, Roboto, Montserrat, JetBrains Mono) now load the `vietnamese` subset

**Task 2 — CLAUDE.md convention update:**
- Updated the D-02-27 paper-skill fonts note to reference JetBrains Mono as the source-cell font
- Documents why PT Mono was replaced (lacks Vietnamese subset on Google Fonts)
- Preserves the `--font-pt-mono` CSS variable reference so the backwards-compat intent is clear

## Verification Results

```
grep "JetBrains_Mono" layout.tsx       → 2 matches (import + const)
grep -c "vietnamese" layout.tsx        → 6 (4 subsets + comment + inline CSS var comment)
grep "PT_Mono" layout.tsx              → 0 (removed)
grep "--font-pt-mono" layout.tsx       → 2 (comment + variable declaration)
grep "font-pt-mono" SegmentRow.tsx     → 1 (unchanged consumer)
grep "JetBrains Mono" CLAUDE.md        → 1 (convention note updated)
TypeScript errors                      → 3 pre-existing errors in UploadForm.test.tsx (unrelated, out of scope)
```

## Deviations from Plan

None — plan executed exactly as written. The pre-existing TypeScript errors in `UploadForm.test.tsx` were confirmed to predate this plan's changes via `git stash` verification; they are out of scope.

## Known Stubs

None.

## Threat Flags

None. The font swap uses `next/font/google` which self-hosts fonts at build time — no runtime Google Fonts CDN calls. This matches the T-02-14-01 threat disposition (accept) documented in the plan.

## Self-Check: PASSED

- [x] `frontend/src/app/layout.tsx` exists and contains `JetBrains_Mono`
- [x] `CLAUDE.md` exists and contains updated convention note
- [x] Commit 7f7ab21 exists (Task 1)
- [x] Commit 0446ee9 exists (Task 2)
- [x] `SegmentRow.tsx` unchanged (CSS var `--font-pt-mono` still works)
