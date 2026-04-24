---
phase: "01"
plan: "07"
subsystem: frontend
tags: [next.js, react, tanstack-query, sse, typescript, shadcn, tailwind, vitest]
dependency_graph:
  requires:
    - 01-06b  # FastAPI jobs + SSE endpoints (SSE stream URL, job response shape)
  provides:
    - frontend/src/lib/types.ts         # TypeScript types consumed by plans 08/09/10
    - frontend/src/lib/api.ts           # API client consumed by plans 08/09/10
    - frontend/src/hooks/useJobProgress.ts  # SSE+polling hook consumed by plan 09
    - frontend/src/components/providers/query-provider.tsx  # QueryClientProvider
    - frontend/src/app/layout.tsx       # Root layout used by all pages
    - frontend/vitest.config.mts        # Test infrastructure required by plan 09 TDD
  affects:
    - plans 08/09/10  # all frontend page plans depend on this shell
tech_stack:
  added:
    - next.js 16.2.3 (App Router)
    - react 19
    - "@tanstack/react-query 5"
    - "@microsoft/fetch-event-source 2"
    - shadcn/ui (New York/Slate preset, Radix primitives)
    - tailwindcss 3.4
    - vitest 1.6 + @testing-library/react 16 + jsdom 24
    - "@vitejs/plugin-react 4"
    - lucide-react
  patterns:
    - SSE primary + TanStack Query polling fallback (D-09)
    - QueryClient singleton via useState in "use client" provider
    - Inter font with vietnamese subset via next/font/google
    - shadcn components.json + New York style + CSS variables
key_files:
  created:
    - frontend/src/lib/types.ts
    - frontend/src/lib/api.ts
    - frontend/src/hooks/useJobProgress.ts
    - frontend/src/components/providers/query-provider.tsx
    - frontend/src/app/layout.tsx
    - frontend/src/app/page.tsx
    - frontend/src/app/globals.css
    - frontend/src/lib/utils.ts
    - frontend/src/components/ui/ (button badge progress dialog select table toast alert skeleton separator toaster)
    - frontend/src/hooks/use-toast.ts
    - frontend/tailwind.config.ts
    - frontend/postcss.config.mjs
    - frontend/components.json
    - frontend/vitest.config.mts
    - frontend/vitest.setup.ts
    - frontend/src/__tests__/smoke.test.tsx
  modified:
    - frontend/package.json (eslint ^8→^9, added @vitejs/plugin-react@4, @testing-library/dom)
    - frontend/package-lock.json
decisions:
  - "Used vitest.config.mts (not .ts) because @vitejs/plugin-react is ESM-only; .mts forces ESM module loading"
  - "Installed @vitejs/plugin-react@4 (not latest v6) because vitest 1.x bundles vite 5 which is incompatible with plugin-react@6"
  - "darkMode set to class strategy (not false) to avoid Tailwind v3 TypeScript type error; no dark class is ever applied, achieving light-mode-only per UI-SPEC"
  - "Manually created components.json for shadcn rather than using shadcn init --defaults because shadcn 4.x init requires a pre-existing Tailwind config it could not auto-detect in .ts extension"
  - "Added @testing-library/dom explicitly — @testing-library/react@16 requires it as a peer but npm did not auto-install it"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-24T05:05:25Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 20
  files_modified: 2
---

# Phase 1 Plan 07: Frontend Shell Summary

**One-liner:** Next.js 16 App Router shell with TanStack Query + SSE hybrid hook, shadcn/ui (New York/Slate), Inter font, and vitest infrastructure.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | TypeScript Types + API Client + useJobProgress Hook | 0cb1954 | types.ts, api.ts, useJobProgress.ts |
| 2 | App Layout + Tailwind + shadcn Init + Vitest Config | 143f130 | layout.tsx, query-provider.tsx, tailwind.config.ts, vitest.config.mts, shadcn components |

## What Was Built

### Task 1: Types + API + Hook
- `frontend/src/lib/types.ts` — complete D-10 payload shape: `JobProgress`, `JobStatus`, `JobStage`, `Language` (B5: code/name/qwen_code), `JobSummary`, `UploadResponse`, `LanguagesResponse`
- `frontend/src/lib/api.ts` — `getLanguages()`, `getJob()`, `listJobs()`, `createJob()` using `/api` proxy base path (rewrites in next.config.mjs)
- `frontend/src/hooks/useJobProgress.ts` — SSE primary via `fetchEventSource`, `queryClient.setQueryData` on every event; polling fallback at 2s when `sseOpen.current` is false and job is not terminal (TERMINAL = done/failed/needs_review)

