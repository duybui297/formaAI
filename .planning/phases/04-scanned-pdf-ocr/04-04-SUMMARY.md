---
phase: 04-scanned-pdf-ocr
plan: "04"
subsystem: frontend
tags: [ocr, review-ui, confidence-chip, image-preview, source-edit, banner, download-menu, tdd]
dependency_graph:
  requires:
    - "04-01 (Segment OCR fields: confidence, region_bbox, region_label, edited_source_text)"
  provides:
    - FlagType union extended with figure_passthrough and ocr_page_error in types.ts and review-types.ts
    - Segment interface extended with 4 OCR fields in both type files
    - JobProgress extended with stage_progress and low_confidence_pages
    - JobSummary extended with low_confidence_pages
    - FlagBadge renders FIGURE (slate) and OCR ERR (amber) badges
    - useSegmentPatch handles editedSourceText with optimistic cache update
    - SegmentRow: ConfidenceChip, image preview expand/collapse, source cell double-click edit
    - Review page: low-confidence banner with clickable page-jump links, download dropdown
    - UploadForm: scanned PDF detection display and override toggle
    - ReviewFilterBar: figure_passthrough and ocr_page_error filter chips
    - KeyboardHelpPanel: i and E shortcut entries
    - useReviewKeyboard: onToggleImage and onEditSource optional callbacks
    - formatStageCopy helper for SSE stage progress display
  affects:
    - frontend/src/lib/types.ts (extended)
    - frontend/src/lib/review-types.ts (extended)
    - frontend/src/components/FlagBadge.tsx (extended)
    - frontend/src/hooks/useSegments.ts (extended)
    - frontend/src/components/SegmentRow.tsx (extended)
    - frontend/src/app/jobs/[id]/review/page.tsx (extended)
    - frontend/src/components/UploadForm.tsx (extended)
    - frontend/src/components/ReviewFilterBar.tsx (extended)
    - frontend/src/components/KeyboardHelpPanel.tsx (extended)
    - frontend/src/hooks/useReviewKeyboard.ts (extended)
tech_stack:
  added:
    - shadcn DropdownMenu component (dropdown-menu.tsx)
    - react-hotkeys-hook used in SegmentRow for row-level i/shift+e hotkeys
  patterns:
    - TDD RED/GREEN cycle for FlagBadge and type extensions
    - React state error handling for image load failures (T-04-18 XSS mitigation)
    - Debounced PATCH 500ms with optimistic cache update (D-02-18 carry-forward)
    - useHotkeys with enabled: isFocused guard for row-scoped keyboard shortcuts
key_files:
  created:
    - frontend/src/components/ui/dropdown-menu.tsx
    - frontend/src/__tests__/phase4-types.test.ts
    - frontend/src/__tests__/phase4-flagbadge.test.tsx
  modified:
    - frontend/src/lib/types.ts
    - frontend/src/lib/review-types.ts
    - frontend/src/components/FlagBadge.tsx
    - frontend/src/hooks/useSegments.ts
    - frontend/src/components/SegmentRow.tsx
    - frontend/src/app/jobs/[id]/review/page.tsx
    - frontend/src/components/UploadForm.tsx
    - frontend/src/components/ReviewFilterBar.tsx
    - frontend/src/components/KeyboardHelpPanel.tsx
    - frontend/src/hooks/useReviewKeyboard.ts
decisions:
  - "SegmentRow keyboard shortcuts (i/shift+e) implemented via useHotkeys with enabled:isFocused guard — avoids threading callbacks through SegmentTable; each row independently handles its own shortcuts when focused"
  - "formatStageCopy exported from SegmentRow.tsx (not a separate file) — single-consumer helper, co-located with the stage progress rendering context"
  - "ReviewFilterBar FLAG_LABELS changed from partial to exhaustive Record<FlagType,string> to satisfy TypeScript after FlagType union extension — added smartart, multi_column_degraded, figure_passthrough, ocr_page_error entries"
  - "Image error handled via React state (setImageError) + conditional render — satisfies T-04-18 XSS mitigation (no DOM manipulation)"
  - "Download triggers browser anchor click pattern (not window.location) — works with Content-Disposition: attachment responses"
metrics:
  duration_minutes: 25
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 10
  completed_date: "2026-04-28"
---

# Phase 4 Plan 04: Frontend OCR UI Extensions

