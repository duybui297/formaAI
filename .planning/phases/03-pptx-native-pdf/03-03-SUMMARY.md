---
phase: "03-pptx-native-pdf"
plan: "03"
subsystem: "pipeline/pptx"
tags: ["pptx", "extractor", "reassembler", "smartart", "overflow", "python-pptx"]
dependency_graph:
  requires:
    - "03-01"  # FlagType enum extension (smartart, multi_column_degraded)
    - "segment.py"  # Segment.from_text, make_segment_id
    - "pipeline/docx/"  # analog pattern reference
  provides:
    - "pipeline/pptx/__init__.py"
    - "pipeline/pptx/smartart.py"
    - "pipeline/pptx/extractor.py"
    - "pipeline/pptx/reassembler.py"
  affects:
    - "workers/translate_worker.py"  # will dispatch to extract_pptx_segments in plan 05
tech_stack:
  added:
    - "python-pptx 1.0.2 — MSO_SHAPE_TYPE, MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE"
  patterns:
    - "run-merge write-back (mirrors DOCX reassembler — never paragraph.text=value)"
    - "mutable seq=[0] counter pattern for shared state across nested generators"
    - "structural_position-keyed lookup dict (replaces DOCX sequential counter matching)"
    - "char-ratio overflow proxy (avoids headless rendering engine dependency)"
key_files:
  created:
    - backend/src/app/pipeline/pptx/__init__.py
    - backend/src/app/pipeline/pptx/smartart.py
    - backend/src/app/pipeline/pptx/extractor.py
    - backend/src/app/pipeline/pptx/reassembler.py
  modified: []
decisions:
  - "D-03-01: SmartArt structural_position ends in .smartart; write-back silently skipped in reassembler"
  - "D-03-02: auto-fit (MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE) applied only when char_ratio shrink_factor >= 0.7; otherwise overflow=True"
  - "Tuple return from reassemble_pptx — (Presentation, list[dict]) — no monkey-patch pattern"
  - "Mutable seq=[0] list pattern enables seq sharing across recursive generator helpers"
metrics:
  duration_minutes: 3
  completed_date: "2026-04-25"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 0
---

# Phase 03 Plan 03: PPTX Pipeline Summary

**One-liner:** PPTX pipeline with group-recursive extractor, run-merge reassembler, SmartArt detection/skip, and char-ratio overflow detection using python-pptx 1.0.2.

## What Was Built

Four files implementing the complete PPTX translation pipeline:

1. **`pipeline/pptx/__init__.py`** — empty package marker (mirrors `docx/__init__.py`)

2. **`pipeline/pptx/smartart.py`** — SmartArt detection and text extraction:
   - `is_smartart(shape)` — primary check via `MSO_SHAPE_TYPE.IGX_GRAPHIC`, fallback via XML `graphicData` URI; defensive `try/except` on all lxml access
   - `extract_smartart_text(shape)` — best-effort `//a:t` text extraction; returns `""` on any exception

3. **`pipeline/pptx/extractor.py`** — Full presentation walker:
   - `extract_pptx_segments(prs, job_id)` — top-level function; walk order: master slides (deduplicated by seg ID) → body shapes → speaker notes
   - `walk_shape_tree()` — recursive GROUP traversal; critical check order: GROUP first, then `is_smartart()`, then TABLE, then `has_text_frame`
   - `walk_text_frame()`, `walk_table()` — paragraph-level Segment emission
   - `_extract_notes_segments()` — speaker notes via `notes_slide.notes_text_frame`
   - `_extract_master_segments()` — master text deduplicated by `seg.id` set
   - structural_position schema: `slide.N.shape.M.tf.0.para.K` / `slide.N.notes.para.K` / `slide.N.shape.M.table.row.R.col.C.para.K` / `master.N.shape.M.para.K` / `slide.N.shape.M.group.shape.P.tf.0.para.K` / `slide.N.shape.M.smartart`

4. **`pipeline/pptx/reassembler.py`** — Reassembler with run-merge write-back:
   - `reassemble_pptx(prs, segments, translated_map)` — returns `tuple[Presentation, list[dict]]`; master → body shapes → notes write-back order
   - `detect_pptx_overflow(shape, source_text, translated_text)` — char-ratio proxy; `auto_adjusted=True` when `shrink_factor >= 0.7` (applies `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE`); `overflow=True` when `shrink_factor < 0.7`
   - `_write_paragraph_runs()` — run-merge write-back; zero-run guard via `paragraph.add_run()`
   - `_write_back_shapes()` — recursive GROUP + SmartArt skip + TABLE + text frame
   - Returns per-segment overflow dicts: `{segment_id, overflow, auto_adjusted, char_ratio}`

## Deviations from Plan

None — plan executed exactly as written.

## Critical Design Invariants (for downstream agents)

| Invariant | File | Rule |
|-----------|------|------|
| `is_smartart()` checked BEFORE `has_text_frame` | extractor.py | SmartArt has `has_text_frame=False`; wrong order silently skips it |
| NEVER `paragraph.text = value` | reassembler.py | Destroys `<p:rPr>` run formatting; always use run-merge |
| `reassemble_pptx` returns tuple | reassembler.py | `(prs, overflow_results)` — no `_phase3_overflow_results` monkey-patch |
| SmartArt write-back silently skipped | reassembler.py | D-03-01; segment exists in review UI, XML not modified |
| auto-fit only when shrink_factor >= 0.7 | reassembler.py | D-03-02; prevents tiny-font on VN/JA expansions |

## Self-Check: PASSED

Files verified:
- FOUND: backend/src/app/pipeline/pptx/__init__.py
- FOUND: backend/src/app/pipeline/pptx/smartart.py
- FOUND: backend/src/app/pipeline/pptx/extractor.py
- FOUND: backend/src/app/pipeline/pptx/reassembler.py

Commits verified:
- FOUND: 9507771 (feat(pptx): add pptx package marker and smartart detection helper)
- FOUND: 782e446 (feat(pptx): implement PPTX segment extractor)
- FOUND: 844acd8 (feat(pptx): implement PPTX reassembler with run-merge write-back)
