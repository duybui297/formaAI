---
status: complete
phase: 03-pptx-native-pdf
source:
  - 03-01-SUMMARY.md
  - 03-03-SUMMARY.md
  - 03-04-SUMMARY.md
  - 03-05-SUMMARY.md
  - 03-06-SUMMARY.md
  - 03-07-SUMMARY.md
started: 2026-04-26T03:49:00Z
updated: 2026-04-26T18:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: |
  Kill running services. Bring stack up fresh (docker compose up or equivalent).
  Backend boots, Alembic migration 0004 (FlagType extension) applies cleanly,
  arq worker starts, frontend dev server boots. Health endpoint or homepage loads.
result: pass
note: |
  Found + fixed bug en route — backend/Dockerfile did not COPY alembic.ini,
  so `alembic current` failed with "No 'script_location' key". Patched in
  commit a857aea, rebuilt, upgrade head succeeded, smoke clean.

### 2. Upload Form Accepts PPTX + PDF
expected: |
  Open upload screen. File picker (or drag-drop) accepts `.pptx` and `.pdf`
  in addition to `.docx`. Drop-zone copy mentions all three formats. Selecting
  a PPTX or PDF does NOT show "unsupported format" error.
result: pass
note: |
  Found + fixed bug en route — POST /upload returned 422
  "PPTX translation is not yet supported." because
  PHASE1_SUPPORTED_FORMATS was still {.docx}. Plan 03-05
  shipped worker dispatch but missed lifting the API gate.
  Patched in commit e6619a9 (renamed to SUPPORTED_FORMATS,
  added .pptx + .pdf, updated 3 stale phase-1 tests).
  Rebuilt api container; upload + Translate Document now
  reaches the worker.

### 3. PPTX End-to-End Translation
expected: |
  Upload a real PPTX (any pair, e.g., EN→VI). Job completes without error.
  Open the translated .pptx in PowerPoint or LibreOffice Impress:
    - Slide count matches source
    - Body text, table cells, and speaker notes are translated
    - Master/layout text is preserved (not duplicated, not left in source language)
    - Run-level formatting (bold, italic, font color) is preserved on first run
    - No SmartArt got translated (stays as-is — flagged in review UI instead)
result: issue
reported: "the layout, space of text and components still not right (can check .data/jobs/7026c344-a5bd-4e2b-8042-24c79f001dc3)"
severity: minor
evidence: |
  Structural integrity verified — 30/30 slides, shape/para/run counts match.
  Translation persisted. Flags persisted as designed:
    - overflow info  (auto-fit succeeded): 76 / 200 segments (38%)
    - overflow warn  (real overflow):      15 / 200 segments (7.5%)
    - llm_refusal:                          1
    - smartart:                             0 (deck has none)
  Phase 3 contract per PROJECT.md is "translated + flagged when imperfect",
  NOT pixel-perfect. User expected tighter visual fidelity. Friction is
  driven by translated-text expansion (EN→VI typically +20-40%) and the
  blank-remaining-runs reassembly strategy losing per-run sizing. Real
  fixes: tighter auto-fit ladder, per-paragraph font-size budget, or
  redact-and-reinsert (à la PDF) for high-density slides.

### 4. PPTX Overflow + AUTO-FIT Badges
expected: |
  Open the review screen for the PPTX job. Segments whose translated text grew
  past the shape's char-ratio threshold show:
    - Red "Overflow" badge if translation exceeded budget AND auto-fit could not save it
    - Blue "Auto-fit" badge if auto-fit shrunk text to keep it inside
  Badges render with correct colors per UI-SPEC.
result: pass
note: |
  Found + fixed bug en route — InlineFlagBadge in SegmentRow.tsx
  ignored flag.details, so all 91 overflow rows rendered the same
  amber Overflow chip (M2 contract violation; FlagBadge.tsx already
  handled the split, the inline copy did not). Patched in commit
  7d2ce8c — threaded details through, branched on auto_adjusted=true,
  added AUTO_FIT_STYLE constant for parity. Verified via Playwright
  screenshot (.playwright-mcp/phase3-overflow-filter.png): AUTO-FIT
  slate + Overflow amber + Refusal red render distinctly.

  Open follow-up (cosmetic, not blocking): ReviewFilterBar still
  groups all 91 overflow flags under one "Overflow (90)" chip
  (the filter bar). Would need a separate "Auto-fit (76)" chip
  to match the row-level split. File for a Phase 3.x polish
  pass or absorb into Phase 4 UI-SPEC delta.

### 5. PPTX SmartArt Skip + SMART Badge
expected: |
  Upload a PPTX containing a SmartArt diagram. In the review UI, segments
  belonging to SmartArt show a "SMART" badge and the source/target columns
  display the original text untranslated (skip-and-flag, not skip-and-drop).
result: skipped
reason: |
  No SmartArt-containing PPTX on hand. Prior test deck had 0 SmartArt
  flags. Defer to a future UAT pass when a SmartArt deck is available.
  Backend logic covered by unit + round-trip tests in 03-03 + 03-07.

