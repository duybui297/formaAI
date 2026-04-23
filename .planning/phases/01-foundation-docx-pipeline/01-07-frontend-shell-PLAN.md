---
phase: 01-foundation-docx-pipeline
plan: "07"
type: execute
wave: 4
depends_on:
  - "01"
  - "06b"
files_modified:
  - frontend/src/app/layout.tsx
  - frontend/src/app/page.tsx
  - frontend/src/app/globals.css
  - frontend/src/lib/types.ts
  - frontend/src/lib/api.ts
  - frontend/src/hooks/useJobProgress.ts
  - frontend/src/components/ui/.gitkeep
  - frontend/src/components/providers/query-provider.tsx
  - frontend/tailwind.config.ts
  - frontend/postcss.config.mjs
  - frontend/package.json
  - frontend/vitest.config.ts
  - frontend/vitest.setup.ts
autonomous: true
requirements:
  - INFRA-04
  - JOB-02
  - JOB-03
  - LANG-01

must_haves:
  truths:
    - "Next.js 16 App Router root layout wraps pages in QueryClientProvider"
    - "useJobProgress hook opens SSE stream via @microsoft/fetch-event-source and falls back to TanStack Query polling"
    - "JobProgress TypeScript interface matches D-10 payload shape exactly"
    - "TanStack Query polling activates when SSE is closed and job is not terminal"
    - "shadcn/ui is initialized with New York style + Slate base color"
    - "Tailwind config is correct for App Router and shadcn"
    - "vitest + @testing-library/react are in devDependencies (W9: required by Plan 09 tests)"
  artifacts:
    - path: "frontend/src/lib/types.ts"
      provides: "JobProgress, JobStatus, JobStage TypeScript interfaces (D-10 shape)"
    - path: "frontend/src/hooks/useJobProgress.ts"
      provides: "SSE + TanStack Query hybrid hook (D-09 pattern)"
    - path: "frontend/src/app/layout.tsx"
      provides: "Root layout with QueryClientProvider, Inter font"
    - path: "frontend/src/lib/api.ts"
      provides: "getLanguages(), getJob(), createJob() API functions"
    - path: "frontend/src/components/providers/query-provider.tsx"
      provides: "Client component holding QueryClient instance"
    - path: "frontend/vitest.config.ts"
      provides: "Vitest config with jsdom env and React Testing Library setup"
  key_links:
    - from: "frontend/src/hooks/useJobProgress.ts"
      to: "/api/jobs/{jobId}/stream"
      via: "fetchEventSource → queryClient.setQueryData"
      pattern: "fetchEventSource"
    - from: "frontend/src/hooks/useJobProgress.ts"
      to: "useQuery refetchInterval fallback"
      via: "sseOpen.current ref"
      pattern: "refetchInterval"
    - from: "frontend/src/app/layout.tsx"
      to: "QueryClientProvider"
      via: "TanStack Query context"
---

<objective>
Set up the Next.js 16 App Router frontend shell: root layout with TanStack Query provider, TypeScript
type definitions (D-10 payload shape), shared API functions, the SSE + polling hybrid hook (D-09),
Tailwind + shadcn initialization, and the vitest test infrastructure (required by Plan 09 TDD tasks).

Purpose: This shell is the foundation all frontend page components (upload form, job status page) depend on.
Output: frontend/src/ skeleton working. shadcn CLI initialized. useJobProgress hook connecting to backend SSE.
vitest configured so Plan 09 tests can run without setup overhead.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md
@.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md

<interfaces>
<!-- useJobProgress hook (RESEARCH.md §7 exact TypeScript pattern) -->
```typescript
"use client"
import { useQueryClient, useQuery } from "@tanstack/react-query"
import { fetchEventSource } from "@microsoft/fetch-event-source"
import { useEffect, useRef } from "react"

const TERMINAL = new Set(["done", "failed", "needs_review"])

export function useJobProgress(jobId: string) {
  const queryClient = useQueryClient()
  const sseOpen = useRef(false)

  useEffect(() => {
    const ctrl = new AbortController()
    sseOpen.current = true

    fetchEventSource(`/api/jobs/${jobId}/stream`, {
      signal: ctrl.signal,
      onmessage(ev) {
        const data: JobProgress = JSON.parse(ev.data)
        queryClient.setQueryData(["job", jobId], data)
      },
      onerror() { sseOpen.current = false },
      onclose() { sseOpen.current = false },
    })
    return () => ctrl.abort()
  }, [jobId, queryClient])

  return useQuery<JobProgress>({
    queryKey: ["job", jobId],
    queryFn: () => fetch(`/api/jobs/${jobId}`).then(r => r.json()),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status && TERMINAL.has(status)) return false
      if (sseOpen.current) return false
      return 2000
    },
    staleTime: 0,
  })
}
```

