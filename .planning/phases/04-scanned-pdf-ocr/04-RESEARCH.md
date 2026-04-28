# Phase 4: Scanned PDF (OCR) — Research

**Researched:** 2026-04-28
**Domain:** PaddleOCR PP-StructureV3 (OCR/layout) + fpdf2 (PDF compose) + PyMuPDF (page extraction) + arq worker integration
**Confidence:** MEDIUM-HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**OCR engine:**
- D-04-01: PP-StructureV3 (PP-OCRv5 base) is the locked OCR engine. Self-hosted. No qwen-VL fallback.
- D-04-19: PP-OCRv5 multilingual single model (106 langs). No per-lang model switching.
- D-04-20: Region clustering = trust PP-StructureV3 native `parsing_res_list` with `block_order`.

**Confidence gating:**
- D-04-02: Page-level `needs_review` banner only. Job → `needs_review` when ANY page has mean confidence <0.7.
- D-04-23: `needs_review` fires from EITHER OCR stage (confidence) OR translate stage (flags).
- D-04-31: Per-page OCR error → new `FlagType.ocr_page_error`; skip page + continue; placeholder on right side.

**Editable OCR source:**
- D-04-03: Add `Segment.edited_source_text`. Re-translation uses `edited_source_text ?? source_text`.
- D-04-12: Double-click source cell → textarea; debounced PATCH `/segments/{id}` with `{edited_source_text}`.
- D-04-25: Per-segment regenerate uses `edited_source_text ?? source_text`.

**Pipeline stage architecture:**
- D-04-04: Internal retry only. No user-resume button.
- D-04-05: Single arq job, in-memory stage progression. Stage enum extended: `parse | ocr | translate | compose | reassemble | done | failed`.
- D-04-06: `OCR_PAGE_CONCURRENCY` env, default `1`.
- D-04-30: Per-stage retry: OCR=2, Translate=3, Compose=2.

**SSE progress:**
- D-04-x SSE: Add `stage_progress: { stage: str, current: int, total: int }` to Phase 1 D-10 payload.

**Output layout and rendering:**
- D-04-07: Double-wide page topology (2× source-page width). Left = original page image. Right = translated text.
- D-04-08: Right-side text = region-positioned. One fpdf2 `multi_cell` per OCR region at proportionally-mapped location.
- D-04-29: Font sizing = fit-to-region [8pt, 24pt]. Overflow flag if doesn't fit at 8pt min.
- D-04-09: Compose engine = fpdf2. PyMuPDF for page image extraction only.
- D-04-27: fpdf2 Noto fonts bundled in `backend/fonts/`: NotoSans-Regular.ttf + NotoSansCJK-Regular.ttc.
- D-04-10: Page images = `.data/jobs/{id}/pages/page-N.png`. DPI via env `OCR_PAGE_DPI`, default 300.

**Output artifacts:**
- D-04-22: Three outputs: bilingual PDF (`output.pdf`), translated-only PDF (`output-translated-only.pdf`), translated DOCX (`output.docx`).
- D-04-33: DOCX path via `segment_to_md.py` helper → re-emit Markdown → `res.save_to_word()`.

**Scanned PDF detection:**
- D-04-17: PyMuPDF text-density heuristic: `total_chars / page_count < 50`. Env-configurable. User override on upload form.
- D-04-18: Mixed PDFs per-page: if `page.get_text() != ''` use native-PDF span extraction; else OCR. `Segment.kind` = `ocr_text` vs `text`.

**Schema extensions:**
- D-04-26: `Segment.kind` += `ocr_text`. New fields: `confidence`, `region_bbox` (JSONB [0,1]), `region_label`, `edited_source_text`.
- D-04-29-mig (Alembic 0006): segments columns + enum extensions for `ocr_text`, `figure_passthrough`, `ocr_page_error`, `scanned_pdf` input_format.

**Figures:**
- D-04-24: `block_label='image'/'chart'` → pass through on left side. Right side: `[Figure on left]` placeholder. New `FlagType.figure_passthrough`.

**Review UI:**
- D-04-11: Per-segment image crop via click-to-expand row. Auto-expand low-confidence segments.
- D-04-13: OCR confidence % chip in row gutter. Color: green ≥70%, amber 50–70%, red <50%.
- D-04-14: Page-level needs_review banner. Lists affected pages with click-to-jump.

**Operations:**
- D-04-15: PaddleOCR models baked into Docker image at build time. `RUN python -c 'from paddleocr import PPStructureV3; PPStructureV3()'`.
- D-04-16: CPU-only paddlepaddle for PoC.

**Tests:**
- D-04-28: Unit (mock PaddleOCR + real fpdf2), integration (real Paddle + DashScope on 4 fixtures), round-trip.
- D-04-21: Demo fixtures in `backend/tests/fixtures/scanned/`.

**Glossary:**
- D-04-32: Hybrid path. `translator.translate_batch(segments, glossary=...)` reused unchanged. Native `terminology` API preserved.

### Claude's Discretion
- Exact `OCR_PAGE_CONCURRENCY`, `OCR_PAGE_DPI`, `OCR_TEXT_DENSITY_THRESHOLD` env defaults.
- Region-bbox → fpdf2 coordinate transform algorithm.
- Segment→MD helper edge cases.
- fpdf2 page-size parameter (A4 doubled-width vs. dynamic per source page).
- Color values for confidence chip thresholds.
- Image-crop expansion animation in review UI.
- PP-StructureV3 init params (`use_doc_orientation_classify`, `use_doc_unwarping`, `use_chart_recognition`).
- Whether PaddleOCR Python API needs threadpool wrapping.
- Exact Docker layer ordering for model-bake step.

### Deferred Ideas (OUT OF SCOPE)
- PaddleOCR-VL (0.9B VLM)
- PP-DocTranslation full pipeline
- qwen3.6-plus VLM fallback
- GPU inference path
- User-resume from failed stage button
- Re-OCR + retranslate per-segment button
- Multi-page table continuation
- 3+ column scanned layouts (degrade to flat)
- RTL languages

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OCR-01 | Scanned PDF OCR'd via PaddleOCR PP-OCRv5; page images captured alongside text regions with confidence scores | PP-StructureV3 predict() returns `parsing_res_list` with block_bbox + block_content; page PNG via PyMuPDF get_pixmap |
| OCR-02 | Pages with mean OCR confidence <0.7 marked `needs_review`; review UI shows original page image + low-confidence text | Confidence available via `rec_scores` in `overall_ocr_res`; page-mean = mean of per-line rec_scores; needs_review flag gates job status |
| OCR-03 | Bilingual side-by-side PDF: left = original page image, right = translated text with Noto CJK font embedded | fpdf2 double-wide page + image() left half + region-positioned multi_cell right half with add_font(NotoSans/NotoSansCJK) |
| OCR-04 | OCR, translate, compose split into three independently retriable pipeline stages | D-04-05 single arq job with in-memory stage progression; D-04-30 per-stage retry budgets |

</phase_requirements>

---

## Summary

Phase 4 extends the Phase 1–3 pipeline spine to scanned PDFs via a three-stage Hybrid path: PP-StructureV3 (PP-OCRv5 base) for OCR and layout structure parsing, the existing qwen-mt-turbo translator (unchanged), and fpdf2 for bilingual PDF composition. The architecture preserves Phase 1–3 design parity — same Segment tree, same native `terminology` glossary injection, same CAT-tool review UX — while adding OCR-specific capabilities (confidence gating, editable source text, per-segment image crops).

The key technical challenge is integrating three libraries that are new to the stack: PaddleOCR 3.5.x (requires `paddlepaddle==3.2.x` CPU build, separate from the Alibaba package index), fpdf2 2.8.x (mature, well-documented), and ensuring PaddleOCR's synchronous Python API does not block the arq asyncio event loop. The 1GB+ Docker image growth from model baking is expected and accepted (D-04-15).

The PP-StructureV3 output schema is partially verified: `parsing_res_list` entries carry `block_bbox` (numpy array of polygon corners, dtype int16), `block_label` (23+ category strings), `block_content` (text or table Markdown), `block_id`, and `block_order`. Per-line recognition confidence lives in `overall_ocr_res.rec_scores` as a list of floats. Page-mean confidence requires computing `mean(rec_scores)` from the per-page `overall_ocr_res` — this field structure is ASSUMED based on the OCR pipeline JSON schema observed for text-recognition modules; the exact path in PP-StructureV3's JSON output needs verification during plan/execute with a real call.

