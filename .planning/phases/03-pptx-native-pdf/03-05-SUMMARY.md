---
phase: "03-pptx-native-pdf"
plan: "05"
subsystem: worker
tags: [worker, dispatch, pptx, pdf, segment-flags]
dependency_graph:
  requires: ["03-03", "03-04"]
  provides: ["worker-pptx-dispatch", "worker-pdf-dispatch", "segment-flag-pptx", "segment-flag-pdf"]
  affects: ["translate_worker", "SegmentFlag persistence"]
tech_stack:
  added: []
  patterns: ["match/case format dispatch", "lazy pipeline imports", "SegmentFlag out-param accumulation"]
key_files:
  modified:
    - backend/src/app/workers/translate_worker.py
decisions:
  - "Lazy pipeline imports inside each match/case branch (noqa PLC0415) to avoid import-time side effects and keep cold-start cost minimal"
  - "DOCX path wrapped in case docx: unchanged logic — not replaced, just scoped"
  - "SegmentFlag persistence done after reassemble completes (not per-batch) for pptx/pdf to keep batch loop format-agnostic"
  - "PDF multi_column_degraded detection uses absence of 'col' in structural_position — mirrors extractor L3 convention"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-25T19:57:25Z"
  tasks_completed: 1
  files_modified: 1
---

# Phase 3 Plan 05: Worker Dispatch Extension Summary

Single-file modification extending `translate_worker.py` to route PPTX and PDF jobs through their respective format pipelines, with SegmentFlag persistence for all three new flag types.

## What Was Built

Added match/case dispatch to `_run_translation` at two sites:

**STAGE 1 (parse):** `match job.input_format` with branches:
- `case "docx"`: existing logic unchanged, wrapped in branch with `_format_ctx = {"type": "docx", "doc": _doc}`
- `case "pptx"`: lazy-imports `PPTXPresentation` + `extract_pptx_segments`, opens presentation, extracts segments
- `case "pdf"`: lazy-imports `pymupdf` + `extract_pdf_segments`, opens document, extracts segments
- `case _`: raises `ValueError(f"Unsupported format: {job.input_format!r}")`

**STAGE 4 (reassemble):** `match _format_ctx["type"]` with branches:
- `case "docx"`: calls existing `reassemble_docx_runs`, saves `.docx`
- `case "pptx"`: calls `reassemble_pptx` (returns tuple), saves `.pptx`; persists overflow + smartart SegmentFlags
- `case "pdf"`: calls `reassemble_pdf` (out-param pattern), saves `.pdf`; persists overflow + multi_column_degraded SegmentFlags

**SegmentFlag types persisted:**

| FlagType | Severity | Trigger |
|----------|----------|---------|
| `overflow` (auto_adjusted=False) | warn | PPTX shrink < 0.7; PDF spare_height < 0 at scale_low=0.7 |
| `overflow` (auto_adjusted=True) | info | PPTX auto-fit applied; PDF scaled within 0.7 threshold |
| `smartart` | warn | Segment structural_position ends in `.smartart` |
| `multi_column_degraded` | info | PDF segment structural_position has no `col` component (3+ col page) |

## Deviations from Plan

None — plan executed exactly as written.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add format dispatch and SegmentFlag persistence for PPTX and PDF | 07620be | backend/src/app/workers/translate_worker.py |

## Verification

```
75 passed in 3.44s
```

All 75 pipeline tests pass. DOCX path regression check: `case "docx"` wraps original logic unchanged, `reassemble_docx_runs` called with same signature.

Acceptance criteria met:
- `case "pptx":` present (lines 287, 470)
- `case "pdf":` present (lines 300, 523)
- `FlagType.smartart` present (line 515)
- `FlagType.multi_column_degraded` present (line 579)
- `extract_pptx_segments` present (lines 289, 291)
- `extract_pdf_segments` present (lines 302, 304)
- `reassemble_pdf` called with `scale_low=0.7` internally (passed via out-param pattern)
- All existing tests pass

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. The match/case addition is purely internal worker logic; T-03-01 and T-03-02 are mitigated by the existing outer `except Exception` handler (lines 601-621) which catches all format-related errors and transitions the job to `failed`.

## Self-Check: PASSED

- `backend/src/app/workers/translate_worker.py` exists and contains all required dispatch patterns
- Commit `07620be` confirmed in git log
- No unexpected file deletions
