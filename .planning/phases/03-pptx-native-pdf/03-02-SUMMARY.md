---
phase: "03-pptx-native-pdf"
plan: "02"
subsystem: "test-scaffold"
tags: ["tdd", "pptx", "pdf", "frontend", "red-state"]
dependency_graph:
  requires:
    - "03-01"
  provides:
    - "test contracts for plans 03-03 and 03-04"
  affects:
    - "backend/tests/pipeline/test_pptx_extractor.py"
    - "backend/tests/pipeline/test_pptx_reassembler.py"
    - "backend/tests/pipeline/test_pdf_extractor.py"
    - "backend/tests/pipeline/test_pdf_reassembler.py"
    - "backend/tests/pipeline/test_pdf_columns.py"
    - "frontend/src/__tests__/formatBreadcrumb.test.ts"
    - "frontend/src/__tests__/FlagBadge.test.tsx"
tech_stack:
  added: []
  patterns:
    - "TDD RED-first: programmatic fixtures via python-pptx/pymupdf (no binary commits)"
    - "lxml OOXML injection for GroupShape fixtures (no python-pptx public API)"
    - "Vitest import-level RED for frontend (module not found = correct state)"
key_files:
  created:
    - "backend/tests/pipeline/test_pptx_extractor.py"
    - "backend/tests/pipeline/test_pptx_reassembler.py"
    - "backend/tests/pipeline/test_pdf_extractor.py"
    - "backend/tests/pipeline/test_pdf_reassembler.py"
    - "backend/tests/pipeline/test_pdf_columns.py"
    - "frontend/src/__tests__/formatBreadcrumb.test.ts"
  modified:
    - "frontend/src/__tests__/FlagBadge.test.tsx"
decisions:
  - "GroupShape fixture uses lxml OOXML injection — python-pptx has no public API for creating grpSp elements; direct XML injection is the only correct approach"
  - "FlagBadge tests use @ts-expect-error for smartart/multi_column_degraded — FlagType union not yet extended; suppression is intentional and self-documenting"
  - "detect_pptx_overflow accepts shape + source + translated text (char ratio proxy) — real pixel measurement requires font metrics unavailable without rendering; char ratio is sufficient for unit tests"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-04-25"
  tasks_completed: 3
  tasks_total: 3
  files_created: 6
  files_modified: 1
---

# Phase 03 Plan 02: TDD Test Scaffold (RED State) Summary

TDD RED scaffold for PPTX extractor/reassembler and native PDF extractor/reassembler/columns — 27 backend tests + 2 frontend test files, all failing on ImportError until Wave 2 plans implement the modules.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | PPTX test files (TDD RED) | 74ca5da | test_pptx_extractor.py, test_pptx_reassembler.py |
| 2 | PDF test files (TDD RED) | bf0c9df | test_pdf_extractor.py, test_pdf_reassembler.py, test_pdf_columns.py |
| 3 | Frontend test files (TDD RED) | f449540 | formatBreadcrumb.test.ts, FlagBadge.test.tsx |

## What Was Built

### Backend — 5 test files, 27 test functions

**test_pptx_extractor.py** (PPTX-01..04, PPTX-02):
- `test_extract_pptx_segments_text_box_produces_segment` — PPTX-01
- `test_extract_pptx_segments_notes_produces_segment` — PPTX-01
- `test_extract_pptx_segments_table_cell_produces_segment` — PPTX-01
- `test_extract_pptx_segments_structural_position_unique` — I4 invariant
- `test_walk_shape_tree_group_recursion_finds_nested_text` — PPTX-04
- `test_smartart_flagged_not_silently_skipped` — PPTX-02
- `test_non_smartart_shape_not_flagged` — PPTX-02
- `test_empty_pptx_returns_no_segments` — adversarial
- `test_extract_pptx_segments_bullet_list_produces_segment` — PPTX-01 bullets

**test_pptx_reassembler.py** (PPTX-03, LAYOUT-03):
- `test_reassemble_pptx_identity_round_trip`
- `test_overflow_detection_flags_segment` — PPTX-03
- `test_autofit_applied_when_shrink_gte_0_7` — PPTX-03 + LAYOUT-03
- `test_smartart_write_back_skipped` — PPTX-02 write-back guard
- `test_reassemble_pptx_bullet_paragraph_preserves_bullet_format`