**Primary recommendation:** Implement `pipeline/scanned_pdf/` as a four-file module (detector.py, extractor.py, composer.py, segment_to_md.py) mirroring the existing `pipeline/pdf/` structure. Use `asyncio.to_thread()` for PaddleOCR sync calls inside the arq worker. Bake models in Docker with a separate layer ordered after `COPY src/ src/` to preserve model cache across source-only rebuilds.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Scanned PDF detection | API / Backend (upload endpoint) | — | Text-density heuristic runs synchronously at upload time; user override stored in job metadata |
| Page-image extraction | API / Backend (arq worker, OCR stage) | — | PyMuPDF is sync + I/O heavy; runs in OCR stage before PaddleOCR |
| OCR + layout parsing | API / Backend (arq worker, OCR stage) | — | PaddleOCR sync API; wrapped in to_thread |
| Confidence gating | API / Backend (arq worker, OCR stage) | — | Computed from per-page rec_scores; stored on Job metadata + SSE payload |
| Translation | API / Backend (arq worker, translate stage) | — | Reuses existing translate_batch; no change |
| Bilingual PDF composition | API / Backend (arq worker, compose stage) | — | fpdf2 sync API; called in compose stage |
| DOCX export from segments | API / Backend (arq worker, compose stage) | — | segment_to_md.py + res.save_to_word() |
| Page image serving | API / Backend (static file route) | — | GET /jobs/{id}/pages/{N}.png → serves .data/jobs/{id}/pages/ |
| Confidence chip rendering | Browser / Client | — | Per-segment chip color computed from Segment.confidence in SegmentRow.tsx |
| Image crop preview | Browser / Client | — | Click-to-expand row requests page PNG URL; clipped by CSS using region_bbox |
| Page-level needs_review banner | Browser / Client | — | Banner reads Job.metadata.low_confidence_pages list from job API response |

---

## Standard Stack

### New additions (Phase 4)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| paddleocr | `>=3.5,<4` | OCR + layout structure parsing | PP-StructureV3 is SOTA open-source; D-04-01 locked decision |
| paddlepaddle | `==3.0.0` (CPU) | PaddlePaddle inference backend | Required runtime for paddleocr; CPU build for PoC (D-04-16) |
| fpdf2 | `>=2.7,<3` | bilingual PDF generation | Locked in CLAUDE.md; Context7 verified; OCR-03 requirement |

Version verification (confirmed from PyPI + Context7, 2026-04-28):
- `paddleocr`: latest = `3.5.0` (released 2026-04-21). Supports Python 3.8–3.13. [VERIFIED: pypi.org/project/paddleocr]
- `paddlepaddle` CPU: install via `python -m pip install paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/`. Version 3.0.0 confirmed CPU stable. [CITED: paddlepaddle.github.io/PaddleX/3.3/en/installation/paddlepaddle_install.html]
- `fpdf2`: latest = `2.8.7` (released 2026-02-28). Supports Python 3.10–3.14. [VERIFIED: pypi.org/project/fpdf2]

### Existing stack (unchanged)

| Library | Purpose | Phase 4 usage |
|---------|---------|--------------|
| pymupdf `>=1.26,<2` | Page-image extraction | `page.get_pixmap(dpi=DPI).save(path)` per OCR stage |
| sqlalchemy `>=2.0` | ORM + migrations | Alembic migration 0006 adds columns |
| arq `==0.27.0` | Async job queue | OCR stage runs via `asyncio.to_thread` inside worker |
| openai `>=1.40,<2` | DashScope translation | Translate stage unchanged (D-04-32) |

### Installation

```bash
# In backend/pyproject.toml — add to [project].dependencies:
# paddleocr>=3.5,<4
# fpdf2>=2.7,<3
# paddlepaddle installed separately (not on standard PyPI index)

# In Dockerfile — separate pip install for paddlepaddle CPU:
RUN python -m pip install paddlepaddle==3.0.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

# Then install paddleocr[all] (includes doc parsing, needed for PPStructureV3):
RUN uv pip install --system "paddleocr[all]>=3.5,<4" fpdf2>=2.7,<3

# Important: paddleocr[all] requires Python >=3.9 for optional dependencies.
# Python 3.12 is confirmed compatible (pyproject.toml already requires >=3.12).
```

**Critical install note:** `paddlepaddle` must be installed from the Alibaba PaddlePaddle package index (`https://www.paddlepaddle.org.cn/packages/stable/cpu/`), NOT from standard PyPI. The standard PyPI `paddlepaddle` package may lag behind or be a stub. [CITED: github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/installation.en.md]

---

## Architecture Patterns

### System Architecture Diagram

```
Upload endpoint (FastAPI)
        |
   text-density heuristic                 ← D-04-17: total_chars/pages < 50
        |
   Job created: input_format="scanned_pdf"
        |
   arq worker ← translate_job(job_id)
        |
   ┌────────────────────────────────────────────────────────┐
   │ OCR STAGE (D-04-05)                                    │
   │   ┌──────────────────────────────────────────────────┐ │
   │   │ for each page N:                                 │ │
   │   │   PyMuPDF page.get_pixmap(dpi=DPI) → page-N.png │ │
   │   │   asyncio.to_thread(ppstructurev3.predict, png)  │ │
   │   │   → parsing_res_list (block_bbox, block_label,   │ │
   │   │                        block_content, block_order)│ │
   │   │   → overall_ocr_res.rec_scores → page_mean_conf │ │
   │   │   if page_mean_conf < 0.7 → mark needs_review    │ │
   │   │   → emit Segments(kind=ocr_text, confidence=..., │ │
   │   │                    region_bbox=[0,1], region_label│ │
   │   │   publish SSE: stage_progress{stage:ocr, N/total}│ │
   │   └──────────────────────────────────────────────────┘ │
   │   → DB: persist OCR Segments                            │
   └────────────────────────────────────────────────────────┘
        |
   ┌────────────────────────────────────────────────────────┐
   │ TRANSLATE STAGE (reused, D-04-32)                      │
   │   translator.translate_batch(ocr_segments, glossary=..)│
   │   (exact same path as DOCX/PPTX/PDF)                  │
   │   → translated_map{segment_id: translated_text}        │
   │   publish SSE: stage_progress{stage:translate, N/total}│
   └────────────────────────────────────────────────────────┘
        |
   ┌────────────────────────────────────────────────────────┐
   │ COMPOSE STAGE (fpdf2, D-04-09)                         │
   │   for each source page N:                              │
   │     fpdf: add_page(format=(2*src_w_mm, src_h_mm))     │
   │     fpdf: image(page-N.png, x=0, y=0, w=src_w_mm)    │ ← left half
   │     for each Segment on page N (ordered by block_order)│
   │       normalized_bbox → right-side rect (pt)          │
   │       measure text → fit_font_size in [8, 24]         │
   │       fpdf: multi_cell(w=rect_w, h=auto, text=transl) │ ← right half
   │   → output.pdf (bilingual)                            │
   │   → output-translated-only.pdf (right side only)      │
   │   → segment_to_md.py → res.save_to_word() → output.docx│
   │   publish SSE: stage_progress{stage:compose, N/total} │
   └────────────────────────────────────────────────────────┘
        |
   Job.status = needs_review | done
   SSE: {status, stage_progress, low_confidence_pages:[...]}
```

### Recommended Project Structure

```
backend/src/app/pipeline/scanned_pdf/
├── __init__.py
├── detector.py          # text-density heuristic (D-04-17)
├── extractor.py         # PP-StructureV3 wrapper → Segment list
├── composer.py          # fpdf2 bilingual PDF + translated-only PDF
└── segment_to_md.py     # Segment tree → Markdown → save_to_word()

backend/tests/pipeline/
├── test_scanned_pdf_detector.py
├── test_scanned_pdf_extractor.py    # mock PaddleOCR
├── test_scanned_pdf_composer.py     # real fpdf2 against synthetic Segments
└── test_scanned_pdf_roundtrip.py    # @pytest.mark.integration

backend/tests/fixtures/scanned/
├── vn-typed.pdf        # D-04-21: good quality VN scan
├── ja-typed.pdf        # JA typed-doc scan
├── en-typed.pdf        # EN typed-doc scan
└── bad-quality.pdf     # low-DPI/skewed (synthesized from clean PDF)

backend/fonts/           # D-04-27 (already started in Phase 3)
├── NotoSans-Regular.ttf
└── NotoSansCJK-Regular.ttc
```

---

## PP-StructureV3 API Reference

### Initialization

