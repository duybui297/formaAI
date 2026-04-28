---
phase: 04-scanned-pdf-ocr
plan: "02"
subsystem: backend
tags: [ocr, pipeline, paddleocr, fpdf2, tdd, green-phase]
dependency_graph:
  requires:
    - 04-01 (Segment OCR fields, conftest mock fixtures, RED test stubs)
  provides:
    - detect_scanned_pdf() text-density heuristic
    - extract_scanned_pdf_segments() PP-StructureV3 async wrapper
    - compose_bilingual_pdf() double-wide PDF composer
    - compose_translated_only_pdf() single-column translated PDF
    - segments_to_markdown() Segment tree to Markdown helper
    - md_to_docx() Markdown to DOCX via python-docx
  affects:
    - backend/src/app/pipeline/scanned_pdf/ (new module, 5 files)
    - backend/tests/pipeline/test_scanned_pdf_detector.py (RED → GREEN)
    - backend/tests/pipeline/test_scanned_pdf_extractor.py (RED → GREEN)
    - backend/tests/pipeline/test_scanned_pdf_composer.py (RED → GREEN)
    - backend/tests/pipeline/test_segment_to_md.py (RED → GREEN)
tech_stack:
  added: []
  patterns:
    - asyncio.to_thread() wrapping PaddleOCR sync API (event-loop safety)
    - Polygon bbox (4,2) numpy ndarray → axis-aligned rect via min/max
    - Normalized [0,1] bbox with T-04-05 clamp guard
    - fpdf2 double-wide page topology (D-04-07)
    - Region-positioned multi_cell with fit-to-region font sizing (D-04-29)
    - Helvetica fallback when Noto fonts absent (CI/dev environments)
    - Text priority: edited_source_text ?? translated_text ?? source_text
key_files:
  created:
    - backend/src/app/pipeline/scanned_pdf/__init__.py
    - backend/src/app/pipeline/scanned_pdf/detector.py
    - backend/src/app/pipeline/scanned_pdf/extractor.py
    - backend/src/app/pipeline/scanned_pdf/composer.py
    - backend/src/app/pipeline/scanned_pdf/segment_to_md.py
  modified:
    - backend/tests/pipeline/test_scanned_pdf_detector.py
    - backend/tests/pipeline/test_scanned_pdf_extractor.py
    - backend/tests/pipeline/test_scanned_pdf_composer.py
    - backend/tests/pipeline/test_segment_to_md.py
decisions:
  - "Noto font fallback: composer uses Helvetica when /backend/fonts/NotoSans-Regular.ttf absent — enables unit tests to run in CI without binary font files"
  - "Polygon bbox handling: _extract_bbox() uses numpy slicing block_bbox_raw[:, 0].min() not flat [x0,y0,x1,y1] indexing (RESEARCH.md Pitfall 1)"
  - "Per-page error isolation: OCR exceptions produce placeholder segment + continue, never terminate job (D-04-31)"
  - "DOCX export: python-docx (already in stack) chosen over PP-StructureV3 save_to_word() — gives full control over translated Segment state (D-04-33)"
  - "segment_to_md uses edited_source_text as the reviewer-edit field (Segment dataclass has no edited_text field, only edited_source_text per D-04-03)"
metrics:
  duration_minutes: 18
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 4
  completed_date: "2026-04-28"
---

# Phase 4 Plan 02: OCR Pipeline Module — detector, extractor, composer, segment_to_md

One-liner: Four-file scanned_pdf pipeline module implemented — PP-StructureV3 async OCR extractor, text-density detector, fpdf2 double-wide bilingual composer, and Markdown/DOCX export helper; all 16 Wave 0 RED tests turned GREEN.

## What Was Built

### Task 1: detector.py and extractor.py

**detector.py** — `detect_scanned_pdf(doc, threshold=50.0) -> bool`
- Text-density heuristic per D-04-17: `total_chars / page_count < threshold`
- Empty doc (0 pages) → False (not scanned, just empty)
- Configurable threshold parameter (default 50 chars/page)
- Structured log output with chars_per_page, threshold, is_scanned

**extractor.py** — `extract_scanned_pdf_segments(doc, job_id, pages_dir, pipeline, dpi=300, concurrency=1) -> tuple[list[Segment], list[int]]`

Core OCR integration:
- Page PNG extraction via `page.get_pixmap(dpi=dpi)` → saves to `pages_dir/page-{N}.png`
- Pixmap released immediately after save (T-04-04: ~8MB per page memory management)
- PaddleOCR sync API wrapped in `asyncio.to_thread()` to avoid blocking arq event loop
- Mixed-PDF per-page detection (D-04-18): pages with extractable text fallback to `kind="text"`

Bbox handling:
- `_extract_bbox()`: polygon (4,2) numpy ndarray → axis-aligned rect using `block_bbox_raw[:, 0].min()` not flat indexing (RESEARCH.md Pitfall 1)
- `_normalize_bbox()`: pixel coords → [0,1] with `max(0.0, min(1.0, ...))` clamp (T-04-05 threat mitigation)

Passthrough labels (D-04-24):
- `_PASSTHROUGH_LABELS` frozenset: `{"image", "chart", "figure", "formula", "formula_number", "algorithm", "seal", "page_number"}`
- These produce `kind="figure_passthrough"` with `source_text="[Figure on left]"`

