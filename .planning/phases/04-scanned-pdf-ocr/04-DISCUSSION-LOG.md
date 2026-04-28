# Phase 4: Scanned PDF (OCR) — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `04-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 04-scanned-pdf-ocr
**Areas discussed:** OCR engine, Output layout + rendering, Review UI extension, Pipeline + ops, plus tail rounds on fallback policy, schema, region clustering, fonts, DPI, lang model, SSE, fixtures, output variants, needs_review state, figures, regenerate, cost cap, retry budgets, bbox coords, page errors, migration, font sizing, tests; final pivot round on PP-DocTranslation hybrid + glossary + outputs + scope.

---

## Gray Area Selection

**Q:** Which gray areas to discuss for Phase 4 (Scanned PDF / OCR)?

| Option | Description | Selected |
|--------|-------------|----------|
| OCR engine | PaddleOCR vs qwen3.6-plus VLM vs Azure DI | ✓ |
| Output layout + rendering | Side-by-side topology + flowing vs region-positioned text | ✓ |
| OCR review UI extension | Page-image crop, confidence, editable source | ✓ |
| Pipeline + ops | 3-stage retry, cold-start, scanned auto-detection | ✓ |

**User's choice:** All four selected.

---

## OCR engine

### Q1: Primary OCR engine?

| Option | Description | Selected |
|--------|-------------|----------|
| PaddleOCR PP-OCRv5 | Locked default per REQ OCR-01; self-host, free; cold-start risk | |
| qwen3.6-plus VLM (single-model OCR+translate) | API call image→translated; loses bbox+confidence; demo risk | |
| PaddleOCR primary + qwen-VL fallback | Hybrid quality booster on low-conf pages | ✓ |
| Azure Document Intelligence | Best layout JSON; cloud-only; adds 2nd cloud dep | |

**User's choice:** PaddleOCR primary + qwen-VL fallback (later revised post-pivot — see final round).

### Q2: Confidence gating UI?

| Option | Description | Selected |
|--------|-------------|----------|
| Page-level needs_review banner only | Job needs_review when ANY page mean <0.7 | ✓ |
| Page banner + per-segment low_ocr_confidence flag | Adds new FlagType | |
| Per-segment only, no page banner | Doesn't satisfy OCR-02 wording | |

**User's choice:** Page-level needs_review banner only.

### Q3: Editable OCR'd source text?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — add edited_source_text field | Mirrors REV-04 edited_text pattern | ✓ |
| No — source read-only like Phases 1–3 | Limits demo-day rescue | |
| Edit only flagged low-confidence segments | Conditional UI complexity | |

**User's choice:** Yes — add edited_source_text field.

### Q4: OCR-04 "independently retriable" implementation?

| Option | Description | Selected |
|--------|-------------|----------|
| Single arq job, internal stage state | One job, stage field updates as work progresses | |
| Chained arq jobs (one per stage) | Maximum isolation; rewrites SSE merge | |
| Single job, monolithic retry | Violates OCR-04 spirit; reject | |

**User's choice:** Need to discuss more — see follow-up below.

---

## Stage retry deep-dive

### Q1: Retry semantics?

| Option | Description | Selected |
|--------|-------------|----------|
| Internal retry only | Each stage transient errors retry; single progress UI | ✓ |
| User-resume from failed stage button | DB checkpoints + UI button to resume | |
| Both | Maximum resilience; maximum complexity | |

**User's choice:** Internal retry only.

### Q2: Job/queue topology?

| Option | Description | Selected |
|--------|-------------|----------|
| Single arq job + in-memory stage progression | Stage field on Job row; SSE D-10 extended | ✓ |
| Single arq job + DB-checkpointed resume | Adds job_stages table | |
| Chained arq jobs (3 separate) | Full isolation; SSE rewrite | |

**User's choice:** Single arq job, in-memory stage progression.

### Q3: OCR concurrency within stage?

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential page-by-page | Simplest; PaddleOCR holds models across calls | |
| asyncio.gather batches of 4 | Mirrors D-17; needs threadpool wrapper | |
| Configurable via env, default sequential | Tuneable on demo machine | ✓ |

**User's choice:** Configurable via env, default sequential.

---

## Output layout + rendering

### Q1: Bilingual page topology?

| Option | Description | Selected |
|--------|-------------|----------|
| Double-wide page (img left, text right) | One output page per source; easy reading flow | ✓ |
| Facing pages (book spread) | Source page count doubles; print-friendly | |
| Interleaved (alternating) | Worst UX; reader can't see both | |
| Configurable via env / job param | Hedges preference | |