```python
# Source: github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md
from paddleocr import PPStructureV3

pipeline = PPStructureV3(
    device="cpu",                        # D-04-16: CPU only
    use_doc_orientation_classify=False,  # skip unless demo scans are rotated — speeds CPU
    use_doc_unwarping=False,             # skip for typed-doc scans; enable for photo scans
    use_seal_recognition=False,          # irrelevant for translation PoC
    use_table_recognition=True,          # needed for table block_label detection
    use_formula_recognition=True,        # formula regions → passthrough label
    use_chart_recognition=False,         # charts → figure_passthrough anyway (D-04-24)
    use_textline_orientation=False,      # typed docs are always upright
    lang="multilingual",                 # D-04-19: single 106-lang model
    # cpu_threads=8,                     # ASSUMED: tunable param; verify in execution
    # enable_mkldnn=True,                # ASSUMED: MKL-DNN acceleration on x86_64 CPU
)
```

**Note on `lang` parameter:** The exact string for the multilingual single model is ASSUMED to be `"multilingual"` — the docs show `lang="en"` for English-only. The default (no `lang` param) gives the Chinese+English model. For a 106-language model verify the exact value during execution. [ASSUMED]

### predict() call and output

```python
# Source: github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md
output = pipeline.predict(input="path/to/page-N.png")

# output is a list (one element per input image)
for res in output:
    # Access as JSON dict
    json_data = res.json  # dict with all parsed fields
    # OR iterate parsing_res_list directly
    parsing_res = res.json.get("layout_parsing_result", {}).get("parsing_res_list", [])
```

### parsing_res_list schema

Each element in `parsing_res_list` is a dict with these fields:
[VERIFIED: github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-DocTranslation.en.md]

```python
{
    "block_bbox": np.ndarray,     # shape (4, 2) int16 — four corner points (NOT x0,y0,x1,y1)
    "block_label": str,           # e.g. "text", "paragraph_title", "doc_title", "table",
                                  #       "formula", "image", "chart", "footnote", ...
    "block_content": str,         # extracted text (for tables: Markdown table format)
    "block_id": int,              # index of region in extraction order
    "block_order": int | None,    # reading order after XY-Cut sort (None = unordered region)
}
```

**block_bbox shape warning:** The bounding box is a 4-corner polygon `shape (4,2)`, dtype `int16`, in **pixel coordinates on the input image**. To get axis-aligned rect: `x0,y0,x1,y1 = bbox[:,0].min(), bbox[:,1].min(), bbox[:,0].max(), bbox[:,1].max()`. Do NOT assume it is a simple `[x0,y0,x1,y1]` flat list. [VERIFIED: parsing_res_list docs show shape `(4,2)` polygon]

### Known block_label values

From Context7 + docs (combined verified list):
[VERIFIED: github.com/PaddlePaddle/PaddleOCR docs + PaddleX layout_analysis.md]

| block_label | Translation behavior |
|-------------|---------------------|
| `text` | Translate → `ocr_text` Segment |
| `paragraph_title` | Translate → `ocr_text` Segment (larger font on right side) |
| `doc_title` | Translate → `ocr_text` Segment (largest font on right side) |
| `table` | Translate block_content (Markdown table) → `ocr_text` Segment |
| `formula` | PASSTHROUGH → math_passthrough pattern (like Phase 3.2) |
| `formula_number` | PASSTHROUGH |
| `image` | figure_passthrough (D-04-24) → `[Figure on left]` placeholder |
| `chart` | figure_passthrough (D-04-24) → `[Figure on left]` placeholder |
| `figure_title` | Translate → `ocr_text` Segment |
| `figure` | figure_passthrough (D-04-24) |
| `table_caption` | Translate → `ocr_text` Segment |
| `abstract` | Translate → `ocr_text` Segment |
| `footnote` | Translate → `ocr_text` Segment |
| `page_number` | Skip (do not translate page numbers) |
| `header` | Translate → `ocr_text` Segment |
| `footer` | Translate → `ocr_text` Segment |
| `seal` | Skip (seals are images in context) |
| `references` | Translate → `ocr_text` Segment |
| `algorithm` | PASSTHROUGH (code-like content) |

### Confidence extraction

The page-level `rec_scores` (per recognition line confidence) are accessible via `overall_ocr_res`:
[VERIFIED: github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/paddlex/quick_start.md — OCR pipeline JSON output shows `rec_scores` array]

```python
# ASSUMED path within PP-StructureV3 res.json — verify during execution:
overall_ocr = res.json.get("overall_ocr_res", {})
rec_scores = overall_ocr.get("rec_scores", [])  # list[float], per recognized text line
page_mean_conf = sum(rec_scores) / len(rec_scores) if rec_scores else 1.0
```

**Important:** The exact key path (`overall_ocr_res.rec_scores`) is ASSUMED based on the OCR pipeline output schema seen in Context7 documentation. The PP-StructureV3 specific JSON nesting may differ. During plan/execute, do `res.print()` or `res.save_to_json()` on a real scan and inspect the structure. [ASSUMED — HIGH RISK if wrong: confidence gating (OCR-02) depends on this]

### DOCX export (save_to_word)

```python
# Source: github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md
# PP-StructureV3 result object has save_to_word() method:
res.save_to_word(save_path="output/")   # saves result-basename.docx into that dir

# For D-04-33 (Segment-tree → Markdown → DOCX):
# Our segment_to_md.py re-emits Markdown from the translated Segment tree.
# Then pass the Markdown text back to PP-DocTranslation's pipeline.load_from_markdown()
# and call save_to_word — OR use a simpler path: just call python-docx 1.2.0 directly
# on the emitted Markdown (python-docx is already in stack; Markdown→DOCX is simpler).
# RECOMMENDED: Use python-docx directly (already in stack) instead of round-tripping
# through PaddleOCR's DOCX export, which may have layout coupling to the original OCR result.
```