Confidence gating (D-04-02):
- `page_mean_conf = mean(rec_scores)` from `overall_ocr_res`; defaults to 1.0 if list empty
- `page_mean_conf < 0.7` → page_num appended to `low_confidence_pages`

Per-page error isolation (D-04-31):
- Exception from `asyncio.to_thread` → placeholder `"[OCR failed for this page]"` segment, confidence=0.0, page added to low_confidence_pages, job continues

Block ordering (D-04-20):
- Blocks sorted by `block_order` (PP-StructureV3 multi-column reading-order recovery); None values sorted last

### Task 2: composer.py and segment_to_md.py

**composer.py** — `compose_bilingual_pdf()` + `compose_translated_only_pdf()`

Bilingual PDF (D-04-07/08):
- `FPDF(unit="mm")` — millimetre unit throughout
- `_pt_to_mm(pt)`: PDF points → mm via `pt * 25.4 / 72.0`
- Per page: `add_page(format=(2 * src_w_mm, src_h_mm))` — double-wide
- Left half: `pdf.image(png_path, x=0, y=0, w=src_w_mm, h=src_h_mm, keep_aspect_ratio=True)`
- Right half: `_render_region()` called per segment, sorted by `region_bbox[1]` (y-coord, top→bottom)

Region rendering (D-04-08/29):
- Position: `x_mm = src_w_mm + x0n * src_w_mm`, `y_mm = y0n * src_h_mm`
- Fit-to-region: tries font sizes `[24, 18, 14, 10, 8]` pts, picks largest that fits via `_estimate_fits()`
- Overflow flag: if 8pt still overflows, appends to `overflow_flags` list (out-parameter), renders at 8pt anyway
- Label-based initial size hints: `doc_title→18pt`, `paragraph_title→14pt`, `footnote→8pt`

Font handling:
- Registers NotoSans + NotoSansCJK when found at `/backend/fonts/` (D-04-27)
- Falls back to built-in Helvetica when absent (CI/dev without binary font files)
- `set_fallback_fonts(["NotoSansCJK"])` for CJK rendering when available

Translated-only PDF: same region positions, `right_offset_mm=0.0`, single-width `format=(src_w_mm, src_h_mm)`

**segment_to_md.py** — `segments_to_markdown()` + `md_to_docx()`

Markdown emission (D-04-33):
- Sorted by `seq_in_job`
- `doc_title` → `# heading`; `paragraph_title`/`header` → `## heading`
- `table` → block_content as-is (PP-StructureV3 emits Markdown table format)
- `figure_passthrough` → `[Figure]`
- `seal`/`page_number` → skipped
- Text priority: `edited_source_text ?? translated_text ?? source_text`
- Blank line between all blocks

DOCX export: python-docx `Document()` → heading level 1/2 from `#`/`##` prefix, paragraph for plain lines

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Noto font fallback for CI environments**
- **Found during:** Task 2 — Noto fonts not committed to git (documented in `backend/fonts/README.md`, Plan 01 decision)
- **Issue:** Without font fallback, `compose_bilingual_pdf()` would crash in any environment lacking the binary font files, making unit tests impossible in CI
- **Fix:** `_init_pdf()` checks `os.path.exists(_NOTO_SANS)` before `add_font()`, falls back to built-in Helvetica. Logs debug-level warning when Noto absent (not warning, since expected in dev/CI)
- **Files modified:** `backend/src/app/pipeline/scanned_pdf/composer.py`
- **Commit:** 1c06ebb

**2. [Rule 1 - Bug] `edited_source_text` field name in segment_to_md**
- **Found during:** Task 2 — plan spec referenced `seg.edited_text` but Segment dataclass uses `edited_source_text` (D-04-03 field name)
- **Fix:** Used `seg.edited_source_text` in the text priority chain per the actual dataclass definition
- **Files modified:** `backend/src/app/pipeline/scanned_pdf/segment_to_md.py`
- **Commit:** 1c06ebb

## Known Stubs

None. All four modules are fully implemented. The `compose_bilingual_pdf()` left-side image render is skipped when `page-{N}.png` does not exist (correct for test environments where page images are not pre-extracted), but the page topology (double-wide format) is always correct.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. All threat mitigations from plan threat model are implemented:
- T-04-04: Pixmap released with `del pixmap` after save
- T-04-05: `_normalize_bbox()` clamps to [0,1]
- T-04-06: Placeholder text contains no sensitive info
- T-04-07: fpdf2 auto-subsets at output time; no action needed in code
- T-04-08: `asyncio.to_thread` wrapping verified (no privilege escalation path)

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/src/app/pipeline/scanned_pdf/__init__.py` | FOUND |
| `backend/src/app/pipeline/scanned_pdf/detector.py` | FOUND |
| `backend/src/app/pipeline/scanned_pdf/extractor.py` | FOUND |
| `backend/src/app/pipeline/scanned_pdf/composer.py` | FOUND |
| `backend/src/app/pipeline/scanned_pdf/segment_to_md.py` | FOUND |
| Commit 40eb29e (Task 1: detector + extractor) | FOUND |
| Commit 1c06ebb (Task 2: composer + segment_to_md) | FOUND |
| 16/16 unit tests GREEN | PASSED |
| Double-wide page: `add_page(format=(2 * src_w_mm, src_h_mm))` | FOUND |
| Polygon bbox: `block_bbox_raw[:, 0].min()` | FOUND |
| asyncio.to_thread wrapping | FOUND |