**User's choice:** Double-wide page.

### Q2: Right-side text rendering?

| Option | Description | Selected |
|--------|-------------|----------|
| Region-positioned (one box per OCR region) | Preserves visual structure | ✓ |
| Flowing text (single column) | Simplest; loses layout | |
| Region-positioned + fallback to flowing | Hedge for extreme expansion | |

**User's choice:** Region-positioned.

### Q3: Compose engine?

| Option | Description | Selected |
|--------|-------------|----------|
| fpdf2 (per REQ OCR-03) | Purpose-built for new PDFs; native Noto support | ✓ |
| PyMuPDF (already in stack) | No new dep; less ergonomic for scratch PDFs | |
| Both (PyMuPDF for image, fpdf2 for text) | Cleanest separation | |

**User's choice:** fpdf2 (per REQ).

### Q4: Page image handling?

| Option | Description | Selected |
|--------|-------------|----------|
| Store page-N.png in .data/jobs/{id}/pages/ | Extract once, reuse 3x (OCR + compose + review) | ✓ |
| Re-extract on demand each stage | No disk cost; 3x rendering cost | |
| Store on disk + embed crops in Segment rows | DB bloat; reject | |

**User's choice:** Store page-N.png in .data/jobs/{id}/pages/.

---

## Review UI extension

### Q1: Image crop placement?

| Option | Description | Selected |
|--------|-------------|----------|
| Expandable preview row (click-to-expand) | Default collapsed; auto-expand low-conf | ✓ |
| Always-visible image column | Density loss; reject | |
| Side drawer on segment focus | New UI surface | |
| Tooltip on hover | Poor discoverability + keyboard nav | |

**User's choice:** Expandable preview row.

### Q2: UX for editing OCR'd source?

| Option | Description | Selected |
|--------|-------------|----------|
| Double-click source cell to edit | Default read-only; mirrors target edit | ✓ |
| Always-editable source cell | Risk of accidental edits | |
| Edit-mode toggle on the page | Page-level on/off | |

**User's choice:** Double-click source cell to edit.

### Q3: OCR confidence display?

| Option | Description | Selected |
|--------|-------------|----------|
| Numeric % chip in row gutter, color-coded | Mirrors expansion-ratio chip | ✓ |
| Color-coded row background tint | Conflicts with paper aesthetic | |
| In flag column only when below threshold | Contradicts D-04-02 page-level only | |
| Hidden, expose via filter chip | Minimal UI; harder to scan | |

**User's choice:** Numeric % chip.

### Q4: Page-level needs_review banner placement?

| Option | Description | Selected |
|--------|-------------|----------|
| Top of review page, list affected pages | Banner with click-to-jump | ✓ |
| Inline divider rows in segment table | Strong signal; complex virtualization | |
| Both | Maximum visibility; redundant | |

**User's choice:** Top of review page banner.

---

## Pipeline + ops

### Q1: Cold-start mitigation?

| Option | Description | Selected |
|--------|-------------|----------|
| Bake models into Docker image | Pin SHA; image grows ~1GB | (revised) |
| Pre-pull on container startup | Image stays small; first-up blocks | |
| Lazy load on first job | Demo-day visible delay; reject | |

**Initial answer:** "I need options that suitable for production later."

### Q1-revised: Production-suitable cold-start?

| Option | Description | Selected |
|--------|-------------|----------|
| Bake models in Docker image, pin SHA | PoC + production reproducibility | ✓ |
| Init container + shared model volume (PV/EFS) | K8s-shaped; storage layer needed | |
| Models in object storage (S3/GCS) | Decouples model versioning from image | |
| External OCR microservice | Independent scaling | |

**User's choice:** Bake models in Docker image, pin SHA.

### Q2: CPU vs GPU?

| Option | Description | Selected |
|--------|-------------|----------|
| CPU-only paddlepaddle | Demo machine = WSL2 Linux; no GPU | |
| GPU if available, CPU fallback | Adds CUDA layer (~3GB) | |
| CPU only, measure perf during smoke | Defer GPU to v2 | ✓ |

**User's choice:** CPU only, measure perf during smoke.

### Q3: Scanned PDF detection?

| Option | Description | Selected |
|--------|-------------|----------|
| Text-layer density heuristic | Cheap; auto-routes | |
| User toggle on upload form | Removes ambiguity; adds friction | |
| Auto-detect + override toggle | Best of both | ✓ |
| Always require explicit format pick | Slower UX | |

