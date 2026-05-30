# Module: upload

## Purpose
Lets user pick one office document (DOCX/PPTX/PDF), choose a language pair + optional glossary, and create a translation job. Handles DOCX tracked-changes decision and scanned-PDF detection before submit.

## Components
| File | Type | Responsibility |
|------|------|----------------|
| `UploadForm.tsx` | Client component (`UploadForm`) | Drag-drop / browse file input, client-side ext + size validation, language + glossary controls, scanned-PDF detection banner, orchestrates tracked-changes flow, builds `FormData` and POSTs to `/api/upload`, redirects to `/jobs/{job_id}` (or calls `onJobCreated`). |
| `GlossarySelect.tsx` | Client component (`GlossarySelect`) | shadcn Select listing glossaries for the chosen source/target pair; fetches via TanStack Query; reports selected `glossary_id` (or `""` for None) through `onChange`. |
| `TrackedChangesModal.tsx` | Client component (`TrackedChangesModal`) | Dialog with 3 radio options (strip / preserve / cancel) shown when a DOCX has tracked changes; emits `onApply("strip"|"preserve")` or `onCancel`. |
| `../../lib/detectTrackedChanges.ts` | Util (`detectTrackedChanges`) | Reads DOCX bytes client-side with JSZip, inspects `word/document.xml` for `<w:ins>` / `<w:del>`; returns `false` for non-DOCX or malformed zip. |

## Data flow
- User drops or browses one file → `handleFile(f)`.
- Validation: extension must be in `{.docx, .pptx, .pdf}` (`ALLOWED_EXTS`), size ≤ 25 MB (`MAX_SIZE_BYTES`). Failures set inline `error` + destructive toast and abort. Multi-file drop is rejected by `onDrop` with a toast.
- On valid file: all tracked-changes + scanned-PDF state reset, `detecting=true`, then `detectTrackedChanges(f)` runs **only for `.docx`** (PPTX/PDF skip it, get `false`). Result stored in `hasTrackedChanges`. `detecting=false` when done.
- User picks source lang (defaults `"auto"`), target lang (required), optional glossary.
- Submit (`handleSubmit`): if `hasTrackedChanges && trackedAction === null` → open `TrackedChangesModal` and return (no POST yet). Otherwise call `submitWithAction(trackedAction)`.
- Modal branch: `onApply(action)` sets `trackedAction` and calls `submitWithAction(action)`; cancel / Escape / overlay-dismiss clears file + tracked state (no submit).
- `submitWithAction`: builds `FormData` (`file`, `source_lang`, `target_lang`, plus `tracked_changes_action` if non-null, `glossary_id` if set, `is_scanned_override` if a scanned value is effective) → `POST /api/upload` → on ok, captures `data.is_scanned`, then `onJobCreated(data.job_id)` if provided else `router.push('/jobs/{job_id}')`. Non-ok shows `data.detail`/`data.error`; network error shows generic toast.

## State & data
- Local `useState`: `file`, `dragState` (`idle`/`valid`/`multi`), `sourceLang` (default `"auto"`), `targetLang`, `glossaryId`, `submitting`, `error`, `hasTrackedChanges`, `showTrackedModal`, `trackedAction` (`strip`/`preserve`/`null`), `detecting`, `isScannedDetected`, `isScannedOverride`. `canSubmit = !!file && !!targetLang && !submitting && !detecting`.
- File input value is reset to `""` after each `onChange` so re-picking the same filename re-fires detection.
- API calls:
  - `UploadForm` POSTs `FormData` directly to `/api/upload` via raw `fetch` (does **not** use `lib/api.ts` `createJob`); response shape `{ job_id, is_scanned? }`.
  - `GlossarySelect` uses TanStack Query `useQuery` (key `["glossaries", sourceLang, targetLang]`) calling `authFetch` on `/glossaries?source_lang=&target_lang=`, unwrapping `{ glossaries: [...] }`. Enabled only when both langs set and source ≠ `"auto"`.
  - Languages are loaded by the embedded `LanguageSelect` component, not by this module directly.
- Validation rules: ext allowlist `.docx/.pptx/.pdf`; 25 MB max; single file only. Scanned-PDF: `effectiveScanned = override ?? detected`; `is_scanned_override` sent only when a value exists; user can toggle override / reset-to-auto via the banner (PDF only, after `isScannedDetected` known).

## Dependencies
- shadcn/ui: `Button`, `Badge`, `Select*` (Trigger/Content/Item/Value), `Dialog*` (Content/Header/Title/Description/Footer), `RadioGroup`/`RadioGroupItem`, `Label`.
- Internal: `@/components/LanguageSelect`, `@/hooks/use-toast`, `@/lib/utils` (`cn`), `@/lib/auth` (`authFetch`), `@/lib/types` (`Glossary`), `@/lib/detectTrackedChanges`.
- External: `next/navigation` (`useRouter`), `@tanstack/react-query` (`useQuery`), `lucide-react` icons, `jszip` (in the util).
- Note: `lib/api.ts` (`createJob`, `getLanguages`) and most of `lib/types.ts` exist but are not directly imported here; only the `Glossary` type is used.

## Tests
- `GlossarySelect.test.tsx`: all `it.todo` placeholders (D-02-25) — hide when langs unset, "No glossary for this pair" on empty list, show matching-pair options, hide non-matching pairs, pass selected id to `onChange`. Not yet implemented.
- `UploadForm.test.tsx` rendering: drop-zone text, source/target labels, Translate button, submit disabled with no file, file-input `accept` attribute. (Some asserted UI strings predate current component copy.)
- File validation: destructive toast for unsupported type, toast for >25 MB, `detectTrackedChanges` called for DOCX, PDF accepted without detection/rejection, filename shown after select.
- Submit disabled state: stays disabled with file but no target lang; detection runs before any POST.
- TrackedChangesModal unit: renders title/desc/3 radios/buttons when open, nothing when closed, `onCancel` on Cancel Upload, `onApply("strip")` default, `onCancel` when cancel radio + Apply.
- Tracked-changes reliability (G1): detection re-fires on re-selecting same file, modal state resets after cancel+reselect, input value cleared to `""`, Submit disabled while detecting.
- Error display (G3): inline error / `role="alert"` handling on non-ok (415) responses and error clears on reselection.
- LanguageSelect-in-form: language selects render when languages API returns a list.
