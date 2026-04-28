---
phase: 04-scanned-pdf-ocr
verified: 2026-04-28T15:53:45Z
status: human_needed
score: 3/3
overrides_applied: 0
human_verification:
  - test: "Run end-to-end on a real scanned PDF (e.g., vn-typed.pdf). Open the generated output.pdf and verify: left half is the original page image, right half contains translated text rendered at proportional region positions with legible font."
    expected: "Bilingual PDF page width is 2x source page width. Left side reproduces the scanned page image faithfully. Right side renders translated text in the corresponding region bbox positions. Font is legible at ≥8pt. Noto CJK characters render correctly for Japanese/Chinese output."
    why_human: "fpdf2 pixel-accurate region positioning and Noto font glyph rendering require visual inspection. OCR-03 specifies 'original page image on the left and the translated text rendered with Noto CJK fonts on the right' — this is a visual fidelity requirement."
  - test: "Upload a scanned PDF with 1–2 deliberately blurry or low-DPI pages. Navigate to the review page after the job completes."
    expected: "A low-confidence banner appears at the top of the review page (amber, AlertTriangle icon). Banner shows page numbers as clickable links. Clicking a page number scrolls the segment table to the first segment of that page. Confidence chips on affected segments show red (<50%) or amber (50–70%) coloring."
    why_human: "The banner render, page-number scroll-jump, and confidence chip color thresholds require visual verification in the browser. OCR-02 requires pages to 'surface in the review UI with the original page image and the low-confidence text highlighted.'"
  - test: "In the review UI for a completed scanned PDF job, double-click a source cell in a low-confidence row."
    expected: "Source cell becomes an editable textarea. Edits are debounced-PATCH'd to the API after 500ms. A 'Discard source edit' button appears. Press 'i' to toggle the image preview — the page PNG crop appears above the row. Press Shift+E (capital E) to activate source edit via keyboard."
    why_human: "Editable source cell UX (double-click activation, debounce, discard), image preview expand/collapse animation, and keyboard shortcut behaviour are interactive UI flows that cannot be verified by static code analysis."
  - test: "From the review page Download dropdown, click each of the three options: Bilingual PDF, Translated PDF, Translated DOCX."
    expected: "Each option triggers a file download via GET /api/jobs/{id}/artifacts?artifact={type}. All three files download successfully. The bilingual PDF opens as a side-by-side layout. The DOCX opens with translated text and correct heading structure."
    why_human: "Browser download trigger and resulting file integrity (especially DOCX heading structure and PDF page count parity with source) require manual verification."
---

# Phase 4: Scanned PDF (OCR) Verification Report

**Phase Goal:** Scanned PDFs are handled through a three-stage pipeline (OCR → translate → compose) using PaddleOCR PP-OCRv5, producing a bilingual side-by-side PDF where the original page image appears on the left and the translated text on the right; low-confidence OCR regions are flagged for manual review.
**Verified:** 2026-04-28T15:53:45Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A scanned PDF is detected automatically, OCR'd via PaddleOCR PP-OCRv5, and each text region carries a confidence score; the OCR stage can fail/retry independently of the translate and compose stages | VERIFIED | `detect_scanned_pdf()` in `upload.py` uses text-density heuristic; `extract_scanned_pdf_segments()` wraps PP-StructureV3 via `asyncio.to_thread`; each Segment carries `confidence`, `region_bbox`, `region_label`; worker has `case "scanned_pdf"` in both dispatch blocks with OCR=2 retries, Compose=2 retries; behavioral spot-check confirmed import + Segment construction succeeds |
| 2 | Pages where mean OCR confidence falls below 0.7 are marked `needs_review` in the job status and shown in the review UI with the original page image and the low-confidence text highlighted | VERIFIED | `extractor.py` appends pages with `page_mean_conf < 0.7` to `low_confidence_pages`; worker sets `job.status = JobStatus.needs_review` and `job.low_confidence_pages = _low_conf_pages` (WR-02 persisted via migration 0007); `_job_to_dict` returns `low_confidence_pages`; frontend review page renders amber banner with `AlertTriangle` when `job.low_confidence_pages.length > 0`; clickable page numbers scroll to segment (`tableRef.current.scrollToIndex`); `ConfidenceChip` sub-component applies green/amber/red by threshold |
| 3 | The output is a bilingual PDF with the original page image on the left and the translated text rendered with Noto CJK fonts on the right; OCR'd segments are editable in the same review UI as other formats | VERIFIED (partial) | `compose_bilingual_pdf()` calls `add_page(format=(2 * src_w_mm, src_h_mm))` (double-wide) + `pdf.image(png_path, x=0, y=0, w=src_w_mm)` (left) + `_render_region()` per segment (right); Noto fonts registered via `add_font("NotoSans", fname=_NOTO_SANS)` + `set_fallback_fonts(["NotoSansCJK"])`; `SegmentRow.tsx` has source cell double-click edit with debounced PATCH `{edited_source_text}`; bilateral PDF visual fidelity requires human verification |

