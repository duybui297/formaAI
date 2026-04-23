---
phase: 01-foundation-docx-pipeline
plan: 09
type: execute
wave: 4
depends_on: [01-07-frontend-shell-PLAN.md]
files_modified:
  - frontend/src/app/jobs/[id]/page.tsx
  - frontend/src/components/StageIndicator.tsx
  - frontend/src/components/ProgressBar.tsx
  - frontend/src/components/JobMetaRow.tsx
  - frontend/src/components/ErrorDetails.tsx
  - frontend/src/hooks/useCounterAnimation.ts
autonomous: true
requirements: [JOB-02, JOB-03, JOB-04, UPLD-05]

must_haves:
  truths:
    - "User redirected to /jobs/{id} after upload sees the job status in real-time"
    - "Stage indicator (Parse → Translate → Reassemble → Done) shows active stage"
    - "Progress bar fills as segments_done/segments_total advances"
    - "Segment counter animates smoothly between SSE events"
    - "Retry chip appears (slate-500, no red) when retry_count > 0"
    - "Detected language badge appears when source was auto-detect"
    - "Failed job shows error banner with collapsible failing segments (no traceback)"
    - "Done job shows Download Translation button (indigo)"
    - "needs_review job shows placeholder card with download still enabled"
    - "Queued job shows skeleton while waiting for worker"
  artifacts:
    - path: "frontend/src/app/jobs/[id]/page.tsx"
      provides: "Job status page root — composes all status sub-components"
      exports: [default]
    - path: "frontend/src/components/StageIndicator.tsx"
      provides: "Four-stage horizontal strip (Parse→Translate→Reassemble→Done)"
      exports: [StageIndicator]
    - path: "frontend/src/components/ProgressBar.tsx"
      provides: "shadcn Progress wrapper, indigo-500 fill, 8px height"
      exports: [ProgressBar]
    - path: "frontend/src/components/ErrorDetails.tsx"
      provides: "Destructive Alert + Collapsible with failing segments"
      exports: [ErrorDetails]
    - path: "frontend/src/hooks/useCounterAnimation.ts"
      provides: "Animated counter that interpolates toward target value"
      exports: [useCounterAnimation]
  key_links:
    - from: "frontend/src/app/jobs/[id]/page.tsx"
      to: "frontend/src/hooks/useJobProgress.ts"
      via: "useJobProgress(jobId)"
      pattern: "useJobProgress"
    - from: "frontend/src/app/jobs/[id]/page.tsx"
      to: "frontend/src/api/jobs.ts"
      via: "GET /api/jobs/{id}/download"
      pattern: "download"
    - from: "frontend/src/components/StageIndicator.tsx"
      to: "JobProgress.stage"
      via: "stage prop matching 'parse'|'translate'|'reassemble'|'done'|'failed'"
      pattern: "stage"
---

<objective>
Build the `/jobs/[id]` status page: a real-time job status view driven by the SSE+TanStack Query hybrid from Plan 07.

Purpose: Users need live feedback during translation — progress, current stage, retries (non-alarming), errors with context, and a download trigger on completion.
Output: job status page + StageIndicator + ProgressBar + ErrorDetails + animated counter hook.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md

<interfaces>
<!-- From frontend/src/lib/types.ts (Plan 07) -->
```typescript
export type JobStatus = 'queued' | 'running' | 'needs_review' | 'failed' | 'done'
export type JobStage = 'parse' | 'translate' | 'reassemble' | 'done' | 'failed'

export interface FailingSegment {
  id: string
  source_text: string
  batch_id: string
}

export interface JobError {
  code: string
  message: string
  failing_segments: FailingSegment[]
}

export interface JobProgress {
  status: JobStatus
  stage: JobStage
  segments_done: number
  segments_total: number
  current_batch: number
  retry_count: number
  last_message: string
  error?: JobError
  detected_lang?: string
  filename?: string
  source_lang?: string
  target_lang?: string
  format?: string
  created_at?: string
}
```

<!-- From frontend/src/hooks/useJobProgress.ts (Plan 07) -->
```typescript
export function useJobProgress(jobId: string): UseQueryResult<JobProgress>
// Returns TanStack Query result. Internally opens SSE and writes to query cache.
// refetchInterval=2000 polling fallback when SSE closed and not terminal.
```

<!-- From frontend/src/lib/api.ts (Plan 07) -->
```typescript
export async function getJob(jobId: string): Promise<JobProgress>
// GET /api/jobs/{id}
```

