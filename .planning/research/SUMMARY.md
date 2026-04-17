# Project Research Summary

**Project:** AI Translation PoC (VNEXT AICore Demo)
**Domain:** Web-based AI document translation — DOCX, PPTX, native PDF, scanned PDF
**Researched:** 2026-04-17
**Confidence:** HIGH (stack and pitfalls verified against live docs and library source; architecture
cross-validated across all four research files)

---

## CRITICAL UPDATES — Read Before Writing Any Code

Research overturned several assumptions in PROJECT.md. These are not minor clarifications — they
change the API call signature, the tool choices, and the expected PoC output format.

| # | What PROJECT.md Said | What Research Found | Action |
|---|----------------------|---------------------|--------|
| 1 | `qwen3.6-plus` as the model | **Does not exist.** Use `qwen-mt-turbo` (translation-specialized, 92 languages, ~$0.49/1M output tokens, native `terminology` API for glossary) | Update all model references on Day 1 |
| 2 | DashScope SDK (implied) | Use **OpenAI SDK** with `base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"` — same SDK Thu already uses for ICOM-P3 | Wire the client correctly in infrastructure spike |
| 3 | DashScope endpoint unspecified | **China vs. international endpoints are separate; API keys are not portable.** From Vietnam, use `dashscope-intl.aliyuncs.com` (Singapore). 401 errors with no helpful message if wrong. | Validate on Day 1 with a `curl` health check |
| 4 | Celery implied for background jobs | Use **arq** (Redis-backed, asyncio-native) — Celery's async support is bolt-on; arq is a natural fit for the FastAPI/asyncio stack | Scaffold arq in Phase 1 |
| 5 | Tesseract for OCR (implied) | Use **PaddleOCR PP-OCRv5** (self-hosted, handles VN + CJK + EN in one model, +13pp over v4) — Tesseract's Japanese model is materially weaker | Pull PaddleOCR into Phase 4 |
| 6 | Per-run translation granularity | **Paragraph-level segmentation only.** Never translate `run.text` individually — runs are typographic fragments, not semantic units | Enforce at the DOCX parser level in Phase 1 |
| 7 | Scanned PDF = reconstructed layout | **Bilingual side-by-side output** (original page image left, translated text right) — full layout reconstruction from OCR is research-level complexity, not a 2-3 week deliverable | Set correct expectations with AICore before demo |
| 8 | — | **#1 demo-killer: silent segment dropping.** `assert len(translations) == len(source_segments)` must fire on every batch call | Wire the assertion before any end-to-end test |
| 9 | — | **NFC normalization is mandatory** at the LLM output boundary for Vietnamese. NFD diacritics look correct on screen but render as boxes in Word and PDF. | Add `unicodedata.normalize('NFC', text)` in post-processor |
| 10 | — | PyMuPDF redact-annot workflow + **bundled Noto CJK fonts in Docker image** (~48 MB for `NotoSansCJK-Regular.ttc`) — original PDF fonts cannot be reused for new text insertion | Add font install to Dockerfile in Phase 1 |

---

## Three Open Questions — Must Be Answered in Phase 0 / Early Phase 1

| # | Question | How to Answer | Blocking For |
|---|----------|---------------|--------------|
| Q1 | Does `qwen-mt-turbo` respond correctly on `dashscope-intl.aliyuncs.com` with the VNEXT API key? | `curl` test from the actual demo machine + Python snippet from STACK.md Section 2 | Everything — entire pipeline depends on this |
| Q2 | Does `qwen-mt-turbo`'s `terminology` parameter actually enforce glossary terms in Vietnamese output? | Send a 5-segment test batch with 3 known company terms; inspect all output segments | Glossary feature (Phase 2) |
| Q3 | What is PaddleOCR PP-OCRv5's first-run model download behavior? (~1 GB on cold start) | `docker run` and time the first OCR call; pin the model version | Phase 4 OCR pipeline; demo day cold-start risk |

---

## Executive Summary

This is a two-to-three week PoC of an AI document translation tool targeting the VNEXT AICore team.
The core differentiators over commodity tools (Azure Translator, DeepL, Google) are: LLM translation
quality via a specialized Qwen model, native glossary enforcement, layout-aware format preservation,
and a side-by-side review UX that no free-tier competitor offers. The research confirms this is an
achievable PoC scope given Thu's existing Python/FastAPI/Next.js stack, with one confirmed technology
upgrade (arq over any Celery assumption) and two confirmed technology selections (qwen-mt-turbo as
the model, PaddleOCR PP-OCRv5 for scanned PDFs).

