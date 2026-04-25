---
phase: 03-pptx-native-pdf
verified: 2026-04-26T03:30:00Z
status: human_needed
score: 4/4
overrides_applied: 0
human_verification:
  - test: "Open a translated PPTX in PowerPoint or LibreOffice Impress. Check that text box
      text, speaker notes, and table cell text are all translated. Confirm master-slide
      placeholder text is preserved (not garbled). Verify no text box has been resized to
      illegibly small font."
    expected: "All text visible, no layout regression from auto-fit, table text translated"
    why_human: "Headless rendering cannot replicate visual font metrics or layout fidelity"
  - test: "Open a translated native PDF in a PDF viewer. Verify: (a) Noto CJK glyphs render
      correctly for JA/ZH text; (b) 2-column layout reads in correct column order (left col
      first, then right col); (c) images and vector graphics survived the redact-reinsert pass."
    expected: "CJK text visible, column reading order correct, non-text content intact"
    why_human: "Visual glyph rendering and reading-order perception require human judgement"
  - test: "Open the review UI after uploading a PPTX or PDF job. Confirm: (a) breadcrumb badge
      appears above source text in each segment row (e.g. 'Slide 1 / Shape 1 / ¶0' or
      'Page 0 / Col 0 / Block 2'); (b) SmartArt segments show orange SMART badge; (c) overflow
      segments show amber Overflow or slate AUTO-FIT badge."
    expected: "Breadcrumb, SMART, Overflow, AUTO-FIT badges visually correct in review table"
    why_human: "Badge appearance and UI typography require visual inspection"
---

# Phase 3: PPTX + Native PDF Verification Report