<!-- Download URL pattern -->
// GET /api/jobs/{id}/download → 200 with Content-Disposition: attachment
// Trigger via window.location.href = `/api/jobs/${jobId}/download`
</interfaces>

<!-- shadcn components used in this plan -->
<!-- Progress, Alert, Collapsible, Badge, Button, Skeleton -->
<!-- Add: npx shadcn@latest add progress alert collapsible badge button skeleton -->
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: useCounterAnimation hook + StageIndicator + ProgressBar components</name>
  <files>
    frontend/src/hooks/useCounterAnimation.ts,
    frontend/src/hooks/useCounterAnimation.test.ts,
    frontend/src/components/StageIndicator.tsx,
    frontend/src/components/ProgressBar.tsx
  </files>
  <behavior>
    - useCounterAnimation(target: number, duration?: number): number
      - returns animated display value that interpolates toward target
      - on terminal state snap, caller passes duration=0 to skip animation
      - uses requestAnimationFrame internally; cleans up on unmount
    - useCounterAnimation(100) with initial 0 → display starts at 0 and increments toward 100 over ~300ms
    - useCounterAnimation(100, 0) → immediately returns 100 (snap-to-final for terminal state)
    - StageIndicator: four stages ['parse','translate','reassemble','done']
      - active stage: indigo-600 label + filled circle (aria-current="step")
      - completed stage: emerald circle + checkmark icon (lucide CheckCircle2)
      - future stage: slate-300 circle
      - connects stages with a horizontal line (border-t border-slate-200 flex-1)
      - when stage='failed', mark the active stage as failed with red-600 X icon
    - ProgressBar: wraps shadcn Progress
      - className override: h-2 [&>div]:bg-indigo-500 (8px, indigo-500 fill)
      - value prop: number 0-100
      - aria-label="Translation progress"
  </behavior>
  <action>
    1. Install shadcn components if not already present: `cd frontend && npx shadcn@latest add progress` (from the frontend/ dir).

    2. Create `frontend/src/hooks/useCounterAnimation.test.ts`:
       - Test: initial render returns 0 when target is 100
       - Test: duration=0 returns target immediately
       - Test: cleanup — no state updates after unmount (use fake timers)
       - Use vitest (or jest if already configured in the project) with @testing-library/react renderHook.

    3. Implement `frontend/src/hooks/useCounterAnimation.ts`:
       ```typescript
       'use client'
       import { useEffect, useRef, useState } from 'react'

       export function useCounterAnimation(target: number, duration = 300): number {
         const [display, setDisplay] = useState(target) // snap on first render
         const rafRef = useRef<number | null>(null)
         const startRef = useRef<number | null>(null)
         const fromRef = useRef(target)

         useEffect(() => {
           if (duration === 0) {
             setDisplay(target)
             return
           }
           const from = fromRef.current
           if (from === target) return

           const step = (now: number) => {
             if (startRef.current === null) startRef.current = now
             const elapsed = now - startRef.current
             const progress = Math.min(elapsed / duration, 1)
             setDisplay(Math.round(from + (target - from) * progress))
             if (progress < 1) {
               rafRef.current = requestAnimationFrame(step)
             } else {
               fromRef.current = target
               startRef.current = null
             }
           }
           rafRef.current = requestAnimationFrame(step)
           return () => {
             if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
           }
         }, [target, duration])

         return display
       }
       ```

    4. Create `frontend/src/components/StageIndicator.tsx`:
       ```typescript
       'use client'
       import { CheckCircle2, XCircle } from 'lucide-react'
       import { cn } from '@/lib/utils'
       import type { JobStage } from '@/lib/types'

       const STAGES: { key: JobStage | 'done'; label: string }[] = [
         { key: 'parse', label: 'Parse' },
         { key: 'translate', label: 'Translate' },
         { key: 'reassemble', label: 'Reassemble' },
         { key: 'done', label: 'Done' },
       ]

       const STAGE_ORDER: Record<string, number> = {
         parse: 0, translate: 1, reassemble: 2, done: 3, failed: 3,
       }

       interface StageIndicatorProps {
         stage: JobStage
       }

       export function StageIndicator({ stage }: StageIndicatorProps) {
         const activeIdx = STAGE_ORDER[stage] ?? 0
         const isFailed = stage === 'failed'

         return (
           <div className="flex items-center gap-0 w-full" role="list" aria-label="Translation stages">
             {STAGES.map(({ key, label }, idx) => {
               const isPast = idx < activeIdx && !(isFailed && idx === activeIdx)
               const isActive = idx === activeIdx
               const isFuture = idx > activeIdx

               return (
                 <div key={key} className="flex items-center flex-1 last:flex-none">
                   <div
                     className="flex flex-col items-center gap-1"
                     role="listitem"
                     aria-current={isActive ? 'step' : undefined}
                   >
                     <div className={cn(
                       'w-6 h-6 rounded-full flex items-center justify-center',
                       isPast && 'bg-emerald-500',
                       isActive && !isFailed && 'bg-indigo-600',
                       isActive && isFailed && 'bg-red-600',
                       isFuture && 'bg-slate-300',
                     )}>
                       {isPast && <CheckCircle2 className="w-4 h-4 text-white" />}
                       {isActive && !isFailed && <div className="w-2 h-2 bg-white rounded-full" />}
                       {isActive && isFailed && <XCircle className="w-4 h-4 text-white" />}
                     </div>
                     <span className={cn(
                       'text-xs',
                       isPast && 'text-emerald-600',
                       isActive && !isFailed && 'text-indigo-600 font-semibold',
                       isActive && isFailed && 'text-red-600 font-semibold',
                       isFuture && 'text-slate-400',
                     )}>
                       {label}
                     </span>
                   </div>
                   {idx < STAGES.length - 1 && (
                     <div className={cn(
                       'flex-1 border-t mt-[-14px]',
                       idx < activeIdx ? 'border-emerald-400' : 'border-slate-200',
                     )} />
                   )}
                 </div>
               )
             })}
           </div>
         )
       }
       ```

    5. Create `frontend/src/components/ProgressBar.tsx`:
       ```typescript
       import { Progress } from '@/components/ui/progress'
       import { cn } from '@/lib/utils'

       interface ProgressBarProps {
         value: number  // 0-100
         className?: string
       }

       export function ProgressBar({ value, className }: ProgressBarProps) {
         return (
           <Progress
             value={value}
             className={cn('h-2 [&>div]:bg-indigo-500', className)}
             aria-label="Translation progress"
             aria-valuenow={value}
             aria-valuemin={0}
             aria-valuemax={100}
           />
         )
       }
       ```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>
    - useCounterAnimation returns display value, animates toward target, snaps on duration=0
    - StageIndicator renders 4 stages with correct color/icon per state
    - ProgressBar wraps shadcn Progress with indigo-500 fill at 8px height
    - TypeScript clean
  </done>
