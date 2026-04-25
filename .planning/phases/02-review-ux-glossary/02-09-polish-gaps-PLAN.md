---
phase: 02-review-ux-glossary
plan: 09
type: execute
wave: 9
depends_on: [02-08]
files_modified:
  - frontend/src/app/glossaries/page.tsx
  - frontend/src/app/glossaries/[id]/page.tsx
  - frontend/src/components/NavBar.tsx
  - frontend/src/components/glossary/GlossaryList.tsx
  - frontend/src/lib/types.ts
  - backend/src/app/api/routes/jobs.py
  - frontend/src/app/jobs/[id]/review/page.tsx
  - frontend/src/components/SegmentRow.tsx
  - frontend/src/hooks/useReviewKeyboard.ts
autonomous: true
gap_closure: true
requirements: [GLOS-01, GLOS-05, REV-01, REV-02]

must_haves:
  truths:
    - "NavBar appears on /glossaries and /glossaries/[id] routes"
    - "Glossary list shows correct term count (not dashes)"
    - "GET /jobs/{id} response includes glossary_id field"
    - "Review keyboard navigation is safe when filteredSegments is empty"
    - "SegmentRow isMounted guard prevents stale setSaveState calls on unmounted instances"
  artifacts:
    - path: "frontend/src/lib/types.ts"
      provides: "Glossary.term_count field + JobProgress.glossary_id field + SegmentsResponse.flag_counts"
      contains: "term_count"
    - path: "frontend/src/components/glossary/GlossaryList.tsx"
      provides: "renders g.term_count not g.terms?.length"
      contains: "term_count"
    - path: "backend/src/app/api/routes/jobs.py"
      provides: "_job_to_dict includes glossary_id"
      contains: "glossary_id"
    - path: "frontend/src/app/glossaries/page.tsx"
      provides: "NavBar imported and rendered"
      contains: "NavBar"
    - path: "frontend/src/hooks/useReviewKeyboard.ts"
      provides: "empty-list guard on j/k hotkeys"
      contains: "segmentCount === 0"
    - path: "frontend/src/components/SegmentRow.tsx"
      provides: "isMountedRef guard on setSaveState callbacks"
      contains: "isMountedRef"
  key_links:
    - from: "frontend/src/app/glossaries/page.tsx"
      to: "frontend/src/components/NavBar.tsx"
      via: "import NavBar + render <NavBar />"
      pattern: "NavBar"
    - from: "frontend/src/lib/types.ts"
      to: "frontend/src/components/glossary/GlossaryList.tsx"
      via: "Glossary.term_count consumed by g.term_count"
      pattern: "term_count"
    - from: "backend/src/app/api/routes/jobs.py"
      to: "frontend/src/lib/types.ts"
      via: "glossary_id in _job_to_dict + JobProgress type"
      pattern: "glossary_id"
---

<objective>
Fix three observed-during-UAT advisory gaps plus two code-review warnings (WR-02, WR-03):