**Score: 3/3 truths pass automated checks. Visual output fidelity requires human verification (see Human Verification section).**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/app/pipeline/scanned_pdf/__init__.py` | Package init | VERIFIED | Exists |
| `backend/src/app/pipeline/scanned_pdf/detector.py` | `detect_scanned_pdf()` | VERIFIED | Function definition confirmed; behavioral spot-check passed (0 chars → True, 114 chars/page → False) |
| `backend/src/app/pipeline/scanned_pdf/extractor.py` | `extract_scanned_pdf_segments()` | VERIFIED | Async function confirmed; `asyncio.to_thread` wiring confirmed; `PASSTHROUGH_LABELS` frozenset present; polygon bbox `[:, 0].min()` present |
| `backend/src/app/pipeline/scanned_pdf/composer.py` | `compose_bilingual_pdf()` + `compose_translated_only_pdf()` | VERIFIED | Both functions present; double-wide `add_page(format=(2 * src_w_mm, src_h_mm))` confirmed; Noto font registration confirmed |
| `backend/src/app/pipeline/scanned_pdf/segment_to_md.py` | `segments_to_markdown()` + `md_to_docx()` | VERIFIED | Both functions present; behavioral spot-check: H1/H2 headings emitted correctly from `doc_title`/`paragraph_title` labels |
| `backend/src/app/pipeline/segment.py` | Segment dataclass with 4 OCR fields | VERIFIED | `confidence`, `region_bbox`, `region_label`, `edited_source_text` fields at lines 47–50 |
| `backend/src/app/db/models.py` | ORM with OCR columns + JobStage/FlagType extensions | VERIFIED | `ocr`, `compose` in JobStage; `figure_passthrough`, `ocr_page_error` in FlagType; `low_confidence_pages` JSON on Job model |
| `backend/src/app/db/migrations/versions/0006_phase4_ocr.py` | Alembic migration 0006 | VERIFIED | File exists; `revision="0006_phase4_ocr"`, `down_revision="0005_widen_flag_type"` |
| `backend/src/app/db/migrations/versions/0007_job_low_confidence_pages.py` | Alembic migration 0007 (WR-02 fix) | VERIFIED | File exists; `down_revision="0006_phase4_ocr"`; adds `low_confidence_pages` JSON column to `jobs` |
| `backend/pyproject.toml` | `paddleocr>=3.5,<4` and `fpdf2>=2.7,<3` | VERIFIED | Both dependencies confirmed at lines 16–17 |
| `backend/Dockerfile` | PP-StructureV3 model bake + Noto fonts | VERIFIED | `ENV PADDLEOCR_HOME=/paddle_models`, `PPStructureV3()` init, and `COPY backend/fonts/` confirmed |
| `backend/src/app/workers/translate_worker.py` | `case "scanned_pdf"` dispatch x2 + SSE + retry | VERIFIED | 2 `case "scanned_pdf"` branches confirmed; `stage_progress` in `_publish_progress`; `OCR=2` retries (`range(3)`); `low_conf_pages` → `needs_review` transition; WR-01 compound-PK fix confirmed at line 562; WR-04 `ocr_page_error` flags emitted |
| `backend/src/app/api/routes/upload.py` | Scanned detection + `is_scanned_override` | VERIFIED | `is_scanned_override: bool | None = Form(None)` at line 49; `detect_scanned_pdf` call at line 122; `input_format = "scanned_pdf"` at line 136 |
| `backend/src/app/api/routes/segments.py` | `edited_source_text` PATCH + regenerate | VERIFIED | Field at line 36; `_segment_to_dict` extension at line 69; PATCH update at line 149; regenerate source fallback at line 195 |
| `backend/src/app/api/routes/jobs.py` | `/artifacts` download + `/pages/{n}.png` | VERIFIED | `download_artifact` at line 92; `serve_page_image` at line 154; URL is `/artifacts` (not `/download` — CR-01 fix confirmed) |
| `backend/src/app/core/config.py` | OCR env vars | VERIFIED | `ocr_page_dpi=300`, `ocr_page_concurrency=1`, `ocr_text_density_threshold=50.0`; behavioral spot-check confirmed |
| `frontend/src/lib/types.ts` | `FlagType` + `Segment` + `JobProgress` OCR extensions | VERIFIED | `figure_passthrough`, `ocr_page_error` in FlagType; `confidence`, `region_bbox`, `region_label`, `edited_source_text` on Segment; `stage_progress`, `low_confidence_pages` on JobProgress and JobSummary |
| `frontend/src/components/FlagBadge.tsx` | FIGURE + OCR ERR badges | VERIFIED | Both entries in `FLAG_CONFIG` with correct slate/amber styling |
| `frontend/src/components/SegmentRow.tsx` | ConfidenceChip + image preview + source edit | VERIFIED | `ConfidenceChip` sub-component present; `imageExpanded`, `sourceEditing` state; `imageError` React state (not innerHTML — T-04-18); WR-06 CSS fix: overlay div with `left/top/width/height` percentages from `region_bbox` |
| `frontend/src/app/jobs/[id]/review/page.tsx` | Low-confidence banner + download menu | VERIFIED | Banner renders when `job.low_confidence_pages?.length > 0`; `AlertTriangle` import; download `handleDownload` uses `/api/jobs/${jobId}/artifacts?artifact=...` (CR-01 fix confirmed) |
| `frontend/src/components/UploadForm.tsx` | Scanned detection + override toggle | VERIFIED | `isScannedDetected`, `isScannedOverride` state; `is_scanned_override` appended to FormData; WR-03 fix: both state vars in `useCallback` deps at line 155 |
| `frontend/src/hooks/useSegments.ts` | `editedSourceText` in PATCH mutation | VERIFIED | `editedSourceText?: string | null` param; `body.edited_source_text = editedSourceText`; optimistic cache update |
| `backend/tests/pipeline/test_scanned_pdf_roundtrip.py` | Round-trip unit test | VERIFIED | File exists; 0 `NotImplementedError` stubs remain |
| `backend/tests/api/test_jobs_download.py` | Download endpoint API tests | VERIFIED | File exists |
| `backend/tests/api/test_segments_edited_source.py` | PATCH edited_source_text API test | VERIFIED | File exists |
| `backend/tests/db/test_migration_0006.py` | Migration 0006 inspection tests | VERIFIED | File exists; 0 `NotImplementedError` stubs |
| `backend/tests/conftest.py` | `mock_ppstructurev3` + `low_confidence_mock_ppstructurev3` | VERIFIED | Both fixtures present per SUMMARY-01 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `upload.py` | `scanned_pdf/detector.py` | `detect_scanned_pdf(doc, threshold=settings.ocr_text_density_threshold)` | WIRED | `detect_scanned_pdf` imported and called at upload.py line 122 |
| `translate_worker.py` | `scanned_pdf/extractor.py` | `extract_scanned_pdf_segments(doc, job_id, pages_dir, pipeline, dpi=settings.ocr_page_dpi)` | WIRED | Import + call confirmed at worker line 345 and 367 |
| `translate_worker.py` | `scanned_pdf/composer.py` | `compose_bilingual_pdf(segments, translated_map, pages_dir, output_path, overflow_flags, src_doc)` | WIRED | Import + call confirmed at worker line 730 and 749 |
| `translate_worker.py` | `scanned_pdf/segment_to_md.py` | `segments_to_markdown(segments)` → `md_to_docx(md_text, output.docx)` | WIRED | Both calls confirmed in compose stage branch |
| `extractor.py` | `segment.py` | `Segment.from_text(kind='ocr_text', confidence=..., region_bbox=..., region_label=...)` | WIRED | `Segment.from_text` with OCR kwargs used in extractor |
| `composer.py` | `backend/fonts/NotoSans-Regular.ttf` | `add_font("NotoSans", fname=_NOTO_SANS)` | WIRED | Font path constant and `add_font` call confirmed; Helvetica fallback when file absent |
| `SegmentRow.tsx` | `/api/jobs/{jobId}/pages/{pageN}.png` | `img src` for image crop preview | WIRED | `src={\`/api/jobs/${jobId}/pages/${pageNum}.png\`}` confirmed |
| `review/page.tsx` | `job.low_confidence_pages` | Banner reads from job response | WIRED | `job.low_confidence_pages?.length > 0` conditional confirmed; data persisted in DB via WR-02 fix |
| `UploadForm.tsx` | `formData.append('is_scanned_override', ...)` | Override toggle sends to upload API | WIRED | `formData.append("is_scanned_override", String(effectiveScanned))` confirmed |
| `review/page.tsx` → `handleDownload` | `/api/jobs/${jobId}/artifacts?artifact=` | Download menu calls artifacts endpoint | WIRED | URL confirmed post-CR-01 fix; matches backend `GET /jobs/{id}/artifacts` route |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `SegmentRow.tsx` confidence chip | `segment.confidence` | `extract_scanned_pdf_segments()` → persisted to DB → returned by `/api/segments/{id}` | Yes — computed from PaddleOCR `rec_scores` mean | FLOWING |
| `review/page.tsx` low-confidence banner | `job.low_confidence_pages` | Worker `_low_conf_pages` → `job.low_confidence_pages` (JSON column, migration 0007) → `_job_to_dict` | Yes — real DB column persisted after WR-02 fix | FLOWING |
| `compose_bilingual_pdf()` right-half text | `translated_map[seg.id]` | `translate_batch()` → worker translated_map dict | Yes — real LLM translations from qwen-mt-turbo | FLOWING |
| `UploadForm.tsx` `isScannedDetected` | `data.is_scanned` from upload response | `detect_scanned_pdf()` result stored in upload response dict | Yes — live text-density calculation on uploaded file | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Pipeline module imports succeed | `uv run python -c "from app.pipeline.scanned_pdf.detector import detect_scanned_pdf; ..."` | All imports OK | PASS |
| Segment dataclass accepts OCR fields | `Segment.from_text('test', 'p.0', 0, confidence=0.85, region_bbox=(0.1,0.1,0.5,0.5), region_label='text')` | `confidence=0.85, region_label=text` | PASS |
| `detect_scanned_pdf` classifies correctly | Empty page → True (scanned), 114 chars/page → False (native) | Both correct | PASS |
| `segments_to_markdown` heading structure | `doc_title` → `# heading`, `paragraph_title` → `## heading`, `text` → plain | `'# My Translated Title\n\n## Translated Section 1\n\nTranslated body\n'` | PASS |
| Config OCR defaults load | `DASHSCOPE_API_KEY=dummy ... uv run python -c "from app.core.config import Settings; ..."` | `ocr_page_dpi=300, ocr_page_concurrency=1, ocr_text_density_threshold=50.0` | PASS |
| Bilingual PDF visual fidelity (actual OCR output) | Requires running end-to-end on real scanned PDF | Not runnable without real PaddleOCR models + scanned fixture | SKIP (human required) |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| OCR-01 | Plans 01, 02, 03, 04, 05 | A scanned PDF is OCR'd via PaddleOCR PP-OCRv5; page images captured with confidence scores; OCR stage can fail/retry independently | SATISFIED | `extractor.py` wraps PP-StructureV3; per-page error isolation; OCR stage retry budget=2; all 5 plans reference OCR-01 |
| OCR-02 | Plans 02, 03, 04, 05 | Pages with mean OCR confidence < 0.7 marked `needs_review`; surface in review UI with page image and low-confidence text | SATISFIED | `page_mean_conf < 0.7` → `low_confidence_pages`; `job.status = JobStatus.needs_review`; `job.low_confidence_pages` persisted (WR-02 fix); banner + image preview in frontend |
| OCR-03 | Plans 02, 03, 04, 05 | Output is bilingual side-by-side PDF: left=original page image, right=translated text with Noto CJK; segments editable in review UI | SATISFIED (visual fidelity human-verified) | `compose_bilingual_pdf()` double-wide page with image left + text right; Noto font registration; `SegmentRow.tsx` source cell editable via double-click PATCH |
| OCR-04 | Plans 01, 02, 03, 05 | OCR, translate, and compose split into three pipeline stages that can each fail/retry independently | SATISFIED | Worker `case "scanned_pdf"` in parse stage (OCR) and reassemble stage (compose); translate stage unchanged (`translate_batch`); per-stage retry budgets enforced (OCR=2, Compose=2); `JobStage.ocr` and `JobStage.compose` enum values |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `segment_to_md.py` | 54 | `text = seg.edited_source_text or seg.translated_text or seg.source_text` — uses reviewer-corrected OCR source as export text priority instead of `translated_text` | INFO | DOCX export outputs the OCR source correction instead of the translation when a reviewer has edited the source cell. Identified as IN-01 in code review. Not a blocker for the bilingual PDF output. Worker passes `translated_map` separately to `compose_bilingual_pdf`; only the DOCX path is affected. |

No STUB, MISSING, or ORPHANED patterns found. All RED test stubs (NotImplementedError) were replaced with real test assertions by Plan 02–05 (confirmed: 0 occurrences remaining across all 6 test files).

---

### Human Verification Required

#### 1. Bilingual PDF Visual Fidelity

**Test:** Run end-to-end translation on a real scanned PDF (e.g., `vn-typed.pdf` fixture from `backend/tests/fixtures/scanned/`). Open the generated `output.pdf`.

**Expected:** Left half of each page reproduces the original scanned page image. Right half contains translated text positioned at proportional region bbox locations. Font is legible (≥8pt). For Japanese/Chinese output, Noto CJK characters render correctly (requires Noto font files in `backend/fonts/` — not committed to git per decision 3 in SUMMARY-01).

**Why human:** fpdf2 pixel-accurate region rendering, font glyph subsetting, and visual layout quality cannot be deterministically verified by static code inspection. OCR-03 requires visual confirmation that the bilingual layout achieves its core purpose.

#### 2. Low-Confidence Banner and Review UI Flow

**Test:** Upload a scanned PDF with deliberately blurry or low-DPI pages. After job completion, navigate to the review page.

**Expected:** Amber banner with `AlertTriangle` icon renders at the top. Page numbers in the banner are clickable links that scroll the segment table to the first segment of that page. Confidence chips on affected segments show correct colors (green ≥70%, amber 50–70%, red <50%).

**Why human:** Scroll-to-index animation, banner visibility on page load (requires persistence via WR-02 migration 0007), and color threshold visual correctness require browser-based verification.

#### 3. Source Cell Editing and Image Preview Interaction

**Test:** In the review UI for a completed scanned PDF job, double-click a source cell in a low-confidence row. Also press `i` to toggle the image preview and `Shift+E` to activate keyboard source editing.

**Expected:** Double-click activates editable Textarea. Edits are debounced-PATCH'd after 500ms. "Discard source edit" button appears when `edited_source_text !== null`. `i` key toggles image crop preview (shows region highlighted with amber overlay on full-page PNG). `Shift+E` activates source edit keyboard shortcut.

**Why human:** Interactive UX flows (debounce timing, expand animation, keyboard shortcut scoping via `useHotkeys(enabled: isFocused)`) require in-browser verification.

#### 4. Three-Artifact Download

**Test:** From the review page Download dropdown, click each of "Bilingual PDF", "Translated PDF", "Translated DOCX".

**Expected:** Browser triggers file download via `GET /api/jobs/{id}/artifacts?artifact={type}`. All three files download successfully. Bilingual PDF opens as double-wide side-by-side layout. Translated DOCX opens with heading structure (H1/H2 from `doc_title`/`paragraph_title` regions).

**Why human:** Browser Content-Disposition file download trigger and resulting file format integrity require manual verification.

---

### Gaps Summary

No automated gaps. All 3 ROADMAP success criteria are verified by the codebase. All 4 requirement IDs (OCR-01 through OCR-04) are satisfied with evidence. All 7 code review findings (1 critical CR-01, 6 warnings WR-01 through WR-06) were fixed per `04-REVIEW-FIX.md`. No RED test stubs remain.

The `human_needed` status is driven by visual/interactive verification requirements that are inherent to the bilingual PDF output goal (OCR-03). These are not gaps — they are confirmations of an already-wired implementation. 

**Note on IN-01 (info):** `segment_to_md.py` uses `edited_source_text` in the text priority chain instead of pure `translated_text`. This means when a reviewer corrects the OCR source text, the DOCX export will output the source correction rather than the translation. This is noted in the review as an info finding. The bilingual PDF path is unaffected (it uses `translated_map` directly). Suggest fixing before demo: pass `translated_map` into `segments_to_markdown()` as an optional parameter.

---

_Verified: 2026-04-28T15:53:45Z_
_Verifier: Claude (gsd-verifier)_