**User's choice:** Auto-detect + override toggle.

### Q4: Mixed PDFs?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-page detection inside OCR stage | Most robust for real-world docs | ✓ |
| All-or-nothing | Wastes compute; degrades native pages | |
| Defer to v2 | Easy scope cut; demo-day risk | |

**User's choice:** Per-page detection inside OCR stage.

---

## Tail decisions round 1

### Q1: qwen-VL fallback policy + glossary?

| Option | Description | Selected |
|--------|-------------|----------|
| Page mean <0.5 → qwen-VL OCR only, then qwen-mt-turbo translates | Native terminology preserved | ✓ |
| Page mean <0.5 → qwen-VL OCR+translate single call | Glossary becomes prompt-text; weaker | |
| Always run qwen-VL on every page | Rejected — contradicts OCR-01 | |
| Defer fallback to v2 | Walk back D-04-01 | |

**User's choice:** qwen-VL OCR only → qwen-mt-turbo translates (later obsolete after pivot).

### Q2: Segment.kind extension?

| Option | Description | Selected |
|--------|-------------|----------|
| Add `ocr_text` | Extends Phase 3.2 enum pattern | ✓ |
| Reuse `text` + add `is_ocr` boolean | Parallel boolean flag | |
| Add `ocr_text` AND `ocr_region` | Multi-line vs region-grouped | |

**User's choice:** Add `ocr_text`.

### Q3: Region clustering?

| Option | Description | Selected |
|--------|-------------|----------|
| Use PaddleOCR PP-StructureV3 layout analysis | Native paragraph/title/table/figure | ✓ |
| DIY clustering by vertical proximity | Lighter compute; loses semantic info | |
| One Segment per OCR'd line | Maximum granularity; loses context | |

**User's choice:** PP-StructureV3 layout analysis.

### Q4: fpdf2 font registration?

| Option | Description | Selected |
|--------|-------------|----------|
| Bundle Noto TTFs in backend/fonts/, register explicitly | Deterministic; no fontconfig dep | ✓ |
| Reuse system Noto via fontconfig | Brittle; reject | |
| Vendor as Python package | None covers CJK fully; reject | |

**User's choice:** Bundle Noto TTFs.

---

## Tail decisions round 2

### Q1: Page DPI?

| Option | Description | Selected |
|--------|-------------|----------|
| 300 DPI | Industry standard | |
| 200 DPI | Smaller files; risk on small text | |
| Configurable via env, default 300 | Tuneable | ✓ |

**User's choice:** Configurable via env, default 300.

### Q2: PaddleOCR `lang` parameter?

| Option | Description | Selected |
|--------|-------------|----------|
| Pass user-selected source_lang → PaddleOCR lang map | Best accuracy for known docs | |
| Always use `ch` (multi-script) | Simplest | |
| Auto-detect via OCR + script ID | 2x cost | |

**Initial answer:** "Any more options to cost effectively?"

### Q2-revised: Cost-effective lang strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| PP-OCRv5 multilingual single model (106 langs) | Cheapest end-to-end | ✓ |
| Default `ch`, lazy-load others | Memory grows up to 3–4GB | |
| Single `ch` model, no other langs | VN works via Latin coverage | |
| Per-lang model dispatch | ~4GB image growth; reject | |

**User's choice:** PP-OCRv5 multilingual single model.

### Q3: SSE payload extension?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `stage` enum + add OCR-specific fields | UI renders stage-specific copy | |
| Reuse fields, switch meaning per stage | Confusing | |
| Add `stage_progress: { stage, current, total }` | Cleaner per-stage progress | ✓ |

**User's choice:** Add stage_progress substructure.

### Q4: Demo fixtures?

| Option | Description | Selected |
|--------|-------------|----------|
| VN + JA + EN + bad-quality scan | Maps LANG-02 + OCR-02 + D-04-19 | ✓ |
| Reuse BMC academic paper + 1 VN scan | Wrong format (text-layer); reject | |
| Just 1 VN scan | Fails LANG-02 | |

**User's choice:** VN + JA + EN + bad-quality scan.

---

## Tail decisions round 3

### Q1: Output filename + variants?

| Option | Description | Selected |
|--------|-------------|----------|
| Single bilingual output.pdf | REQ OCR-03 baseline | |
| Two outputs: bilingual + translated-only | Hedge | ✓ (later revised to three after pivot) |
| Single output, format chosen at upload | Adds upload toggle | |

