---
phase: "02"
plan: "05"
subsystem: frontend
tags: [glossary, ui, tanstack-query, next-font, radix-ui]
dependency_graph:
  requires: ["02-01", "02-03"]
  provides: [glossary-frontend, flag-badge, glossary-select, paper-fonts]
  affects: [upload-form, nav-bar, layout]
tech_stack:
  added: []
  patterns:
    - next/font/google CSS variable injection on html element
    - Radix __none__ sentinel for empty-value SelectItem
    - TanStack Query useQuery with .glossaries unwrap pattern
    - Inline edit state pattern (editingId + editState)
key_files:
  created:
    - frontend/src/components/FlagBadge.tsx
    - frontend/src/components/GlossarySelect.tsx
    - frontend/src/components/glossary/GlossaryList.tsx
    - frontend/src/components/glossary/GlossaryCreateDialog.tsx
    - frontend/src/components/glossary/TermsTable.tsx
    - frontend/src/components/glossary/CSVUploadButton.tsx
    - frontend/src/app/glossaries/page.tsx
    - frontend/src/app/glossaries/[id]/page.tsx
  modified:
    - frontend/src/lib/types.ts
    - frontend/src/app/layout.tsx
    - frontend/src/components/NavBar.tsx
    - frontend/src/components/UploadForm.tsx
decisions:
  - "GlossarySelect disables itself when sourceLang=auto (auto-detect) since the backend needs an explicit lang pair to filter glossaries"
  - "TermsTable single-click delete (no confirm) per UI-SPEC — terms are cheap to re-add"
  - "GlossaryList delete uses window.confirm per plan — PoC scope, no separate Dialog needed"
  - "CSVUploadButton resets e.target.value after import so the same file can be re-imported"
metrics:
  duration_seconds: 321
  completed_date: "2026-04-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 8
  files_modified: 4
---

# Phase 02 Plan 05: Glossary Frontend Summary

**One-liner:** Glossary CRUD frontend with FlagBadge, GlossarySelect (__none__ Radix sentinel), /glossaries list+create page, /glossaries/[id] inline term editor with CSV import, Montserrat/Roboto/PT Mono paper fonts, and UploadForm glossary picker integration.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Extend types.ts + paper fonts in layout.tsx | a0cfe95 | types.ts, layout.tsx |
| 2 | FlagBadge, GlossarySelect, NavBar Glossaries link | c5b55ba | FlagBadge.tsx, GlossarySelect.tsx, NavBar.tsx |
| 3 | Glossary pages, CRUD components, UploadForm integration | 55dec7a | glossaries/page.tsx, [id]/page.tsx, GlossaryList, GlossaryCreateDialog, TermsTable, CSVUploadButton, UploadForm.tsx |

## Verification Results

- TypeScript: zero errors on all new/modified files (pre-existing errors in UploadForm.test.tsx and shadcn command.tsx/popover.tsx unaffected)
- All 12 files from `files_modified` frontmatter exist at correct paths
- GlossarySelect uses `value="__none__"` sentinel (Radix runtime safe — no empty string value)
- GlossarySelect `onValueChange` maps `"__none__"` → `""` before calling parent `onChange`
- Both GlossarySelect and glossaries/page.tsx extract `.glossaries` from `{"glossaries": [...]}` response
- FlagBadge: exactly 4 configs — amber (overflow), violet (glossary_violation), orange (placeholder_mismatch), red (llm_refusal)
- NavBar: "Glossaries" link between Jobs and health dot, active state on `/glossaries/*`
- layout.tsx: `--font-roboto`, `--font-montserrat`, `--font-pt-mono` variables injected on `<html>`
- UploadForm: `glossary_id` appended to FormData when non-empty; `sourceLang="auto"` maps to `""` so GlossarySelect stays disabled
- GlossaryCreateDialog `onCreated: () => void` — no argument, parent invalidates cache and closes dialog

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes

- The "coming soon" text in UploadForm drop zone (`"Drop your DOCX here (PDF & PPTX coming soon)"`) is pre-existing Phase 1 scope text, not a stub introduced by this plan.
- GlossarySelect has an extra guard: `sourceLang !== "auto"` in addition to `!!sourceLang && !!targetLang`. This prevents a wasted API call when auto-detect is selected (backend needs an explicit lang code to filter). Not in the plan but correct per threat model T-02-05-02 and UX intent.

## Known Stubs

None — all data paths are wired to live API endpoints. GlossarySelect, glossaries page, and glossary detail page all call real `/api/glossaries/*` endpoints from Wave 1 backend (plan 02-03).

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. All API calls are client-to-backend proxied through Next.js `/api/*` routes already established in Phase 1.

## Self-Check: PASSED

All 12 files confirmed present. All 3 commits confirmed in git log.
