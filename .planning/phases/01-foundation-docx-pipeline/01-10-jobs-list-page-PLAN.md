---
phase: 01-foundation-docx-pipeline
plan: 10
type: execute
wave: 4
depends_on:
  - "07"
files_modified:
  - frontend/src/app/jobs/page.tsx
  - frontend/src/components/StatusBadge.tsx
autonomous: true
requirements:
  - JOB-01
  - JOB-02

must_haves:
  truths:
    - "User can navigate to /jobs and see a table of all translation jobs"
    - "Each row shows filename, source→target pair, format, status badge, created time, actions"
    - "Status badges use correct semantic colors (emerald=done, red=failed, amber=queued, indigo=running)"
    - "View button navigates to /jobs/{id}"
    - "Download button appears only on done rows and triggers file download"
    - "Empty state shown when no jobs exist"
    - "New Translation button navigates to /"
  artifacts:
    - path: "frontend/src/app/jobs/page.tsx"
      provides: "Jobs list page with shadcn Table, polling every 5s"
      exports: [default]
    - path: "frontend/src/components/StatusBadge.tsx"
      provides: "Reusable status badge with semantic colors per UI-SPEC"
      exports: [StatusBadge]
  key_links:
    - from: "frontend/src/app/jobs/page.tsx"
      to: "frontend/src/lib/api.ts"
      via: "listJobs() — GET /api/jobs"
      pattern: "listJobs"
    - from: "frontend/src/components/StatusBadge.tsx"
      to: "JobStatus type"
      via: "status prop"
      pattern: "JobStatus"
---

<objective>
Build the `/jobs` list page: a polling table showing all translation jobs with status, language pair, and actions.

Purpose: Users need to track multiple jobs, navigate to status pages, and download completed files.
Output: jobs list page + reusable StatusBadge component.
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