**test_pdf_columns.py** (PDF-04):
- `test_cluster_columns_empty_returns_single_group`
- `test_cluster_columns_single_col_returns_one_group`
- `test_cluster_columns_two_col_returns_two_groups`
- `test_cluster_columns_three_col_returns_degraded`
- `test_cluster_columns_two_col_reading_order`

**test_pdf_extractor.py** (PDF-01):
- `test_extract_pdf_segments_single_col`
- `test_extract_pdf_segments_structural_position_has_page`
- `test_extract_pdf_segments_uniqueness`
- `test_extract_pdf_segments_image_only_returns_empty`

**test_pdf_reassembler.py** (PDF-02, PDF-03, LAYOUT-02, LAYOUT-03):
- `test_round_trip_pdf_redact_reinsert`
- `test_pdf_images_preserved_through_redaction`
- `test_overflow_db_flag_persisted` — LAYOUT-02
- `test_auto_adjusted_metadata_in_details` — LAYOUT-03

### Frontend — 2 test files

**formatBreadcrumb.test.ts** (new, RED):
- 9 test cases covering PPTX body/notes/master/smartart, PDF 2-col/degraded, fallback
- RED: `@/lib/formatBreadcrumb` module does not exist yet (plan 06 creates it)

**FlagBadge.test.tsx** (extended):
- Added 4 real test cases: smartart (orange), multi_column_degraded (slate), overflow warning, overflow auto-adjusted info
- Preserved 5 existing `it.todo()` stubs
- RED on smartart/multi_column_degraded: FlagType union not yet extended

## RED State Verification

All backend tests fail with `ModuleNotFoundError: No module named 'app.pipeline.pptx'` or `'app.pipeline.pdf'` — correct TDD RED state. Plans 03-03 (PPTX) and 03-04 (PDF) will make them GREEN.

Frontend formatBreadcrumb.test.ts fails with module resolution error — correct RED state. Plan 03-06 creates the module.

## Deviations from Plan

### Auto-fixed Issues

None.

### Notable Implementation Choices

**1. GroupShape fixture via lxml OOXML injection**
- The plan specified using lxml OOXML injection for PPTX-04 (group recursion) fixtures
- python-pptx has no public API to create `<p:grpSp>` elements
- Implemented exactly as specified: raw XML with proper namespace declarations injected into `slide.shapes._spTree`

**2. pytest-cov installed as deviation**
- Found during Task 1: the worktree's venv did not have `pytest-cov` installed but pyproject.toml `addopts` requires it
- Rule 3 (auto-fix blocking issue): installed `pytest-cov` to unblock test collection
- No code changes, no plan impact

**3. FlagBadge test uses `@ts-expect-error` directives**
- The plan specified tests for `smartart` and `multi_column_degraded` flag types
- FlagType union in `types.ts` does not yet include these values
- Used `@ts-expect-error` with descriptive comments to allow the test file to compile while correctly documenting that the type extension is planned for 03-05/03-06
- This is the correct RED state: tests reference future contract, fail at runtime

## Known Stubs

None — this plan creates only test files. No production stubs introduced.

## Threat Flags

None — test files only. No new network endpoints, auth paths, or schema changes.

## Self-Check

### Commits exist
- 74ca5da: `test(phase-03): add PPTX extractor and reassembler TDD RED tests`
- bf0c9df: `test(phase-03): add PDF extractor, reassembler, and columns TDD RED tests`
- f449540: `test(phase-03): add formatBreadcrumb RED tests and extend FlagBadge with Phase 3 cases`

### Files exist
- backend/tests/pipeline/test_pptx_extractor.py — FOUND
- backend/tests/pipeline/test_pptx_reassembler.py — FOUND
- backend/tests/pipeline/test_pdf_extractor.py — FOUND
- backend/tests/pipeline/test_pdf_reassembler.py — FOUND
- backend/tests/pipeline/test_pdf_columns.py — FOUND
- frontend/src/__tests__/formatBreadcrumb.test.ts — FOUND
- frontend/src/__tests__/FlagBadge.test.tsx — FOUND (extended)

### Test collection
- 27 backend test IDs collected successfully (`pytest --co -q`)
- All backend tests RED (ImportError on app.pipeline.pptx/pdf) as expected

## Self-Check: PASSED
