---
phase: "03-pptx-native-pdf"
plan: "04"
subsystem: "backend/pipeline/pdf"
tags: ["pdf", "pymupdf", "column-clustering", "redact-reinsert", "noto-fonts"]
dependency_graph:
  requires: ["03-01", "03-02"]
  provides: ["pdf-extractor", "pdf-reassembler", "pdf-column-clustering"]
  affects: ["translate_worker.py (dispatch by format)", "SegmentFlag persistence"]
tech_stack:
  added: ["pymupdf.Archive", "pymupdf.Page.insert_htmlbox", "pymupdf.Page.add_redact_annot"]
  patterns: ["redact-reinsert 3-pass", "histogram gap detection", "dict-format span extraction"]
key_files:
  created:
    - backend/src/app/pipeline/pdf/__init__.py
    - backend/src/app/pipeline/pdf/columns.py
    - backend/src/app/pipeline/pdf/extractor.py
    - backend/src/app/pipeline/pdf/fonts.py
    - backend/src/app/pipeline/pdf/reassembler.py
  modified: []
decisions:
  - "Use dict format (not rawdict) for span extraction — rawdict has chars not text; dict has text+flags"
  - "Trailing histogram gaps ignored — page right-margin is not a column separator"
  - "Archive spans both truetype/noto and opentype/noto dirs — CJK fonts are in opentype per wave-0-noto-paths.txt"
metrics:
  duration: "~20 minutes"
  completed: "2026-04-25T19:46:43Z"
  tasks_completed: 3
  files_created: 5
---

# Phase 03 Plan 04: Native PDF Pipeline Summary

**One-liner:** PyMuPDF redact-reinsert PDF pipeline with histogram-based 2-column clustering, dict-format span-to-HTML extraction, Noto font archive builder, and overflow-detected htmlbox reinsertion.

## What Was Built

Five new files implementing the full native PDF translation pipeline under `backend/src/app/pipeline/pdf/`:

| File | Exports | Purpose |
|------|---------|---------|
| `__init__.py` | — | Package marker |
| `columns.py` | `cluster_columns()` | Histogram gap detection for 1/2/degraded column layouts |
| `fonts.py` | `build_noto_archive_and_css()` | PyMuPDF Archive + @font-face CSS for Noto fonts |
| `extractor.py` | `extract_pdf_segments()`, `spans_to_html()` | Block walk, column clustering, HTML generation |
| `reassembler.py` | `reassemble_pdf()` | 3-pass redact-reinsert with overflow detection |

## Decisions Made

### D-impl-01: dict format over rawdict for span extraction
The plan references `rawdict` for span data, but `rawdict` spans have `chars` (individual character dicts) not `text` strings. The `dict` format provides `text` + `flags` in each span and is clip-correct (only `html` format ignores clip). Used `dict` for full-page block extraction and reused the block data directly for `spans_to_html()`.

### D-impl-02: Trailing histogram gap excluded from column gap detection
Initial implementation counted trailing zero-bins (page right-margin) as a column gap, causing a single left-aligned text block to be split into 2 columns. Fixed `_find_gaps()` to only count gaps that are flanked by occupied bins on both sides — leading/trailing zeros are page margins, not column separators.

### D-impl-03: Archive covers both truetype and opentype Noto directories
`wave-0-noto-paths.txt` confirms CJK fonts (`NotoSansCJK-Regular.ttc`) are installed at `/usr/share/fonts/opentype/noto/` while Latin/VN fonts are at `/usr/share/fonts/truetype/noto/`. `build_noto_archive_and_css()` builds an `Archive` spanning both directories.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed trailing histogram gap causing false 2-col detection**
- **Found during:** Task 1 verification
- **Issue:** `_find_gaps()` counted the page right-margin zero-bins as a column gap. A single block on the left side of a 595pt page had 14 trailing empty bins (> the 6-bin threshold), yielding 2 groups instead of 1.
- **Fix:** Added `seen_content` flag to `_find_gaps()` — only gaps preceded AND followed by occupied bins are counted as column separators.
- **Files modified:** `backend/src/app/pipeline/pdf/columns.py`
- **Commit:** `0b87ee4`