</task>

<task type="auto">
  <name>Task 2: ErrorDetails component + JobMetaRow + job status page</name>
  <files>
    frontend/src/components/ErrorDetails.tsx,
    frontend/src/components/JobMetaRow.tsx,
    frontend/src/app/jobs/[id]/page.tsx
  </files>
  <action>
    1. Install remaining shadcn components: `cd frontend && npx shadcn@latest add alert collapsible badge button skeleton`.

    2. Create `frontend/src/components/ErrorDetails.tsx` (per D-11 — no traceback in UI, collapsible failing segments):
       ```typescript
       'use client'
       import { useState } from 'react'
       import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
       import {
         Collapsible,
         CollapsibleContent,
         CollapsibleTrigger,
       } from '@/components/ui/collapsible'
       import { Button } from '@/components/ui/button'
       import { ChevronDown } from 'lucide-react'
       import type { JobError } from '@/lib/types'

       interface ErrorDetailsProps {
         error: JobError
         lastMessage: string
       }

       export function ErrorDetails({ error, lastMessage }: ErrorDetailsProps) {
         const [open, setOpen] = useState(false)

         return (
           <Alert variant="destructive" className="mt-4">
             <AlertTitle>Translation Failed</AlertTitle>
             <AlertDescription className="mt-2 space-y-2">
               <p>{error.message || lastMessage}. Check the details below or try again.</p>
               {error.failing_segments.length > 0 && (
                 <Collapsible open={open} onOpenChange={setOpen}>
                   <CollapsibleTrigger asChild>
                     <Button variant="ghost" size="sm" className="text-red-700 hover:text-red-800 px-0">
                       {open ? 'Hide details' : 'Show failing segments'}
                       <ChevronDown className={`ml-1 h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
                     </Button>
                   </CollapsibleTrigger>
                   <CollapsibleContent className="mt-2 space-y-2">
                     {error.failing_segments.map((seg) => (
                       <div key={seg.id} className="rounded bg-red-50 border border-red-200 p-3 text-sm text-red-900">
                         <p className="font-mono text-xs text-red-500 mb-1">segment {seg.id} · batch {seg.batch_id}</p>
                         <p className="line-clamp-3">{seg.source_text}</p>
                       </div>
                     ))}
                   </CollapsibleContent>
                 </Collapsible>
               )}
             </AlertDescription>
           </Alert>
         )
       }
       ```

    3. Create `frontend/src/components/JobMetaRow.tsx` (filename, lang pair, format, time):
       ```typescript
       import { Badge } from '@/components/ui/badge'
       import { formatDistanceToNow } from 'date-fns'  // use if available, else inline simple format
       import type { JobProgress } from '@/lib/types'

       interface JobMetaRowProps {
         job: JobProgress
       }

       function formatAge(isoString?: string): string {
         if (!isoString) return ''
         try {
           return formatDistanceToNow(new Date(isoString), { addSuffix: true })
         } catch {
           return ''
         }
       }

       export function JobMetaRow({ job }: JobMetaRowProps) {
         const sourceLang = job.source_lang === 'auto' ? (job.detected_lang ?? 'Auto') : (job.source_lang ?? '—')
         return (
           <div className="flex items-center gap-2 text-xs text-slate-500 flex-wrap">
             {job.source_lang && job.target_lang && (
               <span>{sourceLang} → {job.target_lang}</span>
             )}
             {job.format && (
               <Badge variant="outline" className="text-xs text-slate-700">{job.format.toUpperCase()}</Badge>
             )}
             {job.created_at && <span>·</span>}
             {job.created_at && <span>{formatAge(job.created_at)}</span>}
           </div>
         )
       }
       ```
       NOTE: if date-fns is not in package.json, skip the import and write the formatAge inline using `Date` arithmetic (return "{N} min ago" pattern). Do not add new deps without checking package.json first.

    4. Create `frontend/src/app/jobs/[id]/page.tsx`:
       ```typescript
       'use client'
       import { use } from 'react'
       import Link from 'next/link'
       import { ArrowLeft } from 'lucide-react'
       import { Button } from '@/components/ui/button'
       import { Badge } from '@/components/ui/badge'
       import { Skeleton } from '@/components/ui/skeleton'
       import { StageIndicator } from '@/components/StageIndicator'
       import { ProgressBar } from '@/components/ProgressBar'
       import { ErrorDetails } from '@/components/ErrorDetails'
       import { JobMetaRow } from '@/components/JobMetaRow'
       import { useJobProgress } from '@/hooks/useJobProgress'
       import { useCounterAnimation } from '@/hooks/useCounterAnimation'
       import type { JobStatus } from '@/lib/types'

       // Next.js 16 async params: unwrap with React.use()
       export default function JobStatusPage({ params }: { params: Promise<{ id: string }> }) {
         const { id: jobId } = use(params)
         const { data: job, isLoading } = useJobProgress(jobId)

         const TERMINAL: Set<JobStatus> = new Set(['done', 'failed', 'needs_review'])
         const isTerminal = job ? TERMINAL.has(job.status) : false

         const displayCount = useCounterAnimation(
           job?.segments_done ?? 0,
           isTerminal ? 0 : 300,
         )

         if (isLoading) {
           return (
             <div className="space-y-4">
               <Skeleton className="h-4 w-24" />
               <Skeleton className="h-6 w-64" />
               <Skeleton className="h-2 w-full" />
               <Skeleton className="h-4 w-48" />
             </div>
           )
         }

         if (!job) {
           return (
             <div className="text-slate-500 text-sm">
               Job not found.{' '}
               <Link href="/jobs" className="underline">Back to jobs</Link>
             </div>
           )
         }

         const progressPct = job.segments_total > 0
           ? Math.round((job.segments_done / job.segments_total) * 100)
           : (job.status === 'done' ? 100 : 0)

         const STATUS_COLORS: Record<JobStatus, string> = {
           queued: 'text-amber-500',
           running: 'text-indigo-600',
           needs_review: 'text-amber-600',
           failed: 'text-red-600',
           done: 'text-emerald-600',
         }

         return (
           <div className="space-y-6">
             {/* Back link */}
             <Link
               href="/jobs"
               className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
             >
               <ArrowLeft className="h-4 w-4" />
               All Jobs
             </Link>

             {/* Heading */}
             <div>
               <h1 className="text-xl font-semibold text-slate-900">{job.filename ?? jobId}</h1>
               <JobMetaRow job={job} />
             </div>

             {/* Stage indicator */}
             <StageIndicator stage={job.stage} />

             {/* Progress section */}
             <div className="space-y-2">
               {job.status === 'queued' ? (
                 <>
                   <Skeleton className="h-2 w-full" />
                   <p className="text-sm text-slate-500">Waiting for worker...</p>
                 </>
               ) : (
                 <>
                   <ProgressBar value={progressPct} />
                   {job.segments_total > 0 && (
                     <p className="text-sm text-slate-700">
                       {displayCount} / {job.segments_total} segments translated
                     </p>
                   )}
                   {/* Retry chip — D-12: slate-500, no red, no background */}
                   {job.retry_count > 0 && job.status === 'running' && (
                     <p className="text-xs text-slate-500 transition-opacity duration-150">
                       Retrying batch {job.current_batch} ({job.retry_count}/3)
                     </p>
                   )}
                   {/* Detected language badge — D-16 */}
                   {job.detected_lang && job.source_lang === 'auto' && (
                     <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200">
                       Detected: {job.detected_lang}
                     </Badge>
                   )}
                 </>
               )}
             </div>

             {/* Error section — D-11 */}
             {job.status === 'failed' && job.error && (
               <ErrorDetails error={job.error} lastMessage={job.last_message} />
             )}

             {/* Action section */}
             {job.status === 'done' && (
               <Button
                 className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
                 onClick={() => { window.location.href = `/api/jobs/${jobId}/download` }}
               >
                 Download Translation
               </Button>
             )}

             {job.status === 'needs_review' && (
               <div className="rounded-lg border border-slate-200 bg-white p-6 text-center space-y-3">
                 <h2 className="text-base font-semibold text-slate-800">Review Required</h2>
                 <p className="text-sm text-slate-500">
                   Segment-level review will be available in the next release. You can still download the current output.
                 </p>
                 <Button
                   variant="outline"
                   className="border-indigo-600 text-indigo-600 hover:bg-indigo-50"
                   onClick={() => { window.location.href = `/api/jobs/${jobId}/download` }}
                 >
                   Download Current Output
                 </Button>
               </div>
             )}
           </div>
         )
       }
       ```

    IMPORTANT: Next.js 16 `params` is a Promise — use `React.use(params)` to unwrap, NOT `params.id` directly (async params from day one per D-20). This is already shown in the code above.

    IMPORTANT: Retry chip uses `text-slate-500`, NO background fill, NO `text-red-*` (per D-12).
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>
    - ErrorDetails: destructive Alert with shadcn Collapsible, no traceback, shows source_text of failing segments
    - JobMetaRow: lang pair + format badge + age
    - Job status page: queued=skeleton, running=progress+counter+retry chip, done=download button, failed=error banner, needs_review=placeholder card
    - Detected language badge appears when source_lang='auto' and detected_lang is set
    - Retry chip (slate-500, no red) appears only when retry_count > 0 and running
    - TypeScript clean; Next.js 16 async params unwrapped via React.use()
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| SSE stream → React state | Server-pushed JSON parsed with JSON.parse — malformed events crash the component |
| `/api/jobs/{id}/download` | Job ID from URL params passed to backend — SSRF/path traversal if not validated |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-09-01 | Tampering | `JSON.parse(ev.data)` in useJobProgress | mitigate | Parse errors caught in `onmessage` try/catch (Plan 07 already handles this); status page renders "Job not found" gracefully on null data |
| T-01-09-02 | Information Disclosure | ErrorDetails showing `source_text` of failing segments | accept | Source text is the user's own document content — they uploaded it. Low risk for internal PoC. |
| T-01-09-03 | Elevation of Privilege | `window.location.href = /api/jobs/${jobId}/download` | accept | jobId comes from URL params, validated by FastAPI route handler. Frontend is internal PoC only — no auth in Phase 1. |
</threat_model>

<verification>
1. TypeScript: `cd frontend && npx tsc --noEmit` — zero errors
2. Visual: Start dev server, navigate to `/jobs/{id}` for a running job — stage indicator advances, progress bar fills, counter animates
3. Retry chip: Manually set retry_count > 0 in TanStack DevTools — chip appears in slate-500, no red
4. Failed state: Mock a job with status=failed — error banner with collapsible appears, no traceback visible
5. Download button: Done job shows indigo Download button; click triggers browser download
</verification>

<success_criteria>
- `/jobs/[id]` renders with stage indicator, progress bar, animated counter
- Stage indicator active=indigo-600, past=emerald, future=slate-300
- Retry chip text-slate-500 only when running + retry_count > 0
- Failed state: destructive Alert + Collapsible with segment source_text (no stack trace)
- Done state: full-width indigo "Download Translation" button
- needs_review state: placeholder card with "Download Current Output"
- TypeScript strict pass
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-09-SUMMARY.md`
</output>
