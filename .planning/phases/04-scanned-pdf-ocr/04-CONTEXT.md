# Phase 4: Scanned PDF (OCR) — Context

**Gathered:** 2026-04-28
**Status:** Ready for planning
**Source:** /gsd-discuss-phase 4

<domain>
## Phase Boundary

Extend the Phase 1–3 pipeline spine to **scanned PDFs** via a 3-stage pipeline (OCR → translate → compose) using **PaddleOCR PP-StructureV3 (PP-OCRv5 base)** for OCR + layout structure parsing. Translate stage reuses the existing qwen-mt-turbo path with native `terminology` glossary injection. Compose stage produces three output artifacts:

1. `output.pdf` — bilingual side-by-side PDF (left = original page image, right = translated text rendered with Noto CJK via fpdf2). REQ OCR-03 baseline.
2. `output-translated-only.pdf` — translated-only PDF (right side rendered standalone).
3. `output.docx` — translated DOCX via Segment-tree → re-emit Markdown → PaddleOCR MD→DOCX export.

Pages with mean OCR confidence <0.7 surface as page-level `needs_review` banner; reviewer rescues low-quality OCR via editable `edited_source_text` field on Segment.

**Out of scope (explicit):**
- **PP-DocTranslation full pipeline pivot** — block-level chunking + prompt-text glossary breaks Phase 1–3 architecture parity (Segment tree, native `terminology`, CAT-tool review). Hybrid path used instead. Full pipeline deferred to v2 evaluation.
- **PaddleOCR-VL (0.9B VLM)** — newer SOTA OCR model. Deferred to v2 quality bump; ~1.5GB image cost; unproven on demo machine CPU.
- **qwen3.6-plus VLM fallback** — Phase 1 deferred memo flagged this as Phase 4 candidate; dropped after pivot (PP-StructureV3 + reviewer-edit rescue path is sufficient for PoC).
- **GPU inference path** — CPU only for PoC; GPU evaluation v2.
- **User-resume from failed stage button** — internal retry only; manual restart for terminal failures.
- **Re-OCR + retranslate per-segment button** — defer; reviewer edits source instead.
- **Multi-page table continuation** — PaddleOCR `find_tables`/`restructure_pages(merge_tables=True)` not stitched in PoC; per-page tables only.
- **3+ column scanned layouts** — degrade to flat reading order via PP-StructureV3 native fallback.
- **RTL languages** — VN/JA/ZH/EN target; Arabic/Hebrew not exercised.

</domain>

<decisions>
## Implementation Decisions

### OCR engine + fallback policy
- **D-04-01:** **PP-StructureV3 (PP-OCRv5 base)** is the locked OCR engine. Self-hosted. No qwen-VL fallback. PaddleOCR-VL deferred to v2 quality bump. PP-DocTranslation full pipeline deferred to v2. Pivot rationale: hybrid (Paddle OCR/structure + our translate + our compose) preserves Phase 1–3 architecture (Segment tree, native `terminology` glossary, CAT-tool review UX) while gaining Paddle's SOTA layout analysis (`block_label`, `block_order`, `block_bbox`).
- **D-04-19:** PP-OCRv5 **multilingual single model** (106 langs). No per-lang model switching. One ~1GB model bake target. Saves RAM + Docker size + cold-start; slight accuracy ceiling vs language-specific models acceptable for PoC.
- **D-04-20:** Region clustering = trust **PP-StructureV3 native `parsing_res_list`** with `block_order` (multi-column reading-order recovery via XY-Cut). No DIY x-coordinate clustering. Same trust-the-model stance as confidence scores.

### OCR confidence gating + needs_review state
- **D-04-02:** Page-level `needs_review` banner only. Job transitions to `needs_review` when ANY page has mean confidence <0.7. No per-segment `low_ocr_confidence` flag. Banner lists affected pages with click-to-jump (uses `structural_position` breadcrumb `page.N.region.M`).
- **D-04-23:** `needs_review` fires from **EITHER** stage:
  - OCR stage: any page mean conf <0.7 → set needs_review.
  - Translate stage: any segment_flag (overflow / glossary_violation / placeholder_mismatch / llm_refusal / figure_passthrough / ocr_page_error) → set needs_review.
  - Job ends in `needs_review` if any stage flagged it; else `done`.