**User's choice:** Two outputs (revised post-pivot to three).

### Q2: needs_review state transition?

| Option | Description | Selected |
|--------|-------------|----------|
| Either OCR <0.7 OR translate-stage flags | Cross-stage flag aggregation | ✓ |
| Only after translate stage | Simpler; misses low-conf pages | |
| Never auto-transition | Worst UX | |

**User's choice:** Either OCR <0.7 OR translate-stage flags.

### Q3: PP-Structure figures?

| Option | Description | Selected |
|--------|-------------|----------|
| Pass through + info-only flag | Mirrors Phase 3 D-03-05 | ✓ |
| OCR text inside figures (chart labels) | Hard positioning; v2 | |
| Skip silently | Reviewer doesn't know | |

**User's choice:** Pass through + info-only flag.

### Q4: Per-segment regenerate semantics?

| Option | Description | Selected |
|--------|-------------|----------|
| Re-translate only via qwen-mt-turbo | Cheapest; uses edited_source_text | ✓ |
| Re-OCR region + re-translate | 3x expensive | |
| Both buttons | UI density cost | |

**User's choice:** Re-translate only.

---

## Tail decisions round 4

### Q1: qwen-VL fallback cost cap?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-job cap: max 5 fallback pages | Bounds cost; configurable | ✓ (later obsolete after pivot) |
| Per-job USD cost cap | Adds accounting | |
| No cap | Cost predictability lost | |
| Cap = 50% of pages | Adapts to doc length | |

**User's choice:** Max 5 fallback pages (obsolete after pivot dropped fallback).

### Q2: Per-stage retry budget?

| Option | Description | Selected |
|--------|-------------|----------|
| OCR=2, translate=3, compose=2 | Calibrated per stage | ✓ |
| Uniform 3 per stage | Wasteful for OCR | |
| OCR=1, translate=3, compose=2 | Fail-fast OCR | |

**User's choice:** OCR=2, translate=3, compose=2.

### Q3: Region_bbox coordinate system?

| Option | Description | Selected |
|--------|-------------|----------|
| Page-relative normalized [0,1] floats | DPI-independent | ✓ |
| Pixel coords on PNG | Coupled to DPI | |
| PDF point coords | Native; couples to PDF unit | |

**User's choice:** Page-relative normalized [0,1] floats.

### Q4: Per-page PaddleOCR error handling?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip page + emit flag, continue job | New FlagType.ocr_page_error | ✓ |
| Fail whole job loudly | Brittle for demo | |
| Retry failed page with qwen-VL | Counts against fallback cap (obsolete after pivot) | |

**User's choice:** Skip page + emit flag, continue job.

---

## Tail decisions round 5

### Q1: DB migration strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic 0005 — full migration | New columns + enum values + input_format | ✓ |
| Defer all OCR fields to in-memory | edited_source_text MUST persist | |
| Hybrid: persist edited + kind, defer rest | Mid-cost | |

**User's choice:** Alembic 0005 full migration.

### Q2: PP-StructureV3 reading order?

| Option | Description | Selected |
|--------|-------------|----------|
| Trust PP-StructureV3 reading_order | Native XY-Cut algorithm | |
| Reuse Phase 3 D-03-03 column-clustering | Defensive | |
| Hybrid: PP-Structure + fallback | Adds branch | |

**Initial answer:** "I saw PaddleOCR v3.5.0 has released. Check it first."

→ Triggered the PaddleOCR 3.5.0 research round (PaddleOCR-VL, PP-DocTranslation findings) which led to the architecture pivot in the final round below.

**User's eventual choice (after pivot):** Trust PP-StructureV3 native parsing_res_list.

### Q3: Right-side font sizing?

| Option | Description | Selected |
|--------|-------------|----------|
| Fit-to-region with min/max bounds [8pt, 24pt] | Phase 3 LAYOUT-03 ethos | ✓ |
| Fixed 11pt body, 14pt heading | Predictable; risk overflow | |
| Match source font proportionally | Unreliable on scans | |

**User's choice:** Fit-to-region with min/max bounds.

### Q4: Test scaffolding strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| Mocked PaddleOCR + qwen-VL + real fpdf2 | Phase 1 mocking pattern | ✓ |
| Real PaddleOCR everywhere | Slow CI | |
| Mocked PaddleOCR; real qwen-VL via integration | Realistic for fallback (obsolete after pivot) | |

