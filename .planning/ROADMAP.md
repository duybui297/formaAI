# Roadmap: AI Translation PoC

## Overview

A 2–3 week sprint to build a web-based AI document translation demo for the AICore team (an AI-native startup). The build follows the pipeline contract: validate the DashScope endpoint and model first, then ship DOCX end-to-end (the hero format), layer on the two highest-value differentiators (glossary and review UX), extend to PPTX and native PDF, add scanned PDF last, and harden for the demo. Every phase delivers a coherent, verifiable capability — the demo succeeds on Phases 1–3 alone if time is tight.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation + DOCX Pipeline** - Validate DashScope, scaffold infrastructure, deliver working DOCX translation end-to-end with all pipeline correctness invariants wired in
- [ ] **Phase 2: Review UX + Glossary** - Side-by-side segment editor, inline edit, glossary management with terminology injection, export-after-edit — the two demo differentiators
- [ ] **Phase 3: PPTX + Native PDF** - Extend the pipeline to the remaining hero formats with format-specific parsers, reassemblers, and overflow detection
- [ ] **Phase 4: Scanned PDF (OCR)** - PaddleOCR pipeline, bilingual side-by-side output, confidence gating — highest technical risk, demo succeeds without it
- [ ] **Phase 5: Demo Hardening** - Curated demo pack, smoke script, pre-translated backups, README — go/no-go gate before AICore presentation

## Phase Details

### Phase 1: Foundation + DOCX Pipeline
**Goal**: The DashScope endpoint is validated, the full infrastructure stack runs locally, and a real DOCX can be uploaded, translated by `qwen-mt-turbo`, and downloaded with paragraph/table/list structure and formatting preserved — with every pipeline correctness invariant active from day one.
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, UPLD-01, UPLD-02, UPLD-03, UPLD-04, UPLD-05, CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06, JOB-01, JOB-02, JOB-03, JOB-04, DOCX-01, DOCX-02, DOCX-03, DOCX-04, LANG-01, LANG-02
**Success Criteria** (what must be TRUE):
  1. A `curl` health-check script confirms `qwen-mt-turbo` responds correctly from the dev machine via `dashscope-intl.aliyuncs.com`, and a Python snippet documents the `terminology` parameter behavior on a VN↔EN glossary sample
  2. `docker-compose up` brings up FastAPI, PostgreSQL, Redis, arq worker, and Next.js frontend; the frontend can call the backend with CORS configured
  3. User can drag-and-drop a DOCX file, select source and target languages (including auto-detect), optionally select a glossary, submit the form, and be redirected to a job status page that shows live segment progress (e.g., "143 / 210 segments translated")
  4. The translated DOCX downloads with paragraph structure, bold/italic/underline, fonts, headings, table cells, and hyperlinks preserved — the run-merge strategy, NFC normalization, placeholder protection, and segment-count assertion are all active; a failed batch surfaces a human-readable error rather than silent truncation
  5. A job with an invalid format is rejected with a clear error message; a job with a 5xx/rate-limit error surfaces retries in the UI rather than crashing silently
**Plans**: 11 plans

Plans:
- [ ] 01-01-infra-prereqs-PLAN.md — Docker, docker-compose, pyproject.toml, frontend package.json, healthcheck script
- [ ] 01-02-backend-core-PLAN.md — Settings/logging config, DB models (Job+Segment), SQLAlchemy session, Alembic init, test conftest
- [ ] 01-03-llm-core-PLAN.md — LLM client, translate_batch with CORE-03/04/05/06, token budget, TDD
- [ ] 01-04-docx-pipeline-PLAN.md — DOCX extractor + reassembler + placeholder protection, TDD
- [ ] 01-05-job-worker-PLAN.md — arq worker, job service, progress publish, retry logic
- [ ] 01-06-fastapi-api-PLAN.md — FastAPI app, upload endpoint, job/SSE endpoints, languages endpoint
- [ ] 01-07-frontend-shell-PLAN.md — Next.js shell, TypeScript types, useJobProgress hook, TanStack setup
- [ ] 01-08-upload-page-PLAN.md — UploadForm, LanguageSelect, tracked-changes modal, upload proxy
- [ ] 01-09-job-status-page-PLAN.md — Job status page, StageIndicator, ProgressBar, animated counter, ErrorDetails
- [ ] 01-10-jobs-list-page-PLAN.md — Jobs list page, StatusBadge, polling table
- [ ] 01-11-migrations-integration-tests-PLAN.md — Alembic first migration, DashScope integration tests, DOCX round-trip tests

**UI hint**: yes

