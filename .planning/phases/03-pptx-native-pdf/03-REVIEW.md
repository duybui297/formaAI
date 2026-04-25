---
phase: 03-pptx-native-pdf
reviewed: 2026-04-26T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - backend/src/app/pipeline/pdf/__init__.py
  - backend/src/app/pipeline/pdf/columns.py
  - backend/src/app/pipeline/pdf/extractor.py
  - backend/src/app/pipeline/pdf/fonts.py
  - backend/src/app/pipeline/pdf/reassembler.py
  - backend/src/app/pipeline/pptx/__init__.py
  - backend/src/app/pipeline/pptx/extractor.py
  - backend/src/app/pipeline/pptx/reassembler.py
  - backend/src/app/pipeline/pptx/smartart.py
  - backend/src/app/workers/translate_worker.py
  - backend/tests/llm/test_schemas.py
  - backend/tests/pipeline/test_pdf_roundtrip.py
  - backend/tests/pipeline/test_pptx_roundtrip.py
  - backend/tests/pipeline/test_pptx_smartart.py
  - frontend/src/__tests__/UploadForm.test.tsx
  - frontend/src/components/FlagBadge.tsx
  - frontend/src/components/SegmentRow.tsx
  - frontend/src/components/UploadForm.tsx
  - frontend/src/lib/formatBreadcrumb.ts
  - frontend/src/lib/review-types.ts
  - frontend/src/lib/types.ts
findings:
  critical: 0
  warning: 6
  info: 5
  total: 11
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-04-26
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Phase 03 introduces native PDF (redact-reinsert) and PPTX pipelines alongside the existing DOCX pipeline, extending the worker to dispatch across three format paths, adding overflow/auto-adjusted detection for both formats, and delivering frontend breadcrumb display, FlagBadge differentiation (AUTO-FIT vs OVERFLOW), and the SegmentRow editing UX.

The code is well-structured overall. Critical correctness risks are absent. Six warnings are present, primarily around a race condition in the worker's concurrent-batch translate loop, a data-loss risk when `cluster_columns` returns an empty-list sentinel for empty input, a minor HTML-injection surface in PDF extractor, and a real-but-masked structural mismatch in the PPTX table overflow path. Five informational items cover type duplication, dead-code comments, and minor code-quality concerns.

---

## Warnings

### WR-01: Race condition in `segments_done` counter across concurrent batches

**File:** `backend/src/app/workers/translate_worker.py:418`
**Issue:** `segments_done += len(batch_texts)` inside `_translate_one_batch` mutates a `nonlocal` integer that is shared across all concurrent coroutines running under `asyncio.gather`. Because `+=` on an integer is not atomic in CPython's asyncio event loop (it involves a read, add, and write with potential interleaving at any `await` boundary between them), two batches completing near-simultaneously can both read the same stale value and produce an incorrect final count. The progress bar calculation and `_publish_progress` calls will emit wrong `segments_done` values.

**Fix:** Use an accumulator that is safe under concurrent async mutations — either push the increment after the gather, or track a per-batch count and sum them at emit time:

```python
# Option A: accumulate per-batch counts into a list, sum at publish time
batch_done_counts: list[int] = [0] * len(batch_seg_groups)

async def _translate_one_batch(batch_id: int, ...) -> None:
    async with sem:
        ...
        batch_done_counts[batch_id] = len(batch_texts)
        segments_done_now = sum(batch_done_counts)
        await _publish_progress(..., segments_done=segments_done_now, ...)
```

This is safe because each index is written by exactly one coroutine.

---

### WR-02: `cluster_columns` returns `[[]]` (list containing empty list) for empty input

**File:** `backend/src/app/pipeline/pdf/columns.py:88`
**Issue:** When `text_blocks` is empty the function returns `([[]], False)`. The caller in `extractor.py` iterates `column_groups` and then iterates each `col_blocks` list. An empty inner list produces no Segments, so extraction is harmless. However, the reassembler (`reassembler.py:77`) also calls `cluster_columns` and then builds `pos_to_block` by walking the same groups — an empty inner list is iterated safely there too.

The real risk is that downstream code that checks `len(column_groups) == 0` to mean "no columns found" will be surprised: `len([[]])` is `1`, not `0`. Any future caller doing `if not column_groups:` would not detect the empty case. The sentinel is subtly wrong — `([], False)` is the correct empty-columns return.

**Fix:**
```python
if not text_blocks:
    return [], False   # empty list, not list-containing-empty-list
```

---

### WR-03: HTML tag injection from un-escaped span text in `spans_to_html`

**File:** `backend/src/app/pipeline/pdf/extractor.py:54-61`
**Issue:** `spans_to_html` concatenates raw span text into HTML fragments without escaping:

```python
parts.append(f"<b>{text}</b>")
parts.append(f"<i>{text}</i>")
```

If a PDF span text contains `<`, `>`, or `&` — entirely possible in natural text, code snippets, or math PDFs — the resulting HTML is malformed. When this HTML is fed to `page.insert_htmlbox()` in the reassembler the rendering engine may silently drop the block or produce corrupt output. PyMuPDF's htmlbox is a limited HTML renderer, not a browser, so the failure mode is invisible (no exception, just missing text).

