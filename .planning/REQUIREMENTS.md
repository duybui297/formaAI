# Requirements: AI Translation PoC

**Defined:** 2026-04-17
**Core Value:** Translate documents with format fidelity that makes the translated output usable as-is.

## v1 Requirements

Requirements for the 2–3 week demo for the AICore team (an AI-native startup). Each maps to exactly one roadmap phase.

### Infrastructure

- [ ] **INFRA-01**: DashScope international endpoint + `qwen-mt-turbo` access is verified end-to-end from the dev machine (health check script)
- [ ] **INFRA-02**: `qwen-mt-turbo` `terminology` API parameter is validated on a sample VN ↔ EN + VN ↔ JA glossary (spike output documented)
- [ ] **INFRA-03**: FastAPI + PostgreSQL + Redis + arq base project runs via docker-compose
- [ ] **INFRA-04**: Next.js frontend base project runs and can call the FastAPI backend with CORS configured
- [ ] **INFRA-05**: Noto CJK + Noto Sans Vietnamese fonts are bundled in the backend Docker image

### Upload & Job Creation

- [ ] **UPLD-01**: User uploads a file via drag-and-drop or file picker (max 25 MB for PoC)
- [ ] **UPLD-02**: System auto-detects format (DOCX, PPTX, native PDF, scanned PDF) and rejects unsupported types with a clear message
- [ ] **UPLD-03**: User selects source language (or chooses "auto-detect") and target language from a picker populated by `qwen-mt-turbo`'s supported languages
- [ ] **UPLD-04**: User optionally selects a glossary to apply to the job
- [ ] **UPLD-05**: Submitting the form creates a translation job, returns a job ID, and redirects to the job status page

### Translation Core

- [ ] **CORE-01**: Each supported format has a parser that extracts an ordered list of translatable `Segment` rows with stable IDs, source text, style/position context, and a reference back to the document location
- [ ] **CORE-02**: Translation batches use paragraph-level segments and are sent to `qwen-mt-turbo` via the `openai` SDK against the DashScope international endpoint
- [ ] **CORE-03**: Every LLM batch response is validated: `len(translations) == len(source_segments)` must hold, or the batch is retried (max 3) and then failed loudly (no silent drops)
- [ ] **CORE-04**: Every LLM output string is NFC-normalized before persistence
- [ ] **CORE-05**: Non-translatable tokens (URLs, emails, `{{placeholders}}`, numeric codes) are extracted to `⟦T{n}⟧` markers before translation and restored after
- [ ] **CORE-06**: Rate-limit and 5xx errors from DashScope are retried with exponential backoff; the UI surfaces retries as progress, not as failures

### Job Status & Progress

- [ ] **JOB-01**: A job has one of `queued / running / needs_review / failed / done` states, persisted in Postgres
- [ ] **JOB-02**: A job status page polls (or SSE) for updated progress and state transitions
- [ ] **JOB-03**: Per-segment progress (e.g., `143 / 210 segments translated`) is shown while running
- [ ] **JOB-04**: A failed job surfaces a human-readable error and the raw failing segment(s) for debugging

### DOCX (hero format)

- [ ] **DOCX-01**: A DOCX round-trips with text translated and paragraph/table/list structure, bold/italic/underline, fonts, and headings preserved
- [ ] **DOCX-02**: The run-merge strategy (reconstruct paragraph text, translate, write back into `para.runs[0]`, blank `para.runs[1:]`) is implemented — never translate `run.text` individually
- [ ] **DOCX-03**: Hyperlinks and code spans are preserved as non-translatable
- [ ] **DOCX-04**: Tracked changes and comments are flagged and either stripped (with user opt-in) or preserved with their original text

### PPTX

- [ ] **PPTX-01**: A PPTX round-trips with text boxes, speaker notes, tables, bulleted lists, and master-slide text translated
- [ ] **PPTX-02**: SmartArt shapes are detected and flagged as "cannot translate automatically" — not silently skipped
- [ ] **PPTX-03**: Text-box overflow is detected (measured text exceeds shape bounds) and flagged in the review UI; auto-fit is attempted where `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` is safe
- [ ] **PPTX-04**: Group-shape walker recursively finds text in nested grouped shapes

### Native PDF

- [ ] **PDF-01**: A native (text-layer) PDF is parsed with PyMuPDF; each text span's bbox, font, and size are captured alongside source text
- [ ] **PDF-02**: Translated PDF is produced using the redact-annot workflow: for each span, `add_redact_annot(bbox) → apply_redactions() → insert_textbox(bbox, translated_text)` with Noto CJK font fallback
- [ ] **PDF-03**: When translated text does not fit the bbox at the source font size, the font is scaled down within a safe range; if still too large, the segment is flagged for review
- [ ] **PDF-04**: Multi-column layouts are handled via column-clustering heuristic (prove it on one 2-column test PDF; acceptable to flag and degrade on 3+ columns)

### Scanned PDF (OCR)