### 6. Native PDF End-to-End Translation
expected: |
  Upload a native PDF containing CJK text (Japanese or Chinese). Job completes.
  Open translated PDF in any viewer:
    - Page count matches source
    - CJK glyphs render correctly (no tofu / empty boxes) — Noto Sans CJK
      embedded by reassembler
    - Non-text content (images, vector graphics, page background) intact
    - Layout closely matches source (no garbled overlap from redact-reinsert)
result: issue
reported: "(initial run) StringDataRightTruncationError → InvalidCachedStatementError; (after migration + cache fix) tables blank; (after rect-guard fix) tables show content but mixed JP+VI; caption overlapping image"
severity: minor
evidence: |
  Three blocking bugs found + fixed during this test, one open issue:

  Fix 1 — VARCHAR(20) flag_type column couldn't hold 'multi_column_degraded'
    (21 chars). Migration 0005 widens to VARCHAR(32). Commit 8b03f97.

  Fix 2 — asyncpg prepared-statement cache poisoned by mid-session DDL.
    Disabled via connect_args={'statement_cache_size': 0} on both api +
    worker engines. Commit 3df7fd2.

  Fix 3 — PyMuPDF text-block bboxes hug visible glyphs (~3.9pt for 8pt
    CJK fonts in dense tables). Redact-reinsert wiped source rows then
    couldn't refit any line, producing blank cells (97% content loss on
    page 1, 96% on page 3). Added 6pt min-rect-height guard: undersized
    rects skip redact+reinsert, source stays visible (untranslated, but
    intact). Commit 8810e76. Tradeoff: tables now show mixed source +
    translated rows.

  Open issue (not blocking goal — flagged for follow-up):
    Image captions overlap into adjacent images after translation. Caption
    rect width is unchanged, but translated text expands → overflows past
    rect edge into image area. Fix path: rect-vs-image collision detection
    in reassembler, or shrink translated text more aggressively when
    adjacent shape is non-text. Defer to Phase 3.x polish.

### 7. PDF 2-Column Reading Order
expected: |
  Upload a 2-column native PDF (e.g., academic paper). In the translated PDF
  AND in the review UI, segments appear in column-major reading order:
  all of left column first, then all of right column — not interleaved
  row-by-row across both columns.
result: issue
reported: "table format is not preserve good (table 1 and table 2 cannot parse anything); title, header, format of text is not preserve good (no highlight for title heading #1, #2, etc.)"
severity: minor
job_id: c457a7ea-04a7-4fee-983f-d48b87e314f1
evidence: |
  Inspected source vs output:
    page 4: src 28 blocks → out 1 block (96% content loss)
    page 5: src 33 blocks → out 25 blocks
  Page 4 is a rotated/stacked table — blocks are 9-17pt WIDE × 200-635pt
  TALL (vertical column strips). Earlier height-only guard (6pt min) did
  NOT fire; reassembler still redacted the source, then insert_htmlbox
  could not fit a single glyph in a 9pt-wide rect → blank.

  Fix shipped: add _MIN_RECT_WIDTH_PT = 20pt to the rect-too-small
  guard. Skipped rects preserve source visibly. Commit e617caa, worker
  restarted. Test 7 reading-order verdict NOT validated yet — user
  reported tables/headings, not column order.

  Open issue (separate, not patched): no heading hierarchy preserved
  (no <h1>/<h2>/etc. styling in output). spans_to_html in
  backend/src/app/pipeline/pdf/extractor.py only emits <b>/<i> from
  span flags — does not detect font-size-based heading levels. Real fix
  requires heading detection (font-size cluster analysis or rule-based
  span-size threshold). Defer to Phase 3.x or a dedicated heading-aware
  pipeline upgrade.

### 8. PDF 3-Column Multi-Col-Degraded Badge
expected: |
  Upload a 3+ column native PDF (newspaper-style). The review UI shows a
  "MULTI-COL" badge on affected segments, indicating the layout was degraded
  to flat reading order. Translation still happens; no crash.
result: pass
note: |
  Generated sample at .data/samples/three-column-sample.pdf
  (cluster_columns returns is_degraded=True). User uploaded,
  MULTI-COL badge rendered as expected.

  Found follow-up bug en route — Export Document button on review
  page errored for PPTX/PDF jobs because export_service was DOCX-only
  (opened job.input_path with python-docx). Patched in commit 7640e8c:
  PoC pass-through serves the worker's existing output.{pptx,pdf} as
  download (edit-aware re-export for PPTX/PDF deferred). Backend
  media_type now picks docx/pptx/pdf by suffix; frontend filename
  preserves original extension.

### 9. Review-UI Format Breadcrumbs
expected: |
  Open review UI for a translated PPTX or PDF job. Each segment row shows a
  format-aware breadcrumb above the source text:
    - PPTX: `Slide N / Shape M / ¶P` (master/notes use distinct labels)
    - PDF:  `Page N / Col M / Block K` (or `Page N / Block K` when degraded)
  Breadcrumb is muted/secondary visual weight per UI-SPEC.