**2. [Rule 1 - Bug] Switched from rawdict to dict format in extractor**
- **Found during:** Task 2 verification
- **Issue:** Plan references `rawdict` for per-block span data, but rawdict spans have `chars` lists (per-character), not `text` strings. `spans_to_html()` looks up `span.get("text", "")`, returning empty string for every rawdict span, producing 0 segments from real PDFs.
- **Fix:** Updated extractor docstring + comments to use `dict` format throughout. `dict` format has `text` + `flags` in spans and clip works correctly (only `html` format ignores clip).
- **Files modified:** `backend/src/app/pipeline/pdf/extractor.py`
- **Commit:** `c525dbd`

**3. [Rule 1 - Bug] Fixed inaccurate PDF_REDACT_IMAGE_NONE comment**
- **Found during:** Task 3 verification
- **Issue:** Code comment said "images=1: do NOT remove images" but `pymupdf.PDF_REDACT_IMAGE_NONE = 0` (not 1). `PDF_REDACT_IMAGE_REMOVE = 1`.
- **Fix:** Updated comment to say "images=0: preserve images (do NOT remove)".
- **Files modified:** `backend/src/app/pipeline/pdf/reassembler.py`
- **Commit:** `8aad4c2`

## Contract Verification

All plan `must_haves.truths` verified:

| Truth | Verified |
|-------|---------|
| `cluster_columns()` returns 1 group for single-col | Yes — tested with single block at left side of 595pt page |
| `cluster_columns()` returns 2 groups for 2-col with gap >= 30% | Yes — tested with left (mid=115) and right (mid=465) blocks on 595pt page |
| `cluster_columns()` returns `is_degraded=True` for 3+ col | Yes — tested with 3 blocks on 300pt page with 30%+ gaps |
| `extract_pdf_segments()` produces Segments with `page.` prefix positions | Yes — outputs `page.0.col.0.block.0` format |
| `reassemble_pdf()` uses add_redact_annot → apply_redactions → insert_htmlbox order | Yes — verified by source position (p1 < p2 < p3) |
| `insert_htmlbox` called with `scale_low=0.7` | Yes — present in Pass 3 |
| Non-text content preserved via `PDF_REDACT_IMAGE_NONE` | Yes — `images=pymupdf.PDF_REDACT_IMAGE_NONE` in apply_redactions |

## Module Import Verification

```
backend/src/app/pipeline/pdf/__init__.py  ✓ exists (empty)
backend/src/app/pipeline/pdf/columns.py   ✓ def cluster_columns(
backend/src/app/pipeline/pdf/fonts.py     ✓ def build_noto_archive_and_css(
backend/src/app/pipeline/pdf/extractor.py ✓ def extract_pdf_segments( + def spans_to_html(
backend/src/app/pipeline/pdf/reassembler.py ✓ def reassemble_pdf(
```

All 48 existing pipeline tests still pass (0 regressions).

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | `0b87ee4` | feat(pipeline): add PDF column clustering and Noto font builder |
| 2 | `c525dbd` | feat(pipeline): add PDF extractor with block extraction and span-to-HTML |
| 3 | `8aad4c2` | feat(pipeline): add PDF reassembler with redact-reinsert workflow |

## Known Stubs

None — all functions are fully implemented. Font lookup falls back gracefully to filename strings when fonts aren't installed on the dev machine; the Docker container has the correct Noto fonts at the expected paths.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: exception-swallowed | `reassembler.py:131-145` | Per-block `except Exception` logs + appends to overflow_flags but continues — intentional T-03-03 isolation; not a silent swallow |

## Self-Check: PASSED

- All 5 created files exist on disk
- All 3 task commits verified present (0b87ee4, c525dbd, 8aad4c2)
- 48 existing pipeline tests pass with no regressions
- All plan contract elements present in source (verified by grep + import checks)