<!-- D-10 payload TypeScript interface -->
```typescript
type JobStatus = "queued" | "running" | "needs_review" | "failed" | "done"
type JobStage = "parse" | "translate" | "reassemble" | "done" | "failed"

interface JobProgress {
  status: JobStatus
  stage: JobStage | null
  segments_done: number
  segments_total: number
  current_batch: number
  retry_count: number
  last_message: string
  detected_lang?: string
  original_filename?: string
  source_lang?: string
  target_lang?: string
  error?: { code: string; message: string; failing_segments: unknown[] }
}
```

<!-- UI-SPEC decisions -->
<!-- Font: Inter (next/font/google) for Latin/Vietnamese; Noto Sans JP/SC for CJK fallback -->
<!-- Design: light mode only, no dark mode (Phase 1) -->
<!-- shadcn: New York style, Slate base, CSS variables -->
<!-- App name: "AI Translation" -->
<!-- page background: bg-slate-50; cards: bg-white; content column: max-w-3xl mx-auto px-8 py-12 -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: TypeScript Types + API Client + useJobProgress Hook</name>
  <files>
    frontend/src/lib/types.ts
    frontend/src/lib/api.ts
    frontend/src/hooks/useJobProgress.ts
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 7: useJobProgress full TypeScript excerpt, JobProgress interface)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-09 SSE transport, D-10 payload shape)
    .planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md (Language selectors: getLanguages staleTime 24h)
  </read_first>
  <action>
Create `frontend/src/lib/types.ts` (D-10 payload shape exactly):
```typescript
export type JobStatus = "queued" | "running" | "needs_review" | "failed" | "done"
export type JobStage = "parse" | "translate" | "reassemble" | "done" | "failed"

export interface JobProgress {
  id?: string
  status: JobStatus
  stage: JobStage | null
  segments_done: number
  segments_total: number
  current_batch: number
  retry_count: number
  last_message: string
  // From GET /jobs/{id} — not in SSE payload but merged into TanStack cache
  detected_lang?: string
  original_filename?: string
  source_lang?: string
  target_lang?: string
  input_format?: string
  created_at?: string
  error?: {
    code: string
    message: string
    failing_segments: Array<{ id: string; source_text: string; batch_id: number }>
  }
}

// B5: Language shape matches SUPPORTED_LANGUAGES in Plan 06a (list[dict])
export interface Language {
  code: string
  name: string
  qwen_code: string
}

export interface UploadResponse {
  job_id: string
  has_tracked_changes: boolean
}

export interface LanguagesResponse {
  languages: Language[]
  auto_detect_option: string
}

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

Create `frontend/src/lib/api.ts` with typed fetch helpers:
```typescript
const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

// B5: getLanguages returns Language[] (not string[])
export async function getLanguages(): Promise<import("./types").Language[]> {
  const res = await fetch(`${BACKEND_URL}/languages`)
  if (!res.ok) throw new Error("Failed to fetch languages")
  const data = await res.json()
  return data.languages as import("./types").Language[]
}

export async function getJob(jobId: string): Promise<import("./types").JobProgress> {
  const res = await fetch(`${BACKEND_URL}/jobs/${jobId}`)
  if (!res.ok) throw new Error(`Failed to fetch job ${jobId}`)
  return res.json()
}

export async function listJobs(): Promise<import("./types").JobSummary[]> {
  const res = await fetch(`${BACKEND_URL}/jobs`)
  if (!res.ok) throw new Error("Failed to list jobs")
  const data = await res.json()
  return data.jobs
}
```

Create `frontend/src/hooks/useJobProgress.ts` (RESEARCH.md §7 exact TypeScript pattern — copy verbatim):
```typescript
"use client"
import { useQueryClient, useQuery } from "@tanstack/react-query"
import { fetchEventSource } from "@microsoft/fetch-event-source"
import { useEffect, useRef } from "react"
import type { JobProgress } from "@/lib/types"

const TERMINAL = new Set(["done", "failed", "needs_review"])