- **D-04-31:** Per-page PaddleOCR error (corrupted image, model crash) → new `FlagType.ocr_page_error` (page-level via job metadata); skip page + continue job; placeholder `[OCR failed for this page]` on right side; job ends `needs_review`.

### Editable OCR'd source text
- **D-04-03:** Add `Segment.edited_source_text` field. Re-translation uses `edited_source_text ?? source_text` (mirrors Phase 2 D-02-20 `edited_text ?? translated_text`). Higher demo-day rescue value when scan quality is mediocre.
- **D-04-12:** UX = double-click source cell → textarea. Default state read-only (visual parity with DOCX/PPTX/PDF). Debounced PATCH `/segments/{id}` with `{edited_source_text}`. Per-row 'Re-translate' button uses corrected source. Keyboard: `E` (capital) edits source; `e` (lowercase) stays for target (Phase 2 D-02-17 carry-forward).
- **D-04-25:** Per-segment regenerate (REV-04 carry-over) uses `edited_source_text ?? source_text` → qwen-mt-turbo with current job glossary (Phase 2 D-02-26: glossary locked at submit). No re-OCR. Preserves `edited_text`. Cheapest rescue path.

### Pipeline stage architecture (OCR-04)
- **D-04-04:** "Independently retriable" = **internal retry only** per stage. No user-resume button. Failed stages surface terminal error after retry budget exhausted.
- **D-04-05:** **Single arq job, in-memory stage progression.** One arq task runs OCR → translate → compose sequentially. `Job.stage` enum extended: `parse | ocr | translate | compose | reassemble | done | failed`. Stage failures terminate job. SSE consumers (Phase 1 D-09) extended via D-04-x SSE payload below.
- **D-04-06:** OCR concurrency configurable via env `OCR_PAGE_CONCURRENCY`, default `1` (sequential). Lets Thu tune on demo machine without code change.
- **D-04-30:** Per-stage retry budget:
  - OCR = 2 retries (transient PyMuPDF/PaddleOCR errors)
  - Translate = 3 retries (Phase 1 CORE-06 exponential backoff carry-forward)
  - Compose = 2 retries (transient disk/font errors)
  - Retries surface in SSE as `retry_count` (Phase 1 D-12 pattern).

### SSE progress payload extension
- **D-04-x SSE:** Add `stage_progress: { stage: str, current: int, total: int }` substructure to the existing Phase 1 D-10 payload. Each stage reports its own progress dict. Frontend renders stage-specific copy (e.g., `OCR'd 7/12 pages`, `Translated 47/103 segments`, `Composing page 3/12`). Forward-looking for future formats.

### Bilingual output layout + rendering
- **D-04-07:** Output PDF page topology = **double-wide page**. Each output page = 2× source-page width. Left half = original page image (rendered from `.data/jobs/{id}/pages/page-N.png`). Right half = translated text. One output page per source page.
- **D-04-08:** Right-side text = **region-positioned, one fpdf2 `multi_cell` per OCR region**, placed at proportionally-mapped location from source region. Region position from `Segment.region_bbox` (normalized [0,1]). Preserves visual structure (titles stay near top, captions near figures).
- **D-04-29:** Right-side font sizing = **fit-to-region with min/max bounds [8pt, 24pt]**. fpdf2 picks largest font in range that fits translated text in the region rect. Region label may bias initial size (titles → larger, footnotes → smaller). Overflow flag (Phase 2 D-02-09 `FlagType.overflow`) emitted if doesn't fit at min size.
- **D-04-09:** Compose engine = **fpdf2** (per REQ OCR-03). PyMuPDF stays for upstream pixmap → PNG extraction. Clean separation: PyMuPDF for source-PDF parsing (already in stack); fpdf2 for new-PDF generation.
- **D-04-27:** fpdf2 Noto fonts bundled in `backend/fonts/`: `NotoSans-Regular.ttf` (Latin/VN) + `NotoSansCJK-Regular.ttc` (JA/SC/TC/KR). fpdf2 `add_font('Noto', '/backend/fonts/...', uni=True)` with explicit paths. Image still has system Noto via apt (Phase 1 D-18); explicit bundling avoids fontconfig fragility in fpdf2 path. ~50MB extra in repo; subset-embedded at PDF write time.
- **D-04-10:** Page images = `.data/jobs/{id}/pages/page-N.png`. Extract once during OCR stage (PyMuPDF `page.get_pixmap(dpi=DPI)` → PNG). DPI configurable via env `OCR_PAGE_DPI`, default 300. Reused by OCR stage, compose stage (left-side image), AND review UI (per-segment image crops). One extraction, three consumers.

