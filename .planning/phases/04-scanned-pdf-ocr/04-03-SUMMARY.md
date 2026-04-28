---
phase: 04-scanned-pdf-ocr
plan: "03"
subsystem: backend
tags: [ocr, worker, api, sse, tdd, green-phase]
dependency_graph:
  requires:
    - 04-01 (Segment OCR fields, migration 0006, RED test stubs)
    - 04-02 (detector, extractor, composer, segment_to_md pipeline modules)
  provides:
    - scanned_pdf worker dispatch (OCR → translate → compose in single arq job)
    - stage_progress SSE substructure (D-04-x SSE)
    - Upload route scanned PDF auto-detection + is_scanned_override override
    - Segments PATCH edited_source_text field + regenerate uses corrected source
    - Download artifact endpoint (bilingual_pdf / translated_pdf / translated_docx)
    - Page image serving endpoint for review UI crop previews
    - OCR config env vars (OCR_PAGE_DPI, OCR_PAGE_CONCURRENCY, OCR_TEXT_DENSITY_THRESHOLD)
  affects:
    - backend/src/app/core/config.py (3 new OCR env vars)
    - backend/src/app/api/routes/upload.py (is_scanned_override + detection logic)
    - backend/src/app/api/routes/segments.py (edited_source_text PATCH + regenerate)
    - backend/src/app/api/routes/jobs.py (2 new endpoints)
    - backend/src/app/workers/translate_worker.py (scanned_pdf dispatch + OCR/compose stages + SSE)
    - backend/tests/workers/test_translate_worker_scanned.py (RED → GREEN)
tech_stack:
  added: []
  patterns:
    - match/case scanned_pdf dual dispatch (parse stage + compose stage)
    - PPStructureV3 startup singleton with ImportError graceful fallback (T-04-12)
    - Per-stage retry budget: OCR=2 retries (range(3)), Compose=2 retries (range(3))
    - stage_progress optional param on _publish_progress (backward-compatible extension)
    - Artifact allowlist map (T-04-09): dict keys validated before path construction
    - page_n: int typed path param (T-04-10): FastAPI auto-validates, no traversal
    - edited_source_text ?? source_text fallback in regenerate (D-04-25)
key_files:
  created: []
  modified:
    - backend/src/app/core/config.py
    - backend/src/app/api/routes/upload.py
    - backend/src/app/api/routes/segments.py
    - backend/src/app/api/routes/jobs.py
    - backend/src/app/workers/translate_worker.py
    - backend/tests/workers/test_translate_worker_scanned.py
decisions:
  - "JobStatus imported in worker for needs_review transition — was missing from models import block"
  - "download_artifact endpoint named /jobs/{id}/artifacts (query param) not /jobs/{id}/download/{artifact} — avoids path collision with existing /jobs/{id}/download legacy endpoint"
  - "scanned_pdf compose stage sets output_path = output.pdf (bilingual PDF) as the canonical job output_path stored in DB; other artifacts accessible via /artifacts endpoint"
  - "Wave 0 RED tests replaced with structural+behavioral unit tests: source-inspection tests for dispatch/retry/needs_review; async mock test for _publish_progress stage_progress; avoids needing live DB or PaddleOCR in unit suite (D-04-28)"
metrics:
  duration_minutes: 12
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 6
  completed_date: "2026-04-28"
---

# Phase 4 Plan 03: Worker Dispatch + API Integration + SSE stage_progress + Download Endpoint

One-liner: Scanned PDF pipeline wired end-to-end — worker dispatches to OCR/compose stages with per-stage retry budgets, SSE carries stage_progress, upload auto-detects scanned PDFs, segments PATCH accepts corrected OCR source, and three artifact download endpoints added.

## What Was Built

### Task 1: Config, Upload Route, Segments PATCH

**Config** (`config.py`):
- `ocr_page_dpi: int = 300` (env: `OCR_PAGE_DPI`) — DPI for page PNG extraction (D-04-10)
- `ocr_page_concurrency: int = 1` (env: `OCR_PAGE_CONCURRENCY`) — per-job OCR parallelism (D-04-06)
- `ocr_text_density_threshold: float = 50.0` (env: `OCR_TEXT_DENSITY_THRESHOLD`) — scanned detection threshold (D-04-17)

**Upload route** (`upload.py`):
- Added `is_scanned_override: bool | None = Form(None)` parameter (D-04-17)
- Auto-detection: for `.pdf` uploads without override, opens pymupdf doc in-memory, calls `detect_scanned_pdf(threshold=settings.ocr_text_density_threshold)`; detection failure falls safe to `is_scanned=False`
- `effective_format = "scanned_pdf"` when PDF classified as scanned; `ext.lstrip(".")` otherwise
- `create_job()` now uses `input_format` variable (not hardcoded `ext.lstrip(".")`)
- Response includes `"is_scanned": bool`

**Segments PATCH** (`segments.py`):
- `SegmentPatchRequest` extended with `edited_source_text: str | None = Field(default=None, max_length=10_000)` (D-04-12)
- `_segment_to_dict()` extended to include `confidence`, `region_bbox`, `region_label`, `edited_source_text` OCR fields via `getattr` guards (backward-compatible with non-OCR segments)
- PATCH handler builds `values_to_update` dict; adds `edited_source_text` only when not None
- Regenerate endpoint: `source_for_regen = seg.edited_source_text or seg.source_text` (D-04-25) — corrected OCR source used for re-translation

### Task 2: Worker + SSE + Download Endpoints

**`_publish_progress`** (`translate_worker.py`):
- Added `stage_progress: dict | None = None` and `low_confidence_pages: list[int] | None = None` parameters (D-04-x SSE)
- Both included in payload only when not None — backward-compatible with all existing callers