export function useJobProgress(jobId: string) {
  const queryClient = useQueryClient()
  const sseOpen = useRef(false)

  useEffect(() => {
    const ctrl = new AbortController()
    sseOpen.current = true

    fetchEventSource(`/api/jobs/${jobId}/stream`, {
      signal: ctrl.signal,
      onmessage(ev) {
        const data: JobProgress = JSON.parse(ev.data)
        queryClient.setQueryData(["job", jobId], data)
      },
      onerror() {
        sseOpen.current = false  // triggers polling fallback
      },
      onclose() {
        sseOpen.current = false
      },
    })

    return () => ctrl.abort()
  }, [jobId, queryClient])

  return useQuery<JobProgress>({
    queryKey: ["job", jobId],
    queryFn: () => fetch(`/api/jobs/${jobId}`).then(r => r.json()),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status && TERMINAL.has(status)) return false
      if (sseOpen.current) return false
      return 2000  // poll every 2s when SSE closed (D-09 fallback)
    },
    staleTime: 0,
  })
}
```
  </action>
  <verify>
    <automated>
      grep -q "fetchEventSource" frontend/src/hooks/useJobProgress.ts &amp;&amp;
      grep -q "refetchInterval" frontend/src/hooks/useJobProgress.ts &amp;&amp;
      grep -q "sseOpen.current" frontend/src/hooks/useJobProgress.ts &amp;&amp;
      grep -q "TERMINAL" frontend/src/hooks/useJobProgress.ts &amp;&amp;
      grep -q "JobProgress" frontend/src/lib/types.ts &amp;&amp;
      grep -q "qwen_code" frontend/src/lib/types.ts &amp;&amp;
      grep -q "segments_done" frontend/src/lib/types.ts
    </automated>
  </verify>
  <done>
    types.ts defines JobProgress with all D-10 fields (status, stage, segments_done, segments_total, current_batch, retry_count, last_message, error?).
    Language interface has code/name/qwen_code fields matching Plan 06a SUPPORTED_LANGUAGES shape (B5).
    useJobProgress opens SSE via fetchEventSource, calls setQueryData on each event, closes SSE on onerror/onclose.
    Polling fallback: refetchInterval returns 2000 when sseOpen.current is false and status is not terminal.
    Polling stops (returns false) on terminal status or when SSE is open.
    getLanguages() returns Language[] (not string[]).
  </done>
</task>

<task type="auto">
  <name>Task 2: App Layout + Tailwind + shadcn Init + Vitest Config</name>
  <files>
    frontend/src/app/layout.tsx
    frontend/src/app/page.tsx
    frontend/src/app/globals.css
    frontend/src/components/providers/query-provider.tsx
    frontend/tailwind.config.ts
    frontend/postcss.config.mjs
    frontend/src/components/ui/.gitkeep
    frontend/package.json
    frontend/vitest.config.ts
    frontend/vitest.setup.ts
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md (Design System: shadcn New York/Slate, Typography, Color palette, Global Shell layout)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-20: Next.js 16, React 19; no dark mode)
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 9: App Router layout pattern, QueryClientProvider)
  </read_first>
  <action>
Run shadcn init before creating these files:
```bash
cd frontend && npx shadcn@latest init
# When prompted: style=New York, base color=Slate, CSS variables=yes
```

Then add required shadcn components:
```bash
npx shadcn@latest add button badge progress dialog select table toast alert collapsible radiogroup skeleton separator
```

Add vitest and React Testing Library to devDependencies in `frontend/package.json`
(W9 fix — required by Plan 09 TDD tests):
```json
{
  "devDependencies": {
    "vitest": "^1.6.0",
    "@vitest/ui": "^1.6.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "jsdom": "^24.0.0"
  }
}
```
Install: `cd frontend && npm install --save-dev vitest @vitest/ui @testing-library/react @testing-library/jest-dom jsdom`

Create `frontend/vitest.config.ts` (W9 fix — jsdom env + React Testing Library setup):
```typescript
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import path from "path"

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
```

Create `frontend/vitest.setup.ts`:
```typescript
import "@testing-library/jest-dom"
```

Create `frontend/src/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* shadcn CSS variables for New York / Slate theme */
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    /* ... (shadcn init generates these) */
  }
}

body {
  @apply bg-slate-50 text-slate-900;
  font-family: 'Inter', 'Noto Sans JP', 'Noto Sans SC', ui-sans-serif, system-ui, sans-serif;
}
```

Create `frontend/src/components/providers/query-provider.tsx` (W13: file is in files_modified):
```typescript
"use client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useState } from "react"

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        staleTime: 0,
      },
    },
  }))

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
```

Create `frontend/src/app/layout.tsx` (App Router root layout with QueryClientProvider + Inter font):
```typescript
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { QueryProvider } from "@/components/providers/query-provider"