### Output artifacts (D-04-22)
- **D-04-22:** Compose stage produces THREE outputs:
  - `.data/jobs/{id}/output.pdf` — bilingual side-by-side PDF (REQ OCR-03 baseline).
  - `.data/jobs/{id}/output-translated-only.pdf` — translated-only PDF (right-side rendering as standalone PDF, single-column).
  - `.data/jobs/{id}/output.docx` — translated DOCX via Segment-tree → re-emit Markdown helper → PaddleOCR MD→DOCX export (3.5.0 native).
  - All three rendered from the same translated Segment state in a single compose pass. Idempotent (Phase 2 D-02-22 carry-forward). Reviewer downloads any from review UI.
- **D-04-33:** DOCX path implementation:
  - New `backend/src/app/pipeline/scanned_pdf/segment_to_md.py` helper.
  - Walks Segment tree by `structural_position` + `region_label` (Phase 4 schema): titles → `# H1` / `## H2`, paragraphs → text, tables (Segment.kind=`table_cell`) → `|...|...|`, lists → `- item`.
  - Pass concatenated MD to `paddleocr.PPDocTranslation.save_to_markdown(..., as_docx=True)` (or equivalent 3.5.0 export API — verify in plan/research phase).

### Scanned-PDF detection + mixed PDFs
- **D-04-17:** Auto-detect scanned PDF via PyMuPDF text-density heuristic: count extractable text chars across all pages on upload; if `total_chars / page_count < 50` (env-configurable threshold), classify as scanned. Upload form shows: `Detected: scanned PDF — [change]`. User can override before submit. Best UX + safety net.
- **D-04-18:** Mixed PDFs handled per-page **inside OCR stage**: after job is classified scanned, OCR stage iterates pages — if `page.get_text() != ''` use existing native-PDF span extraction (Phase 3 pipeline); else OCR. Per-page Segment.kind hints downstream (`text` vs `ocr_text`). Flag pages that fell back to OCR vs native via `structural_position` + `region_label`.

### Schema extensions
- **D-04-26:** Extend `Segment.kind` enum (Phase 3.2 D-03.2) with `ocr_text`. Segment carries:
  - `confidence: float | None` — page-mean or region-mean from PaddleOCR
  - `region_bbox: tuple[float,float,float,float] | None` — page-relative normalized [0,1] floats; DPI-independent
  - `region_label: str | None` — PP-StructureV3 `block_label` (`doc_title`/`text`/`paragraph_title`/`table`/`formula`/`chart`/`image`/`vision_footnote`/...)
  - `edited_source_text: str | None` — D-04-03
- **D-04-29-mig (Alembic 0005):**
  - `segments`: add `confidence: Float, nullable=True`, `region_bbox: JSONB, nullable=True`, `region_label: String(64), nullable=True`, `edited_source_text: Text, nullable=True`
  - `Segment.kind` enum: add `ocr_text` value
  - `FlagType` enum: add `figure_passthrough`, `ocr_page_error`
  - `jobs.input_format` enum: add `scanned_pdf`

### Figures (PP-StructureV3 detected)
- **D-04-24:** Figures (`block_label='image'`/`'chart'`) pass through untouched on left side (image is the source page). Right side gets `[Figure on left]` placeholder text at corresponding position. New `FlagType.figure_passthrough` (info severity, surfaces in flag chip filter). Mirrors Phase 3 D-03-05 image-passthrough pattern. OCR'ing chart labels deferred to v2.

