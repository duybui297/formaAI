# Module: pipeline

## Purpose
Format-aware extract → translate → reassemble for DOCX / PDF / PPTX, plus a separate scanned-PDF OCR path. Each format walks its native document model, emits an ordered list of `Segment` objects (deterministic IDs), sends source text to the translator, then writes translations back into a copy of the original — preserving run-level formatting, layout, fonts, and structural references as far as the format allows.

## Shared

### `segment.py`
- `Segment` dataclass — the universal unit passed between extract, translate, reassemble.
- Identity: `id = sha256(source_text + "\x00" + structural_position)[:16]` (D-06). Deterministic and job-independent — enables translation-memory reuse without schema migration. Null-byte separator prevents hash collisions.
- Key fields: `seq_in_job` (walk-order index), `source_text`, `structural_position` (e.g. `body.para.0`, `page.0.col.1.block.3`, `slide.2.shape.0.tf.0.para.1`), `translated_text`, `run_index` / `run_group_size` (DOCX/PPTX run-slot targeting), `kind` (`text` | `table_cell` | `math_passthrough` | `ocr_text` | `figure_passthrough`).
- DOCX tracked-change flags: `is_comment`, `is_inserted`, `is_deleted`.
- OCR fields (Phase 4): `confidence`, `region_bbox` (normalized `[0,1]`), `region_label` (PP-StructureV3 block label), `edited_source_text` (reviewer OCR correction).
- `Segment.from_text(...)` factory computes the SHA ID then constructs.

### `placeholder.py`
- Sentinel protection of non-translatable tokens (CORE-05). `extract_placeholders(text) → (masked_text, {n: token})` replaces URLs, emails, `{{...}}` / `${...}` / `<%...%>` template vars, ISO dates, `vN.N` version strings, and HTML markup tags (`<b>`, `<i>`, `<h1>`, `<span ...>` emitted by PDF `spans_to_html`) with `⟦T{n}⟧` markers before sending to qwen-mt-turbo. `restore_placeholders(text, tokens)` swaps markers back.
- T-04-03: missing marker indices are left visible in output (never silently dropped); `PlaceholderRestoreError` available for strict pipelines.

## Per-format submodules

### docx/
| File | Responsibility |
|------|----------------|
| `extractor.py` | Full-document traversal (`walk_document`) using `doc.iter_inner_content()` + `cell.iter_inner_content()` — body paras, table cells (row-major, nested-table recursion), headers/footers/even/first-page variants. NFC-normalizes (CORE-04). `extract_segments()` emits one segment per non-empty paragraph; `extract_run_segments()` splits at run-format boundaries, merging consecutive same-format runs into one segment (`run_index`, `run_group_size`) to cut DashScope call volume. |
| `reassembler.py` | Write-back. `write_translated_paragraph` writes into `runs[0].text` and blanks `runs[1:]` — never `paragraph.text = value` (would call `paragraph.clear()` and destroy all `<w:rPr>`). `write_translated_run` targets the specific `run_index` slot, blanking the merged group. `reassemble_docx` / `reassemble_docx_runs` re-walk in the same order as extraction and pair by walk-order counter (not by parsing `structural_position`). |
| `tracked.py` | Tracked-changes (DOCX-04, D-13). `has_tracked_changes` string-searches body XML for `<w:ins>`/`<w:del>` (drives upload modal). `strip_tracked_changes` unwraps `<w:ins>` (promote children, keep accepted text) and removes `<w:del>` entirely. Preserve path is deferred. |

Notes: Run-level replacement strategy keeps bold/italic/underline/font/color intact. Out-of-bounds `run_index` (malformed DOCX shifting run counts) logs a warning and skips — degraded output, never a crash (T-13-01). Color access in format-key detection is wrapped in try/except (T-13-02).

