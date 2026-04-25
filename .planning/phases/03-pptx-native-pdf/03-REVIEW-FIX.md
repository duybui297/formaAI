---
phase: 03-pptx-native-pdf
fixed_at: 2026-04-26T00:00:00Z
review_path: .planning/phases/03-pptx-native-pdf/03-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-04-26
**Source review:** .planning/phases/03-pptx-native-pdf/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6
- Fixed: 6
- Skipped: 0

## Fixed Issues

### WR-02: `cluster_columns` returns `[[]]` for empty input

**Files modified:** `backend/src/app/pipeline/pdf/columns.py`
**Commit:** d3e4c2d
**Applied fix:** Changed `return [[]], False` to `return [], False` on the empty-input early-return guard. Future callers checking `len(column_groups) == 0` or `if not column_groups:` now correctly detect the empty case.

---

### WR-03: HTML tag injection from un-escaped span text in `spans_to_html`

**Files modified:** `backend/src/app/pipeline/pdf/extractor.py`
**Commit:** 2549d7e
**Applied fix:** Added `import html as _html` at module top-level. Inside `spans_to_html`, added `escaped = _html.escape(text)` immediately after text extraction and replaced all tag-wrapped interpolations (`<b>{text}</b>`, `<i>{text}</i>`, `<b><i>{text}</i></b>`, and bare `text`) with the `escaped` variable. PDF span text containing `<`, `>`, or `&` no longer produces malformed HTML that would silently corrupt `page.insert_htmlbox()` output.

---

### WR-04: PPTX table overflow detection silent dead path

**Files modified:** `backend/src/app/pipeline/pptx/reassembler.py`
**Commit:** 2443bd9
**Applied fix:** Added `detect_pptx_overflow(cell, seg.source_text, translated)` call inside `_write_back_table` immediately after `_write_paragraph_runs`, appending results to `overflow_results` when `overflow` or `auto_adjusted` is True. `cell` is passed as the shape argument because `_Cell` has a `text_frame` attribute, which is what `detect_pptx_overflow` accesses for `auto_size`. Table cells now produce LAYOUT-02 overflow/auto-adjusted flags the same way text frames do.

---

### WR-05: `submitWithAction` missing `glossaryId` from `useCallback` dependency array

**Files modified:** `frontend/src/components/UploadForm.tsx`
**Commit:** 9ca75d3
**Applied fix:** Added `glossaryId` to the `useCallback` dependency array for `submitWithAction` (was `[file, targetLang, sourceLang, router, toast]`, now `[file, targetLang, sourceLang, glossaryId, router, toast]`). This closes the stale-closure bug where changing the glossary selection after the callback was memoized would submit with the old `glossaryId`.

---

### WR-01: Race condition in `segments_done` counter across concurrent batches

**Files modified:** `backend/src/app/workers/translate_worker.py`
**Commit:** 416aeca
**Applied fix:** Replaced the shared `nonlocal segments_done` integer (mutated via `+=` across concurrent coroutines) with a `batch_done_counts: list[int]` pre-allocated to `len(batch_seg_groups)`. Each coroutine writes only to `batch_done_counts[batch_id]` — its own index — then calls `sum(batch_done_counts)` for the progress emit. Since exactly one coroutine ever writes index `i`, there is no contention. Note: this finding involves a logic/concurrency fix and requires human verification that progress reporting is correct end-to-end.

---

### WR-06: `_translate_one_batch` closure shares SQLAlchemy session across concurrent coroutines

**Files modified:** `backend/src/app/workers/translate_worker.py`
**Commit:** 416aeca
**Applied fix:** Moved all DB writes (`session.execute`, `session.flush`, `run_post_check`, `update_job_progress`) out of `_translate_one_batch` and into a sequential loop that runs after `asyncio.gather` completes. During the gather, coroutines only write to the in-memory `translated_map` dict (safe — dict assignment is synchronous and each key is written by exactly one coroutine). The sequential post-gather loop processes batches one at a time, ensuring no two concurrent coroutines ever touch the shared `AsyncSession`. Note: this is a concurrency/logic fix and requires human verification of correct DB write ordering.

---

_Fixed: 2026-04-26_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