1. **NavBar missing on /glossaries routes** — glossaries/page.tsx and glossaries/[id]/page.tsx
   do not render NavBar (it's not in the root layout). Add NavBar to both pages.

2. **IN-03: Terms column shows "—"** — GlossaryList renders `g.terms?.length ?? "—"` but
   the list API returns `term_count`, not the `terms` array. Fix: add `term_count: number`
   to the Glossary type and render `g.term_count` in GlossaryList.

3. **GET /jobs/{id} missing glossary_id** — _job_to_dict in jobs.py omits `glossary_id`.
   Frontend can't display or route on whether a glossary is attached. Add it.

4. **WR-02: Empty segment list crashes keyboard nav** — when filteredSegments is empty,
   `Math.min(focusedIndex + 1, segmentCount - 1)` = `Math.min(1, -1)` = -1. Guard in
   useReviewKeyboard.ts.

5. **WR-03: SegmentRow stale mutation callbacks** — when Virtuoso unmounts a row mid-debounce,
   `setSaveState("saved")` / `setSaveState("idle")` fire on the old instance. Guard with
   `isMountedRef`.

Purpose: Eliminate the remaining UAT-reported UX bugs and apply defensive code patches
flagged in the cross-AI code review before Phase 3 begins.

Output: Updated frontend components + backend routes. All TypeScript errors remain 0.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md

**NavBar component location:** `frontend/src/components/NavBar.tsx`
The root layout (`frontend/src/app/layout.tsx`) does NOT include NavBar — it only wraps
QueryProvider and Toaster. Individual route pages/layouts are responsible for rendering NavBar.
The review page (`frontend/src/app/jobs/[id]/review/page.tsx`) already imports and renders NavBar.
The glossaries pages do not.

**GlossaryList current bug (line 55):**
```tsx
{g.terms?.length ?? "—"}   // WRONG: list API never returns terms array
```
Backend `_glossary_to_dict` in glossaries.py returns `term_count: len(g.terms)` in list
response, not the `terms` array. Frontend type `Glossary` lacks `term_count` field.

**jobs.py _job_to_dict current state:** returns dict without `"glossary_id"` key.
`Job.glossary_id` exists on the ORM model — just needs to be added to the serializer.

**WR-02 location:** `frontend/src/hooks/useReviewKeyboard.ts`
The j/k hotkeys call `onFocusChange(Math.min(...))` without checking if `segmentCount === 0`.
When the filter produces an empty list, this computes -1 and scrolls Virtuoso to index -1.

**WR-03 location:** `frontend/src/components/SegmentRow.tsx`
The `patchMutation.mutate(...)` call passes `onSuccess` and `onError` inline callbacks that
call `setSaveState(...)`. If the component unmounts before the 500ms debounce fires (Virtuoso
virtual window), the callbacks fire on dead state. Add `isMountedRef` to guard them.

**Also IN-01 fix (opportunistic, same file as IN-03):**
`SegmentsResponse` in types.ts is missing `flag_counts: Record<string, number>`. Add it
to complete the type while types.ts is open. (ReviewFilterBar currently computes flag
counts client-side, which is equivalent — this is a type completeness fix only.)
</context>

<interfaces>
<!-- Key types and signatures the executor needs. Extracted from codebase. -->

From frontend/src/lib/types.ts (current state):
```typescript
export interface Glossary {
  id: string
  name: string
  source_lang: string
  target_lang: string
  created_at: string
  updated_at: string
  terms?: GlossaryTerm[]
  // MISSING: term_count: number
}

export interface SegmentsResponse {
  segments: Segment[]
  total: number
  // MISSING: flag_counts: Record<string, number>
}

export interface JobProgress {
  id?: string
  status: JobStatus
  // ... many fields ...
  // MISSING: glossary_id?: string | null
}
```

From backend/src/app/api/routes/jobs.py:
```python
def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "status": job.status.value,
        # ... all fields ...
        # MISSING: "glossary_id": job.glossary_id,
    }
```

From frontend/src/hooks/useReviewKeyboard.ts (pattern to guard):
```typescript
useHotkeys("j", () => {
  onFocusChange(Math.min(focusedIndex + 1, segmentCount - 1));
  // MISSING: if (segmentCount === 0) return;
}, ...)
```

From frontend/src/components/SegmentRow.tsx (mutation callbacks pattern):
```typescript
patchMutation.mutate(
  { id: segment.id, edited_text: value },
  {
    onSuccess: () => {
      setSaveState("saved");  // unsafe if unmounted
      ...
    },
    onError: () => setSaveState("idle"),  // unsafe if unmounted
  }
)
// MISSING: isMountedRef guard
```

NavBar import pattern (from review/page.tsx for reference):
```tsx
import { NavBar } from "@/components/NavBar"
// ...
return (
  <div>
    <NavBar />
    {/* page content */}
  </div>
)
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Fix types.ts (term_count, flag_counts, glossary_id) + backend glossary_id in response</name>
  <files>frontend/src/lib/types.ts, backend/src/app/api/routes/jobs.py</files>
  <action>
**frontend/src/lib/types.ts — three additions:**

1. Add `term_count: number` to `Glossary` interface:
```typescript
export interface Glossary {
  id: string
  name: string
  source_lang: string
  target_lang: string
  term_count: number          // IN-03: returned by list API as len(terms)
  created_at: string
  updated_at: string
  terms?: GlossaryTerm[]      // only populated by GET /glossaries/{id}
}
```

2. Add `flag_counts` to `SegmentsResponse` (IN-01):
```typescript
export interface SegmentsResponse {
  segments: Segment[]
  flag_counts: Record<string, number>   // IN-01: server-computed counts
  total: number
}
```

3. Add `glossary_id` to `JobProgress` interface:
```typescript
export interface JobProgress {
  id?: string
  status: JobStatus
  stage: JobStage | null
  segments_done: number
  segments_total: number
  current_batch: number
  retry_count: number
  last_message: string
  glossary_id?: string | null          // add this line
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
```

**backend/src/app/api/routes/jobs.py — add glossary_id to _job_to_dict:**

In the `_job_to_dict` function, add `"glossary_id": job.glossary_id,` to the returned
dict. A good place is after `"has_tracked_changes"`:
```python
def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "status": job.status.value,
        "stage": job.stage.value if job.stage else None,
        "source_lang": job.source_lang,
        "target_lang": job.target_lang,
        "detected_lang": job.detected_lang,
        "input_format": job.input_format,
        "original_filename": job.original_filename,
        "segments_done": job.segments_done,
        "segments_total": job.segments_total,
        "retry_count": job.retry_count,
        "error_msg": job.error_msg,
        "has_tracked_changes": job.has_tracked_changes,
        "glossary_id": job.glossary_id,             # add this
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
```

Verify TypeScript compiles with 0 Phase 2 errors:
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | grep -v "UploadForm.test" | head -20</automated>
  </verify>
  <done>
    `types.ts` has `term_count: number` in Glossary, `flag_counts` in SegmentsResponse, `glossary_id` in JobProgress.
    `jobs.py` _job_to_dict includes `"glossary_id": job.glossary_id`.
    TypeScript compilation passes with 0 new errors (only the 3 pre-existing TS18046 in UploadForm.test.tsx).
  </done>
</task>

<task type="auto">
  <name>Task 2: NavBar on glossary pages + GlossaryList term_count + WR-02/WR-03 frontend guards</name>
  <files>
    frontend/src/app/glossaries/page.tsx,
    frontend/src/app/glossaries/[id]/page.tsx,
    frontend/src/components/glossary/GlossaryList.tsx,
    frontend/src/hooks/useReviewKeyboard.ts,
    frontend/src/components/SegmentRow.tsx,
    frontend/src/app/jobs/[id]/review/page.tsx
  </files>
  <action>
**1. frontend/src/app/glossaries/page.tsx — add NavBar:**

Import NavBar and wrap the page content:
```tsx
"use client"
import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { GlossaryList } from "@/components/glossary/GlossaryList"
import { GlossaryCreateDialog } from "@/components/glossary/GlossaryCreateDialog"
import { NavBar } from "@/components/NavBar"   // add
import type { Glossary } from "@/lib/types"

export default function GlossariesPage() {
  // ... existing state and queries unchanged ...

  return (
    <div>
      <NavBar />                    {/* add NavBar at top */}
      <div className="px-8 py-8">
        {/* existing content unchanged */}
      </div>
    </div>
  )
}
```

**2. frontend/src/app/glossaries/[id]/page.tsx — add NavBar:**

Read this file first, then add the same `<NavBar />` pattern at the top of the returned JSX.
Import `{ NavBar } from "@/components/NavBar"` at the top.

**3. frontend/src/components/glossary/GlossaryList.tsx — fix IN-03:**

Change line 55 from:
```tsx
{g.terms?.length ?? "—"}
```
to:
```tsx
{g.term_count}
```
No other changes to this file.

**4. frontend/src/hooks/useReviewKeyboard.ts — WR-02: guard empty segment list:**

In the "j" hotkey handler, add early return when list is empty:
```typescript
useHotkeys(
  "j",
  () => {
    if (segmentCount === 0) return;
    onFocusChange(Math.min(focusedIndex + 1, segmentCount - 1));
  },
  { enableOnFormTags: false },
  [focusedIndex, segmentCount]
)
```
Apply the same guard to the "k" hotkey handler:
```typescript
useHotkeys(
  "k",
  () => {
    if (segmentCount === 0) return;
    onFocusChange(Math.max(focusedIndex - 1, 0));
  },
  { enableOnFormTags: false },
  [focusedIndex, segmentCount]
)
```

Also guard the `onEdit` callback consumer in `review/page.tsx`. Open
`frontend/src/app/jobs/[id]/review/page.tsx` and find the `onEdit` prop passed to
`useReviewKeyboard`. Add a bounds check:
```typescript
onEdit: (index) => {
  if (index < 0 || index >= filteredSegments.length) return;
  const seg = filteredSegments[index];
  // ... existing logic
},
```

**5. frontend/src/components/SegmentRow.tsx — WR-03: isMountedRef guard:**

Add `isMountedRef` near the other refs at the top of the component:
```typescript
const isMountedRef = useRef(true);
useEffect(() => {
  return () => {
    isMountedRef.current = false;
  };
}, []);
```

Then guard the `onSuccess` and `onError` callbacks inside `handleChange`:
```typescript
patchMutation.mutate(
  { id: segment.id, edited_text: value },
  {
    onSuccess: () => {
      if (!isMountedRef.current) return;
      setSaveState("saved");
      savedTimerRef.current = setTimeout(() => {
        if (isMountedRef.current) setSaveState("idle");
      }, 1500);
    },
    onError: () => {
      if (!isMountedRef.current) return;
      setSaveState("idle");
    },
  }
);
```

After all changes, verify TypeScript compilation:
```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -v "UploadForm.test" | head -30
```
Expected: 0 new errors.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | grep -v "UploadForm.test" | head -30</automated>
  </verify>
  <done>
    TypeScript compilation passes with 0 new errors.
    `grep "NavBar" frontend/src/app/glossaries/page.tsx` returns an import line.
    `grep "NavBar" frontend/src/app/glossaries/[id]/page.tsx` returns an import line.
    `grep "term_count" frontend/src/components/glossary/GlossaryList.tsx` returns the render line.
    `grep "segmentCount === 0" frontend/src/hooks/useReviewKeyboard.ts` returns 2 matches (j and k).
    `grep "isMountedRef" frontend/src/components/SegmentRow.tsx` returns multiple matches.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| API→frontend type | glossary_id flows from DB through _job_to_dict to frontend; value is server-generated UUID |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-09-01 | Information Disclosure | glossary_id in JobResponse | accept | glossary_id is a UUID; no sensitive data; consistent with other ID fields already in the response |
| T-02-09-02 | Denial | isMountedRef closure over stale ref | accept | `useRef` value persists across renders; cleanup effect runs synchronously on unmount before any async setState; React 18 Strict Mode double-invoke is benign |
</threat_model>

<verification>
```bash
# TypeScript clean
cd /home/thu/dev/projects/ai-translation/frontend
npx tsc --noEmit 2>&1 | grep -v "UploadForm.test" | head -10

# NavBar present on glossaries pages
grep "NavBar" frontend/src/app/glossaries/page.tsx
grep "NavBar" "frontend/src/app/glossaries/[id]/page.tsx"

# term_count used (not terms?.length)
grep "term_count" frontend/src/components/glossary/GlossaryList.tsx
grep -v "terms?.length" frontend/src/components/glossary/GlossaryList.tsx | grep -c "length" || echo "0 old pattern"

# glossary_id in backend response
grep "glossary_id" backend/src/app/api/routes/jobs.py

# WR-02 guard
grep "segmentCount === 0" frontend/src/hooks/useReviewKeyboard.ts

# WR-03 guard
grep "isMountedRef" frontend/src/components/SegmentRow.tsx

# Backend tests still pass
cd /home/thu/dev/projects/ai-translation/backend
uv run pytest tests/ -x -q --ignore=tests/integration 2>&1 | tail -5
```
</verification>

<success_criteria>
- TypeScript compilation: 0 new errors (only pre-existing TS18046 in UploadForm.test.tsx)
- NavBar renders on /glossaries page (import present in page.tsx)
- NavBar renders on /glossaries/[id] page (import present)
- GlossaryList uses `g.term_count` (not `g.terms?.length`)
- `Glossary` type has `term_count: number` in types.ts
- GET /jobs/{id} JSON includes `glossary_id` field (`grep` confirms in _job_to_dict)
- `useReviewKeyboard` j/k handlers guard against empty segment list
- `SegmentRow` has `isMountedRef.current` check in mutation callbacks
- Backend test suite remains green
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-09-SUMMARY.md` using the template at `@$HOME/.claude/get-shit-done/templates/summary.md`.
</output>