### pdf/
| File | Responsibility |
|------|----------------|
| `extractor.py` | PyMuPDF `page.get_text("dict")` block extraction (type==0 only — image blocks lack `lines`). Walks pages → columns (left-to-right) → blocks (top-to-bottom). `spans_to_html` converts spans to minimal HTML (`<b>`/`<i>`/`<h1>`/`<h2>`) via flags + font-name suffix + variant-font heuristics + spatial/height paragraph-break detection. Table cells extracted via `find_tables()` (`table.rows[r].cells[c]`, NOT flat `cells[]`); blocks overlapping cell rects are filtered to avoid double-emission. Math/symbol-font blocks emitted as `kind="math_passthrough"` (skipped from translation). |
| `reassembler.py` | Redact-and-reinsert (PDF-02). Three strict passes per page: (1) all `add_redact_annot`, (2) single `apply_redactions` with `PDF_REDACT_IMAGE_NONE` + `PDF_REDACT_LINE_ART_NONE` (preserve images/vectors, D-03-05), (3) all `insert_htmlbox`. Re-derives identical filtered block walk so `structural_position` resolves to the same rects. Skips redact+reinsert for identity translations, math-passthrough, undersized rects, and translation-too-dense cells (preserves source visible). Adaptive `scale_low` per block/cell via `_estimate_max_fitting_scale`; image-collision clipping via `_clip_rect_away_from_images`. |
| `fonts.py` | Noto font discovery (D-03-04). `build_noto_archive_and_css()` builds a PyMuPDF `Archive` over `/usr/share/fonts/{truetype,opentype}/noto` and an `@font-face` CSS registering `noto` (Latin/VN regular/bold/italic) + `noto-cjk` (JA/ZH/KO). Per-block body font size supplied via `<div style="font-size:Npt">` wrapper; headings sized in `em`. Original DRM-embedded PDF fonts cannot be reused. |
| `columns.py` | Column clustering (PDF-04, D-03-03). x-midpoint histogram (20 bins) + gap detection (gap ≥ 30% page width). Returns `(column_groups, is_degraded)`: 0 gaps → 1 column; 1 gap → 2 columns (each top-to-bottom); 2+ gaps or 3+ peaks → degraded flat reading order. Pure stdlib, no ML. |

Notes: `scale_low` must be set explicitly (default 0 never reports overflow) — text blocks 0.7, table cells adaptive floor 0.3, min readable 0.15. `insert_htmlbox` returning `spare_height < 0` raises an overflow flag; `scale < 1.0` raises auto-adjusted. Per-block `insert_htmlbox` failures are isolated and logged (T-03-03). Output finalized with `subset_fonts()` + `save(garbage=3, deflate=True)`.

### pptx/
| File | Responsibility |
|------|----------------|
| `extractor.py` | Recursive shape-tree walk (`walk_shape_tree`, PPTX-04) with strict check order: GROUP → recurse, `is_smartart()` → flag (BEFORE `has_text_frame`, since SmartArt reports `has_text_frame=False`), TABLE → cell walk, `has_text_frame` → paragraph walk. Also extracts speaker notes and master-slide text (deduplicated by segment ID, extracted once before the slide loop). NFC-normalizes (CORE-04). |
| `reassembler.py` | Run-merge write-back identical to DOCX (`runs[0].text = translated`, blank `runs[1:]`; never `paragraph.text = value`). `detect_pptx_overflow` uses char-count ratio as a shrink-factor proxy (no headless render): `shrink ≥ 0.7` → apply `TEXT_TO_FIT_SHAPE` auto-fit (auto_adjusted); `< 0.7` → flag overflow, skip. Auto-height shapes (height==0) skip auto-fit. SmartArt positions skipped (D-03-01). |
| `smartart.py` | SmartArt detection + best-effort text. `is_smartart` checks `MSO_SHAPE_TYPE.IGX_GRAPHIC` then falls back to graphicData URI namespace match. `extract_smartart_text` joins `.//a:t` element text. All lxml access defensive (returns False/empty, never crashes). |

Notes: SmartArt text is extracted and shown in the review UI but write-back into XML is SKIPPED (D-03-01) — flagged, not silently dropped.

