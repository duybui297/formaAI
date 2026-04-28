---
phase: 04-scanned-pdf-ocr
plan: "01"
subsystem: backend
tags: [ocr, schema, migration, tdd, paddleocr, fpdf2]
dependency_graph:
  requires: []
  provides:
    - Segment dataclass OCR fields (confidence, region_bbox, region_label, edited_source_text)
    - ORM Segment model with 4 nullable OCR columns
    - Alembic migration 0006 adding OCR columns + JobStage enum values
    - paddleocr>=3.5,<4 and fpdf2>=2.7,<3 declared as backend dependencies
    - Dockerfile PP-StructureV3 model bake layer + Noto font bundle
    - Wave 0 RED test stubs for all Phase 4 pipeline components
    - conftest.py mock_ppstructurev3 and low_confidence_mock_ppstructurev3 fixtures
  affects:
    - backend/src/app/pipeline/segment.py (extended)
    - backend/src/app/db/models.py (extended)
    - backend/Dockerfile (extended)
    - backend/pyproject.toml (extended)
    - backend/tests/conftest.py (extended)
tech_stack:
  added:
    - paddleocr>=3.5,<4 (PP-StructureV3 OCR engine)
    - fpdf2>=2.7,<3 (bilingual PDF composition)
    - paddlepaddle==3.0.0 CPU (installed from Alibaba index in Dockerfile)
  patterns:
    - Wave 0 RED test stub pattern (NotImplementedError + unresolved import)
    - PaddleOCR mock fixture pattern (canned parsing_res_list dicts)
    - Alembic ALTER TYPE outside transaction via op.execute("COMMIT") with dialect guard
key_files:
  created:
    - backend/src/app/db/migrations/versions/0006_phase4_ocr.py
    - backend/fonts/README.md
    - backend/tests/fixtures/scanned/README.md
    - backend/tests/pipeline/test_scanned_pdf_detector.py
    - backend/tests/pipeline/test_scanned_pdf_extractor.py
    - backend/tests/pipeline/test_scanned_pdf_composer.py
    - backend/tests/pipeline/test_segment_to_md.py
    - backend/tests/workers/test_translate_worker_scanned.py
    - backend/tests/db/__init__.py
    - backend/tests/db/test_migration_0006.py
  modified:
    - backend/src/app/pipeline/segment.py
    - backend/src/app/db/models.py
    - backend/pyproject.toml
    - backend/Dockerfile
    - backend/tests/conftest.py
    - backend/uv.lock
decisions:
  - "migration 0006 uses dialect guard for ALTER TYPE (skips on SQLite unit tests, runs on PostgreSQL)"
  - "paddlepaddle installed from Alibaba index in Dockerfile — not in pyproject.toml (T-04-02)"
  - "Noto fonts NOT committed to git (binary files, ~50MB) — documented in fonts/README.md"
  - "RED stubs use NotImplementedError + unresolved import to guarantee failure before implementation"
metrics:
  duration_minutes: 15
  tasks_completed: 2
  tasks_total: 2
  files_created: 10
  files_modified: 6
  completed_date: "2026-04-28"
---

# Phase 4 Plan 01: Foundation — Deps, Migration 0006, Schema Extensions, RED Test Stubs

One-liner: Phase 4 OCR foundation — Segment dataclass + ORM extended with 4 OCR fields, Alembic migration 0006 with PostgreSQL enum guard, paddleocr/fpdf2 deps declared, Dockerfile model-bake layer added, 6 Wave 0 RED test files scaffolded.

## What Was Built

### Task 1: Schema Extensions and Migration

Extended the pipeline's core data model to carry PaddleOCR output metadata:

**Segment dataclass** (`segment.py`):
- `confidence: float | None` — page-mean PaddleOCR rec_score for OCR quality gating
- `region_bbox: tuple[float,float,float,float] | None` — normalized [0,1] bounding box for region-positioned compose
- `region_label: str | None` — PP-StructureV3 `block_label` for Markdown heading inference
- `edited_source_text: str | None` — reviewer-corrected OCR source (D-04-03)
- `kind` comment updated to include `ocr_text`

**ORM Segment model** (`models.py`):
- Same four columns added as nullable mapped_columns (Float, JSON, String(64), Text)

**JobStage enum** (`models.py`):
- Added `ocr = "ocr"` after `parse`
- Added `compose = "compose"` after `translate`

**FlagType enum** (`models.py`):
- Added `figure_passthrough = "figure_passthrough"` (info-severity, D-04-24)
- Added `ocr_page_error = "ocr_page_error"` (warn-severity, D-04-31)
- Both fit within existing VARCHAR(32) from migration 0005 — no DDL needed

**Alembic migration 0006** (`0006_phase4_ocr.py`):
- Adds four nullable columns to `segments` table
- Extends `jobstage` PostgreSQL enum via `ALTER TYPE ADD VALUE IF NOT EXISTS`
- Guarded by `bind.dialect.name == "postgresql"` so SQLite unit tests skip ALTER TYPE
- `op.execute("COMMIT")` closes Alembic's implicit transaction before ALTER TYPE (T-04-01 mitigation)

### Task 2: Dependencies, Infrastructure, RED Tests