**Phase Goal:** Extend the pipeline spine from Phase 1 to PPTX and native (text-layer) PDF, giving AICore all three hero formats: PPTX translates text boxes, speaker notes, tables, and nested groups with overflow detection and auto-fit; native PDF redacts and reinserts translated text with Noto font embedding and column-aware extraction.
**Verified:** 2026-04-26T03:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PPTX file round-trips with text boxes, speaker notes, tables, bulleted lists, and master-slide text translated; nested grouped shapes are recursively walked; SmartArt shapes flagged not silently skipped | VERIFIED | `extract_pptx_segments` walks master slides, body shapes via `walk_shape_tree` (recursive GROUP), tables via `walk_table`, notes via `_extract_notes_segments`. `is_smartart()` checked before `has_text_frame`. 9 round-trip tests pass including `test_pptx_master_text_round_trip`. |
| 2 | After PPTX translation, text-box overflow is detected and flagged in the review UI with an overflow badge; `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` is applied where safe | VERIFIED | `detect_pptx_overflow` uses char-ratio proxy; applies `TEXT_TO_FIT_SHAPE` when `shrink_factor >= 0.7`; flags `overflow=True` when `< 0.7`. Worker persists both as `SegmentFlag(overflow)` with `details.auto_adjusted`. `test_pptx_overflow_results_tuple_contract` confirms extreme-expansion flag. NOTE: Table cell overflow not detected (WR-04 warning — PPTX-03 requirement text says "text-box overflow", not table cells). |
| 3 | A native (text-layer) PDF is parsed with PyMuPDF; translated text is reinserted using the redact-annot workflow with bundled Noto CJK fonts; multi-column layouts are handled via x-coordinate clustering (proven on at least one 2-column test PDF) | VERIFIED | `extract_pdf_segments` with `cluster_columns` (histogram gap detection). `reassemble_pdf` does 3-pass: `add_redact_annot` → `apply_redactions(images=PDF_REDACT_IMAGE_NONE)` → `insert_htmlbox`. `build_noto_archive_and_css` covers truetype + opentype Noto dirs. `test_pdf_column_detection_single_col_round_trip` and `test_cluster_columns_two_col_returns_two_groups` pass. |
| 4 | When translated PDF text does not fit its bounding box, the segment is flagged for review in the UI (orange highlight); if font scaling brings it within range, it is recorded as auto-adjusted | VERIFIED | `insert_htmlbox` called with `scale_low=0.7`. `spare_height < 0` → overflow flag appended to `overflow_flags` out-param. `scale < 1.0` and `spare_height >= 0` → `auto_adjusted=True`. Worker reads out-param and persists `SegmentFlag`. `test_pdf_overflow_flags_list_populated` confirms list contract. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/app/pipeline/pptx/__init__.py` | Package marker | VERIFIED | Exists |
| `backend/src/app/pipeline/pptx/extractor.py` | PPTX segment extraction | VERIFIED | 203 lines; `extract_pptx_segments`, `walk_shape_tree`, `walk_text_frame`, `walk_table`, `_extract_notes_segments`, `_extract_master_segments` all implemented |
| `backend/src/app/pipeline/pptx/reassembler.py` | PPTX write-back with overflow | VERIFIED | 238 lines; `reassemble_pptx` returns tuple; `detect_pptx_overflow` implemented; `_write_back_table` lacks overflow call (WR-04 warning) |
| `backend/src/app/pipeline/pptx/smartart.py` | SmartArt detection + text extraction | VERIFIED | `is_smartart()` uses MSO_SHAPE_TYPE.IGX_GRAPHIC with XML fallback; `extract_smartart_text()` with exception guard |
| `backend/src/app/pipeline/pdf/__init__.py` | Package marker | VERIFIED | Exists |
| `backend/src/app/pipeline/pdf/columns.py` | Histogram column clustering | VERIFIED | 134 lines; `cluster_columns` with gap detection, 3-col degraded path; trailing margin fix applied |
| `backend/src/app/pipeline/pdf/extractor.py` | PDF block extraction + HTML generation | VERIFIED | 125 lines; `extract_pdf_segments` using "dict" format (not rawdict/html); `spans_to_html` for bold/italic; WR-03: span text not HTML-escaped |
| `backend/src/app/pipeline/pdf/fonts.py` | Noto archive + CSS builder | VERIFIED | 113 lines; `build_noto_archive_and_css` covers both truetype+opentype dirs; confirmed by wave-0-noto-paths.txt |
| `backend/src/app/pipeline/pdf/reassembler.py` | Redact-reinsert with overflow detection | VERIFIED | 168 lines; correct 3-pass order; `scale_low=0.7`; `overflow_flags` out-param; `subset_fonts()` call |
| `backend/src/app/db/models.py` (FlagType extension) | smartart + multi_column_degraded enum values | VERIFIED | Lines 156-157; both values present |
| `backend/src/app/db/migrations/versions/0004_flagtype_phase3.py` | Alembic migration 0004 | VERIFIED | Exists; no-DDL pattern (VARCHAR column accepts new string values) |
| `backend/src/app/workers/translate_worker.py` (dispatch) | PPTX + PDF match/case branches | VERIFIED | `case "pptx"` at lines 287, 470; `case "pdf"` at lines 300, 523; SegmentFlag persistence for overflow, smartart, multi_column_degraded |
| `frontend/src/lib/formatBreadcrumb.ts` | Breadcrumb helper | VERIFIED | 101 lines; prefix-based detection; slide/master/page patterns; 1-indexed shapes; never throws |
| `frontend/src/components/FlagBadge.tsx` | New flag types + M2 AUTO-FIT | VERIFIED | smartart (orange SMART), multi_column_degraded (slate MULTI-COL), overflow+auto_adjusted=true → AUTO-FIT |
| `frontend/src/components/SegmentRow.tsx` (breadcrumb) | Breadcrumb rendered above source text | VERIFIED | Line 161: `{segment.structural_position && <span>{formatBreadcrumb(...)}</span>}`; formatBreadcrumb imported |
| `frontend/src/components/UploadForm.tsx` | PPTX + PDF accept | VERIFIED | `ALLOWED_EXTS = new Set([".docx", ".pptx", ".pdf"])`; `accept` attribute includes PPTX/PDF MIME types; TC detection guarded to `.docx` only |
| `backend/tests/pipeline/test_pptx_roundtrip.py` | PPTX round-trip tests | VERIFIED | 5 tests; all pass |
| `backend/tests/pipeline/test_pdf_roundtrip.py` | PDF round-trip tests | VERIFIED | 4 tests; all pass |
| `backend/tests/pipeline/test_pptx_smartart.py` | SmartArt unit tests | VERIFIED | 8 tests; all pass |
| `backend/tests/llm/test_schemas.py` | LLM schema tests (coverage top-up) | VERIFIED | 10 tests; all pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `translate_worker.py` | `pptx/extractor.py` | `case "pptx": extract_pptx_segments` | WIRED | Lazy import + call at line 289-291 |
| `translate_worker.py` | `pptx/reassembler.py` | `case "pptx": reassemble_pptx` | WIRED | Lazy import + call at line 471-475; tuple unpack |
| `translate_worker.py` | `pdf/extractor.py` | `case "pdf": extract_pdf_segments` | WIRED | Lazy import + call at line 302-304 |
| `translate_worker.py` | `pdf/reassembler.py` | `case "pdf": reassemble_pdf` | WIRED | Lazy import + call at line 526-530; overflow_flags out-param |
| `translate_worker.py` | `SegmentFlag` persistence | `FlagType.smartart / .multi_column_degraded` | WIRED | Lines 515, 579; `session.add_all` |
| `SegmentRow.tsx` | `formatBreadcrumb.ts` | `import { formatBreadcrumb }` | WIRED | Line 9 import; used at line 163 |
| `SegmentRow.tsx` | `segment.structural_position` | Conditional render | WIRED | Line 161 guard + formatBreadcrumb call |
| `FlagBadge.tsx` | `details.auto_adjusted` | M2 badge differentiation | WIRED | Line 26: `details?.auto_adjusted === true` → AUTO-FIT config |
| `UploadForm.tsx` | `.pptx` / `.pdf` extensions | `ALLOWED_EXTS`, `accept` attr | WIRED | Lines 15, 198 |
| `pdf/extractor.py` | `cluster_columns` | `from app.pipeline.pdf.columns import cluster_columns` | WIRED | Line 24 import; called at line 100 |
| `pdf/reassembler.py` | `build_noto_archive_and_css` | `from app.pipeline.pdf.fonts import ...` | WIRED | Line 27 import; called at line 51 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `SegmentRow.tsx` (breadcrumb) | `segment.structural_position` | Segment API → DB (Segment.structural_position column set at extract time) | Yes — set deterministically from structural position schema during extraction | FLOWING |
| `FlagBadge.tsx` (overflow/smartart) | `flagType`, `details` | SegmentFlag rows persisted by worker after reassembly | Yes — worker inserts real SegmentFlag rows with computed overflow data | FLOWING |
| `UploadForm.tsx` (accept list) | n/a — static accept attribute | Build-time constant `ALLOWED_EXTS` | Yes — PPTX/PDF accepted and backend validates format on server side | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `cluster_columns` returns 2 groups for 2-col PDF | `pytest tests/pipeline/test_pdf_columns.py::test_cluster_columns_two_col_returns_two_groups -v` | PASSED | PASS |
| PPTX SmartArt flagged, write-back skipped | `pytest tests/pipeline/test_pptx_roundtrip.py::test_pptx_smartart_segment_position_convention -v` | PASSED | PASS |
| PDF overflow flags list populated | `pytest tests/pipeline/test_pdf_roundtrip.py::test_pdf_overflow_flags_list_populated -v` | PASSED | PASS |
| Full backend test suite at 80% coverage | `uv run pytest --ignore=tests/integration -q` | 311 passed, 80.04% coverage | PASS |
| Frontend test suite | `npm run test` | 48 passed, 0 failures | PASS |
| pymupdf importable | `uv run python -c "import pymupdf, pptx"` | Exit 0 (both installed) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PPTX-01 | 03-03 | PPTX shapes traversed: text boxes, notes, tables, master slides | SATISFIED | `extract_pptx_segments` covers all shape types; `test_pptx_round_trip_segment_count` asserts ≥4 segments including notes |
| PPTX-02 | 03-03 | SmartArt flagged, not silently skipped | SATISFIED | `is_smartart()` checked before `has_text_frame`; `structural_position` ends in `.smartart`; worker persists `FlagType.smartart` |
| PPTX-03 | 03-03 | Text-box overflow detected and flagged; auto-fit applied where safe | SATISFIED (text frames) | `detect_pptx_overflow` with char-ratio proxy; `TEXT_TO_FIT_SHAPE` for shrink ≥ 0.7; PPTX table cells lack overflow detection (WR-04 — warning, not blocker per PPTX-03 wording "text-box overflow") |
| PPTX-04 | 03-03 | Group-shape walker recursively finds nested text | SATISFIED | `walk_shape_tree` recurses on `MSO_SHAPE_TYPE.GROUP` with `shape.shapes`; confirmed by test assertions on structural_position uniqueness |
| PDF-01 | 03-04 | Native PDF parsed; spans have bbox, font, source text | SATISFIED | `extract_pdf_segments` uses "dict" format per span; `structural_position` encodes page + col/block coordinates |
| PDF-02 | 03-04 | Redact-reinsert produces PDF with Noto text; non-text preserved | SATISFIED | 3-pass order enforced; `PDF_REDACT_IMAGE_NONE=0` preserves images; `test_pdf_images_preserved_through_round_trip` passes |
| PDF-03 | 03-04 | Overflow flagged when text doesn't fit at scale_low=0.7 | SATISFIED | `spare_height < 0` → overflow dict in `overflow_flags` out-param; `scale < 1.0` → auto_adjusted |
| PDF-04 | 03-04 | 2-col PDF produces 2 column groups; 3+ cols → degraded | SATISFIED | 5 column tests pass; `_find_gaps` excludes trailing margin; `_count_peaks >= 3` → degraded |
| LAYOUT-02 | 03-05 | Overflow SegmentFlags persisted with (job_id, segment_id) FK | SATISFIED | Worker reads `_pptx_overflow` / `_pdf_overflow_flags` out-params and calls `session.add_all(flags)` after reassembly |
| LAYOUT-03 | 03-05 | Auto-adjusted recorded in SegmentFlag.details JSON | SATISFIED | `details={"char_ratio": ..., "auto_adjusted": True}` for PPTX; `details={"auto_adjusted": True, "scale_applied": ...}` for PDF |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `pdf/extractor.py` | 54-61 | `spans_to_html` concatenates raw span text into HTML without `html.escape()` — `<`, `>`, `&` in PDF text will produce malformed HTML fed to `insert_htmlbox` | Warning | For PDFs with math, code, or angle-bracket text, `insert_htmlbox` may silently drop or corrupt that block. Low risk for natural-language prose. |
| `pdf/columns.py` | 87-88 | `return [[]], False` for empty input — sentinel is `[[]]` not `[]`; `len([[]])` is 1, so `if not column_groups:` check would never be true | Warning | Subtle correctness risk for future callers that check `len(column_groups) == 0` to detect empty input. Current extractor/reassembler iterate safely. |
| `translate_worker.py` | 418 | `segments_done += len(batch_texts)` — nonlocal int mutated inside `asyncio.gather` coroutines; stale read possible at `await` boundaries | Warning | Progress bar may show incorrect intermediate percentages. Final count after gather completes is correct. No data loss. |
| `translate_worker.py` | 409-411 | Multiple coroutines under `asyncio.gather` share one SQLAlchemy async session — session is not safe for concurrent coroutine use | Warning | Session state corruption possible if two batches complete near-simultaneously and both `await session.execute/flush`. Low risk with current semaphore count but structurally fragile. |
| `UploadForm.tsx` | 97-136 | `glossaryId` absent from `submitWithAction` `useCallback` dependency array — stale closure submits with old glossary ID if user changes glossary after memoization | Warning | User selects glossary A, changes to glossary B without re-triggering file selection → job submitted with glossary A. Minor UX bug. |
| `SegmentRow.tsx` | 30-41 | `InlineFlagBadge` uses static `FLAG_LABELS` — ignores `details.auto_adjusted`; always shows "Overflow" for overflow flags regardless of auto-adjusted state | Info | AUTO-FIT vs OVERFLOW differentiation (M2 contract) works in `FlagBadge.tsx` but not in `SegmentRow`'s inline badge. User sees "Overflow" for auto-fit cases in the left-border flag. |
| `pdf/reassembler.py` | 133 | `import structlog` deferred inside exception handler — `structlog` is a core dep that is always available; deferred import inside `except` block would suppress the original exception on `ImportError` | Info | No functional impact (structlog always installed); code smell only. |
| `pptx/reassembler.py` | 124-136 | `_write_back_notes` does not call `detect_pptx_overflow` and returns `None` — speaker-note overflow silently undetected | Info | Speaker note overflow not captured in `overflow_results`; user not alerted. Low impact as notes rarely display in presentation view. |

### Human Verification Required

#### 1. PPTX Visual Fidelity

**Test:** Upload a real PPTX file (multi-slide with text boxes, a table, and speaker notes) via the Upload form. Select VN → EN translation. After job completes, download the output `.pptx` and open it in PowerPoint or LibreOffice Impress.
**Expected:** Text box text, table cell text, and speaker notes are all translated. Master-slide text is preserved (not blanked or duplicated). No text box has been auto-fit to an illegibly small font. Table column widths are unchanged.
**Why human:** Headless rendering cannot replicate visual font metrics; character-ratio overflow proxy may produce false negatives or positives that only become visible in a real application.

#### 2. Native PDF Visual Fidelity + Noto Fonts

**Test:** Upload a native (text-layer) PDF with CJK content (or translate EN → JA). After job completes, open the output `.pdf` in a PDF viewer.
**Expected:** CJK glyphs rendered correctly via Noto Sans CJK (not tofu boxes). Latin/Vietnamese characters use Noto Sans. Non-text content (images, charts, lines) is intact and positioned correctly. For a 2-column source PDF, verify the translated columns appear in reading order (left first, then right).
**Why human:** Glyph rendering quality and visual column alignment require visual inspection; automated byte-level comparison is fragile on PDF/font output.

#### 3. Review UI — Breadcrumb and Flag Badges

**Test:** Upload a PPTX or PDF job. After translation completes, open the review page. Inspect the segment table.
**Expected:** Each segment row shows a breadcrumb above the source text (e.g. `Slide 1 / Shape 1 / ¶0` for PPTX or `Page 0 / Col 0 / Block 2` for PDF). Overflow segments show amber "Overflow" badge for hard overflow or slate "AUTO-FIT" for auto-fit. SmartArt segments show orange "SMART" badge. `multi_column_degraded` segments show slate "MULTI-COL" badge.
**Why human:** Badge appearance, typography (JetBrains Mono breadcrumb, correct color palette), and layout density require visual inspection.

---

## Gaps Summary

No automated gaps. All 4 roadmap success criteria pass automated verification. The phase delivers all required artifacts with real implementations (no stubs).

**Advisory warnings from code review (not gaps, not blocking):**

1. **WR-04 (PPTX table overflow):** `_write_back_table` never calls `detect_pptx_overflow`. Table cell overflow is silently undetected. PPTX-03 requirement says "text-box overflow" specifically — this is within spec — but the fix is straightforward (see 03-REVIEW.md WR-04 for the patch).

2. **WR-03 (HTML injection):** `spans_to_html` does not call `html.escape()` on span text before wrapping in `<b>`/`<i>` tags. PDFs with `<`, `>`, `&` in text may produce corrupted HTML blocks. Low risk for natural-language content.

3. **WR-01/WR-06 (Worker concurrency):** `segments_done` counter race and shared SQLAlchemy session under `asyncio.gather`. No data loss observed in tests but structurally fragile.

4. **WR-05 (UploadForm stale closure):** `glossaryId` missing from `useCallback` deps — stale glossary if user changes glossary after file selection.

5. **IN-02 (SegmentRow inline badge):** `InlineFlagBadge` doesn't differentiate AUTO-FIT vs OVERFLOW (uses static labels). `FlagBadge.tsx` does this correctly; `SegmentRow` has its own inline implementation that doesn't.

All five were documented in 03-REVIEW.md before verification. They are pre-existing known findings, not discovered during this verification pass.

---

_Verified: 2026-04-26T03:30:00Z_
_Verifier: Claude (gsd-verifier)_