### Phase 2: Review UX + Glossary
**Goal**: The full DOCX workflow gains the two highest-value demo differentiators: a side-by-side Monaco segment editor where reviewers can inline-correct translations before export, and a glossary system that injects company-specific terminology via the `qwen-mt-turbo` `terminology` API and flags violations post-translation.
**Depends on**: Phase 1
**Requirements**: GLOS-01, GLOS-02, GLOS-03, GLOS-04, GLOS-05, REV-01, REV-02, REV-03, REV-04, REV-05, REV-06, LAYOUT-01, LAYOUT-02, LAYOUT-03
**Success Criteria** (what must be TRUE):
  1. User can create a named glossary, add term pairs manually or via CSV/TBX upload, and list/edit/delete glossaries through the UI
  2. When a glossary is attached to a job, its terms are passed to `qwen-mt-turbo` via the `terminology` parameter on every batch; a post-translation pass flags segments where a glossary term's target does not appear in the output
  3. A completed job opens a side-by-side view with source segments on the left and editable translations on the right; users can inline-edit any segment (debounced persistence to DB) and re-translate individual segments without rerunning the whole job
  4. Segment-level flags — overflow, glossary violation, placeholder mismatch, LLM refusal — are visibly surfaced in the review UI; text-expansion ratio is shown for segments above the configured threshold
  5. The Export button reassembles the document using `edited_text ?? translated_text` per segment, produces the translated DOCX, and the operation is idempotent (re-exporting does not corrupt the segment state)
**Plans**: TBD
**UI hint**: yes

### Phase 3: PPTX + Native PDF
**Goal**: The pipeline spine from Phase 1 is extended to PPTX and native (text-layer) PDF, giving AICore all three hero formats: PPTX translates text boxes, speaker notes, tables, and nested groups with overflow detection and auto-fit; native PDF redacts and reinserts translated text with Noto font embedding and column-aware extraction.
**Depends on**: Phase 2
**Requirements**: PPTX-01, PPTX-02, PPTX-03, PPTX-04, PDF-01, PDF-02, PDF-03, PDF-04
**Success Criteria** (what must be TRUE):
  1. A PPTX file round-trips with text boxes, speaker notes, tables, bulleted lists, and master-slide text translated; nested grouped shapes are recursively walked; SmartArt shapes are flagged in the review UI rather than silently skipped
  2. After PPTX translation, text-box overflow is detected and flagged in the review UI with an overflow badge; `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` is applied where safe
  3. A native (text-layer) PDF is parsed with PyMuPDF; translated text is reinserted using the redact-annot workflow with bundled Noto CJK fonts; multi-column layouts are handled via x-coordinate clustering (proven on at least one 2-column test PDF)
  4. When translated PDF text does not fit its bounding box, the segment is flagged for review in the UI (orange highlight); if font scaling brings it within range, it is recorded as auto-adjusted
**Plans**: TBD
**UI hint**: yes

### Phase 4: Scanned PDF (OCR)
**Goal**: Scanned PDFs are handled through a three-stage pipeline (OCR → translate → compose) using PaddleOCR PP-OCRv5, producing a bilingual side-by-side PDF where the original page image appears on the left and the translated text on the right; low-confidence OCR regions are flagged for manual review.
**Depends on**: Phase 3
**Requirements**: OCR-01, OCR-02, OCR-03, OCR-04
**Success Criteria** (what must be TRUE):
  1. A scanned PDF is detected automatically, OCR'd via PaddleOCR PP-OCRv5, and each text region carries a confidence score; the OCR stage can fail/retry independently of the translate and compose stages
  2. Pages where mean OCR confidence falls below 0.7 are marked `needs_review` in the job status and shown in the review UI with the original page image and the low-confidence text highlighted
  3. The output is a bilingual PDF with the original page image on the left and the translated text rendered with Noto CJK fonts on the right; OCR'd segments are editable in the same review UI as other formats
**Plans**: TBD

### Phase 5: Demo Hardening
**Goal**: The demo is hardened for the AICore presentation: a curated set of real documents is pre-translated as a backup, a smoke script validates the full stack is live, and a README + one-page walkthrough ensures Thu can run the demo confidently without debugging on stage. This is the go/no-go gate.
**Depends on**: Phase 4 (or Phase 3 if Phase 4 slips)
**Requirements**: DEMO-01, DEMO-02, DEMO-03
**Success Criteria** (what must be TRUE):
  1. A curated demo pack exists with at least one real DOCX, PPTX, native PDF, and scanned PDF; all four have been pre-translated successfully at least 24 hours before the demo and the translated outputs are saved as fallback artifacts
  2. Running the smoke script from a clean environment confirms DashScope reachability, OCR engine availability, and completes one end-to-end translation job for each supported format without errors
  3. The README covers environment setup, how to run the demo, and known limitations; the one-page walkthrough documents the exact demo flow AICore will see
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation + DOCX Pipeline | 0/11 | Not started | - |
| 2. Review UX + Glossary | 0/TBD | Not started | - |
| 3. PPTX + Native PDF | 0/TBD | Not started | - |
| 4. Scanned PDF (OCR) | 0/TBD | Not started | - |
| 5. Demo Hardening | 0/TBD | Not started | - |