- [ ] **OCR-01**: A scanned PDF is OCR'd via PaddleOCR PP-OCRv5; page images are captured alongside extracted text regions with confidence scores
- [ ] **OCR-02**: Pages with mean OCR confidence below 0.7 are marked `needs_review` and surface in the review UI with the original page image plus the low-confidence text
- [ ] **OCR-03**: Scanned-PDF output is a bilingual side-by-side PDF: left page = original page image, right page = translated text rendered by fpdf2 with Noto CJK font embedded
- [ ] **OCR-04**: OCR, translate, and compose are split into three pipeline stages so each can fail/retry independently

### Glossary (differentiator)

- [ ] **GLOS-01**: User can create a named glossary (e.g., "AICore product names") and add term pairs `{ source_term, target_term, source_lang, target_lang, notes }`
- [ ] **GLOS-02**: User can upload a glossary as CSV or TBX
- [ ] **GLOS-03**: Selected glossary terms are passed to `qwen-mt-turbo` via the `terminology` API parameter on every translation batch
- [ ] **GLOS-04**: A post-translation enforcement pass verifies each glossary term's target appears in the output; violations are flagged (not silently corrected) on the segment
- [ ] **GLOS-05**: Glossaries are listable, editable, and deletable via the UI

### Review UX (differentiator)

- [ ] **REV-01**: Completed jobs open a side-by-side editor: source segments on the left, editable translations on the right, aligned by segment ID
- [ ] **REV-02**: User can edit a translated segment; edits persist to the DB (`Segment.edited_text`) as the user types, debounced
- [ ] **REV-03**: Segment-level flags surface visibly: overflow, glossary violation, low OCR confidence, placeholder mismatch, LLM refusal
- [ ] **REV-04**: User can regenerate a single segment's translation via a button (sends only that segment back to `qwen-mt-turbo`) without rerunning the whole job
- [ ] **REV-05**: Export button reassembles the document using `edited_text ?? translated_text` for every segment and produces a downloadable file in the original format
- [ ] **REV-06**: Reassembly on export is idempotent and does not mutate the translated-segments state

### Smart Layout (differentiator)

- [ ] **LAYOUT-01**: Text-expansion ratio is calculated per segment (`len(target) / len(source)`) and surfaced in review for any segment above a configurable threshold
- [ ] **LAYOUT-02**: Format-specific overflow detectors run post-translation (PPTX text-box height, PDF bbox width) and set flags on the segment
- [ ] **LAYOUT-03**: Auto-fit strategies are applied conservatively (PPTX text-to-fit-shape; PDF font scaling within ±2pt) and recorded as "auto-adjusted" in the segment metadata

### Multi-lingual Support

- [ ] **LANG-01**: Source and target language options are driven by `qwen-mt-turbo`'s supported-language list (not hardcoded); auto-detect is available on source
- [ ] **LANG-02**: Vietnamese ↔ English, Vietnamese ↔ Japanese, Vietnamese ↔ Chinese, and English ↔ Japanese are specifically exercised in the demo test pack

### Demo-Readiness

- [ ] **DEMO-01**: A curated demo pack exists: one real DOCX, one PPTX, one native PDF, one scanned PDF — pre-translated 24h before the demo as a backup
- [ ] **DEMO-02**: A pre-demo smoke script verifies DashScope reachability, OCR engine availability, and runs one end-to-end job on each format
- [ ] **DEMO-03**: README + one-page demo walkthrough is written (setup, how to demo, known limitations)

## v2 Requirements

Deferred to after the PoC demo.

### Broader Formats

- **XLSX-01**: Excel spreadsheets translated in place (sheet names, cell contents, formulas untouched)
- **MD-01**: Markdown translation with frontmatter preserved
- **HTML-01**: HTML document translation with tag structure preserved
- **SRT-01**: Subtitle files (SRT/VTT) translated with timing untouched

### Quality Features

- **TM-01**: Translation memory — reuse prior translations on matching segments
- **EVAL-01**: Automated eval harness (BLEU / COMET / segment-count checks) that runs on every pipeline change
- **AB-01**: A/B compare `qwen-mt-turbo` vs `qwen-mt-plus` vs Azure Translator per-job to quantify the quality gap

### Productization

- **AUTH-01**: Multi-user auth (JWT) with session persistence
- **TENANT-01**: Per-team workspaces and glossary scoping
- **OBS-01**: Observability stack (structured logs, traces, usage + cost dashboards)
- **RATE-01**: Per-user rate limiting and quota tiers
- **SHARE-01**: Shareable job-result links with access control

### Advanced Scanned PDF

- **RECON-01**: Layout-reconstructed scanned PDF output (vs side-by-side) with OCR'd bounding boxes redrawn with translated text
- **TABLE-01**: Table detection inside scanned PDFs and translation into structured output

### Collaboration

- **COLLAB-01**: Multiple reviewers on one job with segment-level assignment
- **APPROVE-01**: Approval workflow (draft → review → approved → exportable)

