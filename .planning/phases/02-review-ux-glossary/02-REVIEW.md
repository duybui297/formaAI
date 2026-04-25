---
phase: 02-review-ux-glossary
reviewed: 2026-04-25T14:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - backend/src/app/workers/translate_worker.py
  - backend/tests/workers/test_segment_persistence.py
  - backend/src/app/api/routes/jobs.py
  - frontend/src/lib/types.ts
  - frontend/src/components/NavBar.tsx
  - frontend/src/app/glossaries/page.tsx
  - frontend/src/app/glossaries/[id]/page.tsx
  - frontend/src/components/glossary/GlossaryList.tsx
  - frontend/src/app/jobs/[id]/review/page.tsx
  - frontend/src/components/SegmentRow.tsx
  - frontend/src/hooks/useReviewKeyboard.ts
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 02 Gap-Closure: Code Review Report

**Reviewed:** 2026-04-25T14:00:00Z
**Depth:** standard
**Files Reviewed:** 11 (gap-closure plans 02-08 segment persistence + session recovery; 02-09 polish)
**Status:** issues_found

## Summary

This review covers the 11 files modified by gap-closure plans 02-08 (segment persistence, session recovery) and 02-09 (polish gaps). The gap-closure work is well-structured: the new test file directly exercises the two gaps it claims to fix, and the `SegmentRow` unmount-safety fix (`isMountedRef`) is already present in the current code.

One significant architectural bug was found: the `asyncio.gather` in `translate_worker.py` runs multiple batch coroutines that share a single SQLAlchemy `AsyncSession`, which is unsafe for concurrent use. This is the most important finding. Two additional warnings cover an `updated_at` field gap in `_job_to_dict` and a temp-file leak in the new test fixture. Four info items address type completeness, a missing error path, and a minor UX omission.

## Warnings

### WR-01: Shared `AsyncSession` used concurrently across `asyncio.gather` batches

**File:** `backend/src/app/workers/translate_worker.py:347-401`

**Issue:** `_translate_one_batch` is defined as an inner coroutine that closes over `session`. When `asyncio.gather` launches all batch coroutines simultaneously, multiple coroutines call `await session.execute(...)` and `await session.flush()` on the same `AsyncSession` instance concurrently. SQLAlchemy's `AsyncSession` is a **single-connection, single-transaction object that is not safe for concurrent coroutine use**. At every `await` point inside one batch coroutine, the event loop may resume another batch coroutine that also issues `session.execute()` — interleaving operations in the same transaction context in unpredictable order and corrupting the session state.

Concrete failure modes:
- Two `session.execute(sa_update(...))` calls interleave, causing one UPDATE to be lost or both to be applied against the wrong row identity.
- `session.flush()` is called by batch A while batch B is mid-execution, flushing incomplete data for batch B's rows.
- If `run_post_check` issues INSERTs (flag rows) inside the shared session while another batch coroutine is also INSERTing, the flush-order is undefined and a duplicate key error can silently consume one batch's flag rows.

The `worker_concurrency=1` cap at the `Semaphore` level means only one batch is inside the `sem` block at a time — but the `asyncio.gather` still creates all coroutines up front, and the `sem` only gates the LLM call. The `session.execute` / `session.flush` / `run_post_check` calls are all inside the `async with sem:` block, so with `worker_concurrency=1` only one batch holds the semaphore at a time and the session operations do not actually interleave. However, this correctness guarantee is fragile: it depends on `worker_concurrency=1` being invariant (a config value, not a code invariant), and the semaphore structure itself does not prevent a reader from bumping `worker_concurrency` on a paid tier and triggering the race silently.

**Fix:** Move all DB operations out of the shared session inside the coroutine, or — the cleaner fix — use a per-batch session from the session factory rather than sharing the outer session:

```python
async def _translate_one_batch(
    batch_id: int, batch_texts: list[str], batch_segs: list
) -> None:
    nonlocal segments_done
    async with sem:
        results = await translate_batch_with_retry(...)
        # Use a fresh session per batch — safe for concurrent use
        async with ctx["session_factory"]() as batch_session:
            for seg, translated in zip(batch_segs, results):
                translated_map[seg.id] = translated
                await batch_session.execute(
                    sa_update(SegmentORM)
                    .where(SegmentORM.id == seg.id)
                    .values(translated_text=translated)
                )
            await run_post_check(
                session=batch_session,
                ...
            )
            await batch_session.commit()
        async with ctx["session_factory"]() as prog_session:
            segments_done += len(batch_texts)
            await update_job_progress(prog_session, job_id, segments_done, ...)
            await prog_session.commit()
        await _publish_progress(...)
```

Alternatively, if keeping the shared session is required, add a module-level `asyncio.Lock` to serialize all session operations:

```python
_session_lock = asyncio.Lock()

async def _translate_one_batch(...):
    nonlocal segments_done
    async with sem:
        results = await translate_batch_with_retry(...)
        async with _session_lock:
            for seg, translated in zip(batch_segs, results):
                ...
                await session.execute(sa_update(...).values(...))
            await session.flush()
            segments_done += len(batch_texts)
            await run_post_check(session=session, ...)
            await update_job_progress(session, ...)
        await _publish_progress(...)
```

---

### WR-02: `_job_to_dict` omits `updated_at` field that `types.ts` expects

**File:** `backend/src/app/api/routes/jobs.py:31-53`

**Issue:** The `JobProgress` / `JobSummary` interfaces in `frontend/src/lib/types.ts` reference `updated_at` as a standard field on job objects. The `_job_to_dict` serializer at line 31 includes `"created_at"` (line 51) but does **not** include `"updated_at"`. The `updated_at` field exists on the `Job` ORM model (it is a standard SQLAlchemy `DateTime` column). Any frontend code that reads `job.updated_at` from the REST response will always get `undefined`.