One-liner: Phase 4 frontend surgical additions — OCR confidence chip, click-to-expand image preview, double-click source edit with debounced PATCH, low-confidence page banner, three-artifact download menu, scanned PDF detection toggle, and SSE stage progress copy.

## What Was Built

### Task 1: Type extensions, FlagBadge, useSegmentPatch (TDD RED → GREEN)

**Type system** (`types.ts`, `review-types.ts`):
- `FlagType` union extended with `"figure_passthrough"` (info/slate) and `"ocr_page_error"` (warn/amber) in both files
- `Segment` interface extended with 4 OCR fields: `confidence: number | null`, `region_bbox: [number,number,number,number] | null`, `region_label: string | null`, `edited_source_text: string | null`
- `JobProgress` extended with `stage_progress?: { stage, current, total }` and `low_confidence_pages?: number[]`
- `JobSummary` extended with `low_confidence_pages?: number[]`
- `JobStage` extended with `"ocr"` and `"compose"` values

**FlagBadge** (`FlagBadge.tsx`):
- `figure_passthrough`: label "FIGURE", `text-slate-600 bg-slate-50 border-slate-200` (info severity, D-04-24)
- `ocr_page_error`: label "OCR ERR", `text-amber-700 bg-amber-50 border-amber-200` (warn severity, D-04-31)

**useSegmentPatch** (`useSegments.ts`):
- Mutation parameter extended with `editedSourceText?: string | null`
- PATCH body conditionally includes `edited_source_text` when provided
- Optimistic update mirrors `edited_text` pattern: sets `seg.edited_source_text` in TanStack cache

TDD: RED tests written first (4 FlagBadge render tests + 10 type contract tests), confirmed failing, then GREEN after implementation.

### Task 2: SegmentRow extensions, review page, UploadForm, download menu

**SegmentRow** (`SegmentRow.tsx`):
- `ConfidenceChip` sub-component: `text-[10px]` chip with green (≥70%), amber (50–70%), red (<50%) coloring; `aria-label="OCR confidence: N%"`; always visible when `confidence !== null`
- Image preview expand/collapse: `useState(() => (segment.confidence ?? 1) < 0.7)` auto-expands low-confidence rows; `ChevronDown/ChevronUp` toggle button in seq-index column; image loads from `/api/jobs/{jobId}/pages/{pageNum}.png`; error handled via `imageError` React state + static fallback paragraph (T-04-18)
- Source cell double-click edit: `onDoubleClick → setSourceEditing(true)`; shadcn `Textarea` with 500ms debounced PATCH `{edited_source_text: value}`; "Discard source edit" button when `edited_source_text !== null`; Escape exits
- `i` hotkey: `useHotkeys("i", toggleImageExpanded, { enabled: isFocused })`
- `shift+e` hotkey: `useHotkeys("shift+e", setSourceEditing(true), { enabled: isFocused })`
- `FLAG_BADGE_STYLES` and `FLAG_LABELS` extended with `figure_passthrough` and `ocr_page_error`
- `LEFT_BORDER` extended: `figure_passthrough → border-l-slate-300`, `ocr_page_error → border-l-amber-400`
- `formatStageCopy` exported helper: maps `stage_progress.stage` to human-readable copy with `{current}/{total}` interpolation

**Review page** (`jobs/[id]/review/page.tsx`):
- Low-confidence banner: renders when `job.low_confidence_pages?.length > 0`; amber-50/amber-300 styling with `AlertTriangle` icon; page numbers are `<button>` elements that call `tableRef.current.scrollToIndex(idx)` to jump to first segment of that page
- Download DropdownMenu: three options (Bilingual PDF, Translated PDF, Translated DOCX); triggers `GET /api/jobs/{jobId}/download?artifact={type}` via anchor click; enabled only when `status === "done" | "needs_review"`

**UploadForm** (`UploadForm.tsx`):
- `isScannedDetected: boolean | null` and `isScannedOverride: boolean | null` state
- Detection display shown for `.pdf` files when `isScannedDetected !== null`; shows "Detected: scanned/native PDF — [Change]" or "Changed to: ... — [Reset to auto]"
- Override toggle cycles: `null → !isScannedDetected → null`
- `is_scanned_override` appended to FormData only when `effectiveScanned !== null`
- Upload response captures `data.is_scanned` to update `isScannedDetected`