**DOCX path recommendation (Claude's Discretion):** The simplest path for D-04-33 is:
1. `segment_to_md.py` walks the translated Segment tree → emits Markdown string.
2. Parse Markdown with `python-docx` 1.2.0 (already in stack) using a simple paragraph/heading/table writer — no need to invoke PP-StructureV3's `save_to_word()` which is coupled to the original OCR result object structure, not to our translated Segment state. [ASSUMED — architectural recommendation]

---

## fpdf2 API Reference

### Custom page size (double-wide)

```python
# Source: github.com/py-pdf/fpdf2/blob/master/docs/PageFormatAndOrientation.md
# [VERIFIED: Context7 fpdf2]

from fpdf import FPDF

# Dynamic format per source page — custom tuple in mm:
# fpdf2 accepts (width_mm, height_mm) as format tuple to add_page()
# Confirmed from the "Configure Per-Page Backgrounds and Formats" example.
pdf = FPDF(unit="mm")
pdf.add_page()  # default A4

# Per-page custom size (D-04-07: 2x source width):
src_w_mm = src_page_width_pt / 2.8346   # 1pt = 1/72 inch; 1 inch = 25.4mm → /72*25.4 ≈ /2.8346
src_h_mm = src_page_height_pt / 2.8346
pdf.add_page(format=(2 * src_w_mm, src_h_mm))
```

### Font registration (Noto)

```python
# Source: github.com/py-pdf/fpdf2/blob/master/docs/Unicode.md [VERIFIED: Context7]

# Register both fonts once at PDF init:
pdf.add_font("NotoSans", fname="/backend/fonts/NotoSans-Regular.ttf")
pdf.add_font("NotoSansCJK", fname="/backend/fonts/NotoSansCJK-Regular.ttc")

# Set fallback font chain for CJK coverage:
pdf.set_font("NotoSans", size=12)
pdf.set_fallback_fonts(["NotoSansCJK"])  # CJK glyphs fall back to CJK font
```

**Font subset embedding:** fpdf2 2.x auto-subsets fonts at `pdf.output()` — only used glyphs are embedded. The 48MB NotoSansCJK.ttc becomes significantly smaller in the output PDF (typical CJK document uses 2-5MB subset). [CITED: fpdf2 docs Unicode.md]

### Image insertion (left half of double-wide page)

```python
# Source: github.com/py-pdf/fpdf2/blob/master/docs/Images.md [VERIFIED: Context7]
# "Place images side by side" example is directly applicable:

pdf.add_page(format=(2 * src_w_mm, src_h_mm))
# Left half = original page image at full page height, half page width:
pdf.image(
    f".data/jobs/{job_id}/pages/page-{page_num}.png",
    x=0, y=0,
    w=src_w_mm,   # half the double-wide page
    h=src_h_mm,   # full page height
    keep_aspect_ratio=True,
)
```

### Region-positioned text (right half)

```python
# Source: fpdf2 multi_cell docs [VERIFIED: Context7]

def render_region(
    pdf: FPDF,
    translated_text: str,
    region_bbox: tuple[float, float, float, float],  # normalized [0,1]
    src_w_mm: float,
    src_h_mm: float,
    region_label: str,
) -> bool:
    """
    Map normalized bbox from left-side page coordinates to right-side fpdf2 coordinates.
    Returns True if overflow at min font size.
    """
    x0n, y0n, x1n, y1n = region_bbox   # [0,1] normalized to source page
    # Right half starts at x=src_w_mm:
    x_mm = src_w_mm + x0n * src_w_mm
    y_mm = y0n * src_h_mm
    w_mm = (x1n - x0n) * src_w_mm
    h_mm = (y1n - y0n) * src_h_mm

    # Select initial font size based on block_label hint:
    initial_size = 14.0 if region_label in ("doc_title",) else 12.0 if region_label in ("paragraph_title",) else 9.0

    # Binary search for largest font in [8, 24] that fits:
    lo, hi = 8.0, 24.0
    chosen = lo
    for candidate in [hi, (hi+lo)/2, lo]:
        pdf.set_font("NotoSans", size=candidate)
        # get_string_width is per-line; for multi-line, estimate via character density
        # Use h_mm as height cap; fpdf2 multi_cell returns output height:
        # (fpdf2 does not expose measure-without-draw directly — use dry_run=True)
        # ASSUMED: fpdf2 multi_cell dry_run or similar — verify in execution
        chosen = candidate
        break  # PLACEHOLDER: real fit algorithm in plan

    # Position cursor and render:
    pdf.set_xy(x_mm, y_mm)
    pdf.set_font("NotoSans", size=chosen)
    pdf.set_fallback_fonts(["NotoSansCJK"])
    pdf.multi_cell(w=w_mm, text=translated_text, align="L")
    return chosen <= lo  # True = still overflow at minimum
```

**fpdf2 fit-font algorithm guidance:** fpdf2 does not natively expose a dry-run measure function for multi_cell. The practical approach is:
1. Estimate line count: `ceil(len(text) / (w_mm / (font_size * 0.5)))` (rough character-width estimate).
2. Compare estimated height vs `h_mm`.
3. Binary search font_size down from 24 to 8.
This is a reasonable approximation; overflow at min size → emit `FlagType.overflow`. [ASSUMED — no exact API for measure-without-draw]

### Page unit conversion (pt → mm for fpdf2)

```
1 PDF point = 1/72 inch
1 inch = 25.4 mm
→ 1 pt = 25.4/72 mm ≈ 0.3528 mm
→ pt_to_mm(pt) = pt * 25.4 / 72
```

PyMuPDF bboxes are in **PDF points**. fpdf2 default unit is **mm**. The FPDF constructor accepts `unit="pt"` to work in points directly — simplifies the coordinate math considerably:

```python
# Simpler: initialize fpdf2 in points to avoid unit conversion:
pdf = FPDF(unit="pt")
# Then src_w_pt and src_h_pt from PyMuPDF page.rect are used directly.
pdf.add_page(format=(2 * src_w_pt, src_h_pt))
```

[ASSUMED — architectural recommendation; verify fpdf2 accepts pt tuples for format=]

---

## Integration Patterns

### 1. PyMuPDF page-image extraction

```python
# Source: PyMuPDF docs [VERIFIED: existing Phase 3 codebase uses pymupdf]
# Existing backend/.venv/lib/python3.12/site-packages/pymupdf-1.27.2.3

import pymupdf
import os

def extract_page_images(doc: pymupdf.Document, job_id: str, dpi: int = 300) -> list[str]:
    """
    Extract each page as PNG. Returns list of file paths (one per page).
    Used by: OCR stage (input to PP-StructureV3), compose stage (left-side image).
    D-04-10: cached at .data/jobs/{job_id}/pages/page-N.png
    """
    pages_dir = f".data/jobs/{job_id}/pages"
    os.makedirs(pages_dir, exist_ok=True)
    paths: list[str] = []
    for page_num, page in enumerate(doc):
        pixmap = page.get_pixmap(dpi=dpi)
        path = os.path.join(pages_dir, f"page-{page_num}.png")
        pixmap.save(path)  # or .pil_save() if PIL is available
        paths.append(path)
    return paths
```

**Memory budget (300 DPI, A4-ish):** A4 page at 300 DPI ≈ 2480×3508 pixels. RGB PNG ≈ 8MB in memory, ~500KB–2MB on disk (PNG compression). For a 30-page PDF: ~240MB peak memory during extraction (one page at a time — release pixmap after save). Safe for PoC. [ASSUMED — standard DPI math]

### 2. asyncio.to_thread wrapping for PaddleOCR

PaddleOCR's Python API is synchronous — calling it directly in an arq coroutine blocks the event loop.

```python
# Pattern: asyncio.to_thread (Python 3.9+, available on 3.12)
import asyncio

async def ocr_page_async(pipeline: "PPStructureV3", page_path: str) -> list[dict]:
    """
    Wrap synchronous PaddleOCR call in a thread so arq event loop stays responsive.

    NOTE: PaddleOCR does NOT hold the Python GIL during model inference
    (underlying C++/ONNX runtime releases it) — so multiple asyncio.to_thread
    calls CAN run concurrently if OCR_PAGE_CONCURRENCY > 1.
    However, CPU memory contention limits practical parallelism on demo machine.
    Default OCR_PAGE_CONCURRENCY=1 is safe; increase only with empirical testing.
    """
    def _sync_predict() -> list[dict]:
        output = pipeline.predict(input=page_path)
        # output is a list (one element for single image input)
        if not output:
            return []
        res = output[0]
        # Return the parsed result dict
        return res.json.get("layout_parsing_result", {}).get("parsing_res_list", [])

    return await asyncio.to_thread(_sync_predict)
```

**Alternative — ThreadPoolExecutor:** For tighter concurrency control (setting max_workers explicitly):

```python
import concurrent.futures
import asyncio

_OCR_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)

async def ocr_page_async(pipeline, page_path: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _OCR_EXECUTOR,
        lambda: _sync_predict(pipeline, page_path)
    )
```

[ASSUMED — asyncio.to_thread is the recommended modern pattern; GIL release claim needs verification against PaddleOCR 3.x internals]

### 3. SSE stage_progress dispatch (D-04-x)

Extend the existing `_publish_progress()` in `translate_worker.py`:

```python
# Existing Phase 1 payload (translate_worker.py line ~200):
payload = {
    "status": status,
    "stage": stage,
    "segments_done": segments_done,
    "segments_total": segments_total,
    "current_batch": current_batch,
    "retry_count": retry_count,
    "last_message": last_message,
}

# Phase 4 addition: stage_progress substructure (D-04-x SSE):
payload["stage_progress"] = {
    "stage": stage,         # "ocr" | "translate" | "compose"
    "current": current,     # pages done (OCR/compose) or batches done (translate)
    "total": total,         # total pages or batches
}
# Also add low_confidence_pages to needs_review payload:
if low_conf_pages:
    payload["low_confidence_pages"] = low_conf_pages  # list[int]
```

### 4. Worker dispatch for scanned_pdf format

Extend the `match job.input_format` block in `translate_worker.py`:

```python
case "scanned_pdf":
    import pymupdf  # noqa: PLC0415
    from app.pipeline.scanned_pdf.extractor import run_ocr_pipeline  # noqa: PLC0415
    from app.pipeline.scanned_pdf.composer import compose_bilingual_pdf  # noqa: PLC0415

    _pdf_doc = pymupdf.open(job.input_path)
    # OCR stage returns segments + low_confidence_pages
    segments, low_conf_pages = await run_ocr_pipeline(
        pipeline=ctx["ocr_pipeline"],  # PPStructureV3 initialized in startup()
        doc=_pdf_doc,
        job_id=job_id,
        dpi=settings.ocr_page_dpi,
        concurrency=settings.ocr_page_concurrency,
        redis=redis,
    )
    _format_ctx = {
        "type": "scanned_pdf",
        "doc": _pdf_doc,
        "low_conf_pages": low_conf_pages,
    }
```

**PPStructureV3 initialization in arq worker startup():** Instantiate once in `startup()` and store in `ctx["ocr_pipeline"]`. Do NOT create a new PPStructureV3 per job — model loading takes seconds. [VERIFIED: standard pattern for expensive model objects in arq]

### 5. Docker model bake layer (D-04-15)

```dockerfile
# Add AFTER uv pip install (so model cache survives source-only rebuilds):
# But BEFORE COPY src/ src/ (so model cache is not invalidated by code changes)

# Install paddlepaddle CPU (Alibaba index):
RUN python -m pip install paddlepaddle==3.0.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

# Install paddleocr[all] + fpdf2:
RUN uv pip install --system "paddleocr[all]>=3.5,<4" "fpdf2>=2.7,<3"

# Bundle Noto fonts for fpdf2 explicit-path registration (D-04-27):
COPY backend/fonts/ /backend/fonts/

# Bake PP-StructureV3 models at build time (D-04-15):
# This triggers model download to ~/.paddlex/official_models/ (or configured cache dir)
# Pin models by setting PADDLEOCR_HOME to a stable path:
ENV PADDLEOCR_HOME=/paddle_models
RUN python -c "from paddleocr import PPStructureV3; PPStructureV3(device='cpu', use_doc_orientation_classify=False, use_doc_unwarping=False)"

# AFTER model bake, copy source code (code changes don't invalidate model layer):
COPY src/ src/
```

**Model cache size:** PP-StructureV3 downloads ~8-12 sub-models (layout detection, text detection, text recognition, formula, table). Total model size is approximately 500MB–1.5GB depending on enabled components. With `use_chart_recognition=False`, `use_doc_unwarping=False`, estimate ~700MB–1GB. [ASSUMED — based on PaddleX docs citing "~1GB model bake target"]

**Cache path:** PaddleOCR 3.x caches models in `~/.paddlex/official_models/` by default. Can be overridden with `PADDLEOCR_HOME` env var. Setting this to `/paddle_models` in Docker ensures predictable location for the bake layer. [ASSUMED — verify exact env var name in PaddleOCR 3.5.x docs]

### 6. Scanned PDF detection heuristic (D-04-17)

```python
# backend/src/app/pipeline/scanned_pdf/detector.py
import pymupdf

def is_scanned_pdf(doc: pymupdf.Document, threshold: float = 50.0) -> bool:
    """
    D-04-17: classify PDF as scanned if extractable text chars/page < threshold.

    Rationale for 50 chars/page:
    - A native text page with even one sentence has 50+ chars.
    - A scanned page with no text layer has 0 chars.
    - A mixed page (native + scan) may have header/footer text only → ~20-40 chars.
    - Threshold 50 is conservative; configurable via OCR_TEXT_DENSITY_THRESHOLD env.

    Edge cases:
    - Form PDFs: may have fillable text fields embedded as AcroForm objects.
      get_text() extracts form field text, so forms often misclassify as native.
      Acceptable for PoC — user override available (D-04-17 override toggle).
    - Image-only PDFs with hidden text layers (searchable scans from Adobe Acrobat):
      get_text() returns the hidden layer text → classified as native.
      Also acceptable — the hidden layer IS the text.
    """
    if len(doc) == 0:
        return False
    total_chars = sum(
        len(page.get_text().strip()) for page in doc
    )
    return (total_chars / len(doc)) < threshold
```

**Why 50 chars/page:** Similar tools (pdf2docx, pdfminer) use 10-20 chars/page as a stricter threshold. 50 gives more safety margin for headers/footers on mostly-scanned pages. [ASSUMED — empirical recommendation; tune during smoke test]

---

## Schema Migration Recipe (Alembic 0006)

**Important naming note:** The existing migration `0005_widen_flag_type.py` is already present (widened VARCHAR to 32). The next migration should be numbered **0006**. The CONTEXT.md refers to it as "Alembic 0005" but the actual file sequence is 0006.

```python
# backend/src/app/db/migrations/versions/0006_phase4_ocr.py
"""Phase 4: Scanned PDF OCR schema additions.

Adds:
- segments: confidence (Float nullable), region_bbox (JSON nullable),
            region_label (String 64 nullable), edited_source_text (Text nullable)
- segments.kind: already stored as plain string column (not SA Enum) per 03.2 decision,
                 so adding "ocr_text" value is a no-op (VARCHAR accepts any string)
- FlagType values: figure_passthrough, ocr_page_error (VARCHAR — no DDL needed)
- jobs.input_format: add "scanned_pdf" value (VARCHAR — no DDL needed)
- jobs.stage enum: add "ocr", "compose" values
  (stage uses SA native Enum — REQUIRES ALTER TYPE, see below)
"""
from __future__ import annotations
from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = "0006_phase4_ocr"
down_revision: Union[str, None] = "0005_widen_flag_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add columns to segments table
    op.add_column("segments", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("segments", sa.Column("region_bbox", sa.JSON(), nullable=True))
    op.add_column("segments", sa.Column("region_label", sa.String(length=64), nullable=True))
    op.add_column("segments", sa.Column("edited_source_text", sa.Text(), nullable=True))

    # 2. Extend JobStage SA Enum (native PostgreSQL enum — requires ALTER TYPE).
    # CRITICAL: PostgreSQL ALTER TYPE ADD VALUE cannot run inside a transaction.
    # Use op.execute() which runs outside the implicit transaction, OR use
    # op.get_bind().execute() after closing the current transaction.
    # The safest pattern for Alembic: use literal SQL outside the transaction block.
    op.execute("COMMIT")  # close Alembic's implicit transaction
    op.execute("ALTER TYPE jobstage ADD VALUE IF NOT EXISTS 'ocr'")
    op.execute("ALTER TYPE jobstage ADD VALUE IF NOT EXISTS 'compose'")
    # Note: cannot rollback ADD VALUE in PostgreSQL < 14. IF NOT EXISTS is idempotent.


def downgrade() -> None:
    op.drop_column("segments", "edited_source_text")
    op.drop_column("segments", "region_label")
    op.drop_column("segments", "region_bbox")
    op.drop_column("segments", "confidence")
    # Note: PostgreSQL does not support DROP VALUE from enum — downgrade cannot
    # remove 'ocr' and 'compose' from jobstage. This is acceptable for PoC.
    # Manually run: UPDATE jobs SET stage='failed' WHERE stage IN ('ocr', 'compose')
    # before removing enum values via pg_catalog (requires superuser).
```

**Known pitfall: ALTER TYPE in transaction.** PostgreSQL 12–15 requires `ALTER TYPE ADD VALUE` to be executed outside an explicit transaction. Alembic wraps each migration in a transaction by default. The pattern above uses `op.execute("COMMIT")` to close the transaction first — this is the standard workaround and is safe. [VERIFIED: SQLAlchemy/Alembic documentation pattern for PostgreSQL enum extension]

**Existing segment kind column:** The `Segment.kind` field in `pipeline/segment.py` is a plain Python `str` field (not a PostgreSQL native Enum). The ORM model `backend/src/app/db/models.py` does NOT have a `kind` column (it was left in-memory per Phase 3.2 "DB column for kind is optional in this PoC" decision). Phase 4 must add the `kind` column to the DB if segments need to be queried by kind. This is an open question — if `kind` is only needed in-memory during a job run, no migration needed; if the review UI or export needs to filter by `kind`, add a `String(32)` column. [ASSUMED — recommend adding it in migration for forward compat]

**FlagType enum note:** `FlagType` in the ORM uses `native_enum=False` (VARCHAR storage per migration 0002). New values `figure_passthrough` and `ocr_page_error` are valid VARCHAR strings immediately — no DDL needed. Migration 0006 should document this in a comment but requires no DDL for these values, mirroring the pattern in `0004_flagtype_phase3.py`. [VERIFIED: 0004_flagtype_phase3.py and 0002_phase2_glossary_flags.py confirm VARCHAR storage]

---

## Common Pitfalls

### Pitfall 1: block_bbox is a polygon, not a flat rect

**What goes wrong:** Treating `block_bbox` as `[x0, y0, x1, y1]` — it is actually `np.ndarray shape (4,2)` with four corner points.

**Why it happens:** The docs and JSON examples show a 2D polygon array. Simple indexing `block_bbox[0]` returns the first corner, not x0.

**How to avoid:** Always extract axis-aligned rect via:
```python
bbox = block["block_bbox"]   # numpy array (4,2) int16
x0, y0 = int(bbox[:, 0].min()), int(bbox[:, 1].min())
x1, y1 = int(bbox[:, 0].max()), int(bbox[:, 1].max())
```

**Warning signs:** `region_bbox` normalization producing values > 1.0 or negative.

### Pitfall 2: paddlepaddle installed from wrong index

**What goes wrong:** `pip install paddlepaddle` from standard PyPI installs an outdated or stub version that does not include the inference backend. PaddleOCR import fails with a cryptic AttributeError.

**Why it happens:** Standard PyPI `paddlepaddle` lags behind the Alibaba package index by months.

**How to avoid:** Always install via:
```bash
python -m pip install paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```
In `pyproject.toml`, do NOT list `paddlepaddle` as a dependency (pip extras conflict with the index). Install it separately in Dockerfile before `uv pip install`. [CITED: PaddleOCR installation guide]

### Pitfall 3: PaddleOCR cold model init in Docker

**What goes wrong:** First call to `PPStructureV3()` on a fresh container downloads ~1GB of models. Demo-day container startup fails or times out.

**Why it happens:** Models are downloaded lazily on first init.

**How to avoid:** D-04-15 Dockerfile bake step — `RUN python -c 'from paddleocr import PPStructureV3; PPStructureV3(...)'` before `COPY src/`. Set `PADDLEOCR_HOME` to a stable path so the bake layer is cached.

**Warning signs:** First job takes 5-10 minutes; subsequent jobs are fast.

### Pitfall 4: PaddleOCR sync call blocking arq event loop

**What goes wrong:** Calling `pipeline.predict(page_path)` directly in an `async def` function stalls the arq event loop for the duration of CPU inference (potentially 5-60 seconds per page on CPU).

**Why it happens:** PaddleOCR 3.x Python API is synchronous — no async variant.

**How to avoid:** Always wrap in `asyncio.to_thread()` or `loop.run_in_executor()`. Keep `OCR_PAGE_CONCURRENCY=1` (default) to avoid memory contention.

### Pitfall 5: fpdf2 in points vs mm unit mismatch

**What goes wrong:** Mixing PyMuPDF's point-unit bboxes with fpdf2's default mm units produces grossly misscaled text placement.

**Why it happens:** PyMuPDF `page.rect.width` is in PDF points; fpdf2 `FPDF(unit="mm")` expects mm.

**How to avoid:** Either initialize `FPDF(unit="pt")` for direct point-unit compatibility, OR apply `pt_to_mm = lambda pt: pt * 25.4 / 72` consistently at every conversion site.

### Pitfall 6: ALTER TYPE ADD VALUE inside Alembic transaction

**What goes wrong:** Alembic migration fails with `ActiveSqlTransaction: ALTER TYPE ADD VALUE cannot run inside a transaction block`.

**Why it happens:** PostgreSQL 12–15 forbids `ALTER TYPE ADD VALUE` inside a transaction.

**How to avoid:** Issue `op.execute("COMMIT")` before `ALTER TYPE` statements in the migration `upgrade()` function. [VERIFIED: standard Alembic workaround]

### Pitfall 7: CJK line-break rules in fpdf2 multi_cell

**What goes wrong:** Japanese/Chinese text does not word-wrap correctly — fpdf2 breaks on spaces (Latin word-break rule), producing overfull lines for CJK text.

**Why it happens:** fpdf2 uses Latin word-breaking by default; CJK text has no spaces between characters.

**How to avoid:** fpdf2 supports `wrapmode="CHAR"` on `multi_cell()` for character-level wrapping (needed for CJK):
```python
pdf.multi_cell(w=w_pt, text=cjk_text, wrapmode="CHAR")
```
[CITED: fpdf2 docs — wrapmode parameter on multi_cell]

### Pitfall 8: Confidence path in PP-StructureV3 res.json

**What goes wrong:** `res.json.get("overall_ocr_res", {}).get("rec_scores", [])` returns empty list — the actual key path is different in PP-StructureV3 vs the bare OCR pipeline.

**Why it happens:** PP-StructureV3 is a composite pipeline; the JSON nesting differs from the standalone text-recognition pipeline documented in Quick Start.

**How to avoid:** During the first integration test, print the full `res.json` dict to inspect the actual structure. Write a `_extract_page_confidence(res_json: dict) -> float` helper that defensively navigates possible key paths and logs a warning if the path is not found (returning 1.0 as safe fallback).

### Pitfall 9: PyMuPDF pixmap memory not released

**What goes wrong:** Extracting all pages at once before releasing pixmaps causes OOM on long documents.

**Why it happens:** Each 300 DPI pixmap is ~8-24MB in memory.

**How to avoid:** Extract and save one page at a time inside the loop:
```python
for page in doc:
    pix = page.get_pixmap(dpi=dpi)
    pix.save(path)
    del pix   # explicit release — pixmap holds C-level memory
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OCR + layout detection | Custom CV pipeline | PP-StructureV3 | SOTA multilingual, 23 layout classes, XY-Cut reading order |
| PDF generation | ReportLab or raw PDF bytes | fpdf2 | CLAUDE.md explicitly bans ReportLab for CJK |
| CJK font handling | Manual glyph registration | fpdf2 `add_font()` + `set_fallback_fonts()` | fpdf2 handles Unicode subsetting automatically |
| DOCX from Markdown | Custom XML writer | python-docx 1.2.0 (already in stack) | Already a project dependency; battle-tested |
| Model download caching | Custom model registry | PaddleOCR's built-in cache (`PADDLEOCR_HOME`) | Built-in; just bake in Docker layer |
| Reading order detection | XY-Cut algorithm | PP-StructureV3 `block_order` | Already computed by model; trust it (D-04-20) |

---

## Runtime State Inventory

This is a new format (scanned PDF) — no rename/refactor involved. No runtime state migration required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | No existing scanned_pdf jobs in DB | None |
| Live service config | No external service config changes | None — Docker image rebuild for model bake |
| OS-registered state | None | None |
| Secrets/env vars | `OCR_PAGE_DPI`, `OCR_PAGE_CONCURRENCY`, `OCR_TEXT_DENSITY_THRESHOLD` — new env vars | Add to docker-compose.yml env section with defaults |
| Build artifacts | New `backend/fonts/` directory needed | Copy NotoSans-Regular.ttf + NotoSansCJK-Regular.ttc into backend/fonts/ |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | paddleocr, fpdf2, all | ✓ | 3.12.3 | — |
| Docker | Model bake layer | ✓ | 29.2.1 | — |
| paddleocr | OCR stage | ✗ | — (not installed) | Must install in Dockerfile |
| paddlepaddle | paddleocr backend | ✗ | — (not installed) | Must install from Alibaba index |
| fpdf2 | Compose stage | ✗ | — (not installed) | Must install |
| pymupdf | Page image extraction | ✓ (in venv) | 1.27.2.3 | — |
| NotoSansCJK-Regular.ttc | fpdf2 CJK font | ✓ (apt fonts-noto-cjk in Dockerfile) | — | Already in base Docker image |
| NotoSans-Regular.ttf | fpdf2 Latin/VN font | ✓ (apt fonts-noto in Dockerfile) | — | Already in base Docker image |
| Redis | SSE progress pub/sub | ✓ (docker-compose service) | 7.x | — |
| PostgreSQL | Job + Segment persistence | ✓ (docker-compose service) | 16.x | — |

**Missing dependencies with no fallback:**
- `paddleocr>=3.5,<4` — must be installed in Dockerfile
- `paddlepaddle==3.0.0` (CPU) — must be installed from Alibaba index in Dockerfile
- `fpdf2>=2.7,<3` — must be added to pyproject.toml

**Missing dependencies with fallback:**
- None for PoC scope.

**Font note:** The apt-installed Noto fonts are present in the Docker image (base layer from Phase 1). The `backend/fonts/` bundle (D-04-27) needs explicit TTF/TTC files because fpdf2 requires explicit file paths and the system font paths (e.g., `/usr/share/fonts/`) may vary. Copy fonts from apt into `backend/fonts/` during Dockerfile build, or download directly from Google Fonts in the Dockerfile.

---

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation: true` in config.json).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `backend/pyproject.toml` — `[tool.pytest.ini_options]` asyncio_mode = "auto" |
| Quick run command | `pytest backend/tests/pipeline/test_scanned_pdf_*.py -x -m "not integration"` |
| Full suite command | `pytest backend/tests/ --cov=src/app --cov-fail-under=80` |
| Integration run | `pytest backend/tests/ -m integration` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OCR-01 | PP-StructureV3 returns parsing_res_list with confidence per region | unit (mock Paddle) | `pytest tests/pipeline/test_scanned_pdf_extractor.py -x` | ❌ Wave 0 |
| OCR-01 | page-N.png extracted from scanned PDF | unit (pymupdf synthetic) | `pytest tests/pipeline/test_scanned_pdf_extractor.py::test_page_images_extracted -x` | ❌ Wave 0 |
| OCR-02 | Page with mean conf <0.7 → Job.needs_review | unit (mock Paddle with low scores) | `pytest tests/pipeline/test_scanned_pdf_extractor.py::test_low_confidence_triggers_needs_review -x` | ❌ Wave 0 |
| OCR-03 | Bilingual PDF: page count matches source, left/right halves | unit (real fpdf2, synthetic Segments) | `pytest tests/pipeline/test_scanned_pdf_composer.py -x` | ❌ Wave 0 |
| OCR-03 | NotoSansCJK font embedded in output PDF | unit (real fpdf2) | `pytest tests/pipeline/test_scanned_pdf_composer.py::test_cjk_font_embedded -x` | ❌ Wave 0 |
| OCR-04 | OCR stage retry on PaddleOCR exception | unit (mock Paddle raises) | `pytest tests/pipeline/test_scanned_pdf_extractor.py::test_ocr_retry -x` | ❌ Wave 0 |
| OCR-04 | Three stage_progress SSE events (ocr/translate/compose) | unit (mock redis publish) | `pytest tests/workers/test_translate_worker_scanned.py -x` | ❌ Wave 0 |
| OCR-01..04 | Real PaddleOCR + DashScope on VN fixture | integration | `pytest tests/integration/test_scanned_pdf_roundtrip.py -m integration` | ❌ Wave 0 |

