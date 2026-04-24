---
phase: 02-review-ux-glossary
plan: "02"
subsystem: backend-db
tags: [orm, alembic, migration, glossary, segment-flags, config]
dependency_graph:
  requires: []
  provides:
    - Glossary ORM model (backend/src/app/db/models.py)
    - GlossaryTerm ORM model (backend/src/app/db/models.py)
    - SegmentFlag ORM model (backend/src/app/db/models.py)
    - FlagType / FlagSeverity enums (backend/src/app/db/models.py)
    - Job.glossary_id FK column (backend/src/app/db/models.py)
    - Segment.edited_text column (backend/src/app/db/models.py)
    - Segment.expansion_ratio column (backend/src/app/db/models.py)
    - Alembic migration 0002_phase2 (backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py)
    - Settings.expansion_ratio_thresholds field (backend/src/app/core/config.py)
    - Settings.expansion_thresholds_dict property (backend/src/app/core/config.py)
  affects:
    - backend/src/app/db/models.py
    - backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py
    - backend/src/app/core/config.py
tech_stack:
  added: []
  patterns:
    - native_enum=False on SAEnum for SQLite compat in unit tests
    - JSON column type (not JSONB) for cross-DB compat
    - field_validator for fail-fast startup validation of JSON env vars
    - @property on pydantic-settings Settings for derived config values
key_files:
  created:
    - backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py
    - backend/tests/test_phase2_models.py
    - backend/tests/test_phase2_config.py
  modified:
    - backend/src/app/db/models.py
    - backend/src/app/core/config.py
decisions:
  - "UniqueConstraint name uq_glossary_terms_source chosen (matches plan spec; existing file had uq_glossary_source_term — corrected)"
  - "Composite Index(segment_id, flag_type) in SegmentFlag.__table_args__ (existing file had only index=True on column — corrected to explicit named composite index)"
  - "Migration column name uses 'severity' not 'flag_severity' to match ORM model attribute"
  - "native_enum=False on both FlagType and FlagSeverity enums avoids PostgreSQL TYPE objects that Alembic downgrade cannot cleanly drop"
  - "expansion_ratio_thresholds stored as JSON str field rather than dict — pydantic-settings can load it from env var without custom type"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-24T19:45:00Z"
  tasks_completed: 3
  files_modified: 5
  tests_added: 22
requirements:
  - GLOS-01
  - GLOS-02
  - GLOS-03
  - GLOS-04
  - REV-02
  - REV-03
  - REV-05
  - LAYOUT-01
---

# Phase 02 Plan 02: DB Migration + Models Summary

**One-liner:** Phase 2 schema extension — Glossary/GlossaryTerm/SegmentFlag ORM models with Alembic migration and expansion_ratio_thresholds config, all SQLite-compatible via native_enum=False.

## What Was Built

Three tasks executed to extend the backend database schema for Phase 2 features:

**Task 1 (models.py):** Extended `backend/src/app/db/models.py` with:
- `FlagType` enum: `overflow`, `glossary_violation`, `placeholder_mismatch`, `llm_refusal`
- `FlagSeverity` enum: `info`, `warn`, `block`
- `Glossary` model: id (UUID), name, source_lang, target_lang, timestamps, terms relationship
- `GlossaryTerm` model: id, glossary_id FK (CASCADE), source_term, target_term, notes, created_at; `UniqueConstraint(glossary_id, source_term, name="uq_glossary_terms_source")`
- `SegmentFlag` model: id, segment_id FK (CASCADE), flag_type (SAEnum native_enum=False), severity (SAEnum native_enum=False), details (JSON), created_at; `Index("ix_segment_flags_segment_flag", "segment_id", "flag_type")`
- `Job.glossary_id`: String(36) FK `glossaries.id ON DELETE SET NULL`, nullable
- `Segment.edited_text`: Text, nullable
- `Segment.expansion_ratio`: Float, nullable
- `Segment.flags` relationship (lazy=selectin, back_populates="segment")
- Added `Float`, `Index` to SQLAlchemy imports

