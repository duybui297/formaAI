# Module: translator

## Purpose
NOTE: This is NOT a 2-panel live text-translation workspace. The actual module is a document-translation **dashboard** ("Upload & Translate" screen). It composes three stacked regions: (1) an upload form for submitting a document + language pair, (2) an active-job progress card with a live simulated terminal/progress bar, and (3) a "Recent Translations" table listing prior jobs with Review/Download actions. There is no side-by-side input/output text panel; live segment-by-segment translation review lives elsewhere (`/jobs/{id}/review`).

## Components
| File | Type | Responsibility |
|------|------|----------------|
| `app/(app)/translator/page.tsx` | Next.js route (server component wrapper) | Thin page; renders `<TranslatorWorkspace />`, no props/logic. |
| `features/translator/TranslatorWorkspace.tsx` | Client component (`"use client"`) | Top-level orchestrator. Holds `selectedJobId` state, queries job list, renders UploadForm + JobProgressCard + recent-jobs table. |
| `StatusDot` (in TranslatorWorkspace.tsx) | Local presentational fn | Colored status pill (done/needs_review/failed/running/queued). |
| `JobProgressCard` (in TranslatorWorkspace.tsx) | Local client component | Polls one job via `useJobProgress`, shows progress %, animated segment counter, simulated build log, error details, and Review/Download CTAs on completion. |

## Data flow
- User submits document + source/target lang in `UploadForm` (separate module `features/upload/UploadForm`). On success its `onJobCreated(id)` callback sets `selectedJobId`.
- Setting `selectedJobId` mounts `JobProgressCard` (keyed by id), which subscribes to `useJobProgress(jobId)` for live status/progress.
- `progressPct` is computed from `segments_done / segments_total` (or 100 when `status === "done"`). The terminal "build log" lines and segment counter (`useCounterAnimation`) are **cosmetic/simulated UI** — the log text is hardcoded, gated only on `progressPct` thresholds, not real backend stages.
- On terminal state (`done`/`needs_review`): card shows "Review Translation" link → `/jobs/{id}/review`, and "Download" → `window.location.href = /api/jobs/{id}/download`.
- Separately, the workspace lists recent jobs via TanStack Query (`listJobs`), `refetchInterval: 5000ms` (5s poll). Clicking a row sets `selectedJobId` (re-focuses progress card). Row hover reveals Review (`/jobs/{id}/review`) + Download (`/api/jobs/{id}/download`) actions for completed jobs. Table is sliced to first 10.
- Backend is REAL, not stubbed: `listJobs()` → `apiFetch("/jobs")` returns `data.jobs`; job progress via `useJobProgress`; download/review via real route paths. No mock data.

## State & data
- Local `useState`: `selectedJobId: string | null` (TranslatorWorkspace); none additional at top level.
- TanStack Query: `useQuery({ queryKey: ["jobs"], queryFn: listJobs, refetchInterval: 5000 })` for the recent-jobs table.
- `JobProgressCard` consumes `useJobProgress(jobId)` (custom hook) for per-job live status; `useCounterAnimation` for the animated segment count.
- API calls: `listJobs` (GET `/jobs`); job-progress fetch inside `useJobProgress`; download via direct nav to `/api/jobs/{id}/download`.

## Dependencies
- shadcn/ui: `Skeleton` (`@/components/ui/skeleton`).
- Sibling feature modules: `features/upload/UploadForm`; `features/jobs/{ProgressBar, StageIndicator, ErrorDetails, JobMetaRow}` (imported; only `ErrorDetails` is actually used in current render — ProgressBar/StageIndicator/JobMetaRow imported but unused here).
- Hooks: `@/hooks/useJobProgress`, `@/hooks/useCounterAnimation`.
- Lib: `@/lib/api` (`listJobs`), `@/lib/types` (`JobStatus`, `JobSummary`), `@/lib/utils` (`cn`).
- TanStack Query (`@tanstack/react-query`), Next.js `Link`.
- Icons (lucide-react): `FileText, Download, Eye, Loader2, CheckCircle2, AlertCircle, X`.

## Tests
No tests in module.