**ReviewFilterBar** (`ReviewFilterBar.tsx`):
- `FLAG_LABELS` record made exhaustive: added `smartart`, `multi_column_degraded`, `figure_passthrough`, `ocr_page_error`
- `ALL_FLAGS` array extended with same four values for filter chip rendering

**KeyboardHelpPanel** (`KeyboardHelpPanel.tsx`):
- Added `{ key: "i", action: "Show/hide image preview" }` and `{ key: "E", action: "Edit source text" }`

**useReviewKeyboard** (`useReviewKeyboard.ts`):
- Added optional `onToggleImage?: (index: number) => void` and `onEditSource?: (index: number) => void` callbacks
- Added `useHotkeys("i", ...)` and `useHotkeys("shift+e", ...)` bindings

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added figure_passthrough and ocr_page_error to ReviewFilterBar**
- **Found during:** Task 2 — TypeScript error: `Record<FlagType, string>` in ReviewFilterBar was missing the new Phase 4 FlagType values
- **Issue:** ReviewFilterBar's `FLAG_LABELS: Record<FlagType, string>` became non-exhaustive when FlagType was extended, causing TS2739 compile error
- **Fix:** Added all missing FlagType entries (smartart, multi_column_degraded, figure_passthrough, ocr_page_error) to both `FLAG_LABELS` and `ALL_FLAGS` — these are also now filter-able flag types in the review UI
- **Files modified:** `frontend/src/components/ReviewFilterBar.tsx`
- **Commit:** 012fc68

**2. [Rule 1 - Bug] Removed stale @ts-expect-error directives in test files**
- **Found during:** Task 2 TypeScript check — TS2578 "Unused @ts-expect-error" after FlagType union was extended to include smartart, multi_column_degraded, and Phase 4 values
- **Fix:** Removed `@ts-expect-error` comments from `FlagBadge.test.tsx` (3 directives) and `phase4-flagbadge.test.tsx` (4 directives)
- **Files modified:** `frontend/src/__tests__/FlagBadge.test.tsx`, `frontend/src/__tests__/phase4-flagbadge.test.tsx`
- **Commit:** 012fc68

**3. [Rule 3 - Blocking] Installed shadcn DropdownMenu component**
- **Found during:** Task 2 — `dropdown-menu.tsx` not present in `frontend/src/components/ui/`; plan referenced it as "already in shadcn registry"
- **Fix:** `npx shadcn@latest add dropdown-menu --yes` installed the component
- **Files modified:** `frontend/src/components/ui/dropdown-menu.tsx` (created), `frontend/package.json`, `frontend/package-lock.json`
- **Commit:** 012fc68

### Pre-existing Out-of-Scope Issues

`frontend/src/__tests__/UploadForm.test.tsx` lines 482-485 have a pre-existing TypeScript strictness issue (`res` typed as `unknown` from `vi.fn()` mock). Not caused by Phase 4 changes; not fixed (out of scope per deviation rules). Logged here for visibility.

## Known Stubs

None. All Phase 4 frontend surfaces are wired to real data:
- Confidence chip reads `segment.confidence` from API response
- Image preview reads from `/api/jobs/{jobId}/pages/{pageNum}.png` (backend serves page PNGs)
- Source edit PATCHes `/api/segments/{id}` with `edited_source_text`
- Banner reads `job.low_confidence_pages` from job API response
- Download menu calls `/api/jobs/{jobId}/download?artifact=...`
- UploadForm sends `is_scanned_override` to `/api/upload`

## Threat Flags

No new network endpoints or auth paths introduced in the frontend. All fetch calls use existing job-scoped API routes. T-04-18 (XSS via image onError) was mitigated by using React state (`setImageError`) + static paragraph render rather than DOM manipulation.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `frontend/src/lib/types.ts` | FOUND |
| `frontend/src/lib/review-types.ts` | FOUND |
| `frontend/src/components/FlagBadge.tsx` | FOUND |
| `frontend/src/hooks/useSegments.ts` | FOUND |
| `frontend/src/components/SegmentRow.tsx` | FOUND |
| `frontend/src/app/jobs/[id]/review/page.tsx` | FOUND |
| `frontend/src/components/UploadForm.tsx` | FOUND |
| `frontend/src/components/ui/dropdown-menu.tsx` | FOUND |
| Commit 67c2d6b (Task 1) | FOUND |
| Commit 012fc68 (Task 2) | FOUND |
| `npm test -- --run` | 62 passed, 20 todo |
| `npx tsc --noEmit` (Phase 4 files) | No errors |