The recommended approach is a format-first, pipeline-centric build: ship a working end-to-end DOCX
path first (upload -> parse -> segment -> translate -> reassemble -> download), then add the review
UX, then extend to PPTX and native PDF, then add OCR for scanned PDFs. Every stage should validate
the segment-count assertion and NFC normalization from day one — these are not cleanup tasks, they
are correctness invariants. The DashScope endpoint and model name must be validated before writing
any other pipeline code.

The top risks are: (1) DashScope region mismatch causing 401 errors on demo day, (2) silent segment
dropping by the LLM making output shorter than input with no error raised, (3) CJK/Vietnamese glyph
rendering failures in PDF output if Noto fonts are not bundled, and (4) PPTX text-box overflow
making slides look broken. All four have concrete mitigations documented in PITFALLS.md. The OCR
path (Phase 4) carries the most implementation uncertainty; limiting scanned PDF output to a
bilingual side-by-side rather than full layout reconstruction is the correct PoC trade-off.

---

## Key Findings

### Stack — "Buy This, Not That"

| Buy | Instead Of | Why |
|-----|------------|-----|
| `qwen-mt-turbo` via DashScope | `qwen3-max`, `qwen3.6-plus` (nonexistent) | Translation-specialized; 92 languages; native `terminology` API; ~12x cheaper than qwen3-max |
| OpenAI SDK + `dashscope-intl` base URL | `dashscope` Python SDK | Thu already uses it for ICOM-P3; OpenAI ecosystem tooling; `extra_body` for terminology |
| arq 0.27 + Redis | Celery | asyncio-native; single Redis dep already in stack; no Beat process |
| PaddleOCR PP-OCRv5 | Tesseract 5 | Tesseract's Japanese model is materially weaker; PaddleOCR handles VN+CJK+EN in one model |
| PyMuPDF + Noto fonts (Docker) | pdfplumber, reportlab | PyMuPDF has both extraction and text reinsertion; pdfplumber is extraction-only |
| python-docx paragraph-level | python-docx run-level | Runs are typographic fragments; paragraph is the semantic translation unit |
| Local FS then MinIO | AWS S3 for PoC | Zero IAM setup for a single-machine demo |
| PostgreSQL + SQLAlchemy async | SQLite | Concurrent job updates cause write serialization on SQLite |
| Monaco DiffEditor | react-diff-viewer | Monaco enables inline editing before export; diff-viewer is read-only |
| SSE (sse-starlette) | WebSocket | One-directional push; simpler for progress streaming |

**Full verified versions:** Python 3.12, FastAPI 0.115+, Next.js 15 (App Router), PostgreSQL 16,
Redis 7, python-docx 1.2.0, python-pptx 1.0.2, PyMuPDF 1.26.x, arq 0.27.0, openai 1.x,
PaddleOCR 3.x (PP-OCRv5), SQLAlchemy 2.0 + asyncpg 0.30.x, @monaco-editor/react 4.x.

See `.planning/research/STACK.md` for full rationale and version compatibility notes.

### Expected Features

**Must have (table stakes — demo fails without these):**
- File upload (drag-drop) with progress indicator and format detection
- DOCX translation with format preservation (styles, tables, headers/footers)
- Native PDF translation with single-column layout fidelity
- Source language auto-detect + target language picker
- Download translated file in original format (DOCX->DOCX, PDF->PDF, PPTX->PPTX)
- Basic job status (pending / translating / done / failed)
- Clear error state for unsupported formats / oversized files

**Should have (the four differentiators that win the demo):**
- D1 — LLM quality: `qwen-mt-turbo` with segment batching and document-context system prompt
- D2 — Glossary: CSV upload + native `terminology` API injection + post-processing safety net
- D3 — Smart layout: PPTX text-box overflow detection + auto-scale + overflow badges in UI
- D4 — Review UX: side-by-side Monaco DiffEditor, inline editable segments, export after edit

**Build in Phase 3 if Phase 1+2 are stable:**
- PPTX translation with overflow detection
- Glossary hit highlighting in review pane
- Single-segment re-translate button
- PDF complexity score + pre-translation warning