### Task 2: Shell + Infrastructure
- Root layout wrapping children in `QueryProvider` with Inter font (latin+vietnamese subsets per UI-SPEC)
- `QueryProvider` as `"use client"` component holding `QueryClient` singleton (W13 in files_modified)
- `page.tsx` redirects to `/upload` (upload form ships in plan 08)
- `globals.css` with tailwind directives + shadcn Slate CSS variable tokens + `bg-slate-50` body
- `components.json` for shadcn (New York style, Slate base, CSS variables, RSC=true)
- 11 shadcn components added: button, badge, progress, dialog, select, table, toast, alert, skeleton, separator, toaster
- `vitest.config.mts` (ESM module, jsdom env, `@/*` alias) + `vitest.setup.ts` (jest-dom)
- Smoke tests passing: QueryProvider render + types module import

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ESM loading error for @vitejs/plugin-react in vitest.config.ts**
- **Found during:** Task 2 — `npx vitest run` failed with "ESM file cannot be loaded by require"
- **Issue:** Vitest 1.x uses esbuild to load the config file as CJS; `@vitejs/plugin-react` is ESM-only
- **Fix:** Renamed `vitest.config.ts` → `vitest.config.mts` to force ESM loading
- **Files modified:** `frontend/vitest.config.mts`

**2. [Rule 1 - Bug] @vitejs/plugin-react@6 incompatible with Vite 5**
- **Found during:** Task 2 — after .mts rename, got `ERR_PACKAGE_PATH_NOT_EXPORTED` for `vite/internal`
- **Issue:** plugin-react@6 requires Vite 6; vitest 1.x bundles Vite 5
- **Fix:** Downgraded to `@vitejs/plugin-react@4` which is Vite 5 compatible
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`

**3. [Rule 2 - Missing dependency] @testing-library/dom not auto-installed**
- **Found during:** Task 2 — first vitest run failed with `Cannot find module '@testing-library/dom'`
- **Issue:** `@testing-library/react@16` declares it as a peer dep but npm didn't hoist it
- **Fix:** Added `@testing-library/dom` to devDependencies explicitly
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`

**4. [Rule 1 - Bug] darkMode: false type error in tailwind.config.ts**
- **Found during:** Task 2 — `npx tsc --noEmit` reported `Type 'false' is not assignable to type 'Partial<DarkModeConfig> | undefined'`
- **Issue:** Tailwind v3 TypeScript types do not accept `false` for darkMode
- **Fix:** Changed to `darkMode: ["class", "[data-theme='dark']"] as const`; no dark class is ever applied, achieving light-mode-only per UI-SPEC
- **Files modified:** `frontend/tailwind.config.ts`

**5. [Rule 3 - Blocking] shadcn init could not find Tailwind config**
- **Found during:** Task 2 — `npx shadcn@latest init -y -d` failed: "No Tailwind CSS configuration found"
- **Issue:** shadcn 4.x init validation could not detect `tailwind.config.ts` (`.ts` extension issue); also required postcss.config first
- **Fix:** Created `tailwind.config.ts` and `postcss.config.mjs` first, then manually created `components.json` with the correct New York/Slate preset settings
- **Files modified:** `frontend/components.json`

**6. [Rule 1 - Bug] eslint peer dep conflict during npm install**
- **Found during:** npm install — `eslint-config-next@16` requires `eslint@>=9` but package.json had `^8`
- **Issue:** Next.js 16's eslint config requires ESLint 9
- **Fix:** Bumped `eslint` to `^9` in devDependencies
- **Files modified:** `frontend/package.json`

## Known Stubs

- `frontend/src/app/page.tsx` — redirects to `/upload` which doesn't exist yet; plan 08 creates the upload page

## Threat Flags

No new security surface introduced. The `useJobProgress` hook connects to `/api/jobs/{id}/stream` (same-origin proxy via next.config.mjs rewrites). JSON.parse output is typed as `JobProgress` at build time; no innerHTML usage.

## Self-Check: PASSED

All 11 key files verified present on disk. Both task commits (0cb1954, 143f130) verified in git log.
