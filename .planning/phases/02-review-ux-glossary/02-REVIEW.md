---
phase: 02-review-ux-glossary
reviewed: 2026-04-25T10:30:00Z
depth: standard
files_reviewed: 50
files_reviewed_list:
  - CLAUDE.md
  - backend/src/app/api/routes/export.py
  - backend/src/app/api/routes/glossaries.py
  - backend/src/app/api/routes/segments.py
  - backend/src/app/api/routes/upload.py
  - backend/src/app/core/config.py
  - backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py
  - backend/src/app/db/models.py
  - backend/src/app/main.py
  - backend/src/app/services/export_service.py
  - backend/src/app/services/glossary_service.py
  - backend/src/app/services/job_service.py
  - backend/src/app/workers/translate_worker.py
  - backend/tests/api/test_glossaries.py
  - backend/tests/api/test_segments.py
  - backend/tests/services/test_csv_import.py
  - backend/tests/services/test_export_service.py
  - backend/tests/services/test_glossary_service.py
  - backend/tests/services/test_post_check.py
  - backend/tests/services/test_tbx_import.py
  - backend/tests/workers/test_worker_glossary.py
  - frontend/e2e/phase-2-review.spec.ts
  - frontend/src/__tests__/FlagBadge.test.tsx
  - frontend/src/__tests__/GlossarySelect.test.tsx
  - frontend/src/__tests__/SegmentTable.test.tsx
  - frontend/src/__tests__/useSegments.test.ts
  - frontend/src/app/glossaries/[id]/page.tsx
  - frontend/src/app/glossaries/page.tsx
  - frontend/src/app/jobs/[id]/page.tsx
  - frontend/src/app/jobs/[id]/review/page.tsx
  - frontend/src/app/layout.tsx
  - frontend/src/components/FlagBadge.tsx
  - frontend/src/components/GlossarySelect.tsx
  - frontend/src/components/KeyboardHelpPanel.tsx
  - frontend/src/components/NavBar.tsx
  - frontend/src/components/ReviewFilterBar.tsx
  - frontend/src/components/ReviewPageHeader.tsx
  - frontend/src/components/SegmentRow.tsx
  - frontend/src/components/SegmentTable.tsx
  - frontend/src/components/UploadForm.tsx
  - frontend/src/components/glossary/CSVUploadButton.tsx
  - frontend/src/components/glossary/GlossaryCreateDialog.tsx
  - frontend/src/components/glossary/GlossaryList.tsx
  - frontend/src/components/glossary/TermsTable.tsx
  - frontend/src/hooks/useReviewKeyboard.ts
  - frontend/src/hooks/useSegments.ts
  - frontend/src/lib/review-types.ts
  - frontend/src/lib/types.ts
findings:
  critical: 0
  warning: 5
  info: 6
  total: 11
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-25T10:30:00Z
**Depth:** standard
**Files Reviewed:** 50
**Status:** issues_found

## Summary

Phase 2 delivers a substantial feature set across the full stack: glossary CRUD, CSV/TBX import, glossary injection into the translation worker, post-translation flag checking (overflow, glossary violation, placeholder mismatch, LLM refusal), the review editor UI with keyboard shortcuts, and DOCX export. The overall implementation quality is high — the design decisions are sound, error handling is generally present, and test coverage is meaningful for the service layer.

Five warnings and six info items were found. No critical (security/crash) issues were identified. The most significant warnings are: a duplicate type definition that creates a type-split risk across the frontend, a race condition in `SegmentRow`'s save-state when the component unmounts during a debounced save, a missing reset of `focusedIndex` bounds when the filter changes to a shorter list, and two minor logic gaps in the worker and glossary service.

## Warnings

### WR-01: Duplicate `Segment` / `SegmentFlag` type definitions split frontend type safety

**File:** `frontend/src/lib/review-types.ts:1-34` and `frontend/src/lib/types.ts:56-101`

**Issue:** `Segment`, `SegmentFlag`, `FlagType`, and `SegmentsResponse` are defined in both `review-types.ts` and `types.ts`. The two definitions are not identical — `types.ts` has `FlagSeverity` typed as `"info" | "warn" | "block"` while `review-types.ts` types `severity` as `string`. Components in `SegmentRow.tsx` and `ReviewFilterBar.tsx` import from `review-types.ts`; `FlagBadge.tsx` imports `FlagType` from `types.ts`. If a caller passes a `Segment` from one module to a component that expects the other module's shape, TypeScript will silently accept it (structurally compatible) but any future divergence will be invisible at the call site.