export interface JobSummary {
  id: string
  original_filename: string
  source_lang: string
  target_lang: string
  input_format: string
  status: JobStatus
  created_at: string
}
```

<!-- From frontend/src/lib/api.ts (Plan 07) -->
```typescript
export async function listJobs(): Promise<JobSummary[]>
// GET /api/jobs — returns array of job summaries, newest-first
```
</interfaces>

<!-- shadcn components: Table, Badge, Button -->
<!-- Add: npx shadcn@latest add table badge button -->
</context>

<tasks>

<task type="auto">
  <name>Task 1: StatusBadge component + jobs list page</name>
  <files>
    frontend/src/components/StatusBadge.tsx
    frontend/src/app/jobs/page.tsx
  </files>
  <action>
    1. Install shadcn Table if not already present: `cd frontend && npx shadcn@latest add table`.

    2. Create `frontend/src/components/StatusBadge.tsx`:
       ```typescript
       import { Badge } from '@/components/ui/badge'
       import { cn } from '@/lib/utils'
       import type { JobStatus } from '@/lib/types'

       const STATUS_STYLES: Record<JobStatus, string> = {
         queued: 'text-amber-500 border-amber-200 bg-amber-50',
         running: 'text-indigo-600 border-indigo-200 bg-indigo-50',
         needs_review: 'text-amber-600 border-amber-300 bg-amber-50',
         failed: 'text-red-600 border-red-200 bg-red-50',
         done: 'text-emerald-600 border-emerald-200 bg-emerald-50',
       }

       const STATUS_LABELS: Record<JobStatus, string> = {
         queued: 'queued',
         running: 'running',
         needs_review: 'needs review',
         failed: 'failed',
         done: 'done',
       }

       interface StatusBadgeProps {
         status: JobStatus
         className?: string
       }

       export function StatusBadge({ status, className }: StatusBadgeProps) {
         return (
           <Badge
             variant="outline"
             className={cn('text-xs font-medium', STATUS_STYLES[status], className)}
           >
             {STATUS_LABELS[status]}
           </Badge>
         )
       }
       ```

    3. Create `frontend/src/app/jobs/page.tsx`:
       ```typescript
       'use client'
       import Link from 'next/link'
       import { useRouter } from 'next/navigation'
       import { useQuery } from '@tanstack/react-query'
       import {
         Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
       } from '@/components/ui/table'
       import { Button } from '@/components/ui/button'
       import { Badge } from '@/components/ui/badge'
       import { StatusBadge } from '@/components/StatusBadge'
       import { NavBar } from '@/components/NavBar'
       import { listJobs } from '@/lib/api'
       import type { JobSummary } from '@/lib/types'

       function formatAge(isoString: string): string {
         const diffMs = Date.now() - new Date(isoString).getTime()
         const diffMin = Math.floor(diffMs / 60_000)
         if (diffMin < 1) return 'just now'
         if (diffMin < 60) return `${diffMin}m ago`
         const diffH = Math.floor(diffMin / 60)
         if (diffH < 24) return `${diffH}h ago`
         return `${Math.floor(diffH / 24)}d ago`
       }

       function sourceLangDisplay(job: JobSummary): string {
         return job.source_lang === 'auto' ? 'Auto' : job.source_lang
       }

       export default function JobsPage() {
         const router = useRouter()
         const { data: jobs = [], isLoading } = useQuery({
           queryKey: ['jobs'],
           queryFn: listJobs,
           refetchInterval: 5_000,  // poll every 5s — jobs list has no SSE
         })

         return (
           <>
             <NavBar />
             <main className="max-w-3xl mx-auto px-8 py-12 space-y-6">
               {/* Heading row */}
               <div className="flex items-center justify-between">
                 <h1 className="text-xl font-semibold text-slate-900">Translation Jobs</h1>
                 <Button
                   className="bg-indigo-600 hover:bg-indigo-700 text-white"
                   onClick={() => router.push('/')}
                 >
                   New Translation
                 </Button>
               </div>

               {/* Table */}
               {isLoading ? (
                 <p className="text-sm text-slate-500">Loading jobs...</p>
               ) : jobs.length === 0 ? (
                 /* Empty state */
                 <div className="text-center py-16 space-y-3">
                   <p className="text-base font-semibold text-slate-700">No translations yet</p>
                   <p className="text-sm text-slate-500">Upload a document to get started.</p>
                   <Button
                     variant="outline"
                     className="border-indigo-600 text-indigo-600 hover:bg-indigo-50 mt-2"
                     onClick={() => router.push('/')}
                   >
                     Translate a Document
                   </Button>
                 </div>
               ) : (
                 <Table>
                   <TableHeader>
                     <TableRow>
                       <TableHead className="w-8 text-xs">#</TableHead>
                       <TableHead className="text-xs">Filename</TableHead>
                       <TableHead className="text-xs">Languages</TableHead>
                       <TableHead className="text-xs">Format</TableHead>
                       <TableHead className="text-xs">Status</TableHead>
                       <TableHead className="text-xs">Created</TableHead>
                       <TableHead className="text-xs text-right">Actions</TableHead>
                     </TableRow>
                   </TableHeader>
                   <TableBody>
                     {jobs.map((job, idx) => (
                       <TableRow
                         key={job.id}
                         className="hover:bg-slate-50 cursor-pointer"
                         onClick={() => router.push(`/jobs/${job.id}`)}
                       >
                         <TableCell className="text-xs text-slate-400 font-mono">{idx + 1}</TableCell>
                         <TableCell className="text-sm text-slate-800 max-w-[200px] truncate">
                           {job.original_filename}
                         </TableCell>
                         <TableCell className="text-xs text-slate-600">
                           {sourceLangDisplay(job)} → {job.target_lang}
                         </TableCell>
                         <TableCell>
                           <Badge variant="outline" className="text-xs text-slate-700">
                             {job.input_format.toUpperCase()}
                           </Badge>
                         </TableCell>
                         <TableCell>
                           <StatusBadge status={job.status} />
                         </TableCell>
                         <TableCell className="text-xs text-slate-500">
                           {formatAge(job.created_at)}
                         </TableCell>
                         <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                           <div className="flex items-center justify-end gap-1">
                             <Button
                               variant="ghost"
                               size="sm"
                               className="h-7 px-2 text-xs"
                               asChild
                             >
                               <Link href={`/jobs/${job.id}`}>View</Link>
                             </Button>
                             {job.status === 'done' && (
                               <Button
                                 variant="ghost"
                                 size="sm"
                                 className="h-7 px-2 text-xs text-indigo-600 hover:text-indigo-700"
                                 onClick={() => { window.location.href = `/api/jobs/${job.id}/download` }}
                               >
                                 Download
                               </Button>
                             )}
                           </div>
                         </TableCell>
                       </TableRow>
                     ))}
                   </TableBody>
                 </Table>
               )}
             </main>
           </>
         )
       }
       ```

    NOTE: Uses `job.original_filename` and `job.input_format` — matching the JobSummary shape defined in Plan 07 types.ts (aligned with Plan 06a Job model fields).

    NOTE: Table rows are clickable (navigate to /jobs/{id}) but action column click uses stopPropagation.

    NOTE: `refetchInterval: 5_000` on jobs list. No SSE needed here — this is a list view.

    NOTE: Download in action column triggers `window.location.href` (browser download).
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&amp;1 | head -30</automated>
  </verify>
  <done>
    - /jobs page renders table with columns: #, Filename, Languages, Format, Status, Created, Actions
    - StatusBadge renders correct colors per semantic status table (UI-SPEC)
    - Empty state shows "No translations yet" with "Translate a Document" CTA
    - Polling every 5s via refetchInterval
    - Download button only visible for done status rows
    - Uses original_filename and input_format field names (matching Plan 07 JobSummary + Plan 06a model)
    - TypeScript clean
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| GET /api/jobs response | Server-returned job list — validate structure before rendering |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-10-01 | Information Disclosure | Jobs table shows all jobs to anyone loading the page | accept | Internal PoC, no auth in Phase 1. Phase 2 adds auth per roadmap. |
| T-01-10-02 | Tampering | `window.location.href = /api/jobs/${job.id}/download` | accept | job.id from server-trusted list response. Phase 1 internal only. |
</threat_model>

<verification>
1. TypeScript: `cd frontend && npx tsc --noEmit` — zero errors
2. Visual: Navigate to /jobs — table renders with column headers
3. Empty state: Clear jobs from DB — "No translations yet" shows with CTA
4. Status badges: Verify colors match UI-SPEC (emerald=done, red=failed, amber=queued, indigo=running)
5. Polling: Inspect network tab — GET /api/jobs fires every 5s
6. Download column: Only "done" rows show Download action
</verification>

<success_criteria>
- /jobs page renders full table with correct columns
- StatusBadge exported and used on /jobs; reusable in /jobs/[id] if needed
- Empty state matches copywriting contract exactly
- 5s polling active when page is open
- TypeScript strict pass
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-10-SUMMARY.md`
</output>
