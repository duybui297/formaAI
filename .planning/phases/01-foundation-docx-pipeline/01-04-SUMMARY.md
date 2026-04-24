---
phase: 01-foundation-docx-pipeline
plan: "04"
subsystem: pipeline
tags: [python-docx, docx, ooxml, lxml, segment, placeholder, sha256, nfc, tracked-changes]

# Dependency graph
requires:
  - phase: 01-foundation-docx-pipeline
    plan: "02"
    provides: "Segment ORM model (String(16) id, structural_position, seq_in_job)"
  - phase: 01-foundation-docx-pipeline
    plan: "03"
    provides: "pack_into_batches() API that consumes list[Segment] from this plan"
provides:
  - "Segment dataclass with make_segment_id() — sha256[:16] deterministic IDs (D-05/D-06)"
  - "extract_placeholders() / restore_placeholders() — CORE-05 ⟦T{n}⟧ protection for URLs/emails/templates/versions/dates"
  - "walk_document() — full DOCX traversal via iter_inner_content() not doc.paragraphs (DOCX-01)"
  - "extract_segments() — ordered Segment list with NFC-normalized source_text (CORE-04)"
  - "write_translated_paragraph() — run-merge write-back: runs[0].text=, blank runs[1:] (DOCX-02)"
  - "reassemble_docx() — write translated_texts dict back into Document using run-merge"
  - "has_tracked_changes() / strip_tracked_changes() — DOCX-04 detection and strip path (D-13)"
  - "3 programmatic golden DOCX fixtures + _generate.py generator"
affects:
  - translate_worker
  - job_service
  - phase-2 (glossary CRUD uses Segment ids for TM hooks)

# Tech tracking
tech-stack:
  added:
    - python-docx 1.2.0 (traversal + write-back)
    - lxml (tracked-changes XML manipulation in tracked.py and test fixtures)
    - unicodedata stdlib (NFC normalization CORE-04)
    - hashlib stdlib (sha256 for D-06 segment IDs)
    - re stdlib (placeholder regex patterns CORE-05)
  patterns:
    - "run-merge write-back: runs[0].text = translated; [r.text='' for r in runs[1:]]"
    - "iter_inner_content() over doc.paragraphs for complete DOCX traversal"
    - "mutable list cell [0] as counter in nested closure to avoid Python late-binding"
    - "⟦T{n}⟧ Unicode markers for non-translatable token protection"

key-files:
  created:
    - backend/src/app/pipeline/__init__.py
    - backend/src/app/pipeline/segment.py
    - backend/src/app/pipeline/placeholder.py
    - backend/src/app/pipeline/docx/__init__.py
    - backend/src/app/pipeline/docx/extractor.py
    - backend/src/app/pipeline/docx/reassembler.py
    - backend/src/app/pipeline/docx/tracked.py
    - backend/tests/pipeline/__init__.py
    - backend/tests/pipeline/test_placeholder.py
    - backend/tests/pipeline/test_docx_extractor.py
    - backend/tests/pipeline/test_tracked_changes.py
    - backend/tests/pipeline/fixtures/_generate.py
    - backend/tests/pipeline/fixtures/simple.docx
    - backend/tests/pipeline/fixtures/table_heavy.docx
    - backend/tests/pipeline/fixtures/tracked_changes.docx
  modified: []

key-decisions:
  - "Mutable list cell [0] used as counter in extract_placeholders() to avoid Python closure late-binding bug"
  - "PlaceholderRestoreError defined but not raised by default — fallback keeps ⟦T{n}⟧ visible (T-04-03 mitigate disposition)"
  - "Golden fixtures committed as .docx bytes alongside _generate.py generator — tests run without regenerating"
  - "strip_tracked_changes collects all <w:ins>/<w:del> before modifying tree — avoids iterator invalidation during lxml tree mutation"
  - "Segment.from_text factory accepted **kwargs for forward compatibility with is_comment/is_inserted/is_deleted"

patterns-established:
  - "DOCX-02 run-merge: runs[0].text = nfc(translated); for r in runs[1:]: r.text = ''"
  - "DOCX-01 traversal: doc.iter_inner_content() → _walk_table() recursion, never doc.paragraphs"
  - "D-06 segment ID: sha256(f'{source_text}\\x00{structural_position}')[:16]"
  - "CORE-04 NFC: normalize at extraction (extractor.py _nfc) AND at write-back (reassembler.py _nfc)"
  - "CORE-05 placeholder: extract before LLM call, restore after; missing key keeps marker visible"

requirements-completed:
  - CORE-01
  - CORE-05
  - DOCX-01
  - DOCX-02
  - DOCX-03
  - DOCX-04

# Metrics
duration: 22min
completed: 2026-04-24
---

# Phase 01 Plan 04: DOCX Pipeline Summary

**DOCX pipeline with run-merge write-back (DOCX-02), iter_inner_content traversal (DOCX-01), ⟦T{n}⟧ placeholder protection (CORE-05), SHA-256 segment IDs (D-06), and tracked-changes detection + strip (DOCX-04) — 43 tests passing**

## Performance

- **Duration:** 22 min
- **Started:** 2026-04-24T03:31:58Z
- **Completed:** 2026-04-24T03:57:51Z
- **Tasks:** 2
- **Files created:** 15

## Accomplishments