The comment in `review-types.ts` line 2 says these will be consolidated into `types.ts` by Plan 05, but Plan 05 is already complete per the SUMMARY files. The consolidation did not happen.

**Fix:** Delete `frontend/src/lib/review-types.ts` and update all imports in `SegmentRow.tsx`, `SegmentTable.tsx`, `ReviewFilterBar.tsx`, `useSegments.ts`, and `review/page.tsx` to import from `@/lib/types`. The `types.ts` definitions are the more complete versions (typed `FlagSeverity`, complete `Glossary` shape).

---

### WR-02: `focusedIndex` not clamped when filter narrows the segment list

**File:** `frontend/src/app/jobs/[id]/review/page.tsx:103-106`

**Issue:** When `onFilterChange` is called, `focusedIndex` is reset to `0` but only if the caller sets it. Looking at the handler:

```typescript
onFilterChange={(f) => {
  setActiveFilter(f);
  setFocusedIndex(0);
}}
```

This does reset to 0 on filter change, which is correct. However, if `filteredSegments.length` is 0 (no segments matching the filter), the keyboard handler `onFocusChange(Math.min(focusedIndex + 1, segmentCount - 1))` will compute `Math.min(0 + 1, 0 - 1)` = `Math.min(1, -1)` = `-1`. A focus index of `-1` will cause `filteredSegments[-1]` to be `undefined` in the `onEdit` handler (`filteredSegments[index]` at line 70), and the `onRegenerate` handler will call `handleFocusChange(-1)`, which calls `scrollToIndex(-1)` on Virtuoso — undefined behavior.

**Fix:** Guard against empty segment list in `useReviewKeyboard.ts`:
```typescript
// j: next segment
useHotkeys(
  "j",
  () => {
    if (segmentCount === 0) return;
    onFocusChange(Math.min(focusedIndex + 1, segmentCount - 1));
  },
  ...
```
Also guard in the `onEdit` callback in `review/page.tsx`:
```typescript
onEdit: (index) => {
  if (index < 0 || index >= filteredSegments.length) return;
  const seg = filteredSegments[index];
  ...
```

---

### WR-03: `SegmentRow` debounce timer can fire after component unmount, calling a stale mutation

**File:** `frontend/src/components/SegmentRow.tsx:86-107`

**Issue:** `handleChange` starts a 500ms debounce timer that calls `patchMutation.mutate(...)`. The cleanup `useEffect` at line 111-116 clears `debounceRef` and `savedTimerRef` on unmount. However, there is a subtle race: if the user types, immediately scrolls the segment out of the Virtuoso virtual window (causing unmount), and the debounce fires before the cleanup runs, `patchMutation.mutate` will be called on an already-unmounted component. TanStack Query's `useMutation` is resilient to this (mutations survive component unmount), but the `setSaveState("saved")` / `setSaveState("idle")` callbacks in the `onSuccess`/`onError` closures passed to `mutate()` call state setters on the unmounted component. In React 18 strict mode this is a no-op with a warning; in production it silently succeeds but sets state on a dead instance. More critically, if Virtuoso immediately remounts the same row (recycled renderer), the new instance's `saveState` will be `"idle"` while the inflight mutation completes and calls the old closure's `setSaveState` — the new instance never shows "Saved".

**Fix:** Use an `isMounted` ref to guard the `setSaveState` callbacks:
```typescript
const isMountedRef = useRef(true);
useEffect(() => {
  return () => { isMountedRef.current = false; };
}, []);

// In handleChange's mutate onSuccess:
onSuccess: () => {
  if (isMountedRef.current) {
    setSaveState("saved");
    savedTimerRef.current = setTimeout(() => {
      if (isMountedRef.current) setSaveState("idle");
    }, 1500);
  }
},
onError: () => {
  if (isMountedRef.current) setSaveState("idle");
},
```

---

### WR-04: Worker `segments_done` counter has a data race under concurrent batches

**File:** `backend/src/app/workers/translate_worker.py:337-338`

**Issue:** The `nonlocal segments_done` variable is incremented in `_translate_one_batch` which runs concurrently under `asyncio.gather`. In CPython's asyncio model with a single event loop, the increment itself is safe (no preemption between reads), but the read-modify-write `segments_done += len(batch_texts)` at line 338 is not atomic across `await` points. If `asyncio.gather` runs multiple batches and one batch's `await run_post_check(...)` suspends, another batch can execute its `segments_done += ...` before the first one resumes. In practice the gathered coroutines run cooperatively, so the increment happens in a non-suspended segment — but this is an implicit reliance on CPython cooperative scheduling rather than an explicit guarantee. If `worker_concurrency > 1`, two batches could interleave their increments incorrectly.