**Fix:** Escape before wrapping in tags:

```python
import html as _html

def spans_to_html(block: dict) -> str:
    parts: list[str] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")
            if not text:
                continue
            escaped = _html.escape(text)   # escapes <, >, &, "
            flags = span.get("flags", 0)
            is_bold = bool(flags & (2**4))
            is_italic = bool(flags & (2**1))
            if is_bold and is_italic:
                parts.append(f"<b><i>{escaped}</i></b>")
            elif is_bold:
                parts.append(f"<b>{escaped}</b>")
            elif is_italic:
                parts.append(f"<i>{escaped}</i>")
            else:
                parts.append(escaped)
        parts.append(" ")
    return "".join(parts).strip()
```

---

### WR-04: PPTX table overflow detection silently returns empty list (dead path)

**File:** `backend/src/app/pipeline/pptx/reassembler.py:105-121`
**Issue:** `_write_back_table` builds an `overflow_results` list and returns it, but the list is **never populated** — the loop writes translated text but calls no overflow detection. Contrast this with `_write_back_text_frame` which correctly calls `detect_pptx_overflow`. The `overflow_results` list is always `[]` for table cells. Table cells will silently expand with no `SegmentFlag.overflow` or `SegmentFlag.auto_adjusted` record written, defeating LAYOUT-02 for PPTX tables.

**Fix:** After `_write_paragraph_runs`, call `detect_pptx_overflow` the same way `_write_back_text_frame` does:

```python
def _write_back_table(table, translated_map, seg_by_pos, shape_pos) -> list[dict]:
    overflow_results: list[dict] = []
    for row_idx, row in enumerate(table.rows):
        for col_idx, cell in enumerate(row.cells):
            for para_idx, para in enumerate(cell.text_frame.paragraphs):
                pos = f"{shape_pos}.table.row.{row_idx}.col.{col_idx}.para.{para_idx}"
                seg = seg_by_pos.get(pos)
                if seg is None:
                    continue
                translated = translated_map.get(seg.id, seg.source_text)
                _write_paragraph_runs(para, translated)
                # BUG FIX: detect overflow for table cells too
                result = detect_pptx_overflow(cell, seg.source_text, translated)
                if result["overflow"] or result["auto_adjusted"]:
                    overflow_results.append({"segment_id": seg.id, **result})
    return overflow_results
```

Note: `detect_pptx_overflow` takes `shape` as its first arg; pass `cell` (a `_Cell` object) rather than the table shape — `cell` has a `text_frame` attribute, which is what `auto_size` is set on inside `detect_pptx_overflow`.

---

### WR-05: `submitWithAction` missing from `useCallback` dependency array in `UploadForm`

**File:** `frontend/src/components/UploadForm.tsx:285-295`
**Issue:** `submitWithAction` (line 97) is defined via `useCallback` with `[file, targetLang, sourceLang, router, toast]` as dependencies. Inside the `TrackedChangesModal`'s `onApply` handler (line 285-289), `submitWithAction` is called as a closure. However `onApply` is an inline function passed directly as a JSX prop — it is recreated on every render and captures `submitWithAction` from the surrounding render scope. This is **not** a stale-closure bug in the rendering sense (it captures the latest reference because it's inline), but there is a real risk: `handleFile` (line 47) is also `useCallback` but declares only `[toast]` as its dependency. It calls `setFile`, `setTrackedAction`, etc. — all stable setter refs — so this specific `handleFile` dependency list is correct.

The actual bug is in `onDrop` at line 75-87: it declares `[handleFile, toast]` as deps but `toast` is redundant since it's already captured through `handleFile`. This is a minor lint warning, not a runtime bug. More importantly, `submitWithAction` captures `glossaryId` (line 105) but `glossaryId` is **absent** from the `useCallback` dependency array (line 136: `[file, targetLang, sourceLang, router, toast]`). If the user changes the glossary after the callback is memoized, the stale closure will submit with the old `glossaryId`.

**Fix:**
```typescript
const submitWithAction = useCallback(
  async (action: "strip" | "preserve" | null) => { ... },
  [file, targetLang, sourceLang, glossaryId, router, toast]  // add glossaryId
)
```

---

### WR-06: `_translate_one_batch` closure mutates `translated_map` dict without coordination

**File:** `backend/src/app/workers/translate_worker.py:409-411`
**Issue:** Multiple coroutines running under `asyncio.gather` all write into the shared `translated_map` dict. In CPython's asyncio model this is safe *only* because dict assignment (`d[k] = v`) does not cross an `await` boundary mid-operation. However, the `zip(batch_segs, results)` loop at line 409 does iterate across multiple assignments between `await` boundaries — specifically, `results` is fully materialized before the loop starts, so the loop body is synchronous. This is currently safe.