**Explicit anti-features for PoC (do not build):**
- Translation memory / fuzzy matching (v2)
- Multi-file batch upload (v2)
- User auth / RBAC / multi-tenancy (v2)
- Pixel-perfect scanned PDF reconstruction (research-level; not in scope)
- XLSX support (deferred)
- BLEU/COMET quality scoring (misleading without reference translations)
- Real-time multi-user collaboration (v2)

See `.planning/research/FEATURES.md` for full competitive scan and priority matrix.

### Architecture Approach

The system is a four-layer pipeline: Next.js frontend -> FastAPI REST API -> arq worker ->
format-specific translation pipeline. The worker runs the pipeline synchronously in a single asyncio
process: format detection -> parse -> segment extraction -> pre-process (placeholder protection) ->
adaptive batching -> Qwen-MT call -> post-process (NFC normalize, placeholder restore,
segment-count assert, overflow flag) -> reassemble -> write output file. The key architectural
invariant is the `Segment` frozen dataclass: every piece of translatable text gets a stable ID,
position metadata, and style context at parse time. Reassembly runs once at export time using
`edited_text ?? translated_text` per segment.

**Major components:**
1. FastAPI API (`app/api/`) — HTTP boundary: validate input, enqueue to arq, serve segment/glossary CRUD, stream SSE progress
2. arq Worker (`app/worker.py`) — dequeues jobs, runs pipeline, writes progress_pct + status to DB
3. Format Pipeline (`app/pipeline/`) — pure functions: detector, parser, segment extractor, pre-processor, Qwen client, post-processor, reassembler (per format)
4. OCR Subsystem (`app/ocr/`) — PaddleOCR PP-StructureV3; called only by `pdf_scanned` parser
5. Storage Layer — PostgreSQL (jobs, segments, glossaries), Redis (arq queue), local FS then MinIO (files)
6. Next.js Frontend — upload form, job status poller, Monaco side-by-side review editor, glossary manager, download

See `.planning/research/ARCHITECTURE.md` for full data-flow diagrams and anti-patterns.

### Top 10 Demo-Killers (pre-demo checklist)

| # | Demo-Killer | Prevention |
|---|-------------|------------|
| 1 | **Silent segment dropping** — LLM skips a paragraph; output shorter than source | `assert len(translations) == len(source_segments)` after every batch; retry at half-size on failure |
| 2 | **DOCX run-splitting corruption** — `run.text = translated` fractures mid-word formatting | Paragraph-level extraction always; write back to `para.runs[0]`, blank remaining runs |
| 3 | **DashScope 401 / wrong endpoint** — China key from Vietnam = 401 with no message | `curl` health check from demo machine 24 h before; `base_url` in env var, never hardcoded |
| 4 | **Vietnamese NFC normalization** — NFD diacritics render as boxes in Word/PDF | `unicodedata.normalize('NFC', text)` in post-processor; unit test with known NFD VN string |
| 5 | **PPTX text-box overflow** — translated text silently clips at shape boundary | Heuristic overflow detector after reassembly; set `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE`; flag in review UI |
| 6 | **PDF column-layout scramble** — two-column doc extracted in interleaved order | Cluster blocks by x-coordinate before concatenating; two-column PDF in smoke test suite |
| 7 | **Missing CJK/VN glyphs in PDF output** — original font subset has no target glyphs | Always embed bundled Noto fonts in Docker; never reuse source PDF's font for new text insertion |
| 8 | **LLM adds commentary** — model prepends "Translated from English:" to output | System prompt: "Return ONLY the translated text. No explanations, no prefixes." Validate output |
| 9 | **No progress feedback** — 2-minute job with static spinner = demo feels broken | SSE progress stream from Day 1; show "Translating segment N/M" at minimum |
| 10 | **Demo doc triggers model refusal** — Qwen content filter blocks an innocuous slide | Pre-translate the exact demo doc 24 h before; never live-translate it for the first time on stage |

See `.planning/research/PITFALLS.md` for all 15 pitfalls, recovery strategies, and the full
pre-demo checklist.

---

## Implications for Roadmap

### Suggested Phase Structure

#### Phase 0: Infrastructure Spike (Day 1 — before any pipeline work)
**Rationale:** Q1, Q2, Q3 from the open questions above must be answered before building anything.
A wrong model name or wrong endpoint kills the entire pipeline.
**Delivers:** Confirmed working DashScope call from the demo machine; confirmed `terminology` API
behavior for Vietnamese; confirmed PaddleOCR cold-start time.
**Avoids:** Pitfall 3 (endpoint/region mismatch) and glossary enforcement surprises in Phase 2.
**Research flag:** Spike only — no research phase needed; just a Python script and a `curl`.