More concretely: the `update_job_progress` call at line 354 uses the mutated `segments_done` from whichever batch just finished, which races with another batch's mutation. The reported progress count in the DB / Redis can undercount (show the same value twice) or overcount (skip a value) depending on scheduling.

**Fix:** Use `asyncio.Lock` to guard the shared counter:
```python
_progress_lock = asyncio.Lock()

async def _translate_one_batch(...):
    nonlocal segments_done
    async with sem:
        results = await translate_batch_with_retry(...)
        for seg, translated in zip(batch_segs, results):
            translated_map[seg.id] = translated
        async with _progress_lock:
            segments_done += len(batch_texts)
            current_done = segments_done
        await run_post_check(...)
        await update_job_progress(session, job_id, current_done, ...)
```

---

### WR-05: `update_term` mutates a SQLAlchemy ORM object before the `IntegrityError` is catchable

**File:** `backend/src/app/services/glossary_service.py:170-185`

**Issue:** In `update_term`, the code mutates `t.source_term`, `t.target_term`, `t.notes` directly on the ORM model before calling `session.commit()`:

```python
if source_term is not None:
    ...
    t.source_term = source_term.strip()   # mutation happens here
...
try:
    await session.commit()
except IntegrityError:
    await session.rollback()
    raise
```

After `session.rollback()`, the `t` object is in an expired/detached state with the updated (but uncommitted) values still set on its Python attributes. The caller in `update_term_endpoint` (glossaries.py:274-291) catches the `IntegrityError` and returns a 409 response, so the caller never sees `t` in this state. However, if a caller were to access `t` after the rollback (e.g., to log its fields), the attributes would reflect the mutation that was never persisted. This is a violation of the coding style rule "ALWAYS create new objects, NEVER mutate existing ones" and could lead to subtle bugs if the pattern is extended.

The risk is currently low because the caller does not use `t` after the `IntegrityError` path, but this is a fragile pattern.

**Fix:** Use a SQL `UPDATE` statement instead of ORM attribute mutation, matching the pattern used in `patch_segment` (segments.py:137-141):
```python
updates: dict = {}
if source_term is not None:
    if len(source_term.strip()) < 2:
        raise ValueError("source_term must be at least 2 characters (D-02-07)")
    updates["source_term"] = source_term.strip()
if target_term is not None:
    if len(target_term.strip()) < 2:
        raise ValueError("target_term must be at least 2 characters (D-02-07)")
    updates["target_term"] = target_term.strip()
if notes is not None:
    updates["notes"] = notes
if not updates:
    return await get_term(session, term_id)  # nothing to update

try:
    await session.execute(
        update(GlossaryTerm).where(GlossaryTerm.id == term_id).values(**updates)
    )
    await session.commit()
except IntegrityError:
    await session.rollback()
    raise
return await get_term(session, term_id)
```

## Info

### IN-01: `SegmentsResponse` in `types.ts` is missing the `flag_counts` field returned by the API

**File:** `frontend/src/lib/types.ts:79-82`

**Issue:** The `GET /jobs/{id}/segments` endpoint returns `{ segments, flag_counts, total }` (segments.py:101-105). The `SegmentsResponse` interface in `types.ts` only declares `segments` and `total`, omitting `flag_counts`. The `useSegments` hook discards `flag_counts` silently. The `ReviewFilterBar` computes flag counts client-side by iterating `segments` — which is functionally equivalent but duplicates work the server already did.

**Fix:** Add `flag_counts` to `SegmentsResponse` in `types.ts` and optionally expose it from `useSegments` so `ReviewFilterBar` can use the server-computed counts directly:
```typescript
export interface SegmentsResponse {
  segments: Segment[]
  flag_counts: Record<string, number>
  total: number
}
```

---

### IN-02: `CSVUploadButton` accept attribute only allows `.csv` but the endpoint also accepts `.tbx`

**File:** `frontend/src/components/glossary/CSVUploadButton.tsx:55`

**Issue:** The hidden file input has `accept=".csv"` but the backend import endpoint (`POST /glossaries/{id}/terms/import`) accepts both `.csv` and `.tbx`. The button is named "Import CSV" in the UI and only accepts CSV, so `.tbx` files cannot be imported via the UI even though the backend supports them.

