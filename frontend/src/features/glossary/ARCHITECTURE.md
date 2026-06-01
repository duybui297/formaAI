# Module: glossary

## Purpose
Manage terminology glossaries and their terms used to constrain translation (per source→target language pair).

## Components
| File | Type | Responsibility |
|------|------|----------------|
| `GlossaryList.tsx` | Presentational component | Renders glossaries in a shadcn Table; each name links to `/glossaries/{id}`; per-row delete with `window.confirm`. Takes `glossaries` + `onDelete` props (no fetching). |
| `GlossaryCreateDialog.tsx` | Dialog/form component | Modal form (name + source/target `LanguageSelect`) that POSTs a new glossary; resets form and calls `onCreated` on success. |
| `TermsTable.tsx` | Stateful component | Lists/edits/deletes terms (inline edit via local `editState`) and embeds `TermAddRow` for inline add. Calls `onTermsChange` to trigger parent refetch after mutations. |
| `CSVUploadButton.tsx` | Action component | Hidden file input (`.csv`) + button; uploads CSV as `FormData` for bulk term import; reports imported count via `onImported`. |

## Data flow
- List glossaries (parent page fetches) → rendered by `GlossaryList`.
- Create: `GlossaryCreateDialog` POSTs `/glossaries` → `onCreated` → parent refetches list.
- View/edit terms: detail page (`/glossaries/{id}`) loads glossary with `terms` → `TermsTable`.
  - Add term: `TermAddRow` POSTs `/glossaries/{id}/terms`.
  - Edit term: PATCH `/glossaries/{id}/terms/{termId}`.
  - Delete term: DELETE `/glossaries/{id}/terms/{termId}`.
  - All term mutations call `onTermsChange` → parent refetch.
- CSV import: `CSVUploadButton` parses/sends raw CSV file as multipart `FormData` to `/glossaries/{id}/terms/import` (backend parses CSV + bulk-inserts); response `{ imported }` → `onImported(count)`.

### Backend endpoints
| Action | Method | Endpoint |
|--------|--------|----------|
| Create glossary | POST | `/glossaries` |
| Delete glossary | (via parent `onDelete`) | `/glossaries/{id}` |
| Add term | POST | `/glossaries/{id}/terms` |
| Edit term | PATCH | `/glossaries/{id}/terms/{termId}` |
| Delete term | DELETE | `/glossaries/{id}/terms/{termId}` |
| Bulk CSV import | POST | `/glossaries/{id}/terms/import` |

## State & data
- No TanStack Query inside this module. Components are stateless re: fetching; they receive data via props and signal changes via callbacks (`onDelete`, `onCreated`, `onTermsChange`, `onImported`). Fetching/caching/invalidation is owned by parent pages.
- Local UI state only: `useState` for form fields, edit state, submitting/saving flags; `useRef` for the hidden file input.
- API calls are **inline via `authFetch`** (`@/lib/auth`) inside each component — they are **not** defined in `lib/api.ts` (`api.ts` contains no glossary calls). Pattern: `throwOnError: false`, manual `res.ok` check, parse `data.detail`/`data.error` for toast messages.

## Dependencies
- shadcn/ui: `Table` family, `Button`, `Input`, `Dialog` family.
- App components: `LanguageSelect` (`@/components/LanguageSelect`).
- Hooks: `useToast` (`@/hooks/use-toast`).
- Lib: `authFetch` (`@/lib/auth`); types `Glossary`, `GlossaryTerm` (`@/lib/types`).
- Next.js: `Link`.
- Icons: `lucide-react` (`Trash2`, `Pencil`, `Check`, `X`, `Upload`).
- No external CSV-parsing library — CSV is parsed server-side; client sends the raw file as `FormData`.

## Tests
No tests in module.
