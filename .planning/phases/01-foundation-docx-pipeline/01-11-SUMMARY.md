---
phase: "01"
plan: "11"
subsystem: db-migration, integration-tests
tags: [alembic, migration, integration-test, docx, llm, dashscope, lang-pairs]
dependency_graph:
  requires: ["01-02", "01-03", "01-04", "01-06a"]
  provides: [initial-schema-migration, integration-test-suite]
  affects: [db, tests]
tech_stack:
  added: []
  patterns: [alembic-string-pk, pytest-mark-integration, docx-round-trip-test, skip-on-missing-key]
key_files:
  created:
    - backend/src/app/db/migrations/versions/001_initial_schema.py
    - backend/tests/integration/__init__.py
    - backend/tests/integration/test_healthcheck.py
    - backend/tests/integration/test_docx_roundtrip.py
    - backend/tests/integration/test_lang_pairs.py
  modified: []
decisions:
  - "Migration uses sa.String(36) for Job.id and Segment.job_id FK, matching Plan 02 ORM — keeps unit tests SQLite-compatible (W8)"
  - "error_msg column is TEXT not JSONB — aligns with Plan 02 ORM Mapped[str | None] mapped_column(Text) (W8)"
  - "Integration tests marked @pytest.mark.integration; skip in CI by deselecting with -m 'not integration'"
  - "healthcheck tests skip via module-scoped pytest.skip() when DASHSCOPE_API_KEY absent — clean CI behavior, not test failure"
  - "DOCX round-trip test builds document programmatically (no golden fixture dependency) — deterministic and portable"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-24"
  tasks_completed: 2
  files_created: 5
  files_modified: 0
---

# Phase 1 Plan 11: Migrations + Integration Tests Summary

Alembic first migration (jobs + segments tables aligned with Plan 02 ORM) plus an
integration test suite covering DashScope health, DOCX round-trip, and language pair coverage.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Alembic first migration (jobs + segments) | `102305a` | `backend/src/app/db/migrations/versions/001_initial_schema.py` |
| 2 | Integration tests (INFRA-01/02, DOCX-01, LANG-02) | `14eabbc` | `backend/tests/integration/` (4 files) |

## What Was Built

### Task 1 — Alembic Migration

`backend/src/app/db/migrations/versions/001_initial_schema.py` — the project's first Alembic
revision creates both `jobs` and `segments` tables from scratch:

- `jobs.id`: `sa.String(36)` — matches Plan 02 ORM `mapped_column(String(36))`. No `postgresql.UUID` import — keeps unit test SQLite-compat (W8).
- `segments.id`: `sa.String(16)` — 16-char SHA256 hex (D-06 deterministic ID).
- `segments.job_id` FK: `sa.String(36)` with `ondelete="CASCADE"` — matching jobs.id type.
- `error_msg`: `sa.Text` — **not JSONB**. Plan 02 ORM uses `Mapped[str | None] = mapped_column(Text)` (W8).
- No `current_batch` or `last_message` columns — not present in Plan 02 model (W8).
- Indexes: `ix_jobs_status`, `ix_jobs_created_at`, `ix_segments_job_id_seq` (composite).
- `downgrade()` drops `segments` before `jobs` (FK order safety).

Running `alembic upgrade head` against a fresh PostgreSQL database produces both tables
with correct column types, constraints, and indexes.

### Task 2 — Integration Test Suite

9 tests across 3 files:

**`test_healthcheck.py`** (4 tests — require `DASHSCOPE_API_KEY`):
- `test_dashscope_reachable_and_translates` — INFRA-01: VN→EN probe, asserts non-empty + hello/world keyword
- `test_terminology_respected_vn_en` — INFRA-02: brand name preserved VN→EN via terminology param
- `test_terminology_respected_ja_en` — INFRA-02: brand name preserved JA→EN
- `test_auto_detect_source_language` — D-16: `source_lang="auto"` works for JA input

**`test_docx_roundtrip.py`** (2 tests — no network):
- `test_docx_roundtrip_structure_preserved` — DOCX-01: programmatic DOCX with heading + bold para + 2×2 table; extract → mock translate → reassemble → reload; heading and table cell contain `[TR]` prefix
- `test_extract_segments_does_not_miss_table_cells` — CORE-01: table cells appear in extracted segment list (not missed by `doc.paragraphs` anti-pattern)

**`test_lang_pairs.py`** (3 tests — no network):
- `test_required_lang_pairs_in_supported_list` — LANG-02: all 8 required pair codes present
- `test_auto_detect_in_source_options` — LANG-01: "auto" in codes
- `test_priority_languages_present` — UI-SPEC: vi, en, ja, zh all present

## Verification Results

```
Integration test collection:   9 tests discovered
Lang pair tests (no network):  3 passed
DOCX round-trip (no network):  2 passed
Healthcheck (no key):          4 skipped (not failed)
Unit tests (-m "not integration"): 131 passed, 9 deselected
Coverage: 80.32% (unchanged — integration tests deselected during unit run)
W8 check: no postgresql.UUID dialect import in migration
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected `seg.text` to `seg.source_text` in round-trip test**
- **Found during:** Task 2 implementation
- **Issue:** Plan context used `seg.text` for the translated_texts dict comprehension, but the `Segment` dataclass (segment.py) uses `source_text` as the attribute name. Using `seg.text` would cause `AttributeError` at runtime.
- **Fix:** Used `{seg.id: f"[TR] {seg.source_text}" for seg in segments}` matching actual dataclass field.
- **Files modified:** `backend/tests/integration/test_docx_roundtrip.py`
- **Commit:** `14eabbc` (included in Task 2 commit)

None other — plan executed as written.

## Known Stubs

None. Migration and tests are fully wired.

## Threat Flags

No new security surface introduced. Migration is internal DDL; integration tests
are local-only (T-01-11-02 mitigated: no print() of raw API responses, key from env).

## Self-Check: PASSED

- `backend/src/app/db/migrations/versions/001_initial_schema.py` exists
- `backend/tests/integration/__init__.py` exists
- `backend/tests/integration/test_healthcheck.py` exists
- `backend/tests/integration/test_docx_roundtrip.py` exists
- `backend/tests/integration/test_lang_pairs.py` exists
- Commits `102305a` and `14eabbc` exist in git log
- 131 unit tests pass; 9 integration tests collected; 5 pass, 4 skip without key