### Review UI extensions (CAT-tool, D-02-14 carry-forward)
- **D-04-11:** Per-segment image crop = **click-to-expand row** (default collapsed, same density as Phase 2/3). Click row OR press `i` to expand: image crop renders above source/target cells using cached `.data/jobs/{id}/pages/page-N.png` clipped to `region_bbox`. react-virtuoso variable row height already handled (Phase 2 D-02-16). **Auto-expand low-confidence segments** by default.
- **D-04-13:** OCR confidence per segment = **numeric % chip in row gutter**, color-coded: green ≥70%, amber 50–70%, red <50%. Always visible. Mirrors Phase 2 expansion-ratio chip pattern.
- **D-04-14:** Page-level needs_review banner at top of review page. Lists affected pages: `Pages 3, 7, 12 have low OCR confidence — verify before export.` Click page number → jumps to first segment of that page (uses breadcrumb `page.N.region.M`).

### Operations (cold-start, deployment)
- **D-04-15:** PaddleOCR models **baked into Docker image at build time**. `RUN python -c 'from paddleocr import PPStructureV3; PPStructureV3()'` in Dockerfile (or equivalent for the 3.5.0 init API). Pin PaddleOCR PyPI version + sub-model SHAs. Production: same image + tag-immutable in registry; model updates via image rebuild + rolling deploy. Image grows ~1GB. Demo-day safe (zero first-job latency).
- **D-04-16:** **CPU-only paddlepaddle** for PoC. Demo machine = Thu's WSL2 Linux (no NVIDIA GPU). Defer GPU question to v2. Measure perf during smoke-script run.

### Test scaffolding (Phase 1 TDD pattern)
- **D-04-28:**
  - **Unit:** Mock PaddleOCR results (canned `parsing_res_list` dicts with line+confidence) + mock qwen-mt-turbo (existing pattern). Real fpdf2 against synthetic Segments.
  - **Integration (`@pytest.mark.integration`):** Real PaddleOCR + real DashScope on the 4 demo fixtures (D-04-21). Slow; runs in CI integration job, not unit feedback loop.
  - **Round-trip:** scanned PDF → OCR'd Segment list → translated → composed bilingual PDF → assert page count matches source.
- **D-04-21:** Demo fixtures in `backend/tests/fixtures/scanned/`:
  - VN typed-doc scan (good quality)
  - JA typed-doc scan
  - EN typed-doc scan
  - Bad-quality scan (low DPI / skewed) → exercises confidence gating + `needs_review` banner + edit-source-text rescue path
  - Maps to LANG-02 + OCR-02 + D-04-02/03.

### Glossary preservation (post-pivot)
- **D-04-32 (revision):** Hybrid path skips PP-DocTranslation's translate stage entirely. Existing `translator.translate_batch(segments, glossary=...)` call site (Phase 1 D-15 + Phase 2 D-02-05) is reused without modification. Native qwen-mt-turbo `terminology` API injection unchanged across all formats. PP-DocTranslation's prompt-text glossary mechanism not used. GLOS-04 enforcement parity preserved.

### Claude's Discretion
- Exact `OCR_PAGE_CONCURRENCY`, `OCR_PAGE_DPI`, `OCR_TEXT_DENSITY_THRESHOLD` env defaults (tune empirically).
- Region-bbox → fpdf2 coordinate transform algorithm (proportional scale, target rect aspect-ratio handling).
- Segment→MD helper edge cases (mixed inline styles, nested lists, empty regions).
- fpdf2 page-size parameter (A4 doubled-width vs. dynamic per source page).
- Color values for confidence chip thresholds (paper skill secondary palette).
- Image-crop expansion animation in review UI.
- PP-StructureV3 init params (`use_doc_orientation_classify`, `use_doc_unwarping`, `use_chart_recognition`) — start permissive, tune during smoke.
- Whether PaddleOCR Python API needs threadpool wrapping for asyncio worker (likely yes — investigate in plan/research).
- Exact Docker layer ordering for model-bake step (cache invalidation vs build time tradeoff).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project foundation
- `.planning/PROJECT.md` — Core value, constraint list, key decisions
- `.planning/REQUIREMENTS.md` — OCR-01..04 acceptance criteria, LANG-02 multi-lingual coverage
- `.planning/ROADMAP.md` §"Phase 4: Scanned PDF (OCR)" — Goal + 3 success criteria
- `./CLAUDE.md` — paper-skill fonts, GSD enforcement, immutability, tech-stack §"OCR for Scanned PDFs", §"What NOT to Use" (Tesseract for JA, ReportLab for CJK)