This is a feature gap, not a bug — the backend handles both. If TBX import is intentionally out of scope for the UI, the button label and component name are accurate. If TBX is intended to be supported in the UI, the accept attribute and button label should be updated.

**Fix (if TBX UI support is desired):**
```tsx
<input
  ref={inputRef}
  type="file"
  accept=".csv,.tbx"
  className="hidden"
  onChange={handleFileChange}
/>
```
And rename the button to "Import CSV / TBX".

---

### IN-03: `GlossaryList` displays `g.terms?.length` which is only available after `GET /glossaries/{id}` — the list endpoint does not return terms

**File:** `frontend/src/components/glossary/GlossaryList.tsx:54`

**Issue:** The `term_count` field is returned by the list endpoint serializer (`_glossary_to_dict`) as `len(g.terms) if g.terms is not None else 0`. The `Glossary` TypeScript interface in `types.ts` has `terms?: GlossaryTerm[]` (optional), but the glossary list API does NOT include `terms` in the list response (only `term_count`). `GlossaryList` renders `g.terms?.length ?? "—"`, which will always render `"—"` since the list endpoint never populates `terms`.

The backend does return `term_count` in the list response, but `types.ts` has no `term_count` field on the `Glossary` interface, so the frontend cannot access it.

**Fix:** Add `term_count` to the `Glossary` interface in `types.ts` and use it in `GlossaryList`:
```typescript
export interface Glossary {
  id: string
  name: string
  source_lang: string
  target_lang: string
  term_count: number          // add this
  created_at: string
  updated_at: string
  terms?: GlossaryTerm[]
}
```
```tsx
// In GlossaryList.tsx line 54:
<TableCell className="text-slate-600">
  {g.term_count}
</TableCell>
```

---

### IN-04: All frontend unit tests for Phase 2 components are `it.todo` stubs — zero actual assertions

**File:** `frontend/src/__tests__/FlagBadge.test.tsx`, `frontend/src/__tests__/GlossarySelect.test.tsx`, `frontend/src/__tests__/SegmentTable.test.tsx`, `frontend/src/__tests__/useSegments.test.ts`

**Issue:** All four frontend test files consist entirely of `it.todo(...)` stubs with the actual component imports commented out. The components they target (`FlagBadge`, `GlossarySelect`, `SegmentTable`, `useSegments`) are fully implemented. These tests do not provide any coverage. The project's CLAUDE.md global rules require 80% test coverage.

**Fix:** Implement the test bodies. The `it.todo` descriptions are well-written and map exactly to testable behavior — the implementation work is primarily: uncomment the imports, set up a React Testing Library render environment, and add assertions against the rendered output. Priority order by risk: `useSegments` (optimistic update / rollback logic is complex), `SegmentTable` (keyboard navigation), `FlagBadge` (simple, quick win).

---

### IN-05: `glossary_id` passed via `Form(None)` is not validated as a UUID format

**File:** `backend/src/app/api/routes/upload.py:48`

**Issue:** `glossary_id: str | None = Form(None)` accepts any string. The glossary existence check at line 94 correctly returns 422 if the glossary is not found, but a caller could pass `glossary_id="../../etc/passwd"` or other strings that are not UUIDs. The lookup `get_glossary(session, glossary_id)` executes `WHERE Glossary.id == glossary_id` with a parameterized query (safe from SQL injection), so there is no injection risk, but the absence of format validation allows unnecessary DB round-trips on invalid IDs.

**Fix:** Add a UUID format validator:
```python
import re
_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

if glossary_id is not None:
    if not _UUID_RE.match(glossary_id):
        raise HTTPException(status_code=422, detail="Invalid glossary_id format.")
    g = await get_glossary(session, glossary_id)
    ...
```

---

### IN-06: `delete_term` in `TermsTable.tsx` has no confirmation dialog, unlike glossary delete

**File:** `frontend/src/components/glossary/TermsTable.tsx:155-168`

**Issue:** `deleteTerm` at line 155 issues a DELETE request immediately on click without any confirmation. By contrast, `GlossaryList.tsx:65` uses `window.confirm(...)` before deleting a glossary. The asymmetry is minor (terms are described as "cheap to re-add" in the API docstring for `delete_term_endpoint`), but a mis-click on the delete icon in `TermsTable` is unrecoverable via the UI.

**Fix (low priority):** Either add a `window.confirm` before `deleteTerm`, or add an undo toast pattern. The current behavior matches the documented design intent so this is a UX preference rather than a defect.

---

_Reviewed: 2026-04-25T10:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