**Task 2 (migration):** Hand-wrote `0002_phase2_glossary_flags.py` with:
- `down_revision = "e0e8f781ec72"` (verified via `alembic heads`)
- Creates glossaries, glossary_terms, segment_flags tables
- Adds jobs.glossary_id FK (ON DELETE SET NULL), segments.edited_text, segments.expansion_ratio
- Both enum columns use `native_enum=False` (no PostgreSQL TYPE objects)
- Composite index `ix_segment_flags_segment_flag(segment_id, flag_type)`
- UniqueConstraint `uq_glossary_terms_source(glossary_id, source_term)`
- Clean `downgrade()` that drops FK constraints before columns/tables

**Task 3 (config.py):** Extended `backend/src/app/core/config.py` with:
- `expansion_ratio_thresholds: str` field (JSON string, default values for 6 language pairs)
- `@field_validator` for fail-fast startup JSON validation (T-02-02-01)
- `expansion_thresholds_dict: dict[str, float]` property

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| Task 1 | Phase 2 ORM models + TDD tests | 0961c58 |
| Task 2 | Alembic migration 0002_phase2 | 538b264 |
| Task 3 | Config expansion_ratio_thresholds + TDD tests | 044345d |

## Test Results

- 164 unit tests pass (142 pre-existing + 11 model tests + 11 config tests)
- 9 integration tests deselected (require Postgres/Redis)
- 3 untracked test files from parallel agents (test_csv_import.py, test_glossary_service.py, test_post_check.py, test_tbx_import.py) excluded — they depend on glossary_service which Plan 01 creates

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed UniqueConstraint name in GlossaryTerm**
- **Found during:** Task 1 inspection of existing models.py
- **Issue:** Existing file used `uq_glossary_source_term`; plan spec requires `uq_glossary_terms_source` to match migration
- **Fix:** Updated `__table_args__` UniqueConstraint name to `uq_glossary_terms_source`
- **Files modified:** `backend/src/app/db/models.py`
- **Commit:** 0961c58

**2. [Rule 1 - Bug] Added composite Index to SegmentFlag**
- **Found during:** Task 1 inspection of existing models.py
- **Issue:** Existing file used `index=True` on `segment_id` column (simple index); plan spec requires a named composite index `ix_segment_flags_segment_flag(segment_id, flag_type)` for GROUP BY query performance
- **Fix:** Added `__table_args__` with `Index("ix_segment_flags_segment_flag", "segment_id", "flag_type")`; removed `index=True` from column definition
- **Files modified:** `backend/src/app/db/models.py`
- **Commit:** 0961c58

**3. [Rule 2 - Missing] Added `Index` to SQLAlchemy imports**
- **Found during:** Task 1 — needed for composite Index in `__table_args__`
- **Fix:** Added `Index` to the `from sqlalchemy import ...` line
- **Files modified:** `backend/src/app/db/models.py`
- **Commit:** 0961c58

**4. [Rule 2 - Missing] Added `Field` and `json` imports to config.py**
- **Found during:** Task 3 — `Field(default=..., description=...)` and `json.loads()` required for new field and property
- **Fix:** Added `import json` and `Field` to pydantic import
- **Files modified:** `backend/src/app/core/config.py`
- **Commit:** 044345d

## Known Stubs

None — all Phase 2 schema elements are fully implemented. The migration creates real tables/columns; models are complete ORM definitions; config property parses and returns real values.

## Threat Flags

T-02-02-01 mitigated as planned: `@field_validator("expansion_ratio_thresholds")` validates JSON shape at `Settings()` construction, causing app startup to fail with a clear `ValidationError` if the env var is malformed. Tested by 3 dedicated test cases.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py | FOUND |
| backend/tests/test_phase2_models.py | FOUND |
| backend/tests/test_phase2_config.py | FOUND |
| .planning/phases/02-review-ux-glossary/02-02-SUMMARY.md | FOUND |
| Commit 0961c58 (models) | FOUND |
| Commit 538b264 (migration) | FOUND |
| Commit 044345d (config) | FOUND |