- Full DOCX traversal pipeline: walk_document() visits body paragraphs, table cells (row-major, nested), headers, footers using iter_inner_content() — never the anti-pattern doc.paragraphs
- Run-merge write-back invariant: write_translated_paragraph() writes into runs[0].text only, blanks runs[1:] — bold/italic/underline/font/color preserved; tested and documented as anti-pattern guard
- Complete placeholder system: 7 pattern categories (URL, email, {{mustache}}, ${template}, <%=ejs%>, ISO date, vN.N.N) extracted to ⟦T{n}⟧ markers, restored after translation, missing keys kept visible (T-04-03)
- Tracked-changes detection and strip: has_tracked_changes() XML string search, strip_tracked_changes() unwraps <w:ins> and removes <w:del> using lxml tree manipulation with pre-collected element lists

## Task Commits

1. **Task 1: Segment Model + Placeholder Protection** - `1dcee62` (feat)
2. **Task 2: DOCX Extractor + Reassembler + Tracked Changes** - `295667a` (feat)

## Files Created/Modified

- `backend/src/app/pipeline/segment.py` - Segment dataclass + make_segment_id() D-05/D-06
- `backend/src/app/pipeline/placeholder.py` - extract_placeholders(), restore_placeholders(), PlaceholderRestoreError
- `backend/src/app/pipeline/docx/extractor.py` - walk_document(), _walk_table(), extract_segments()
- `backend/src/app/pipeline/docx/reassembler.py` - write_translated_paragraph(), reassemble_docx()
- `backend/src/app/pipeline/docx/tracked.py` - has_tracked_changes(), strip_tracked_changes()
- `backend/tests/pipeline/test_placeholder.py` - 18 tests for placeholder + segment ID
- `backend/tests/pipeline/test_docx_extractor.py` - 16 tests for traversal + run-merge + round-trip
- `backend/tests/pipeline/test_tracked_changes.py` - 9 tests for tracked-changes detection + strip
- `backend/tests/pipeline/fixtures/_generate.py` - Programmatic fixture generator (deterministic)
- `backend/tests/pipeline/fixtures/simple.docx` - 3 body paras + 2×2 table (7 segments)
- `backend/tests/pipeline/fixtures/table_heavy.docx` - 2×2 outer table with nested 2×1 inner table
- `backend/tests/pipeline/fixtures/tracked_changes.docx` - Doc with injected <w:ins> + <w:del> nodes

## Decisions Made

- **Closure counter pattern:** `extract_placeholders()` uses a mutable list cell `counter = [0]` to avoid Python's late-binding closure issue — plain `nonlocal counter` inside a nested function defined in a loop does not capture the loop variable correctly in all Python versions.
- **T-04-03 fallback strategy:** `restore_placeholders()` keeps ⟦T{n}⟧ marker visible when token key is missing rather than raising immediately — the marker is visible to the human reviewer in the output document. `PlaceholderRestoreError` is available for callers that want strict mode.
- **Fixture commit strategy:** Golden fixtures committed as .docx binary alongside `_generate.py` — tests do not need to re-generate on every run; generator is available for future fixture updates.
- **lxml pre-collection before mutation:** `strip_tracked_changes()` collects all `<w:ins>` elements into a list before modifying the tree — avoids iterator invalidation when unwrapping elements modifies the parent.

## Deviations from Plan

None — plan executed exactly as written. The closure scoping note in the plan's REFACTOR step was handled directly in the GREEN implementation using the mutable list cell pattern, avoiding a separate refactor commit.

## Issues Encountered

None — all tests passed on first GREEN run (43/43).

## TDD Gate Compliance

- RED gate: `test_placeholder.py` imported non-existent modules → collected 0 items / 1 error. `test_docx_extractor.py` + `test_tracked_changes.py` similarly failed with ModuleNotFoundError. RED confirmed before any implementation.
- GREEN gate: All 43 tests pass after implementation.
- REFACTOR: No separate refactor needed — closure fix applied inline during GREEN.

## Known Stubs

None — all implemented functionality is wired. No placeholder data or TODO stubs.

## Threat Flags

No new security surface introduced beyond what the plan's threat model documents. `strip_tracked_changes()` operates only on the in-memory lxml tree; the source file at input_path is preserved by the caller (T-04-01 mitigated as designed).

## Self-Check

Files created — spot check:
- `backend/src/app/pipeline/segment.py` — FOUND
- `backend/src/app/pipeline/placeholder.py` — FOUND
- `backend/src/app/pipeline/docx/extractor.py` — FOUND
- `backend/src/app/pipeline/docx/reassembler.py` — FOUND
- `backend/src/app/pipeline/docx/tracked.py` — FOUND
- `backend/tests/pipeline/fixtures/simple.docx` — FOUND

Commits — both present in log:
- `1dcee62` feat(pipeline): add Segment dataclass + SHA ID + placeholder protection
- `295667a` feat(docx): add DOCX extractor, reassembler, and tracked-changes handler

Test count: 43 passed, 0 failed, 0 errors.

## Self-Check: PASSED

## Next Phase Readiness

- `extract_segments(doc, job_id)` → `list[Segment]` ready to feed into `pack_into_batches()` from Plan 03
- `reassemble_docx(doc, segments, translated_texts: dict[str, str])` ready for the translate worker (Plan 05/06)
- `has_tracked_changes(doc)` ready for upload endpoint response (Plan 05 API layer)
- All pipeline correctness invariants active from day one: NFC normalization, run-merge, placeholder protection, tracked-changes detection

---
*Phase: 01-foundation-docx-pipeline*
*Completed: 2026-04-24*
