# Module: jobs

## Purpose
Show translation job list + live progress of a running job. The list renders all jobs with status/format/age; the detail view drives a stage pipeline, progress bar, and (on failure) error details from live `JobProgress` updates.

## Components
| File | Type | Responsibility |
|------|------|----------------|
| `JobsTable.tsx` | Component | Renders `JobSummary[]` as a clickable shadcn Table (filename, languages, format badge, status, created age, View/Download actions). Row click navigates to `/jobs/{id}`; Download links to `/api/jobs/{id}/download` when status is `done`. |
| `ProgressBar.tsx` | Component | Thin wrapper over shadcn `Progress` (0–100 `value`), indigo fill, ARIA progressbar attributes. |
| `StatusBadge.tsx` | Component | Maps `JobStatus` → color styles + human label (`queued`, `running`, `needs review`, `failed`, `done`). |
| `StageIndicator.tsx` | Component | Renders the stage pipeline Parse → Translate → Reassemble → Done from `JobStage`; marks past (emerald check), active (indigo dot / red X on `failed`), and future (slate) steps. |
| `ErrorDetails.tsx` | Component | Failed-job alert: shows `error.message` (fallback `lastMessage`) and a collapsible list of `error.failing_segments` (id, batch_id, source_text). |
| `JobMetaRow.tsx` | Component | Compact meta line from `JobProgress`: source→target lang (uses `detected_lang` when `source_lang === "auto"`), format badge, created age. |

## Data flow
- `listJobs` result → `JobsTable` renders the `JobSummary[]` list.
- Per-job live updates via `useJobProgress(jobId)`: opens SSE through `fetchEventSource` on `/api/jobs/{id}/stream`, and on each message `setQueryData(["job", jobId], data)`.
- `useQuery(["job", jobId])` provides the read interface + polling fallback; queryFn fetches `GET /jobs/{id}`.
- Terminal states (`done`, `failed`, `needs_review`) stop refetching (and the stream closes on `onclose`/`onerror`).
- Stage pipeline (`StageIndicator`) and progress bar are driven by `JobProgress` fields: `stage`, `segments_done`/`segments_total`, and `stage_progress`.

## State & data
- TanStack Query key: `["job", jobId]`. Single cache entry shared by SSE writer and `useQuery` reader.
- SSE merge: `onmessage` parses the event JSON into `JobProgress` and overwrites the cache via `setQueryData`. `GET /jobs/{id}` fields not present in the SSE payload (e.g. `glossary_id`, `original_filename`, `error`) are merged into the same cache entry through the query path.
- Refetch/polling: `refetchInterval` returns `false` when status is terminal or while SSE is open (`sseOpen` ref); otherwise polls every `2000ms` (D-09 fallback after SSE `onerror`/`onclose`). `staleTime: 0`.
- Auth: SSE sends `Authorization: Bearer <token>` from `getToken()`.
- `low_confidence_pages`: present on both `JobProgress` (D-04-14, needs_review banner) and `JobSummary` (from job metadata); not consumed inside this module's components.

## Dependencies
- `@microsoft/fetch-event-source` — SSE client with custom auth header.
- `@tanstack/react-query` — `useQuery` / `useQueryClient` cache + polling.
- shadcn ui — Table, Badge, Button, Progress, Alert, Collapsible.
- `lib/types` — `JobStatus`, `JobStage`, `JobProgress`, `JobSummary`.
- `next/navigation` + `next/link` (JobsTable), `lucide-react` icons (StageIndicator, ErrorDetails), `lib/auth` (`getToken`).

## Tests
No tests in module.