The `JobSummary` type in `types.ts` (line 46–54) does not declare `updated_at` — so this is not yet causing a TypeScript error — but the `JobProgress` interface (line 5–27) also doesn't declare it explicitly, though `updated_at` appears in the backend docstring comment at line 78 in `jobs.py` as one of the returned D-10 fields.

**Fix:** Add `updated_at` to `_job_to_dict`:

```python
"updated_at": job.updated_at.isoformat() if job.updated_at else None,
```

Insert after line 52 (`"created_at": ...`).

---

### WR-03: Temp file created in `_make_minimal_docx` leaks on test failure

**File:** `backend/tests/workers/test_segment_persistence.py:24-31`

**Issue:** `_make_minimal_docx` creates a temp file with `delete=False` and returns its path. The `job` fixture stores the path but never schedules cleanup — neither in a `yield`-based cleanup block nor via `tmp_path` (which is pytest-managed). If the test fails between fixture setup and teardown, the `.docx` file is left in the system's temp directory. On a CI runner this is harmless but accumulates across runs; in a shared dev environment it can cause false positives if a stale file is accidentally reused.

**Fix:** Pass the temp file through `tmp_path` (which pytest cleans up automatically) instead of `tempfile.NamedTemporaryFile`:

```python
def _make_minimal_docx(tmp_path) -> str:
    """Write a DOCX with one paragraph to a tmp_path file; return path."""
    doc = DocxDocument()
    doc.add_paragraph("Hello world")
    path = str(tmp_path / "test.docx")
    doc.save(path)
    return path
```

And update the `job` fixture signature to accept `tmp_path`:

```python
@pytest_asyncio.fixture
async def job(session_factory, tmp_path):
    docx_path = _make_minimal_docx(tmp_path)
    ...
```

The three test functions already receive `tmp_path` — the same `tmp_path` fixture instance is passed to both `job` and the test body within the same test invocation.

## Info

### IN-01: `translate_worker.py` — `segments_done` counter has no lock under concurrent batches

**File:** `backend/src/app/workers/translate_worker.py:350, 370`

**Issue:** The `nonlocal segments_done` increment at line 370 (`segments_done += len(batch_texts)`) runs inside the `async with sem:` block. As noted in WR-01, with `worker_concurrency=1` only one batch holds the semaphore at a time, so in practice this never races. But if `worker_concurrency` is bumped, two batches can hold the semaphore simultaneously and `segments_done += len(batch_texts)` becomes a non-atomic read-modify-write across `await` points. The reported progress in DB/Redis can undercount or skip values. This is secondary to WR-01 but worth noting separately.

**Fix:** If WR-01 is addressed with a per-batch session, move the counter increment into a single async-safe update (e.g., use `asyncio.Lock` around just the counter increment, or derive `segments_done` from a count query rather than an in-memory accumulator).

---

### IN-02: `GlossaryList` renders `g.term_count` correctly but the field was missing from `types.ts` in earlier phase; confirm it is now present

**File:** `frontend/src/components/glossary/GlossaryList.tsx:55` and `frontend/src/lib/types.ts:96-104`

**Issue:** `GlossaryList` at line 55 renders `{g.term_count}`. The `Glossary` interface in `types.ts` does include `term_count: number` at line 98 — this is correctly typed. This is a **resolved** item from the previous broader review (IN-03 in `02-REVIEWS.md`). No action needed; confirmed correct.

---

### IN-03: `useReviewKeyboard` `escape` handler uses `enableOnFormTags` but not `enableOnContentEditable`

**File:** `frontend/src/hooks/useReviewKeyboard.ts:76-80`

**Issue:** The `escape` handler at line 76 sets `enableOnFormTags: ["textarea"]` so pressing Escape inside the translation textarea blurs it. This is correct for `<textarea>` elements. If any segment cells are later changed to use `contentEditable` divs (e.g., for rich text), the Escape key will not fire inside them because `contentEditable` elements require `enableOnContentEditable: true`. This is a forward-looking concern — currently all editing uses `<Textarea>` and the hook is correct.

**Fix (preemptive, low priority):** Add `enableOnContentEditable: true` to the escape handler options so the behavior stays consistent if the editor is ever upgraded:

```typescript
useHotkeys(
  "escape",
  () => (document.activeElement as HTMLElement)?.blur(),
  { enableOnFormTags: ["textarea"], enableOnContentEditable: true }
);
```

---

### IN-04: `GlossariesPage` delete mutation has no error handling — silent failure on 404/409

**File:** `frontend/src/app/glossaries/page.tsx:23-29`

**Issue:** The `deleteMutation` at line 23 has `onSuccess` (invalidates cache) but no `onError` callback. If the DELETE request fails (e.g., glossary is currently attached to a running job and the backend returns 409), the UI silently does nothing — the glossary stays in the list (TanStack Query does not re-fetch on mutation error by default), and the user receives no feedback. There is no toast or alert.

**Fix:** Add a minimal `onError` handler:

```typescript
const deleteMutation = useMutation({
  mutationFn: (id: string) =>
    fetch(`/api/glossaries/${id}`, { method: "DELETE" }).then((r) => {
      if (!r.ok) throw new Error(`Delete failed: ${r.status}`)
    }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["glossaries"] }),
  onError: (err) => {
    // Replace with toast when a toast library is available
    console.error("Failed to delete glossary:", err)
    alert("Failed to delete glossary. It may be in use by a running job.")
  },
})
```

---

_Reviewed: 2026-04-25T14:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