The risk is subtle but worth noting: any future refactor that adds an `await` inside the zip loop would introduce a real race. The pattern is fragile. More concretely, `session.execute` at line 413 is awaited inside the same `async with sem:` block but after the dict writes, so the current ordering is safe only because the semaphore serializes the `await session.execute` calls (not really — multiple coroutines can hold the semaphore simultaneously at different `await` points).

Actually `asyncio.Semaphore` only gates entry; multiple coroutines *inside* the `async with sem:` block run concurrently between their own `await` points. The `session` object is shared across all concurrent `_translate_one_batch` calls. SQLAlchemy async sessions are **not thread-safe and not coroutine-safe** for concurrent use. Two concurrent batches calling `await session.execute(sa_update(...))` and `await session.flush()` on the same session object can corrupt the session state.

**Fix:** Each batch should use a scoped sub-session, or the session mutations should be consolidated outside the concurrent gather (post-translate loop). Alternatively, collect all `(seg.id, translated)` pairs and execute them in a single bulk UPDATE after gather completes:

```python
# After asyncio.gather completes, do DB writes outside the concurrent section
await session.execute(
    sa_update(SegmentORM),
    [{"id": seg_id, "translated_text": text} for seg_id, text in translated_map.items()]
)
await session.flush()
```

---

## Info

### IN-01: Duplicate type definitions across `review-types.ts` and `types.ts`

**File:** `frontend/src/lib/review-types.ts:1-37` and `frontend/src/lib/types.ts:57-91`
**Issue:** `FlagType`, `SegmentFlag`, `Segment`, and `SegmentsResponse` are defined in both files. `review-types.ts` has a slightly different `SegmentsResponse` (missing `flag_counts`), and `SegmentFlag` uses `severity: string` vs `severity: FlagSeverity` in `types.ts`. Code that imports from `review-types.ts` gets a weaker type for severity. The comment in `review-types.ts` acknowledges the duplication and defers consolidation to Plan 05.
**Fix:** Consolidate into `types.ts` and delete `review-types.ts`, or re-export the canonical types from `review-types.ts`: `export type { FlagType, Segment, SegmentFlag, SegmentsResponse } from "@/lib/types"`.

---

### IN-02: `InlineFlagBadge` in `SegmentRow` does not differentiate AUTO-FIT vs OVERFLOW

**File:** `frontend/src/components/SegmentRow.tsx:30-41`
**Issue:** `InlineFlagBadge` uses a static `FLAG_LABELS` record and shows "Overflow" for all `overflow` flags regardless of `details.auto_adjusted`. `FlagBadge.tsx` correctly implements the M2 contract (AUTO-FIT label for `auto_adjusted=true`) but `SegmentRow` has its own inline badge implementation that ignores the `auto_adjusted` detail.
**Fix:** Either pass `details` to `InlineFlagBadge` and mirror the `FlagBadge` logic, or replace the inline badge with a `<FlagBadge>` import (removing the "plan 05 scope" deferral comment since the types are already available).

---

### IN-03: `structlog` imported inside exception handler (deferred import pattern)

**File:** `backend/src/app/pipeline/pdf/reassembler.py:133`
**Issue:** `import structlog` is deferred to inside a `try/except` block with a `# noqa: PLC0415` suppression. The comment exists elsewhere in the codebase (worker uses many deferred imports for format-specific libs), but `structlog` is a core infrastructure dependency that is always available — there is no reason to defer it. Deferred imports inside exception handlers are especially surprising because a failed import would raise `ImportError` and suppress the original exception.
**Fix:** Move `import structlog` to the module top-level in `reassembler.py`.

---

### IN-04: `_write_back_notes` ignores overflow — inconsistent with text frame path

**File:** `backend/src/app/pipeline/pptx/reassembler.py:124-136`
**Issue:** `_write_back_notes` writes translations back to speaker notes paragraphs but does not call `detect_pptx_overflow` and returns `None` instead of a list. Speaker notes can expand just as much as body text. The function signature and the `_write_back_text_frame` pattern suggest overflow detection was intended for notes too but was omitted.
**Fix:** Return `list[dict]` and call `detect_pptx_overflow` per paragraph, or document explicitly that speaker note overflow is out of scope for this phase.

---

### IN-05: `formatBreadcrumb` returns raw input on empty string but docstring implies it returns the raw string only for unknown patterns

**File:** `frontend/src/lib/formatBreadcrumb.ts:15`
**Issue:** `if (!structuralPosition) return structuralPosition` returns `""` when called with an empty string. This is benign (the SegmentRow renders an empty breadcrumb span), but the early-return type is `string` while the caller expects a possibly-undefined structural_position from the `Segment` type (`structural_position?: string | null`). If called with `null` or `undefined`, `structuralPosition` would be falsy and return `null`/`undefined`, yet the TypeScript signature declares `(structuralPosition: string): string` — the caller in `SegmentRow` already guards `segment.structural_position &&` before calling, so this does not currently crash, but the type is misleading.
**Fix:** Accept the actual input type: `(structuralPosition: string | null | undefined): string` and return `""` for null/undefined.

---

_Reviewed: 2026-04-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