#### Phase 1: Core Pipeline — DOCX End-to-End
**Rationale:** DOCX is the hero format and the simplest reassembly path. Getting upload -> parse ->
segment -> translate -> reassemble -> download working for DOCX proves the entire pipeline contract
(Segment dataclass, arq worker, DB schema, file storage) before adding format complexity.
**Delivers:** Working DOCX translation with format preservation; downloadable output; arq worker
wired end-to-end; DB schema with jobs + segments + glossaries; Dockerfile with Noto fonts.
**Features:** File upload, format detection, DOCX translation, basic job status, download.
**Pitfalls to wire in Phase 1 (non-negotiable):**
- Paragraph-level segmentation (never per-run)
- Segment-count assertion after every batch call
- NFC normalization in post-processor
- Noto fonts in Dockerfile (`apt-get install fonts-noto-cjk fonts-noto && fc-cache -f`)
- `DASHSCOPE_BASE_URL` in env config, never hardcoded
**Standard patterns:** FastAPI, arq, SQLAlchemy async, python-docx — no research phase needed.

#### Phase 2: Review UX + Glossary
**Rationale:** The review UX and glossary are the two differentiators most visible to AICore. They
layer cleanly on top of Phase 1's segment data model. Monaco editor and glossary injection can be
built in parallel.
**Delivers:** Full DOCX workflow with side-by-side Monaco review, inline edit, glossary CSV upload
with `terminology` API injection, export-after-edit, SSE progress stream.
**Features:** D2 (glossary), D4 (review UX), progress indicator, export after edit.
**Pitfalls to wire in Phase 2:**
- Placeholder protection (URLs, `{{vars}}`, emails) before LLM call
- Adaptive batching with numbered segment markers (`[1] text`)
- Glossary post-processing safety net for brand names (str.replace with word-boundary anchors)
- SSE progress emission after each batch completes
**Research flag:** Glossary `terminology` API behavior confirmed in Phase 0 spike. No additional
research phase needed.

#### Phase 3: PPTX + Native PDF
**Rationale:** PPTX and native PDF share the same pipeline spine as DOCX (same Segment dataclass,
same Qwen client, same arq worker). The only new work is format-specific parsers and reassemblers.
Native PDF is higher risk than PPTX due to the redact-annot + font embedding complexity.
**Delivers:** All three hero formats working end-to-end.
**Features:** PPTX translation with overflow detection + auto-scale + overflow badges; native PDF
with Noto font embedding and `insert_htmlbox`; PDF complexity score pre-translation.
**Pitfalls to wire in Phase 3:**
- PPTX: recursive group shape walker; SmartArt detection + flagging (not silent skip)
- PPTX: `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` on all text frames after translation
- Native PDF: x-coordinate column clustering for multi-column documents
- Native PDF: always embed bundled Noto font; never reuse source font
- Native PDF: `insert_htmlbox` overflow flag -> orange segment highlight in review UI
**Research flag:** PDF multi-column clustering heuristic may need a research spike if the two-column
smoke test PDF shows mis-ordering. PyMuPDF-Layout library is the fallback.

#### Phase 4: Scanned PDF (OCR)
**Rationale:** Scanned PDF is explicitly P2 in scope and carries the most implementation
uncertainty. Build only after Phases 1-3 are demo-stable.
**Delivers:** Scanned PDF -> bilingual side-by-side PDF (original page image left, translated text
right); low-confidence OCR regions flagged with `[?]`; review UI shows OCR source text.
**Features:** PaddleOCR PP-StructureV3 integration, confidence gate (0.7 threshold), bilingual
fpdf2 output, low-confidence flagging.
**Pitfalls to wire in Phase 4:**
- OCR confidence gate: if mean page confidence < 0.7, flag for manual review — do not auto-translate
- Image pre-processing: deskew + 300 DPI upscale before OCR
- Cache OCR results by file hash; never re-OCR on retry
- Segment IDs: use content-hash IDs (not positional) to survive re-translation
**Research flag:** PP-StructureV3 output format + fpdf2 bilingual composition warrant a 1-day spike
at the start of Phase 4 to confirm bounding-box format and page composition approach.

### Phase Ordering Rationale

- DOCX first because it has the cleanest fidelity path (python-docx XML manipulation) and proves
  the entire pipeline contract with the lowest implementation risk.
