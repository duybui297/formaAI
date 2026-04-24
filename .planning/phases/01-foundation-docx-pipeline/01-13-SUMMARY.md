---
phase: 01-foundation-docx-pipeline
plan: "13"
subsystem: docx-pipeline
tags: [tdd, format-preservation, run-level, gap-closure, G2]
dependency_graph:
  requires: []
  provides:
    - extract_run_segments (extractor.py)
    - write_translated_run (reassembler.py)
    - reassemble_docx_runs (reassembler.py)
  affects:
    - translate_worker.py (DOCX branch now uses run-level path)
tech_stack:
  added: []
  patterns:
    - per-run segment extraction with format-boundary splitting
    - walk-order counter-matching for reassembly (no structural_position string parsing)
    - T-13-01 bounds validation before run array access
    - T-13-02 color attribute access wrapped in try/except
key_files:
  created: []
  modified:
    - backend/src/app/pipeline/segment.py
    - backend/src/app/pipeline/docx/extractor.py
    - backend/src/app/pipeline/docx/reassembler.py
    - backend/src/app/workers/translate_worker.py
    - backend/tests/pipeline/test_docx_extractor.py
decisions:
  - "Per-run segment extraction chosen over inline format markers (deferred to Phase 2+)"
  - "Consecutive same-format runs merged into one Segment to cap DashScope call volume (~15-45% increase vs paragraph-level)"
  - "para_seq counter extracted from structural_position prefix in reassemble_docx_runs — avoids full string parsing while remaining walk-order correct"
  - "Old extract_segments/write_translated_paragraph/reassemble_docx preserved for backward compat"
metrics:
  duration: "~3 minutes"
  completed: "2026-04-24"
  tasks_completed: 3
  files_modified: 5
  tests_added: 5
  tests_total: 48
---

# Phase 1 Plan 13: Per-run Format Preservation in DOCX Reassembly Summary

**One-liner:** Per-run segment extraction with format-boundary splitting and run-slot write-back, closing UAT gap G2 (bold/italic/underline destroyed on multi-format paragraphs).

## What Was Built

Closed UAT gap G2: the previous run-merge strategy (`runs[0].text = translated; runs[1:].text = ""`) collapsed all formatting in a multi-format paragraph to the first run's style. A paragraph with bold + plain + italic runs became entirely bold after translation.

**Root cause fixed:** Segment extraction was paragraph-level (one `Segment` per paragraph). Reassembly wrote the full translated text into `runs[0]` and blanked the rest, losing all per-run `<w:rPr>` diversity.

**Strategy implemented:** Per-run segment extraction — one `Segment` per *run group* (consecutive runs with identical formatting merged to reduce LLM call count). Each segment carries `run_index` (first run in the group) and `run_group_size`. Reassembly writes translated text back into the original run slot by `run_index`, leaving all other runs' `<w:rPr>` untouched.

## Changes

### `segment.py`
Added two optional fields with defaults (fully backward-compatible):
- `run_index: int | None = None` — which run slot in the paragraph this segment maps to
- `run_group_size: int = 1` — how many consecutive same-format runs this segment covers

### `extractor.py`
Added:
- `_run_format_key(run)` — returns `(bold, italic, underline, color, font_name, font_size)` tuple; color access wrapped in try/except (T-13-02)
- `extract_run_segments(doc, job_id)` — splits paragraphs at format-change boundaries; merges consecutive same-format runs; emits `Segment` with `run_index`/`run_group_size`

Old `extract_segments()` preserved unchanged.

### `reassembler.py`
Added:
- `write_translated_run(paragraph, seg, translated_text)` — writes to the exact run slot; validates `run_index < len(runs)` before array access (T-13-01); blanks merged-group tail runs without removing `<w:r>` elements
- `reassemble_docx_runs(doc, segments, translated_texts)` — walk-order counter-matching (same pattern as `reassemble_docx()`); groups segments by `para_seq` extracted from `structural_position` prefix; calls `write_translated_run` per segment

Old `write_translated_paragraph()` and `reassemble_docx()` preserved unchanged.

### `translate_worker.py`
DOCX branch now calls `extract_run_segments()` instead of `extract_segments()` and `reassemble_docx_runs()` instead of `reassemble_docx()`. Old imports kept for other callers.

## TDD Cycle

**RED (`f94e030`):** 5 failing tests added — `ImportError` for `extract_run_segments`, `write_translated_run`, `reassemble_docx_runs`.

**GREEN (`e68fdf6`):** All 5 new tests pass + 0 regressions on existing 16 pipeline tests (48 total pass).

**REFACTOR:** Not required — implementation is clean and within function-length guidelines.

## Test Coverage

| Test | Validates |
|------|-----------|
| `test_extract_run_segments_multi_format_paragraph` | 3-run doc → 3 segments with correct run_index |
| `test_extract_run_segments_uniform_format_merges` | 3 same-format runs → 1 segment, run_group_size=3 |
| `test_write_translated_run_preserves_formatting` | Writing to run_index=2 leaves run_index=0 untouched |
| `test_write_translated_run_run_index_out_of_bounds_skips` | T-13-01: no IndexError on run_index=99 |
| `test_reassemble_docx_runs_round_trip` | Full extract+reassemble preserves bold/italic/plain per run |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes on `reassemble_docx_runs` counter logic

The plan specified a `para_seq` counter walk with segment grouping. The implementation extracts `para_seq` from `structural_position` prefix (format: `"{loc_tag}.{para_seq}.run{n}"`) rather than maintaining a separate parallel counter. This is semantically equivalent — the structural_position was assigned by the same `para_seq` counter in `extract_run_segments()` — and is more robust against off-by-one errors from the empty-paragraph handling divergence between the two walkers.

Empty paragraphs are always skipped in `reassemble_docx_runs` (they produce no segments in `extract_run_segments`), so `para_seq` lookup correctly returns an empty list for those, leaving them untouched.

## Cost Impact (documented)

Per-run segmentation increases DashScope call volume relative to paragraph-level extraction:
- **Worst case:** every run has distinct formatting → one Segment per run
- **Typical case (ICOM_Proposal_JP.docx):** estimated 400-500 run-level segments vs 346 paragraph-level (~15-45% more calls)
- **Mitigation:** same-format run merging keeps call count close to paragraph-level for uniform text
- **Pace budget:** at DASHSCOPE_PACE_SECONDS=1.2 default, ~10 min wall-clock for 500-segment doc (vs ~7 min before); acceptable for PoC

Accepted trade-off per D-13: format fidelity over raw throughput.

## Known Stubs

None.

## Threat Flags

No new security surface introduced. `extract_run_segments` reads the same DOCX files as `extract_segments`; no new file paths, network endpoints, or auth paths.

## Self-Check: PASSED

- `backend/src/app/pipeline/segment.py` — `run_index`/`run_group_size` fields present
- `backend/src/app/pipeline/docx/extractor.py` — `_run_format_key` and `extract_run_segments` present
- `backend/src/app/pipeline/docx/reassembler.py` — `write_translated_run` and `reassemble_docx_runs` present
- `backend/src/app/workers/translate_worker.py` — `extract_run_segments` and `reassemble_docx_runs` at call sites
- RED commit `f94e030` confirmed
- GREEN commit `e68fdf6` confirmed
- 48 pipeline tests pass, 0 regressions