**User's choice:** Mocked PaddleOCR + qwen-VL + real fpdf2.

---

## Final pivot round (post PaddleOCR 3.5.0 research)

### Research findings shared

PaddleOCR 3.5.0 brings:
- **PaddleOCR-VL** (0.9B VLM, 109 langs, SOTA on doc parsing)
- **PP-StructureV3** (native multi-column reading order, table/formula recognition)
- **PP-DocTranslation** (end-to-end pipeline with `glossary` param + `chat_bot_config`)

User selected "Pivot to PP-DocTranslation pipeline" but asked for clarifications on architecture / glossary / output / scope.

### Q1: PP-DocTranslation pivot — what survives from Phase 1–3?

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid: Paddle for OCR/structure, OUR translate + compose | Preserves Segment tree + native terminology + CAT-tool review | ✓ |
| Full PP-DocTranslation, accept block-level review | Cleaner if review divergence accepted | |
| Full PP-DocTranslation + post-process MD into Segments | Frankenstein | |

**User's choice:** Hybrid path.

### Q2: Glossary mechanism for OCR jobs?

| Option | Description | Selected |
|--------|-------------|----------|
| Native terminology API (skip PP-DocTranslation translate) | D-02-05 preserved | ✓ |
| Prompt-text injection (PP-DocTranslation native) | Weaker than DOCX/PPTX/PDF | |
| Both — prompt-text + post-check enforcement | Mid-cost | |

**User's choice:** Native terminology API.

### Q3: Output formats for OCR jobs?

| Option | Description | Selected |
|--------|-------------|----------|
| Bilingual PDF + translated DOCX | DOCX free from Paddle export | |
| Bilingual PDF only (REQ baseline) | Simplest scope | |
| Translated DOCX + translated-only PDF (drop bilingual) | Breaks OCR-03 | |
| All three: bilingual PDF + translated PDF + translated DOCX | Maximum coverage | ✓ |

**User's choice:** All three outputs.

### Q4: Phase 4 scope/timeline?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Phase 4 tight, hybrid path makes timeline | No timeline expansion | ✓ |
| Extend Phase 4 to 1.5–2 weeks for full pivot | If full pivot picked | |
| Phase 4.1 adds DOCX post-demo | De-risks demo | |
| Phase 4 ships hybrid + DOCX, skip Paddle-VL evaluation | Lowest risk + max coverage | |

**User's choice:** Keep Phase 4 tight.

---

## Cascade clarifications (post-pivot)

### Q1: qwen-VL fallback policy after pivot?

| Option | Description | Selected |
|--------|-------------|----------|
| Drop qwen-VL fallback entirely | Reviewer-edit is the rescue | ✓ |
| Keep qwen-VL fallback per D-04-19 | External API dep + cost-cap | |
| Replace qwen-VL with PaddleOCR-VL fallback | ~1.5GB image cost | |

**User's choice:** Drop qwen-VL fallback entirely.

### Q2: DOCX compose path?

| Option | Description | Selected |
|--------|-------------|----------|
| Re-emit Markdown from Segments → Paddle MD→DOCX | Cleanest leverage of 3.5.0 | ✓ |
| Build DOCX directly with python-docx | Reuses Phase 1 pattern | |
| Both with fallback | More code paths | |

**User's choice:** Re-emit Markdown → Paddle MD→DOCX.

---

## Claude's Discretion

Areas where user said "you decide" or deferred to Claude (per `04-CONTEXT.md` D-section):

- Exact `OCR_PAGE_CONCURRENCY`, `OCR_PAGE_DPI`, `OCR_TEXT_DENSITY_THRESHOLD` env defaults
- Region-bbox → fpdf2 coordinate transform algorithm
- Segment→MD helper edge cases
- fpdf2 page-size parameter (A4 doubled-width vs dynamic)
- Confidence chip color thresholds (paper skill secondary palette)
- Image-crop expansion animation
- PP-StructureV3 init params (`use_doc_orientation_classify`, `use_doc_unwarping`, etc.)
- PaddleOCR Python API asyncio wrapping strategy
- Docker layer ordering for model bake

## Deferred Ideas

See `04-CONTEXT.md` `<deferred>` section. Notable deferrals to v2:
- PaddleOCR-VL (0.9B VLM) as quality bump
- Full PP-DocTranslation pipeline as alt path
- qwen3.6-plus VLM ultimate-rescue tier
- GPU inference path
- User-resume from failed stage button
- Multi-page table continuation
- Re-OCR + retranslate per-segment button