### Phase 1–3 carry-forward (MUST read to avoid re-deciding)
- `.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md` — D-04 (.data/jobs/{id}/ layout), D-05/06 (Segment tree + deterministic IDs), D-07 (token-budget batching), D-09/10 (SSE + TanStack), D-15 (terminology plumbing), D-17 (worker concurrency), D-19 (structlog), deferred §qwen3.6-plus VLM hook (now resolved as v2)
- `.planning/phases/02-review-ux-glossary/02-CONTEXT.md` — D-02-05 (native `terminology` API), D-02-09 (segment_flags table), D-02-10 (compound PK + run_post_check job_id), D-02-14 (CAT-tool segment table — extend, don't redesign), D-02-16 (react-virtuoso virtualization), D-02-17 (keyboard shortcuts), D-02-18 (debounced PATCH), D-02-20 (edited_text ?? translated_text), D-02-22 (output.pdf overwrite + idempotent), D-02-26 (glossary locked at submit), D-02-27 (paper skill fonts)
- `.planning/phases/03-pptx-native-pdf/03-CONTEXT.md` — D-03-04 (bundled Noto fonts), D-03-05 (non-text passthrough pattern), D-03-07 (breadcrumb badge), D-03-04 worker dispatch via `match job.input_format`
- `.planning/phases/03.2-pdf-table-formula-fidelity/03.2-CONTEXT.md` — Segment.kind enum (`text|table_cell|math_passthrough` — Phase 4 adds `ocr_text`); kind-aware reassembler dispatch pattern
- `.planning/STATE.md` §Blockers/Concerns — PaddleOCR PP-OCRv5 cold-start mitigation (resolved by D-04-15 image bake)

### Existing code to extend (not rewrite)
- `backend/src/app/db/models.py` — `Job`, `Segment`, `SegmentFlag`, `FlagType`, `Glossary`, `GlossaryTerm`. Phase 4 extends per D-04-26 + adds Alembic migration 0005.
- `backend/src/app/pipeline/segment.py` — `Segment` dataclass + `make_segment_id`. Extend with `confidence`, `region_bbox`, `region_label`, `edited_source_text` (D-04-26).
- `backend/src/app/pipeline/pdf/extractor.py` + `reassembler.py` — Phase 3 native-PDF analog patterns. Phase 4 mirrors structure under `backend/src/app/pipeline/scanned_pdf/`.
- `backend/src/app/llm/translator.py` — `translate_batch(segments, glossary=...)` call site reused unchanged (D-04-32 glossary preservation).
- `backend/src/app/llm/terminology.py` — `glossary_to_terms()` injection boundary; no change.
- `backend/src/app/services/glossary_service.py` — `run_post_check(..., job_id=...)` reused for OCR jobs.
- `backend/src/app/workers/translate_worker.py` — `match job.input_format` dispatch; add `case "scanned_pdf"` branch (D-04-05).
- `backend/src/app/api/routes/upload.py` — extend with `is_scanned_override: bool` Form field (D-04-17 override toggle).
- `backend/src/app/api/routes/segments.py` — extend PATCH to accept `edited_source_text` (D-04-12).
- `backend/Dockerfile` — add PaddleOCR model bake layer (D-04-15) + bundle `backend/fonts/Noto*` (D-04-27).
- `backend/pyproject.toml` — add `paddleocr>=3.5,<4`, `paddlepaddle` (CPU build), `fpdf2>=2.7`.
- `frontend/src/components/SegmentRow.tsx` — extend with click-to-expand image preview (D-04-11), source double-click (D-04-12), confidence chip (D-04-13).
- `frontend/src/components/FlagBadge.tsx` — add `figure_passthrough`, `ocr_page_error` colors/labels.
- `frontend/src/app/jobs/[id]/review/page.tsx` — add top-of-page banner (D-04-14).
- `frontend/src/components/UploadForm.tsx` — add scanned-PDF override toggle (D-04-17).

### New external library docs (verify in research/plan phase)
- **PaddleOCR 3.5.0** — https://www.paddleocr.ai/latest/ — PP-StructureV3 (`pipeline.predict()`, `parsing_res_list`, `block_bbox`, `block_label`, `block_order`), PaddleOCR-VL (deferred v2), PP-DocTranslation MD→DOCX export (used in compose D-04-33), CPU inference on Linux/Apple Silicon
- **PP-StructureV3 docs** — https://www.paddleocr.ai/latest/version3.x/pipeline_usage/PP-StructureV3.html — output schema (`parsing_res_list[*].block_bbox/block_label/block_content/block_order`), markdown_ignore_labels config
- **fpdf2** — https://py-pdf.github.io/fpdf2/ — `add_font(uni=True)` Unicode + subset embedding, `multi_cell` text-flow, page-size customization (double-wide), `add_page` per source page
- **PaddlePaddle CPU** — https://www.paddlepaddle.org.cn/ — pip install for CPU-only; pin version compatible with paddleocr 3.5.x

### Demo fixtures (to source during plan/execute)
- `backend/tests/fixtures/scanned/vn-typed.pdf` — Vietnamese typed-doc scan
- `backend/tests/fixtures/scanned/ja-typed.pdf` — Japanese typed-doc scan
- `backend/tests/fixtures/scanned/en-typed.pdf` — English typed-doc scan
- `backend/tests/fixtures/scanned/bad-quality.pdf` — low-DPI/skewed scan exercising D-04-02/03/31 paths

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`Segment` dataclass** (`backend/src/app/pipeline/segment.py`) — Phase 3.2 already has `kind: str` field; Phase 4 extends enum with `ocr_text`. Backward-compatible default (`kind="text"`).
- **Compound PK + `run_post_check(job_id=...)`** (Phase 2 D-02-10) — Phase 4 OCR Segment inserts use the same `(job_id, id)` pattern; flag inserts pass `segment_job_id`.
- **Worker dispatch via `match job.input_format`** (Phase 3 D-03) — Phase 4 adds `case "scanned_pdf"` branch alongside docx/pptx/pdf.
- **Reassembler kind-aware dispatch** (Phase 3.2 D-03.2-03) — `text` redact+reinsert, `table_cell` per-cell, `math_passthrough` skip; Phase 4 adds `ocr_text` → fpdf2 region-render path.
- **Translator with native `terminology` glossary** (Phase 2 D-02-05) — reused unchanged for OCR jobs (D-04-32).
- **`translate_batch` token-budget packing** (Phase 1 D-07) — same batching call from OCR's translate stage.
- **SegmentFlag table + post-check pipeline** (Phase 2 D-02-09/10) — extended with new flag types.
- **CAT-tool segment table** (Phase 2 D-02-14) + **react-virtuoso virtualization** (D-02-16) + **TanStack optimistic mutations** (D-02-19) — extended with click-to-expand image row + confidence chip + double-click source-cell edit.
- **`useJobProgress` SSE hook** (Phase 1 D-09) — extended via `stage_progress` substructure (D-04-x).
- **Per-job `.data/jobs/{id}/` layout** (Phase 1 D-04) — adds `pages/` subdir for cached page PNGs (D-04-10).
- **Bundled Noto via apt** (Phase 1 D-18) — `backend/fonts/` bundle for fpdf2 explicit-path registration (D-04-27); both can coexist.
- **PyMuPDF in stack** — reused for source-PDF parsing + page-image pixmap extraction (D-04-09).
- **Phase 3.1 PDF reassembler `_MIN_RECT_WIDTH_PT` guard** — keep; doesn't apply to fpdf2 compose path but compose tests should not regress on PDF tests.

### Established Patterns (from Phases 1–3)
- **Async FastAPI + SQLAlchemy 2.0 + asyncpg + Alembic** — Phase 4 migration 0005.
- **Pydantic V2 immutable DTOs** (`frozen=True`) — Phase 4 schemas.
- **Structured JSON logging with bound `job_id`** — extend with `stage` + `page_index` context vars.
- **Hybrid SSE + TanStack cache** (D-09) — extended for stage_progress.
- **TDD with pytest + pytest-asyncio** — Phase 1 mocking pattern for LLM extends to PaddleOCR mocking (D-04-28).
- **Per-format pipeline subdir** (`backend/src/app/pipeline/{docx,pptx,pdf}/`) — Phase 4 adds `scanned_pdf/`.

### Integration Points
- **Upload form → `POST /upload`**: extend with `is_scanned_override: bool` Form field. Auto-detected default rendered in form (D-04-17).
- **Worker → PaddleOCR**: PaddleOCR Python API likely sync; wrap in `asyncio.to_thread` or `run_in_executor` to keep arq event loop responsive. Verify in research.
- **OCR stage → DB**: Persist Segments with `kind=ocr_text`, `confidence`, `region_bbox`, `region_label`. Page-mean confidence stored on Job-level metadata for needs_review banner.
- **Translate stage**: existing `translator.translate_batch()` call site; native `terminology` injection unchanged.
- **Compose stage → fpdf2**: build 3 outputs from same translated Segment state in single pass (D-04-22).
- **Compose stage → PaddleOCR MD→DOCX export**: Segment-tree → re-emit Markdown → save as DOCX (D-04-33).
- **Review UI → `GET /jobs/{id}/segments`**: existing endpoint returns extended Segment payload (confidence, region_bbox, region_label, edited_source_text).
- **Review UI → `PATCH /segments/{id}`**: extend to accept `edited_source_text` (D-04-12).
- **Review UI → `GET /jobs/{id}/pages/{N}.png`**: new static-file route serving cached page images for crop rendering. Or proxy-served via existing `.data/` static mount.
- **Frontend → SSE consumer**: parse new `stage_progress` substructure; render stage-specific copy (D-04-x SSE).

</code_context>

<specifics>
## Specific Ideas

- **"AICore demo: scan a Vietnamese government form, get a translated DOCX in 30 seconds"** — DOCX output (D-04-22) is the demo headline. Bilingual PDF is the auditability/verification artifact; DOCX is the "usable as-is" deliverable that lands the PROJECT.md core value pitch.
- **Architecture parity is non-negotiable** — pivot from "full PP-DocTranslation" → "hybrid Paddle-for-OCR + our-translate" preserves the Phase 1–3 spine. CAT-tool review, native `terminology` glossary, deterministic Segment IDs, SegmentFlag enforcement all stay consistent across DOCX/PPTX/PDF/scanned_pdf jobs. AICore sees one coherent product, not "DOCX has X but OCR has Y".
- **Reviewer-as-rescue, not VLM-as-rescue** — dropping qwen-VL fallback is the simplification dividend of PaddleOCR's improving quality. `edited_source_text` (D-04-03) + per-segment regenerate (D-04-25) gives reviewer the same fix-and-retry power that DOCX/PPTX/PDF reviewers have. Demo-day robustness: humans recover from edge cases the model can't.
- **Three-output compose stage as differentiator** — Phase 3 PoC stops at native-PDF round-trip. Phase 4 producing translated DOCX from a scan is the "wait, that's actually impressive" beat. Free win from PaddleOCR 3.5.0's MD→DOCX export — exploit it.
- **Region-positioned text > flowing text** — preserves visual structure (heading near top, caption near figure) so the bilingual PDF reads like a translated original, not a wall of text. Aligns with "format fidelity that makes output usable as-is" core value.
- **PaddleOCR-VL deferred is a forward door, not a closed door** — when v2 quality work begins, swap PP-StructureV3 → PaddleOCR-VL is a single dispatch change inside `pipeline/scanned_pdf/extractor.py`. Architecture doesn't lock us out.
- **STATE.md cold-start blocker resolved here** — D-04-15 (image bake) is the answer to the recorded blocker; smoke-script (Phase 1 D-18) verifies model availability + CPU inference time on demo machine.

</specifics>

<deferred>
## Deferred Ideas

### To v2 (post-PoC quality bump)
- **PaddleOCR-VL (0.9B VLM)** — newer SOTA OCR model. Single-extractor-swap upgrade path. Adds ~1.5GB image cost; needs CPU inference benchmark on demo-machine-class hardware.
- **PP-DocTranslation full pipeline** — block-level chunked translation with prompt-text glossary. Different review UX. Could be an alt path for "translate-first, review-second" workflows where Segment-grain editing is overkill.
- **qwen3.6-plus VLM ultimate-rescue tier** — escalation from PP-StructureV3 → PaddleOCR-VL → qwen-VL. Useful when scan quality is genuinely uncrossable. Cost-cap logic from earlier draft (max-pages-per-job) preserved as design hook.
- **GPU inference path** — `paddlepaddle-gpu` + CUDA Docker layer for production scaling.
- **Multi-page table continuation** — PaddleOCR `restructure_pages(merge_tables=True)` stitches cross-page tables; preserves `relevel_titles` for multi-level heading hierarchy. Re-eval after PoC.
- **User-resume from failed stage** — "Retry from compose" button + DB-checkpointed `job_stages` table. Useful production resilience pattern.
- **Re-OCR + retranslate per-segment button** — OCR-aware regenerate path. Costs more compute; reviewer-edit covers most cases.
- **Mixed-PDF advanced handling** — per-page detection currently flags fall-back; v2 adds visual indicators in review UI ("page 5 was OCR'd, page 6 was native").
- **Region-positioned + flowing-text fallback** — extreme expansion handling when fit-to-region [8pt, 24pt] still overflows.
- **Per-page region-mean confidence (not just page-mean)** — finer-grained `low_ocr_confidence` flagging at segment level.
- **Layout-reconstructed scanned PDF output (REQ RECON-01)** — already in v2 per REQUIREMENTS.md.
- **Table detection inside scanned PDFs structured output (REQ TABLE-01)** — already in v2.
- **Scheduled / batch / API-key OCR jobs** — single-team PoC has no need.
- **Token-aware per-language tokenizers** for stricter glossary matching — Phase 2 deferred; same disposition.
- **Browser-side OCR via PaddleOCR.js** — interesting privacy story; out of PoC scope.

### To Phase 5 (Demo Hardening)
- Pre-translate demo fixture set 24h before demo per DEMO-01.
- Smoke script extension: PaddleOCR availability + cold-start timing + CPU inference budget per page (DEMO-02).
- README update: scanned-PDF flow + known limitations + edit-source rescue UX walkthrough (DEMO-03).

### Out-of-scope per PROJECT.md
- Pixel-perfect scanned-PDF reconstruction — explicit OOS.
- Multi-tenant auth + workspaces.
- Production observability stack.

### Follow-ups (during Phase 4 execution)
- **REQUIREMENTS.md edit** — OCR-03 should be amended to acknowledge the additional translated-only PDF + DOCX outputs (D-04-22). Or add new IDs OCR-05 (translated-only PDF) + OCR-06 (translated DOCX). Reconcile in plan phase.
- **CLAUDE.md edit** — add note under §"OCR for Scanned PDFs" that PoC uses PP-StructureV3 (not bare PP-OCRv5) for layout structure; PaddleOCR-VL noted as v2 quality option; PP-DocTranslation noted as v2 alt path.
- **STATE.md** — once cold-start mitigation lands (D-04-15), move PaddleOCR PP-OCRv5 from blockers to resolved.

</deferred>

---

*Phase: 04-scanned-pdf-ocr*
*Context gathered: 2026-04-28 via /gsd-discuss-phase*
