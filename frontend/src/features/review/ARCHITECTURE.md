# Module: review

## Purpose
CAT-tool style segment review: per-row source/translation inline edit, flag triage, and keyboard navigation before document export.

## Components
| File | Type | Responsibility |
|------|------|----------------|
| SegmentTable.tsx | Component (forwardRef) | Virtualized list (`Virtuoso`) of segments; exposes `scrollToIndex` via `useImperativeHandle`; tracks `focusedIndex`, scrolls focused row into view; wires per-row `textareaRef` into a shared `editingRef` Map. |
| SegmentRow.tsx | Component | Single row: source cell (double-click / `shift+e` to edit), editable target `Textarea` (debounced PATCH), save-state indicator, regenerate button, discard-edit, inline flag badges, confidence chip, OCR page-image preview with bbox overlay. Also exports `formatStageCopy`. |
| FlagBadge.tsx | Component | Standalone shadcn `Badge` for a `FlagType`; maps type→label+color; overflow + `details.auto_adjusted===true` renders informational `AUTO-FIT` instead of warning. |
| ReviewFilterBar.tsx | Component | Sticky filter chip bar; `All (n)` plus one chip per `FlagType` with live counts computed from `segments`; emits `ReviewFilterType` (`FlagType \| "all"`); Shortcuts toggle button. |
| ReviewPageHeader.tsx | Component | Sticky header: back link, filename, lang pair, glossary tag; Export button (`POST /jobs/{id}/export`) triggering browser blob download with original extension; gated on status `done`/`needs_review`. |
| KeyboardHelpPanel.tsx | Component | Fixed overlay listing keyboard shortcuts (`j k n e E i r Esc ? / Ctrl+Shift+P`); shown when `open`. |

## Data flow
- Load segments via `useSegments(jobId)` → `GET /jobs/{id}/segments` → `Segment[]`.
- Render through `SegmentTable` → `react-virtuoso` virtualized list → one `SegmentRow` per segment (keyed by `segment.id`).
- Inline target edit in `SegmentRow`: local state + 500ms debounce → `useSegmentPatch` optimistic PATCH; save indicator cycles `saving → saved → idle`; `Discard edit` PATCHes `edited_text: null`.
- Source edit (double-click or `shift+e`): debounced PATCH with `edited_source_text`; `Discard source edit` clears it.
- Regenerate: `useSegmentRegenerate` → `POST .../regenerate`, replaces `translated_text`.
- Flag filtering: `ReviewFilterBar` counts flags per type; active filter narrows visible segments (filter applied by parent page).
- Keyboard nav via `useReviewKeyboard`: `j`/`k` move focus, `n` jumps to next flagged index (cycles), `e` edits target, `shift+e` edits source, `i` toggles image, `r` regenerates, `?`/`ctrl+shift+p` toggles help, `escape` blurs textarea.

## State & data
- TanStack Query key: `["segments", jobId]` (single source for list + all mutations).
- `useSegmentPatch` optimistic pattern: `onMutate` → `cancelQueries` → snapshot `previousSegments` → `setQueryData` (patch matching segment's `edited_text`/`edited_source_text`) → `onError` rollback to snapshot + destructive toast → `onSettled` `invalidateQueries`.
- `useSegmentRegenerate`: `onSuccess` `setQueryData` to swap `translated_text` → `onError` toast → `onSettled` `invalidateQueries`.
- Display precedence: `edited_text` (if non-null) > `translated_text` > `""`; source: `edited_source_text` > `source_text`.
- Flag counts: `ReviewFilterBar` computes client-side per `FlagType` from `segments`; server also returns `flag_counts` in `SegmentsResponse` (IN-01).
- Filter state: `ReviewFilterType` lifted to parent; `focusedIndex` lifted, owned by parent, passed to table + keyboard hook.
- Per-row local: `localValue`/`localSourceValue`, `saveState`, `sourceEditing`, `imageExpanded` (auto-expand when `confidence < 0.7`), `imageError`; `isMountedRef` guards stale mutation callbacks; debounce timers cleared on unmount.

## Dependencies
- `react-virtuoso` (`Virtuoso`, `VirtuosoHandle`) — row virtualization.
- `react-hotkeys-hook` (`useHotkeys`) — in `useReviewKeyboard` and per-row `i`/`shift+e`.
- shadcn UI: `Table`-pattern flex rows, `Textarea`, `Badge`, `Button`; `lucide-react` icons.
- `@tanstack/react-query` — `useQuery`/`useMutation`/`useQueryClient`.
- `@/lib/types` — `Segment`, `SegmentFlag`, `FlagType`, `SegmentsResponse`, `JobSummary`.
- `@/lib/auth` (`authFetch`), `@/lib/utils` (`cn`), `@/lib/formatBreadcrumb`, `@/hooks/use-toast`.
- Hooks: `@/hooks/useSegments` (`useSegments`, `useSegmentPatch`, `useSegmentRegenerate`), `@/hooks/useReviewKeyboard`.

## Tests
- `SegmentTable.test.tsx` — all `it.todo` placeholders: render without DOM explosion (REV-01), focused-row ring class, `j`/`k`/`n` navigation, `e` focuses target textarea. Not yet implemented.
- `FlagBadge.test.tsx` — `it.todo` for overflow/glossary/placeholder/refusal color + label; active tests for `smartart` (orange/`SMART`), `multi_column_degraded` (slate/`MULTI-COL`), overflow warning amber when `auto_adjusted` absent, and AUTO-FIT info badge when `auto_adjusted=true`.
- `phase4-flagbadge.test.tsx` — `figure_passthrough` (`FIGURE`, slate/info) and `ocr_page_error` (`OCR ERR`, amber/warn) label + styling.

## Notes
- `SegmentRow` deliberately uses an inline `InlineFlagBadge` (with its own `FLAG_BADGE_STYLES`/`FLAG_LABELS`/`LEFT_BORDER` maps) rather than importing `FlagBadge.tsx`, while keeping the same AUTO-FIT contract — duplicated styling to be reconciled later.