### Failure Modes

| Failure Mode | Trigger | Expected Behavior | Test Coverage |
|-------------|---------|-------------------|--------------|
| Bad scan / corrupted page image | PyMuPDF fails on page | `FlagType.ocr_page_error`; placeholder on right; job continues | unit: mock pymupdf raise |
| Low OCR confidence (<0.7) | PaddleOCR rec_scores all low | Job → `needs_review`; banner in review UI | unit: mock rec_scores=[0.3] |
| Text expansion overflow (right side) | Translated text > region bbox at 8pt | `FlagType.overflow` on Segment; right side shows best-effort | unit: real fpdf2 with long translated text |
| Figure block detected | block_label = "image"/"chart" | `FlagType.figure_passthrough` + `[Figure on left]` placeholder | unit: mock parsing_res with image block |
| Mixed PDF (some pages native) | D-04-18 per-page detection | Native pages use Phase 3 extractor; scanned pages use PP-StructureV3 | unit: PyMuPDF synthetic mixed doc |
| PaddleOCR model not found | Docker missing model bake | Container startup fails with ImportError | Manual: verify Docker build step |
| DashScope API failure in translate | Network error / 5xx | Exponential backoff (Phase 1 CORE-06); 3 retries; job failed | unit: existing translate_batch tests |
| fpdf2 compose disk error | `.data/jobs/` not writable | Compose stage raises; job → failed | unit: mock file open to raise |
| Confidence path missing in res.json | PP-StructureV3 JSON structure differs from assumed | `_extract_page_confidence` returns 1.0 fallback; logs warning | unit: pass mock res.json without rec_scores key |

