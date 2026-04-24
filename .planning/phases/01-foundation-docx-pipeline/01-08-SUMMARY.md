---
phase: "01"
plan: "08"
subsystem: frontend
tags: [upload, form, tracked-changes, language-select, modal, next-js]
dependency_graph:
  requires:
    - "01-07"  # frontend scaffold, shadcn, QueryProvider, types.ts, api.ts
  provides:
    - upload-page           # /upload route fully functional
    - tracked-changes-flow  # B4 Option A: client-side detection before POST
    - language-select       # code-as-value LanguageSelect with priority groups
    - navbar                # app shell with DashScope health dot
    - upload-proxy-route    # /api/upload → FastAPI /upload forwarding
  affects:
    - "01-09"  # job status page (redirected to from UploadForm after submit)
tech_stack:
  added:
    - "@radix-ui/react-radio-group: shadcn RadioGroup for tracked-changes modal"
    - "@radix-ui/react-label: shadcn Label for form controls"
  patterns:
    - "vi.hoisted() for vitest mock vars shared across vi.mock factories"
    - "B4 Option A: JSZip client-side DOCX detection before first POST"
    - "TrackedChangesModal extracted as standalone testable component"
key_files:
  created:
    - frontend/src/lib/detectTrackedChanges.ts
    - frontend/src/app/api/upload/route.ts
    - frontend/src/app/upload/page.tsx
    - frontend/src/components/NavBar.tsx
    - frontend/src/components/LanguageSelect.tsx
    - frontend/src/components/UploadForm.tsx
    - frontend/src/components/TrackedChangesModal.tsx
    - frontend/src/components/ui/radio-group.tsx
    - frontend/src/components/ui/label.tsx
    - frontend/src/__tests__/UploadForm.test.tsx
  modified:
    - frontend/package.json  # added @radix-ui/react-radio-group, @radix-ui/react-label
decisions:
  - "TrackedChangesModal extracted from UploadForm for standalone testability"
  - "vi.hoisted() used for mock variables referenced inside vi.mock factories (Vitest ESM requirement)"
  - "fireEvent.change + Object.defineProperty(files) for hidden file input in jsdom (userEvent.upload unreliable on hidden inputs)"
  - "B4 guard: trackedAction defaults to null (not 'strip') — guard if (hasTrackedChanges && trackedAction === null) is live"
metrics:
  duration: "9m"
  completed: "2026-04-24"
  tasks_completed: 3
  files_created: 10
  files_modified: 1
  tests_added: 20
  tests_total: 22
---

# Phase 1 Plan 08: Upload Page Summary

JWT auth with refresh rotation using jose library — NOT applicable here.

**One-liner:** Upload page with drag-and-drop, B4 Option A tracked-changes detection via JSZip client-side before first POST, and language-code-as-value LanguageSelect.

## What Was Built

### Task 1: Core utilities + infrastructure (commit d7b2145)
- `detectTrackedChanges.ts` — B4 Option A: reads DOCX bytes with JSZip, checks `word/document.xml` for `<w:ins>`/`<w:del>` before any POST fires
- `api/upload/route.ts` — Next.js proxy: forwards FormData (file, source_lang, target_lang, tracked_changes_action) to FastAPI `POST /upload`
- `NavBar.tsx` — app shell: Upload/Jobs links with active state, DashScope health dot (emerald/red/amber)
- `LanguageSelect.tsx` — shadcn Select with B5 fix: language `code` as value, `name` as display; PRIORITY_CODES `[vi,en,ja,zh,zh-tw]` in Recommended group; 24h staleTime
- `ui/radio-group.tsx` + `ui/label.tsx` — shadcn primitives via `@radix-ui/react-radio-group` + `@radix-ui/react-label`

### Task 2: UploadForm + upload page (commit 82d8f85)
- `UploadForm.tsx` — drag-and-drop zone (200px min-height), B4 Option A flow, swap button, disabled submit guard
- `upload/page.tsx` — NavBar + UploadForm + footer; heading "Translate a Document"

