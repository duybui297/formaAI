# Frontend Architecture

Aggregate view of the AI Translation PoC frontend. Per-module detail lives in each module's own `ARCHITECTURE.md` (linked below). For stack + run instructions see [`FRONTEND.md`](./FRONTEND.md).

## 1. Layers

```
app/          Next.js App Router — routing, layouts, pages (thin; compose features)
  (auth)/     unauthenticated: login, register, forgot/reset-password
  (app)/      authenticated shell: sidebar + pages, renders feature components
  api/upload  sole local route handler (rest proxied to backend)
middleware.ts  auth gate (cookie forma_access_token) — redirects pre-render

features/     domain modules — the real UI logic (see §3)
components/    ui/ shadcn primitives · layout/AppSidebar · providers/QueryProvider
hooks/         cross-feature React hooks (SSE, segment cache, keyboard, animation)
lib/           api client, auth client, shared types, pure utils
```

Rule of thumb: **pages compose, features implement, lib/hooks are shared plumbing.**

## 2. Feature modules

| Module | Purpose | Doc |
|--------|---------|-----|
| upload | Pick file + langs + glossary → create job; tracked-changes detect branch | [features/upload/ARCHITECTURE.md](./src/features/upload/ARCHITECTURE.md) |
| jobs | Job list + live progress (SSE), stage pipeline, error/failed-segment detail | [features/jobs/ARCHITECTURE.md](./src/features/jobs/ARCHITECTURE.md) |
| review | CAT-tool segment table — inline edit/regenerate, flag filter, keyboard nav | [features/review/ARCHITECTURE.md](./src/features/review/ARCHITECTURE.md) |
| glossary | Manage glossaries + terms, CSV import | [features/glossary/ARCHITECTURE.md](./src/features/glossary/ARCHITECTURE.md) |
| translator | Document-translation dashboard (upload + progress + recent jobs) | [features/translator/ARCHITECTURE.md](./src/features/translator/ARCHITECTURE.md) |

## 3. Cross-cutting layers

### lib/
- `types.ts` — single source of shared types: `JobStatus`/`JobStage`/`JobProgress`/`JobSummary`, `Segment`/`SegmentFlag`/`FlagType`/`FlagSeverity`, `Glossary`/`GlossaryTerm`, `Language`. Mirrors backend payload shapes.
- `api.ts` — thin typed client: `getLanguages`, `getJob`, `listJobs`, `createJob`. Calls go through `authFetch`. **Note:** only job/language calls live here; glossary calls are inline (`authFetch`) in glossary components, and `UploadForm` POSTs `/upload` via raw `fetch` rather than `createJob`.
- `auth.ts` — token store (`sessionStorage` + `forma_access_token` cookie), `authFetch` (adds `Authorization`, strips `Content-Type` for FormData, auto-throws on !ok unless `throwOnError:false`), auth API (`login/register/logout/me/refresh/forgot/reset`), `refreshAccessToken` (CSRF cookie → `X-CSRF-Token`), `bootstrapSession`.
- `detectTrackedChanges.ts` — client-side detect of Word tracked-changes (used by upload to warn before submit).
- `utils.ts`, `formatBreadcrumb.ts` — pure helpers.

### hooks/
- `useJobProgress(jobId)` — opens SSE (`fetchEventSource` → `/api/jobs/{id}/stream`), pushes events into `["job", jobId]` cache; `useQuery` fallback + ~2s poll; stops on terminal status.
- `useSegments(jobId)` / `useSegmentPatch` / `useSegmentRegenerate` — query key `["segments", jobId]`; optimistic mutation pattern `onMutate → cancelQueries → setQueryData → onError rollback`.
- `useReviewKeyboard` — hotkey nav for the review table (react-hotkeys-hook).
- `useCounterAnimation`, `use-toast` — UI helpers.

### components/
- `ui/` — shadcn/ui (new-york) primitives over Radix: button, dialog, table, textarea, select, toast, etc.
- `layout/AppSidebar.tsx` — nav for the `(app)` shell.
- `providers/QueryProvider` — single `QueryClient` (`retry:1`, `staleTime:0`).

## 4. Global data flow

```
Browser ──► middleware.ts (cookie check) ──► (auth)/* or (app)/* page
(app) page ─renders─► feature component
feature ──► lib/api or hooks ──► authFetch('/api/...') ─Bearer token─►
            next.config.mjs rewrite /api/* ──► FastAPI backend (BACKEND_URL)
backend job progress ──► SSE /jobs/{id}/stream ──► useJobProgress ──► ["job",id] cache ──► UI
```

End-to-end job lifecycle:
1. **upload** — select file/langs/glossary, optional tracked-changes warning → `POST /upload` → `{ job_id }`.
2. **jobs/translator** — `useJobProgress` streams stage/segment progress until `done` or `needs_review`/`failed`.
3. **review** — `useSegments` loads segments → inline edit (`useSegmentPatch`) / `useSegmentRegenerate`, filter by flag.
4. **export** — backend `POST /jobs/{id}/export`; download via `/api/jobs/{id}/download`.

## 5. State management

- **Server state**: TanStack Query v5 only. Keys: `["job", jobId]`, `["segments", jobId]`, plus glossary/list queries. SSE writes directly into the job cache; segment edits use optimistic updates with rollback.
- **Auth/session state**: not in Query — `sessionStorage` (token + user) and the `forma_access_token` cookie (read by `middleware.ts`, 8h). `bootstrapSession()` rehydrates user from `/auth/me`.
- **Local UI state**: `useState`/`useRef` inside components (form fields, filters, dialogs).

## 6. Auth & routing

- `middleware.ts` runs before render: no token + non-auth route → `/login?redirect=<path>`; token + auth route → `/dashboard`. Skips `_next`, static, `/api/*`.
- Two route groups: `(auth)` (own minimal layout) and `(app)` (sidebar shell). `app/layout.tsx` loads fonts + `QueryProvider`.

## 7. Known inconsistencies (from module docs)

- `UploadForm` bypasses `lib/api.ts createJob` (raw `fetch` to `/upload`); some `UploadForm.test.tsx` text assertions are stale.
- Glossary module makes API calls inline via `authFetch` — no glossary functions in `lib/api.ts`, no TanStack Query (parents own fetch/invalidation).
- `review/SegmentRow` duplicates badge styling inline (`InlineFlagBadge`); standalone `FlagBadge.tsx` is exercised only by tests.
- `translator/TranslatorWorkspace` is a document dashboard (not a 2-panel text translator); its terminal "build log" + segment counter are cosmetic, and several `features/jobs/*` imports are currently unused.
- `@monaco-editor/react` remains in deps but is not used by the review view (legacy; see project CLAUDE.md).