### Validation Dimensions

| Dimension | Criteria | How Verified |
|-----------|---------|-------------|
| Correctness | OCR'd text Segments have source_text from PaddleOCR | Unit: mock Paddle → check Segment.source_text |
| Correctness | region_bbox is normalized [0,1] | Unit: assert all(0 <= v <= 1 for v in bbox) |
| Robustness | page with mean conf 0.65 → needs_review, 0.75 → no flag | Unit: parametrize on mock scores |
| Robustness | Per-page PaddleOCR crash → job continues, placeholder emitted | Unit: mock predict() raises on page 2 |
| Performance | CPU inference time per page logged (structlog stage_duration_ms) | Integration: log inspection |
| Safety | No scanned PDF job returns 0 output files | Unit: assert len(compose_outputs) == 3 |
| Observability | All three stages publish stage_progress SSE | Unit: mock redis, assert 3 publish calls |

### Sampling Rate

- Per task commit: `pytest backend/tests/pipeline/test_scanned_pdf_*.py -x -m "not integration"`
- Per wave merge: `pytest backend/tests/ --cov=src/app --cov-fail-under=80 -m "not integration"`
- Phase gate: Full suite (including `@pytest.mark.integration`) green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/pipeline/test_scanned_pdf_detector.py` — covers scanned detection heuristic
- [ ] `backend/tests/pipeline/test_scanned_pdf_extractor.py` — covers OCR-01, OCR-02, OCR-04 (mock PaddleOCR)
- [ ] `backend/tests/pipeline/test_scanned_pdf_composer.py` — covers OCR-03 (real fpdf2)
- [ ] `backend/tests/workers/test_translate_worker_scanned.py` — covers stage dispatch + SSE
- [ ] `backend/tests/integration/test_scanned_pdf_roundtrip.py` — `@pytest.mark.integration` real Paddle + DashScope
- [ ] `backend/tests/fixtures/scanned/` — 4 demo fixtures (D-04-21); bad-quality.pdf can be synthesized in conftest
- [ ] Framework install: `uv pip install --system "paddleocr[all]>=3.5,<4" fpdf2>=2.7,<3` — post-pyproject.toml update

---

## Security Domain

`security_enforcement` is absent from config.json → treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Validate uploaded file is a real PDF before OCR; max 25MB (UPLD-01); reject non-PDF MIME types |
| V2 Authentication | no | Phase 4 is single-user internal PoC |
| V6 Cryptography | no | No cryptographic operations |
| V4 Access Control | minimal | Job-scoped file access: `.data/jobs/{id}/` paths are only accessible by the job's worker |

### Known Threat Patterns for OCR + file serving

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via job_id | Tampering | Validate `job_id` is a valid UUID before building `.data/jobs/{job_id}/pages/` path; reject non-UUID strings |
| Malformed PDF causing PyMuPDF crash | Denial of Service | Wrap `pymupdf.open()` in try/except; catch `RuntimeError` (malformed PDF); return `FlagType.ocr_page_error` |
| PaddleOCR model poisoning via PADDLEOCR_HOME | Elevation of Privilege | Pin model SHA checksums in Dockerfile; do not allow env override at runtime |
| Page image disk exhaustion | Denial of Service | Enforce 25MB source file limit (UPLD-01); 300 DPI A4 yields ~2MB PNG/page; 30-page PDF ≈ 60MB pages dir; monitor `.data/` disk usage |

---

## Code Examples

### Complete PP-StructureV3 predict call with output parsing

```python
# Source: github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md
# [VERIFIED: Context7 /paddlepaddle/paddleocr]