- Review UX + Glossary in Phase 2 because they are the highest-value demo differentiators and are
  pure additions to Phase 1's segment data model — no rework required.
- PPTX before native PDF in Phase 3 because PPTX reassembly is structurally identical to DOCX;
  native PDF (redact-annot + font embedding) is the hardest reassembly path.
- OCR last because it has the most external uncertainty and is explicitly P2 — the demo succeeds
  without it if Phases 1-3 are solid.

### Research Flags

**Needs a spike before building:**
- Phase 3 (native PDF): two-column column-clustering heuristic — run the smoke test PDF first,
  spike PyMuPDF-Layout if clustering fails.
- Phase 4 (scanned PDF): PP-StructureV3 output format + fpdf2 composition — 1-day spike at the
  start of Phase 4.

**Standard patterns — skip research phase:**
- Phase 0: DashScope API call — just a curl + Python snippet.
- Phase 1: FastAPI, arq, SQLAlchemy async, python-docx — all in STACK.md with verified patterns.
- Phase 2: Monaco DiffEditor, SSE with sse-starlette — well-documented integration.
- Phase 3 PPTX: python-pptx text-frame replacement — standard pattern from STACK.md.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Live DashScope catalog verified 2026-04-17; all library versions confirmed via Context7 and PyPI |
| Features | HIGH | Competitive scan across 10+ products; feature boundaries well-established |
| Architecture | HIGH (core pipeline), MEDIUM (OCR, PDF reassembly) | Core pipeline is standard; OCR output format and bilingual PDF composition need a spike |
| Pitfalls | HIGH | All 15 pitfalls traced to specific GitHub issues, official docs, or production reports |

**Overall confidence: HIGH** for the DOCX + review UX + glossary path (Phases 0-2). MEDIUM for
native PDF column handling (Phase 3) and scanned PDF OCR pipeline (Phase 4) due to format-specific
edge cases that require test-doc validation.

### Gaps to Address

- **DashScope rate limits for `qwen-mt-turbo` international** — not published; implement exponential
  backoff from Day 1; measure actual limits during Phase 1 testing.
- **`qwen-mt-turbo` `terminology` enforcement on Vietnamese** — API supports the parameter but
  enforcement strength on low-frequency VN terms is unknown; Phase 0 spike answers this; add
  post-processing safety net regardless.
- **PaddleOCR CPU-only inference speed on the demo machine** — if too slow for a live demo, fall
  back to Azure Document Intelligence ($1.50/1K pages, confirmed VN+JA+ZH support).
- **SmartArt in real VNEXT PPTX files** — python-pptx cannot translate SmartArt; must flag visibly
  rather than silently skip; check any demo PPTX for SmartArt before demo day.

---

## Sources

### Primary (HIGH confidence — official docs or Context7-verified)
- Alibaba Cloud Model Studio live catalog (2026-04-17) — model IDs, pricing, token limits
- Alibaba Cloud DashScope compatibility docs — OpenAI-compatible endpoint, `extra_body` terminology
- Qwen-MT official blog — 92-language support, RL training, benchmark results
- PyMuPDF official docs (Context7) — redact-annot workflow, insert_htmlbox, font embedding
- python-docx 1.2.0 docs (Context7) — run-level text, paragraph traversal
- python-pptx 1.0.2 docs (Context7) — text-frame, auto-size, shape types
- PaddleOCR PP-OCRv5 technical report (arXiv 2507.05595) — +13pp improvement, PP-StructureV3
- arq PyPI and GitHub — asyncio-native, maintenance-mode status, Redis settings

### Secondary (MEDIUM confidence — multiple-source agreement)
- GitHub issues (python-docx #340, #519, #910) — run-splitting, tracked changes behavior
- GitHub issues (python-pptx #448, #969) — SmartArt not supported, shrink text overflow
- PyMuPDF GitHub discussions — multi-column reading order, insert_htmlbox overflow
- GitHub issues (QwenLM/Qwen3 #1838) — international endpoint model availability
- WMT24/25 terminology translation papers — prompt-injection glossary effectiveness

### Tertiary (LOW confidence — needs validation during implementation)
- DashScope rate limits for `qwen-mt-turbo` international — not published; measure during Phase 1
- PP-StructureV3 bilingual PDF output pipeline — referenced in PaddleOCR docs; needs Phase 4 spike

---
*Research completed: 2026-04-17*
*Ready for roadmap: yes*