### scanned_pdf/ (OCR path)
| File | Responsibility |
|------|----------------|
| `detector.py` | Text-density routing (D-04-17). `detect_scanned_pdf` returns True when extractable `total_chars / page_count < threshold` (default 50). Empty docs → False; form/hidden-OCR-layer PDFs classify as native. |
| `extractor.py` | OCR via PP-StructureV3 (D-04-01). Renders each page to PNG (300 DPI, pixmap freed immediately, T-04-04). Mixed-PDF check (D-04-18): pages with native text use a plain `text` segment. Runs `pipeline.predict()` in `asyncio.to_thread` (non-blocking arq loop). Blocks sorted by `block_order`; emits `ocr_text` segments with normalized bbox + page-mean confidence. Passthrough labels (image/chart/figure/formula/seal/page_number) → `figure_passthrough` with `[Figure on left]` placeholder + bbox. Returns `(segments, low_confidence_pages)`; confidence gate at 0.7 (D-04-02). |
| `segment_to_md.py` | DOCX-export helper (D-04-33). `segments_to_markdown` walks segments by `seq_in_job`, maps `region_label` → Markdown (`doc_title`→H1; `paragraph_title`/`header`→H2; `table`→passthrough; seal/page_number skipped), text priority `edited_source_text` → `translated_text` → `source_text`. `md_to_docx` renders Markdown to DOCX via python-docx. |
| `composer.py` | Bilingual PDF rebuild via fpdf2 (OCR-03, D-04-07/08/09). `compose_bilingual_pdf` emits double-wide pages: left = original page PNG, right = translated text positioned at proportionally-mapped region bbox, sorted top-to-bottom. `compose_translated_only_pdf` emits single-column translated-only pages. Fit-to-region font search in [8,24]pt (`_estimate_fits`); `figure_passthrough` regions cropped from source PNG and re-inserted right (self-contained). NotoSans/NotoCJK registered with Helvetica fallback. Overflow at min font → overflow flag. |

Notes: Per-page OCR errors are isolated — a failed page emits `[OCR failed for this page]` placeholder, adds to `low_confidence_pages`, and the job continues (D-04-31). bbox values clamped to `[0,1]` (T-04-05).

## Extract → reassemble contract
- **Extraction** produces an ordered `list[Segment]`; `structural_position` encodes the exact location in the native model (paragraph/run, page/column/block, slide/shape/frame/para, page/region). `seq_in_job` is the walk-order index. Source text is always NFC-normalized at extraction.
- **Translation** is keyed by `Segment.id`; the worker builds `translated_map: {id → text}`.
- **Reassembly** mutates a copy of the original document. DOCX/PPTX re-walk in identical order and pair by walk-order counter or `structural_position` map; PDF/scanned-PDF resolve `structural_position` to a re-derived block/cell/region rect. Segments absent from `translated_map` are left as source.
- **Flags raised** (persisted by the worker as `SegmentFlag`):
  - `overflow` — PDF `insert_htmlbox spare_height < 0`, rect-too-small, translation-too-dense, image-collision; PPTX shrink < 0.7; scanned-PDF min-font overflow.
  - `auto_adjusted` — PDF `scale < 1.0`; PPTX auto-fit applied (shrink ≥ 0.7).
  - SmartArt — extracted + shown in review UI, write-back skipped (D-03-01).
  - `math_passthrough` / `figure_passthrough` — source glyphs/figure region preserved, translation skipped.
  - `multi_column_degraded` — `cluster_columns` returns `is_degraded=True` (3+ columns → flat reading order).
  - `ocr_page_error` — per-page OCR failure placeholder + low-confidence-page list.

## Dependencies
- **python-docx** — DOCX read/write, run/tracked-change manipulation; also used by `segment_to_md.md_to_docx`.
- **PyMuPDF (pymupdf)** — PDF extraction, redact-reinsert, `insert_htmlbox`, `Archive`/font CSS, page-to-PNG rendering for the OCR path.
- **python-pptx** — PPTX shape-tree traversal and write-back; `MSO_SHAPE_TYPE`, `MSO_AUTO_SIZE`, SmartArt enum/XML.
- **PaddleOCR (PP-StructureV3)** — scanned-PDF layout + OCR (injected `pipeline` object).
- **fpdf2** — bilingual / translated-only PDF composition; **Pillow** for figure cropping; **numpy** for bbox shape handling.
- **structlog** — structured logging across PDF/scanned-PDF paths.
- **Internal**: `app.pipeline.segment` (Segment), `app.pipeline.placeholder` (token protection). The LLM translator (qwen-mt-turbo via openai SDK) lives outside this module; the pipeline only produces/consumes `Segment` text and `translated_map`.