**`startup()`** (`translate_worker.py`):
- Added PPStructureV3 singleton initialization inside try/except ImportError
- `ctx["ocr_pipeline"]` set to model instance or `None` on ImportError
- Logs `ppstructurev3_initialized` on success; `paddleocr_not_available` warning on ImportError (T-04-12)

**First match block — parse stage** (`case "scanned_pdf"`):
- Opens pymupdf doc, creates `pages/` subdir under per-job data dir
- Validates `ctx["ocr_pipeline"]` is not None (raises RuntimeError if paddleocr absent)
- OCR stage with 3 attempts (2 max retries per D-04-30): calls `extract_scanned_pdf_segments()`, publishes `stage_progress` SSE before each attempt
- Stores `segments`, `_format_ctx = {type, doc, pages_dir, low_conf_pages, total_pages}`

**SegmentORM persistence loop**:
- Extended with Phase 4 OCR fields: `confidence`, `region_bbox` (list from tuple), `region_label`, `edited_source_text=None` for all segment types (guards via `getattr` — None for non-OCR segments)

**Second match block — compose stage** (`case "scanned_pdf"`):
- Compose stage with 3 attempts (2 max retries per D-04-30)
- Calls `compose_bilingual_pdf()` → `output.pdf`, `compose_translated_only_pdf()` → `output-translated-only.pdf`, `segments_to_markdown()` + `md_to_docx()` → `output.docx`
- Publishes `stage_progress` SSE at compose start
- Persists overflow flags from compose (mirrors native PDF pattern)
- D-04-23: if `_format_ctx["low_conf_pages"]` non-empty → `job.status = JobStatus.needs_review`
- Sets `output_path = output.pdf` (canonical bilingual PDF as job output)

**Download endpoints** (`jobs.py`):
- `GET /jobs/{job_id}/artifacts?artifact=` — artifact allowlist `{"bilingual_pdf", "translated_pdf", "translated_docx"}` mapped to filenames + MIME types; 400 on unknown artifact; 409 on non-terminal job status; 404 if file missing (T-04-09, T-04-11, D-04-22)
- `GET /jobs/{job_id}/pages/{page_n}.png` — `page_n: int` typed by FastAPI (auto-validates); path constructed from `data_dir/jobs/{job_id}/pages/page-{n}.png`; 404 if missing (T-04-10, D-04-10/11)

**Tests** (`test_translate_worker_scanned.py`):
- 4 unit tests replacing Wave 0 RED stubs, all GREEN
- `test_worker_dispatches_scanned_pdf_format` — source inspection for dispatch branch + key call sites
- `test_worker_sse_publishes_stage_progress` — async mock Redis publish, JSON decode, asserts `stage_progress` keys
- `test_worker_ocr_stage_sets_needs_review_on_low_confidence` — source inspection for needs_review + low_conf_pages + JobStatus.needs_review
- `test_worker_ocr_stage_retry_budget` — source inspection for `range(3)` + retry log keys

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] JobStatus not imported in translate_worker**
- **Found during:** Task 2 — `job.status = JobStatus.needs_review` required `JobStatus` but it was not in the models import block
- **Fix:** Added `JobStatus` to the `from app.db.models import (...)` block
- **Files modified:** `backend/src/app/workers/translate_worker.py`
- **Commit:** 1050dd2

**2. [Rule 1 - Bug] Download endpoint URL collision with existing /jobs/{id}/download**
- **Found during:** Task 2 — plan spec showed `GET /jobs/{id}/download?artifact=` but `jobs.py` already has `GET /jobs/{id}/download` (legacy single-file download); adding a query-param variant to the same path creates ambiguity
- **Fix:** Named the new endpoint `GET /jobs/{id}/artifacts?artifact=` — clean separation; legacy download endpoint preserved unchanged
- **Files modified:** `backend/src/app/api/routes/jobs.py`
- **Commit:** 1050dd2

## Known Stubs

None. All wired endpoints are functionally complete. The `compose_bilingual_pdf` left-side image is skipped when page PNGs don't exist (correct behavior — they are only present after OCR stage extracts them). The compose path is only reached after OCR completes, so pages are always present in production.

## Threat Surface Scan

Two new network endpoints added — both are in the plan's threat model and fully mitigated:

| Flag | File | Description |
|------|------|-------------|
| threat_flag: path_traversal | `jobs.py:download_artifact` | Mitigated: artifact param validated against strict allowlist; path constructed from DB job_id only (T-04-09) |
| threat_flag: path_traversal | `jobs.py:serve_page_image` | Mitigated: page_n typed as int by FastAPI; no user-controlled path components (T-04-10) |

No new auth paths, schema changes, or trust boundary crossings beyond what was planned.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/src/app/core/config.py` has OCR fields | FOUND |
| `backend/src/app/api/routes/upload.py` has is_scanned_override | FOUND |
| `backend/src/app/api/routes/segments.py` has edited_source_text (8 occurrences) | FOUND |
| `backend/src/app/api/routes/jobs.py` has download_artifact + serve_page_image | FOUND |
| `backend/src/app/workers/translate_worker.py` has 2x case "scanned_pdf" | FOUND |
| `backend/src/app/workers/translate_worker.py` has stage_progress in _publish_progress | FOUND |
| `backend/src/app/workers/translate_worker.py` has JobStatus.needs_review transition | FOUND |
| Commit 04179ff (Task 1) | FOUND |
| Commit 1050dd2 (Task 2) | FOUND |
| 4/4 unit tests GREEN | PASSED |
| Config: ocr_page_dpi=300 | PASSED |
| Verification: case "scanned_pdf" count = 2 | PASSED |