### Task 3: Tests + TrackedChangesModal extraction (commit 521c39b)
- `TrackedChangesModal.tsx` — extracted from UploadForm for testability; strip/preserve/cancel RadioGroup; Apply Selection + Cancel Upload buttons; `onApply`/`onCancel` callbacks
- `UploadForm.test.tsx` — 20 tests: rendering, file validation (unsupported type, too large), detectTrackedChanges call path, modal D-13 spec (title, buttons, cancel resets file, apply→strip default), submit disabled state, LanguageSelect integration

## Key Design Decisions

### B4 Option A confirmed
`detectTrackedChanges(file)` is called on file **selection**, not on submit. `trackedAction` defaults to `null` — the guard `if (hasTrackedChanges && trackedAction === null)` is live. Modal appears before any `fetch("/api/upload")` call.

### Modal as separate component
`TrackedChangesModal` was extracted during Task 3 to enable direct unit testing without needing to navigate Radix Select in jsdom (which can't be driven by keyboard in test environments). The modal props (`onApply`, `onCancel`, `onOpenChange`) cleanly separate the UI contract from UploadForm state management.

### Vitest mock pattern
`vi.hoisted()` required for variables referenced inside `vi.mock` factory functions. Module-scope `const mockFoo = vi.fn()` variables are hoisted by Vitest but the closure capture only works reliably with `vi.hoisted`. Used for `mockPush`, `mockToast`, `mockDetect`.

### File input testing
`userEvent.upload` from `@testing-library/user-event` does not reliably trigger `onChange` on hidden `<input type="file">` elements in jsdom. Used `fireEvent.change` + `Object.defineProperty(input, 'files', ...)` instead — standard pattern for hidden file inputs in jsdom.

## Deviations from Plan

### Auto-fix: TrackedChangesModal extracted into own file
- **Found during:** Task 3
- **Issue:** Tests that needed to verify D-13 modal spec (title, buttons, radio options, cancel behavior) could not be written against `UploadForm` in isolation because the modal only appears when `hasTrackedChanges=true` AND `trackedAction=null` AND a submit occurs — requiring a real `targetLang` value, which can't be set via Radix Select in jsdom.
- **Fix:** Extracted `TrackedChangesModal` as standalone component with explicit `onApply`/`onCancel` callbacks. `UploadForm` delegates to it. Both are tested independently.
- **Files modified:** `frontend/src/components/UploadForm.tsx`, `frontend/src/components/TrackedChangesModal.tsx` (new)
- **Commits:** d7b2145, 82d8f85, 521c39b

### Auto-add: `@radix-ui/react-radio-group` + `@radix-ui/react-label` (Rule 2)
- **Found during:** Task 1
- **Issue:** Plan specified RadioGroup and Label from shadcn but these Radix primitives were missing from `package.json`.
- **Fix:** Installed packages, created `ui/radio-group.tsx` + `ui/label.tsx` following shadcn patterns.
- **Commit:** d7b2145

## Known Stubs

None. All components wire to real data sources:
- `LanguageSelect` fetches from `GET /api/languages` via TanStack Query
- `UploadForm` posts to `POST /api/upload` via the Next.js proxy route
- `NavBar` health dot queries `GET /api/health`
- `detectTrackedChanges` reads real file bytes via JSZip

## Threat Flags

No new security surface introduced beyond what is documented in the plan's `<threat_model>`:
- T-08-01: Extension + size check in UploadForm before any network call (implemented)
- T-08-02: Frontend only passes `"strip"` or `"preserve"` to `tracked_changes_action` (never `"cancel"`)
- T-08-03: 25MB limit enforced before `detectTrackedChanges` is called
- T-08-04: Backend error messages forwarded — accepted for internal PoC

## Self-Check: PASSED

All 10 created files verified present on disk.
All 3 task commits verified in git log: d7b2145, 82d8f85, 521c39b.
TypeScript: `npx tsc --noEmit` exits 0.
Tests: 22/22 pass (`npx vitest run`).
