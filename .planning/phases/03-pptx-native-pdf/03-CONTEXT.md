# Phase 03: PPTX + Native PDF — Context

**Gathered:** 2026-04-25
**Status:** Ready for planning
**Source:** /gsd-discuss-phase 3

<domain>
## Phase Boundary

Extend the Phase 1 pipeline spine to two more hero formats:

1. **PPTX** — translate text boxes, speaker notes, tables, bulleted lists, master-slide text. Walk grouped shapes recursively. Detect SmartArt (don't silently skip). Detect text-box overflow + apply conservative auto-fit.
2. **Native PDF** — parse text-layer PDFs with PyMuPDF. Extract spans with bbox/font/size. Translate. Reinsert via redact-annot workflow with bundled Noto fonts. Handle 2-column layouts via x-coordinate clustering. Use HTML round-trip (`page.get_text("html")` → translate → `insert_htmlbox()`) to preserve span styling.

**Out of scope:**
- Scanned PDFs (Phase 4 OCR)
- 3+ column PDF layouts (flag and degrade to flat reading order)
- Original-font fidelity (use bundled Noto — original PDF fonts are DRM/subset, can't re-use)
- Image-embedded text translation (info-flag only; VLM extraction deferred to v2)
- Right-to-left languages (`insert_htmlbox` ready but not exercised in PoC)

</domain>

<decisions>
## Implementation Decisions

### PPTX — SmartArt UX (D-03-01)
**SmartArt shapes get a Segment row + new `smartart` flag (orange badge in review UI).** Best-effort text extraction via python-pptx; translation runs but reassembly skips SmartArt write-back. User sees what couldn't be auto-translated and can copy/paste manually into the source file. Rationale: PPTX-02 mandates flag-not-skip; review UX should make the limitation actionable, not hidden.

### PPTX — overflow auto-fit policy (D-03-02)
**Conservative auto-fit: apply `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` only when measured shrink factor stays ≥ 0.7 of source font size.** If shrink would drop below 0.7, flag overflow + skip auto-fit. Prevents tiny-font surprises on long Vietnamese/Japanese expansions. Maps to LAYOUT-03.

### PDF — column-clustering threshold (D-03-03)
**Threshold-based 2-col detection: cluster spans by x-coordinate; if 2 dense clusters separated by gap ≥ 30% of page width, treat as 2-column reading order. 3+ clusters or ambiguous → fall back to flat reading order + flag page `multi-column-degraded`.** Proven PyMuPDF pattern. Maps to PDF-04.

### PDF — font handling (D-03-04)
**Bundled Noto for all output: Noto Sans (latin/VN), Noto Sans CJK (ja/zh/ko).** Original PDF fonts are typically DRM-embedded/subsetted and can't legally be re-used. Tradeoff: visual style differs from source. Industry standard for redact-annot translation. Match-style and try-original variants explicitly rejected (over-engineering for PoC).

### PDF — non-text content preservation (D-03-05)
**Images, charts, vector graphics pass through untouched.** PyMuPDF's `apply_redactions()` preserves non-text content by default. Image-embedded text is NOT translated in this phase (Phase 4 OCR covers scanned PDFs; native-PDF image-text is acceptable to leave). No `pdf_image_with_text` flag — keep flag set minimal (overflow, glossary_violation, placeholder_mismatch, llm_refusal, smartart, multi-column-degraded already enough).

### PDF — column layout preservation strategy (D-03-06)
**HTML round-trip via PyMuPDF `insert_htmlbox`.** Pipeline: `page.get_text("html")` per text block → translate the HTML inline (preserve bold/italic/color span tags) → `page.insert_htmlbox(rect, translated_html, css)`. Preserves span styling, handles text expansion via natural reflow, RTL-ready (not exercised in PoC). Heavier than direct redact-annot per-span but PyMuPDF native; no external HTML renderer.

**NOT chosen:**
- Per-span bbox-pin: rejected — fails on VN/JA expansion
- Per-page reflow: rejected — column boundaries drift, page breaks misalign
- Adaptive (pin short, reflow long): rejected — adds branch complexity, user prefers single approach
- pdf2docx round-trip: rejected as primary path — 3-conversion chain, fidelity loss; remains as documented fallback only

### Review UI — segment-position display (D-03-07)
**Breadcrumb badge in segment row source cell.** PPTX: `Slide 3 / Shape 1 / ¶2`. PDF: `Page 2 / Col 1 / Block 5`. No new table column — reuse existing CAT-tool layout. `structural_position` string parsed at render time into the badge. Keeps table width stable on review screens that already feel dense.

### Carry-forward (locked, no re-decide)
- **D-05/D-06:** Segment tree + deterministic `sha256(source_text + structural_position)[:16]` ID. PPTX `structural_position` example: `slide.3.shape.0.tf.0.para.1`. PDF: `page.2.col.1.block.5.span.2`.
- **Compound PK** (Phase 2 D-02-10): segments table PK is `(job_id, id)`. PPTX/PDF parsers MUST use the same job-scoped insert path.
- **Glossary `terminology` injection per batch** unchanged.
- **Batch packing** (D-07): same token-budget logic, same `pack_into_batches()`.
- **Worker session pattern** (Phase 2 D-02-10): `run_post_check(..., job_id=...)`, all SegmentFlag inserts pass `segment_job_id`.
- **Review UI = CAT-tool table** (D-02-14): extend, don't redesign.
- **Paper-skill fonts** (D-02-27): Roboto / Montserrat / JetBrains Mono with `vietnamese` subset.

### Pipeline structure
- New: `backend/src/app/pipeline/pptx/` (extractor.py, reassembler.py, smartart.py)
- New: `backend/src/app/pipeline/pdf/` (extractor.py, reassembler.py, columns.py, fonts.py)
- Worker `translate_job()` dispatches by `job.input_format`. Existing `docx/` path untouched.

### New flag types
Extend `FlagType` enum:
- `smartart` (PPTX): SmartArt shape detected, manual edit only
- `multi_column_degraded` (PDF): 3+ columns or ambiguous clustering, flat reading order applied

### Frontend changes
- `FlagBadge.tsx`: add color/label for `smartart` (orange, "SMART") and `multi_column_degraded` (slate, "MULTI-COL").
- `SegmentRow.tsx`: render breadcrumb badge from `structural_position`. Helper: `formatBreadcrumb(pos: string, format: "docx" | "pptx" | "pdf"): string`.
- `UploadForm.tsx`: accept `.pptx` and `.pdf` extensions; backend already detects format.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project foundation
- `.planning/PROJECT.md` — Core value, validated requirements (PPTX/PDF still active), out-of-scope
- `.planning/REQUIREMENTS.md` — PPTX-01..04, PDF-01..04, LAYOUT-02, LAYOUT-03 acceptance criteria
- `.planning/ROADMAP.md` §"Phase 3: PPTX + Native PDF" — Goal + 4 success criteria
- `./CLAUDE.md` — paper-skill fonts, GSD enforcement, immutability, tech-stack notes (PyMuPDF + python-pptx versions, JetBrains Mono swap, etc.)

### Phase 1 carry-forward (Segment tree, batch packing, transport, glossary plumbing)
- `.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md` — D-01..D-20
- `.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md` — qwen-mt-turbo behavior, batch-packing patterns
- `.planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md` — Phase 1 codebase conventions
- `backend/src/app/pipeline/segment.py` — Segment dataclass + `make_segment_id`
- `backend/src/app/pipeline/docx/extractor.py` — analog parser pattern (PPTX/PDF mirror this)
- `backend/src/app/pipeline/docx/reassembler.py` — analog reassembly pattern
- `backend/src/app/workers/translate_worker.py` — current dispatch + persistence path

### Phase 2 carry-forward (compound PK, run_post_check job_id, review UI, fonts)
- `.planning/phases/02-review-ux-glossary/02-CONTEXT.md` — D-02-01..27 (especially D-02-13 deferral, D-02-14 CAT-tool, D-02-27 fonts)
- `.planning/phases/02-review-ux-glossary/02-VERIFICATION.md` — final state of Phase 2
- `backend/src/app/db/models.py` — Segment + SegmentFlag (compound PK + FK)
- `backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py` — schema reference
- `backend/src/app/services/glossary_service.py` — `run_post_check(..., job_id)` call signature
- `frontend/src/components/SegmentRow.tsx` — review-row pattern + JetBrains Mono cell
- `frontend/src/components/FlagBadge.tsx` — flag-type → badge mapping (extend with new types)

### External docs (technology references)
- PyMuPDF: https://pymupdf.readthedocs.io/en/latest/ — `Page.get_text("html")`, `insert_htmlbox`, `add_redact_annot`, `apply_redactions`, multi-column extraction patterns
- python-pptx 1.0.2: https://python-pptx.readthedocs.io/ — `Shape.shape_type`, `Shape.has_text_frame`, `Shape.has_smart_art`, group recursion, `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE`, `notes_slide.notes_text_frame`, `slide.shapes` walk
- Noto fonts (already bundled per Dockerfile): `fonts-noto`, `fonts-noto-cjk` apt packages

</canonical_refs>

<specifics>
## Specific Ideas

- **Block-level extraction for PDF.** Use `page.get_text("dict")["blocks"]` to group spans into paragraph blocks before HTML round-trip. Each block becomes one Segment (or a small group when text expansion forces split). Avoids over-segmentation at line level.
- **PPTX speaker notes are first-class Segments**, not buried metadata. `slide.notes_slide.notes_text_frame` extracted same as body text. Position string: `slide.N.notes.para.K`.
- **Master slide text** translated once per master, not per occurrence. Detect via `slide.slide_layout.slide_master.shapes`.
- **SmartArt detection check**: `shape.shape_type == MSO_SHAPE_TYPE.PLACEHOLDER and shape.has_text_frame == False` is the lossy heuristic; use `shape.element.findall(".//{*}graphicFrame")` for definitive XML detection.
- **Demo coverage:** PPTX/PDF must work for VN ↔ EN at minimum, JA/ZH for showcase. JetBrains Mono / Noto Sans CJK already bundled.
- **Reusable from Phase 2:** the `expansion_ratio` field on Segment, the `overflow` flag, the review table virtualization, the export endpoint pattern (per-format reassembler dispatched by job.input_format).

</specifics>

<deferred>
## Deferred Ideas

### To Phase 4 (OCR)
- Scanned PDF handling (separate phase by ROADMAP)
- VLM-based image-embedded-text extraction (qwen3.6-plus path, evaluate when Phase 4 starts)

### To v2
- 3+ column PDF layouts with intelligent clustering
- Original-font fidelity (font matching beyond Noto)
- RTL language support exercised end-to-end (Arabic/Hebrew demo file)
- pdf2docx round-trip as production fallback (still useful as last-resort, not primary path)
- Layout reflow for heavily-expanded translations (block-level handles 95% of cases; complex multi-column reflow deferred)
- Adaptive pin/reflow strategy (rejected here for simplicity, may revisit if HTML round-trip proves insufficient)

### Backlog (already logged)
- 999.1 — Phase 2 textarea active-edit visual state polish

</deferred>

---

*Phase: 03-pptx-native-pdf*
*Context gathered: 2026-04-25 via /gsd-discuss-phase*
