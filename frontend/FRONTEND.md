# Frontend — AI Translation PoC

Web UI for AI document translation. Upload DOCX/PDF/PPTX → translate (qwen-mt-turbo) → review segments → export.

## Tech Stack

| Layer | Tech | Version | Notes |
|-------|------|---------|-------|
| Framework | Next.js | 16.x (App Router) | Turbopack default (`--turbopack` in dev) |
| Runtime | React | 19 | RSC enabled |
| Language | TypeScript | 5.x | strict, `@/*` → `src/*` |
| Styling | Tailwind CSS | 3.4 | + `tailwindcss-animate`, `tailwind-merge`, `clsx` |
| UI kit | shadcn/ui (new-york) | — | Radix primitives + `class-variance-authority` |
| Icons | lucide-react | 0.400 | |
| Server state | TanStack Query | 5 | job polling + optimistic segment mutations |
| Live progress | `@microsoft/fetch-event-source` | 2 | SSE w/ auth headers (native EventSource lacks headers) |
| Virtualized table | react-virtuoso | 4 | review segment table (variable-height rows) |
| Editor | @monaco-editor/react | 4.6 | in deps, NOT used for review (legacy; see CLAUDE.md) |
| Hotkeys | react-hotkeys-hook | 5 | review keyboard nav |
| Zip | jszip | 3 | client-side export bundling |
| Tests | Vitest + Testing Library | 1.6 | jsdom env |
| E2E | Playwright | 1.59 | `e2e/` |
| Lint | ESLint 9 + eslint-config-next | — | |

Fonts via `next/font/google`: Inter (default body), Roboto, Montserrat, JetBrains Mono (source cells — CSS var `--font-pt-mono` kept for back-compat).

## Architecture

Full architecture (layers, per-module breakdown, data flow, state management) → [`ARCHITECTURE.md`](./ARCHITECTURE.md).

Per-module docs:
- [features/upload](./src/features/upload/ARCHITECTURE.md) — create job (file + langs + glossary), tracked-changes detect
- [features/jobs](./src/features/jobs/ARCHITECTURE.md) — job list + live SSE progress, stage pipeline, errors
- [features/review](./src/features/review/ARCHITECTURE.md) — CAT segment table, inline edit/regenerate, flag filter
- [features/glossary](./src/features/glossary/ARCHITECTURE.md) — glossaries + terms, CSV import
- [features/translator](./src/features/translator/ARCHITECTURE.md) — document-translation dashboard

## Structure

```
src/
  app/                      # Next.js App Router
    (auth)/                 # login, register, forgot/reset-password — own layout
    (app)/                  # authed app — own layout w/ AppSidebar
      dashboard/ upload/ translator/ jobs/ jobs/[id]/ jobs/[id]/review/
      history/ glossaries/ glossaries/[id]/ settings/ pricing/
    api/upload/route.ts     # only Next API route (rest proxied to backend)
    layout.tsx page.tsx
  features/                 # domain feature components
    upload/    UploadForm, GlossarySelect, TrackedChangesModal
    jobs/      JobsTable, ProgressBar, StatusBadge, StageIndicator, ErrorDetails
    review/    SegmentTable, SegmentRow, FlagBadge, ReviewFilterBar, KeyboardHelpPanel
    glossary/  GlossaryList, TermsTable, GlossaryCreateDialog, CSVUploadButton
    translator/ TranslatorWorkspace (2-panel)
  components/
    ui/                     # shadcn primitives (button, dialog, table, toast, ...)
    layout/AppSidebar.tsx
    providers/query-provider.tsx
  lib/      api.ts auth.ts types.ts utils.ts detectTrackedChanges.ts formatBreadcrumb.ts
  hooks/    useJobProgress (SSE) useSegments useReviewKeyboard useCounterAnimation use-toast
middleware.ts               # auth guard via cookie
```

## Run

Prereqs: Node 20, backend reachable.

```bash
# install
npm install

# dev (Turbopack, :3000) — set BACKEND_URL if backend not at http://api:8000
BACKEND_URL=http://localhost:8000 npm run dev

# build / prod
npm run build && npm start

# checks
npm run lint
npm run type-check        # tsc --noEmit
npm test                  # vitest run
npm run test:watch
```

Env: `BACKEND_URL` (proxy target, default `http://api:8000`). `NEXT_PUBLIC_API_URL` referenced as override in api.ts comment.

**Docker** — `Dockerfile.frontend` (dev, source bind-mounted), `Dockerfile.frontend.prod`. Orchestrated via root `docker-compose.yml` / `docker-compose.prod.yml` alongside backend + `api` service. Root `Makefile` likely wraps compose.

```bash
# from repo root
docker compose up        # frontend + backend + deps
```