result: pass
note: |
  Two bugs found + fixed en route:

  Fix 1 — backend GET /jobs/{id}/segments serializer omitted
  structural_position. Frontend received undefined, conditional
  guard hid the breadcrumb on every row. One-line patch in
  _segment_to_dict (commit 6a92042).

  Fix 2 — breadcrumb displayed mixed indexing (PPTX shape was
  1-based, all other parts raw 0-based). User wanted consistent
  1-based display. Added _oneBased helper, applied across
  slide/page/master/col/block/para/notes; updated tests
  (commit 4fd98e3).

### 10. DOCX Regression Check
expected: |
  Upload a DOCX file (Phase 1 hero format). Existing DOCX flow still works:
  job completes, output preserves run-level formatting, review UI renders
  segments without breaking. No regression from Phase 3 worker dispatch
  changes.
result: pass
note: |
  DOCX path untouched by Phase 3 worker dispatch (verified by
  inspection of translate_worker.py + 311 backend tests + 48
  frontend tests, all green).

  Future-feature request from user (not blocking, log for backlog):
  breadcrumbs across all formats should use more human-friendly,
  non-technical labels. Current output reads developer-style
  (`Slide 1 / Shape 2 / ¶3`, `Page 1 / Col 1 / Block 5`).
  Suggested polish for a Phase 3.x or post-PoC iteration:
    - PPTX: "Slide 1, text box 2, paragraph 3" or icon + count
    - PDF:  "Page 1, left column, paragraph 5"
    - DOCX: "Page 4, heading 'Introduction', paragraph 2"
  Plus iconography to skip the labels entirely on small screens.

## Summary

total: 10
passed: 6
issues: 3
pending: 0
skipped: 1
blocked: 0

## Gaps

- truth: "Translated PPTX preserves visual layout (text density, component spacing) close to source"
  status: failed
  reason: "User reported: the layout, space of text and components still not right (can check .data/jobs/7026c344-a5bd-4e2b-8042-24c79f001dc3)"
  severity: minor
  test: 3
  artifacts:
    - path: ".data/jobs/7026c344-a5bd-4e2b-8042-24c79f001dc3/output.pptx"
      issue: "200 segments → 91 overflow flags (76 info auto-fit, 15 warn real overflow)"
    - path: "backend/src/app/pipeline/pptx/reassembler.py"
      issue: "blank-remaining-runs strategy loses per-run sizing on multi-run paragraphs"
  missing:
    - "Tighter auto-fit ladder (current threshold may shrink too aggressively)"
    - "Per-paragraph font-size budget to keep text inside shape without illegible shrink"
    - "Optionally: switch dense slides to redact-and-reinsert like the PDF pipeline"
  root_cause: ""
  debug_session: ""

- truth: "Native PDF translation preserves layout, table content, and image-caption positioning"
  status: failed
  reason: "User reported caption overlapping image (post 3 hotfixes). Tables OK after rect-guard fallback, but show mixed JP source + VI translation."
  severity: minor
  test: 6
  artifacts:
    - path: ".data/jobs/d73528f6-2283-4111-923b-15730fdca660/output.pdf"
      issue: "Tables now render content (after rect-guard fix); captions overflow rect into adjacent image."
    - path: "backend/src/app/pipeline/pdf/reassembler.py"
      issue: "Reassembler does not detect rect-vs-image collisions; translated text widens past original rect."
  missing:
    - "Rect-vs-image collision detection in PDF reassembler"
    - "Adaptive shrink when adjacent shape is non-text image"
    - "Smarter table reassembly (cell-aware) so dense rows can be translated"
  root_cause: ""
  debug_session: ""
  fixed_in_this_uat:
    - "VARCHAR(20) → VARCHAR(32) flag_type column (commit 8b03f97)"
    - "asyncpg prepared-statement cache disabled (commit 3df7fd2)"
    - "Min rect-height guard: skip redact+reinsert below 6pt (commit 8810e76)"

- truth: "Academic-paper PDF preserves table content + heading hierarchy on translation"
  status: failed
  reason: "User reported: tables 1 + 2 blank in output; headings (#1, #2) lose visual hierarchy."
  severity: minor
  test: 7
  job_id: c457a7ea-04a7-4fee-983f-d48b87e314f1
  artifacts:
    - path: "backend/src/app/pipeline/pdf/reassembler.py"
      issue: "Min-rect guard was height-only; rotated-column tables (9pt wide × 600pt tall) bypassed the guard and produced blanks."
    - path: "backend/src/app/pipeline/pdf/extractor.py"
      issue: "spans_to_html does not emit <h1>/<h2>/etc. — heading levels lost."
  missing:
    - "Heading detection (font-size cluster analysis or threshold rule)"
    - "Heading-aware span-to-HTML so <h1>/<h2> tags carry through translation"
  root_cause: ""
  debug_session: ""
  fixed_in_this_uat:
    - "Min rect-width guard: skip redact+reinsert below 20pt (commit e617caa)"