**pyproject.toml**: Added `paddleocr>=3.5,<4` and `fpdf2>=2.7,<3` to project dependencies.

**Dockerfile** (three new layers before `COPY src/`):
1. `pip install paddlepaddle==3.0.0` from Alibaba index (T-04-02: prevents wrong-index stub install)
2. `pip install "paddleocr>=3.5,<4" "fpdf2>=2.7,<3"` for PP-StructureV3 + compose engine
3. `COPY backend/fonts/` and `ENV PADDLEOCR_HOME=/paddle_models` + model bake via `PPStructureV3()` init (D-04-15: zero demo-day cold start)

**backend/fonts/README.md**: Documents expected Noto font files (NotoSans-Regular.ttf, NotoSansCJK-Regular.ttc), download sources, and why explicit paths are needed for fpdf2.

**conftest.py extensions**:
- `_make_bbox()` helper creates numpy (4,2) polygon from axis-aligned rect
- `mock_ppstructurev3` fixture: canned 2-block result with mean confidence 0.89 (above 0.7)
- `low_confidence_mock_ppstructurev3` fixture: 1-block result with mean confidence 0.45 (below 0.7, triggers needs_review)

**Wave 0 RED test stubs** (6 files, 20 test functions total):
- `test_scanned_pdf_detector.py` — 3 tests for text-density heuristic (D-04-17)
- `test_scanned_pdf_extractor.py` — 5 tests for PP-StructureV3 wrapper (OCR-01)
- `test_scanned_pdf_composer.py` — 4 tests for fpdf2 bilingual composer (OCR-03)
- `test_segment_to_md.py` — 4 tests for Segment→Markdown helper (D-04-33)
- `test_translate_worker_scanned.py` — 4 tests for worker dispatch (OCR-04)
- `test_migration_0006.py` — 2 tests for migration column additions

All stubs raise `NotImplementedError` and import from unimplemented modules — confirmed RED via ImportError at collection time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added SQLite dialect guard to migration 0006**
- **Found during:** Task 1 — plan's migration template lacked a dialect check
- **Issue:** `op.execute("COMMIT")` + `ALTER TYPE ADD VALUE` would crash on SQLite (unit tests use in-memory SQLite)
- **Fix:** Added `if bind.dialect.name == "postgresql":` guard around the ALTER TYPE block
- **Files modified:** `backend/src/app/db/migrations/versions/0006_phase4_ocr.py`
- **Commit:** c74f9cb

**2. [Rule 3 - Blocking] Added `tests/db/__init__.py`**
- **Found during:** Task 2 — pytest requires `__init__.py` for the new `tests/db/` directory to be recognized as a package
- **Fix:** Created empty `__init__.py` alongside `test_migration_0006.py`
- **Files modified:** `backend/tests/db/__init__.py`
- **Commit:** 66a0b8a

**3. [Rule 3 - Blocking] uv.lock updated as side-effect of paddleocr install**
- **Found during:** Task 2 verification — `uv run` triggered package resolution and updated `uv.lock`
- **Fix:** Committed `uv.lock` with the Task 2 commit (generated file rides with causing commit per git-workflow.md)
- **Files modified:** `backend/uv.lock`
- **Commit:** 66a0b8a

## Decisions Made

1. **Migration dialect guard**: Migration 0006 skips `ALTER TYPE` on SQLite to keep unit tests green. PostgreSQL path uses `IF NOT EXISTS` for idempotency (T-04-01).
2. **paddlepaddle not in pyproject.toml**: Must be installed from Alibaba index — standard PyPI version is a stub. Dockerfile handles this; pyproject.toml only declares `paddleocr` which uv can install from PyPI.
3. **Noto fonts not in git**: Binary files (~50MB). Documented in `backend/fonts/README.md`. CI should fetch during build.
4. **numpy import in conftest**: `import numpy as np` added at module level in conftest.py for the `_make_bbox` helper. numpy is a transitive dependency of paddleocr — always available in the test environment.

## Known Stubs

All Wave 0 RED test stubs are intentional — they will be implemented in Plans 02–05. The stub pattern (NotImplementedError + unresolved import) is by design per the TDD execution protocol.

No implementation stubs exist — all modified production code (segment.py, models.py, migration) is complete and functional.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/src/app/db/migrations/versions/0006_phase4_ocr.py` | FOUND |
| `backend/fonts/README.md` | FOUND |
| `backend/tests/fixtures/scanned/README.md` | FOUND |
| `backend/tests/pipeline/test_scanned_pdf_detector.py` | FOUND |
| `backend/tests/pipeline/test_scanned_pdf_extractor.py` | FOUND |
| `backend/tests/pipeline/test_scanned_pdf_composer.py` | FOUND |
| `backend/tests/pipeline/test_segment_to_md.py` | FOUND |
| `backend/tests/workers/test_translate_worker_scanned.py` | FOUND |
| `backend/tests/db/__init__.py` | FOUND |
| `backend/tests/db/test_migration_0006.py` | FOUND |
| Commit c74f9cb (Task 1) | FOUND |
| Commit 66a0b8a (Task 2) | FOUND |
| `Segment.from_text(confidence=0.9)` assertion | PASSED |