## Out of Scope

Explicitly excluded from the PoC. Prevents scope creep.

| Feature | Reason |
|---------|--------|
| Pixel-perfect scanned-PDF reconstruction | Research-level hard; side-by-side is the honest PoC bar |
| Translation memory / fuzzy-match reuse | Adds complexity without demo payoff; glossary covers the terminology story |
| Multi-tenant auth & workspaces | PoC is single-team internal; defer to productization |
| Production observability (Prometheus, tracing, dashboards) | Log + trace enough to debug; ops polish wastes the 2–3 week budget |
| Billing / usage metering | Not a PoC concern |
| Fine-tuned translation models | Use `qwen-mt-turbo` off-the-shelf; fine-tuning is a v2 question once quality gaps are measured |
| Human-translator marketplace | Not the product we're pitching |
| Mobile app | Web-only for the PoC |
| XLSX support | Deferred to v2; demo doesn't hinge on spreadsheets |
| Real-time collaborative editing | Single-reviewer editing is enough for demo |
| Per-segment LLM streaming to UI | Progress polling/SSE is sufficient; full streaming adds complexity without demo value |
| RTL languages (Arabic, Hebrew) | Demo audience (VN, JA, ZH, EN) doesn't need them; font/layout work is non-trivial |
| Support for documents > 25 MB | PoC file-size ceiling; larger files require chunked upload + longer-running job infra |

## Traceability

Each v1 requirement maps to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Pending |
| UPLD-01 | Phase 1 | Pending |
| UPLD-02 | Phase 1 | Pending |
| UPLD-03 | Phase 1 | Pending |
| UPLD-04 | Phase 1 | Pending |
| UPLD-05 | Phase 1 | Pending |
| CORE-01 | Phase 1 | Pending |
| CORE-02 | Phase 1 | Pending |
| CORE-03 | Phase 1 | Pending |
| CORE-04 | Phase 1 | Pending |
| CORE-05 | Phase 1 | Pending |
| CORE-06 | Phase 1 | Pending |
| JOB-01 | Phase 1 | Pending |
| JOB-02 | Phase 1 | Pending |
| JOB-03 | Phase 1 | Pending |
| JOB-04 | Phase 1 | Pending |
| DOCX-01 | Phase 1 | Pending |
| DOCX-02 | Phase 1 | Pending |
| DOCX-03 | Phase 1 | Pending |
| DOCX-04 | Phase 1 | Pending |
| LANG-01 | Phase 1 | Pending |
| LANG-02 | Phase 1 | Pending |
| GLOS-01 | Phase 2 | Pending |
| GLOS-02 | Phase 2 | Pending |
| GLOS-03 | Phase 2 | Pending |
| GLOS-04 | Phase 2 | Pending |
| GLOS-05 | Phase 2 | Pending |
| REV-01 | Phase 2 | Pending |
| REV-02 | Phase 2 | Pending |
| REV-03 | Phase 2 | Pending |
| REV-04 | Phase 2 | Pending |
| REV-05 | Phase 2 | Pending |
| REV-06 | Phase 2 | Pending |
| LAYOUT-01 | Phase 2 | Pending |
| LAYOUT-02 | Phase 2 | Pending |
| LAYOUT-03 | Phase 2 | Pending |
| PPTX-01 | Phase 3 | Pending |
| PPTX-02 | Phase 3 | Pending |
| PPTX-03 | Phase 3 | Pending |
| PPTX-04 | Phase 3 | Pending |
| PDF-01 | Phase 3 | Pending |
| PDF-02 | Phase 3 | Pending |
| PDF-03 | Phase 3 | Pending |
| PDF-04 | Phase 3 | Pending |
| OCR-01 | Phase 4 | Pending |
| OCR-02 | Phase 4 | Pending |
| OCR-03 | Phase 4 | Pending |
| OCR-04 | Phase 4 | Pending |
| DEMO-01 | Phase 5 | Pending |
| DEMO-02 | Phase 5 | Pending |
| DEMO-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 55 total
- Mapped to phases: 55
- Unmapped: 0 ✓

| Phase | Requirements | Count |
|-------|-------------|-------|
| Phase 1: Foundation + DOCX Pipeline | INFRA-01–05, UPLD-01–05, CORE-01–06, JOB-01–04, DOCX-01–04, LANG-01–02 | 26 |
| Phase 2: Review UX + Glossary | GLOS-01–05, REV-01–06, LAYOUT-01–03 | 14 |
| Phase 3: PPTX + Native PDF | PPTX-01–04, PDF-01–04 | 8 |
| Phase 4: Scanned PDF (OCR) | OCR-01–04 | 4 |
| Phase 5: Demo Hardening | DEMO-01–03 | 3 |
| **Total** | | **55** |

---
*Requirements defined: 2026-04-17*
*Last updated: 2026-04-17 — traceability populated after roadmap creation*