from paddleocr import PPStructureV3

pipeline = PPStructureV3(
    device="cpu",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
)

output = pipeline.predict(input="path/to/page-0.png")
for res in output:
    res.print()
    json_data = res.json
    # Inspect parsing_res_list:
    parsing_list = json_data.get("layout_parsing_result", {}).get("parsing_res_list", [])
    # Sort by reading order:
    ordered = sorted(
        [r for r in parsing_list if r.get("block_order") is not None],
        key=lambda r: r["block_order"]
    )
```

### fpdf2 bilingual PDF: double-wide page with side-by-side image + text

```python
# Source: github.com/py-pdf/fpdf2/blob/master/docs/Images.md [VERIFIED: Context7]
# Source: github.com/py-pdf/fpdf2/blob/master/docs/PageFormatAndOrientation.md [VERIFIED: Context7]

from fpdf import FPDF
import pymupdf

def compose_bilingual_page(
    pdf: FPDF,
    page_image_path: str,
    segments: list,   # Segments for this page, ordered by block_order
    translated_map: dict[str, str],
    src_w_pt: float,
    src_h_pt: float,
) -> None:
    """Add one double-wide page to pdf: left=source image, right=translated text."""
    # Use pt units throughout (initialized with FPDF(unit="pt"))
    pdf.add_page(format=(2 * src_w_pt, src_h_pt))

    # Left half: original page image
    pdf.image(
        page_image_path,
        x=0, y=0,
        w=src_w_pt, h=src_h_pt,
        keep_aspect_ratio=True,
    )

    # Right half: translated text, region-positioned
    for seg in segments:
        if seg.region_bbox is None:
            continue
        x0n, y0n, x1n, y1n = seg.region_bbox
        x_pt = src_w_pt + x0n * src_w_pt
        y_pt = y0n * src_h_pt
        w_pt = (x1n - x0n) * src_w_pt
        h_pt = (y1n - y0n) * src_h_pt

        translated = translated_map.get(seg.id, seg.source_text)
        font_size = _fit_font_size(pdf, translated, w_pt, h_pt)  # [8, 24]

        pdf.set_xy(x_pt, y_pt)
        pdf.set_font("NotoSans", size=font_size)
        pdf.set_fallback_fonts(["NotoSansCJK"])
        wrapmode = "CHAR" if _needs_char_wrap(translated) else "WORD"
        pdf.multi_cell(w=w_pt, text=translated, align="L", wrapmode=wrapmode)
```

### Alembic migration for ALTER TYPE (PostgreSQL enum extension)

```python
# [VERIFIED: standard Alembic workaround for PostgreSQL ALTER TYPE ADD VALUE]
def upgrade() -> None:
    op.add_column("segments", sa.Column("confidence", sa.Float(), nullable=True))
    # ... other column adds ...

    # Extend SA native enum (JobStage) — must be outside transaction:
    op.execute("COMMIT")
    op.execute("ALTER TYPE jobstage ADD VALUE IF NOT EXISTS 'ocr'")
    op.execute("ALTER TYPE jobstage ADD VALUE IF NOT EXISTS 'compose'")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tesseract 5 for JA/ZH | PaddleOCR PP-OCRv5 / PP-StructureV3 | 2024-2025 | +13pp on multilingual benchmarks vs PP-OCRv4; Japanese detection +30% |