const inter = Inter({
  subsets: ["latin", "vietnamese"],  // Vietnamese diacritics (UI-SPEC typography)
  variable: "--font-inter",
})

export const metadata: Metadata = {
  title: "AI Translation",
  description: "Translate documents with format fidelity",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased`}>
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  )
}
```

Create `frontend/src/app/page.tsx` (root redirect to /upload):
```typescript
import { redirect } from "next/navigation"

export default function HomePage() {
  redirect("/upload")
}
```

Update `frontend/tailwind.config.ts` to include shadcn and App Router paths:
```typescript
import type { Config } from "tailwindcss"
import { fontFamily } from "tailwindcss/defaultTheme"

const config: Config = {
  darkMode: false,  // UI-SPEC: light mode only in Phase 1
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", ...fontFamily.sans],
      },
      // shadcn color tokens (generated by shadcn init)
    },
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
```

Create `frontend/postcss.config.mjs`:
```javascript
const config = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
export default config
```

Create `frontend/src/components/ui/.gitkeep` (shadcn components generated here by shadcn CLI).
  </action>
  <verify>
    <automated>
      grep -q "QueryProvider" frontend/src/app/layout.tsx &amp;&amp;
      grep -q "QueryClientProvider" frontend/src/components/providers/query-provider.tsx &amp;&amp;
      grep -q "Inter" frontend/src/app/layout.tsx &amp;&amp;
      grep -q "vietnamese" frontend/src/app/layout.tsx &amp;&amp;
      grep -q "darkMode: false" frontend/tailwind.config.ts &amp;&amp;
      test -f frontend/vitest.config.ts &amp;&amp;
      test -f frontend/vitest.setup.ts &amp;&amp;
      grep -q "jsdom" frontend/vitest.config.ts
    </automated>
  </verify>
  <done>
    layout.tsx loads Inter with latin + vietnamese subsets, wraps children in QueryProvider.
    QueryProvider is a "use client" component holding QueryClient instance (W13: in files_modified).
    page.tsx redirects to /upload.
    tailwind.config.ts has darkMode: false (light-mode-only per UI-SPEC).
    globals.css applies bg-slate-50 body background.
    vitest.config.ts with jsdom env + @testing-library/jest-dom setup (W9: Plan 09 tests can run).
    vitest + @testing-library/react in package.json devDependencies (W9).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → /api/jobs/{id}/stream | SSE connection to backend; no auth in Phase 1 |
| fetchEventSource → JSON.parse | LLM-originated progress payload must not contain XSS |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-01 | Information Disclosure | SSE stream exposes job progress to any client | accept | Internal PoC; no auth in Phase 1; job_id is UUID (unguessable) |
| T-07-02 | Tampering | JSON.parse(ev.data) in SSE message handler | mitigate | Data originates from our worker via Redis; TypeScript interface validates shape at build time; no innerHTML usage |
| T-07-03 | Spoofing | QueryProvider client vs server boundary | accept | QueryProvider is "use client" — no server component contamination; standard Next.js App Router pattern |
</threat_model>

<verification>
After all tasks complete:
1. `cd frontend && npx tsc --noEmit` — no TypeScript errors
2. `grep -q "fetchEventSource" frontend/src/hooks/useJobProgress.ts` — passes
3. `grep -q "refetchInterval" frontend/src/hooks/useJobProgress.ts` — passes
4. `grep -q "darkMode: false" frontend/tailwind.config.ts` — passes
5. `grep -q "jsdom" frontend/vitest.config.ts` — passes (W9)
6. After `cd frontend && npm run dev`: browser at http://localhost:3000 redirects to /upload
7. `cd frontend && npx vitest run --reporter=verbose` — test runner executes without config errors
</verification>

<success_criteria>
- TypeScript compiles without errors (npx tsc --noEmit)
- useJobProgress opens SSE, calls setQueryData, falls back to 2s polling when SSE closed
- refetchInterval returns false when status is terminal or SSE is open
- layout.tsx loads Inter font with vietnamese subset; wraps in QueryProvider
- tailwind.config.ts has darkMode: false
- QueryProvider is "use client" component with QueryClientProvider
- vitest.config.ts configured with jsdom + @testing-library/react setup (W9 prerequisite for Plan 09)
- package.json devDependencies includes vitest, @vitest/ui, @testing-library/react, @testing-library/jest-dom, jsdom
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-07-SUMMARY.md`
</output>