| bare OCR → flat text | PP-StructureV3 with layout labels + reading order | PaddleOCR 3.0 (2025) | Structure-aware translation; preserve heading/table layout |
| PyFPDF | fpdf2 (2020+) | 2020 (fork) | Unicode TrueType subset, multi_cell wrapmode, keep_aspect_ratio, active maintenance |

**Deprecated/outdated:**
- `Tesseract` for Japanese: poor JA model, no layout analysis. CLAUDE.md explicitly bans it.
- `ReportLab` for CJK PDF generation: CLAUDE.md explicitly bans it.
- `PaddleOCR 2.x` API: `PPStructure` class (v2 API) replaced by `PPStructureV3` in v3.x; do not use `from paddleocr import PPStructure`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `lang="multilingual"` is the correct init param for PP-OCRv5 106-lang model | PP-StructureV3 API Reference | OCR accuracy may be lower if wrong model variant loaded; easily corrected at execution time |
| A2 | Page confidence available at `res.json["overall_ocr_res"]["rec_scores"]` in PP-StructureV3 output | PP-StructureV3 API Reference | OCR-02 confidence gating broken; critical — must verify on first real call |
| A3 | `asyncio.to_thread` works for PaddleOCR because underlying inference releases GIL | Integration Patterns §2 | If GIL not released, event loop will still block (just in a thread, which is better but adds overhead). Worst case: switch to ProcessPoolExecutor. |
| A4 | `FPDF(unit="pt")` with `add_page(format=(2*w_pt, h_pt))` is a valid fpdf2 call | fpdf2 API Reference | Must verify fpdf2 accepts (width, height) tuple in pt units; from docs the format param accepts tuples but tested examples use mm |
| A5 | DOCX export via python-docx is simpler than PP-StructureV3 save_to_word for D-04-33 | Architecture Patterns | If PP-StructureV3 save_to_word produces better DOCX structure, the recommendation is wrong — but python-docx is already proven in stack |
| A6 | PP-StructureV3 CPU inference: ~30–120 seconds per page on x86_64 (no GPU) | Environment Availability | If much slower, demo-day experience suffers; measure in smoke script and enforce OCR_PAGE_DPI reduction as mitigation |
| A7 | `PADDLEOCR_HOME` env var overrides model cache directory in PaddleOCR 3.5.x | Docker model bake recipe | If wrong env var name, model bake step fails silently and cold-start reappears on demo day |
| A8 | Segment.kind column does not exist in DB yet (Phase 3.2 kept it in-memory only) | Schema Migration Recipe | If existing DB already has a kind column from Phase 3.2 gap-closure, migration would fail on duplicate column |
| A9 | fpdf2 `multi_cell(wrapmode="CHAR")` is available in fpdf2 2.7+ | CJK pitfall | If wrapmode param was introduced later, CJK wrapping fails silently |
| A10 | `paddleocr[all]` extras require Python >=3.9 (stated in installation guide) but Python 3.12 is compatible | Standard Stack | Non-issue (project requires 3.12 which is >=3.9) |

---

## Open Questions

1. **Confidence path in PP-StructureV3 res.json (HIGH PRIORITY)**
   - What we know: OCR pipeline JSON shows `rec_scores` at `res.json["rec_scores"]` for standalone text recognition; PP-StructureV3 is a composite pipeline with different JSON structure.
   - What's unclear: Exact nested key path for per-line recognition confidence in PP-StructureV3 output.
   - Recommendation: In Wave 0, run `PPStructureV3().predict(test_image)[0].save_to_json("debug/")` and inspect the JSON to locate confidence scores before implementing `_extract_page_confidence()`.

2. **`lang` parameter for multilingual model**
   - What we know: Docs show `lang="en"` for English-only and no `lang` param for Chinese+English default.
   - What's unclear: Whether `lang="multilingual"` or some other value activates the 106-language model, or if it's the default.
   - Recommendation: Check the PP-StructureV3 docs appendix (section 5 in the GitHub .md) for the supported lang values table. Default (no lang) may already be multilingual.

3. **DOCX compose path (D-04-33): save_to_word vs python-docx**
   - What we know: PP-StructureV3 has `res.save_to_word()` but it is coupled to the original OCR result object, not to our translated Segment state.
   - What's unclear: Whether we can reconstruct a result object from translated Segments to call save_to_word(), or whether python-docx is the simpler path.
   - Recommendation: Use python-docx 1.2.0 directly via `segment_to_md.py` + a simple Markdown-to-DOCX writer. This is architecturally cleaner and avoids coupling to PaddleOCR internals.

4. **fpdf2 measure-without-draw for font fitting**
   - What we know: fpdf2 does not expose a documented dry-run measure for `multi_cell`.
   - What's unclear: Whether `get_string_width()` or a `FPDF.offset_rendering()` context manager can be used to measure without drawing.
   - Recommendation: Use character-count heuristic for font-size fitting (estimate chars per line from font metrics) as primary approach. If fpdf2 2.8.x adds a measure API, use it; otherwise accept approximation.

5. **Alembic migration number (0006 vs 0005)**
   - What we know: CONTEXT.md refers to "Alembic 0005" for Phase 4. But the file `0005_widen_flag_type.py` already exists.
   - What's unclear: Was CONTEXT.md written before or after 0005_widen_flag_type was created?
   - Recommendation: Name the Phase 4 migration `0006_phase4_ocr.py`. If the planner was expecting `0005`, clarify with the team before creating conflicting files.

6. **Segment.kind DB column existence**
   - What we know: Phase 3.2 decided "DB column for kind is optional in this PoC (in-memory only)". The ORM model does not show a `kind` column.
   - What's unclear: Whether Phase 4 needs `kind` persisted to DB (for review UI filtering by kind=ocr_text vs kind=text on mixed PDFs).
   - Recommendation: Add `kind` as a `String(32)` column in migration 0006 with default `"text"`. Cost is minimal; enables future mixed-PDF filtering and review UI differentiation.

---

## Sources

### Primary (HIGH confidence)
- Context7 `/paddlepaddle/paddleocr` — PP-StructureV3 API, parsing_res_list schema, install commands
- Context7 `/py-pdf/fpdf2` — add_font, multi_cell, image(), custom page format, Unicode/CJK
- `backend/src/app/db/migrations/versions/0004_flagtype_phase3.py` — confirmed VARCHAR enum pattern (no DDL for new values)
- `backend/src/app/db/migrations/versions/0005_widen_flag_type.py` — confirmed existing migration numbering
- `backend/src/app/workers/translate_worker.py` — confirmed match/case dispatch pattern for new format
- `backend/src/app/pipeline/pdf/reassembler.py` — confirmed kind-aware dispatch pattern to reuse
- `backend/pyproject.toml` — confirmed Python 3.12 requirement, existing deps

### Secondary (MEDIUM confidence)
- pypi.org/project/paddleocr — confirmed version 3.5.0, Python 3.8–3.13 support
- pypi.org/project/fpdf2 — confirmed version 2.8.7, Python 3.10–3.14
- paddlepaddle.github.io/PaddleX/3.3/en/installation/paddlepaddle_install.html — CPU install command
- github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md — init API, save_to_word, predict() usage
- github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-DocTranslation.en.md — parsing_res_list fields + JSON example

### Tertiary (LOW confidence, flagged)
- Confidence path `overall_ocr_res.rec_scores` in PP-StructureV3 — inferred from OCR pipeline Quick Start JSON; not directly confirmed for PP-StructureV3 composite output
- `lang="multilingual"` param value — not explicitly confirmed for 106-language model
- CPU inference timing estimate (30–120s/page) — inferred from PaddleX benchmark tables (GPU vs CPU ratio)
- `PADDLEOCR_HOME` env var name for cache override — inferred from general PaddleX docs

---

## Metadata

**Confidence breakdown:**
- Standard stack (paddleocr, paddlepaddle, fpdf2 versions): HIGH — verified from PyPI + Context7
- PP-StructureV3 API (predict, parsing_res_list schema, save_to_word): MEDIUM — verified from official GitHub docs; confidence extraction path ASSUMED
- fpdf2 API (add_font, multi_cell, image, custom page): HIGH — verified via Context7
- Alembic migration recipe: HIGH — derived from existing migration patterns in codebase
- asyncio.to_thread pattern: MEDIUM — standard Python pattern; GIL behavior for PaddleOCR ASSUMED
- Docker bake recipe: MEDIUM — standard Docker pattern; PADDLEOCR_HOME name ASSUMED

**Research date:** 2026-04-28
**Valid until:** 2026-05-28 (30 days — paddleocr 3.x is actively developed; re-verify if >30 days)
