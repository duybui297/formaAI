---
status: partial
phase: 02-review-ux-glossary
source: [02-VERIFICATION.md]
started: 2026-04-25T03:45:00Z
updated: 2026-04-25T16:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Review page visual rendering
expected: Side-by-side table renders with source segments on left, editable textareas on right; flag badges visible on flagged segments
result: pass
prior_attempt:
  reported: "stuck at translate_job process"
  diagnosis: |
    Worker container started 2026-04-25T05:43 UTC, but the 02-08 fix
    (commit fdae1d6) landed at 06:24 UTC. Bind mount updated disk
    immediately, but arq Python process kept the pre-fix module in memory.
    Old code did not persist Segment ORM rows; run_post_check then
    inserted SegmentFlag rows referencing IDs not in the segments table,
    causing FK violation, fatal job failure, and stuck "running" state.
  fix: "docker compose restart worker — picks up 02-08 code"
  applied_at: 2026-04-25T07:50:00Z

### 2. Debounced inline edit + save indicator
expected: Textarea shows "Saving..." then "Saved" within ~600ms; network PATCH call appears in DevTools
result: pass

### 3. Keyboard shortcuts
expected: j/k move segment focus; shift+? toggles keyboard help panel; Escape blurs active textarea
result: issue
reported: "shift+? cannot work (may be due to ? need to hold shift first). also j/k combination not good for UX"
severity: major

### 4. Export DOCX file download
expected: Browser triggers a DOCX file download; re-clicking does not corrupt segment state
result: issue
reported: "error banner Export failed - Unknown error. Try again."
severity: major
diagnosis: |
  AttributeError: 'Segment' object has no attribute 'run_index' at
  backend/src/app/services/export_service.py:102 — reassemble_docx_runs
  is called with ORM Segment rows, but `run_index` and `run_group_size`
  are dataclass-only fields (pipeline/segment.py). Worker reassembly
  works because it passes the live dataclass list; export reloads from
  DB and the columns don't exist.
  Also: api should surface specific error to UI, not "Unknown error".

### 5. End-to-end glossary injection
expected: Glossary terms appear in job; segments with glossary violations show violet "GLOSSARY" badge
result: issue
reported: "Translation Failed: sqlalchemy IntegrityError UniqueViolationError"
severity: blocker
diagnosis: |
  duplicate key value violates unique constraint "segments_pkey"
  Key (id)=(c8f39cf9b5b68be1) already exists.
  segments.id PK is global; make_segment_id() = sha256(source_text +
  structural_position)[:16] is deterministic per (text, position) but
  job-independent (D-06 intent: translation memory reuse v2).
  Re-uploading same/overlapping doc content → duplicate ids across jobs
  → INSERT collision in translate_worker.py:322. PoC blocker.

### 6. CSV import flow
expected: Browser file picker accepts CSV; dedup enforced via UniqueConstraint; parsed rows appear in terms table
result: pass
note: "duplicates rejected as expected"

### 7. End-to-end segment persistence
expected: Real translation job (non-mocked) completes; review page displays translated segments (not empty); glossary violation badges appear on relevant segments when glossary attached
result: partial
reported: "review page can show segment but still cannot download (can still download unedited but translated document in the job page)"
severity: major
note: |
  Persistence works (review page renders segments). Job-page download
  works because worker saved output.docx during translate_to_done.
  Review-page Export fails — same root cause as test 4 (run_index
  AttributeError). Once test 4 is fixed, this passes fully.
cross_ref_test: 4

## Summary

total: 7
passed: 3
issues: 3
partial: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Translation job completes so review page can render segments"
  status: resolved
  reason: "Stale worker process; restarted at 07:50 UTC to pick up 02-08 fix"
  severity: blocker
  test: 1
  artifacts: ["02-08-SUMMARY.md"]
  missing: []
  resolution: "ops — docker compose restart worker"

- truth: "Keyboard shortcut shift+? toggles the keyboard help panel; j/k navigation feels good"
  status: failed
  reason: "User reported: shift+? cannot work (may be due to ? need to hold shift first). also j/k combination not good for UX"
  severity: major
  test: 3
  artifacts: ["frontend/src/hooks/useReviewKeyboard.ts", "frontend/src/components/KeyboardHelpPanel.tsx"]
  missing: ["correct ? key detection (event.key === '?' OR shift + '/')", "evaluate j/k vs alternative nav (arrows, n/p)"]

- truth: "Export downloads a DOCX assembled from edited_text ?? translated_text; idempotent re-export"
  status: failed
  reason: "AttributeError: 'Segment' object has no attribute 'run_index' at export_service.py:102"
  severity: major
  test: 4
  artifacts: ["backend/src/app/services/export_service.py", "backend/src/app/db/models.py", "backend/src/app/pipeline/docx/reassembler.py", "backend/src/app/workers/translate_worker.py"]
  missing:
    - "ORM Segment columns: run_index (Integer nullable), run_group_size (Integer default 1)"
    - "Alembic migration adding both columns"
    - "translate_worker.py:305-321 populates run_index/run_group_size in SegmentORM(...)"
    - "API error response surfaces specific error code (not generic Unknown)"

- truth: "Translation job persists segments without PK collision when re-uploading documents"
  status: failed
  reason: "duplicate key value violates unique constraint segments_pkey: Key (id)=(c8f39cf9b5b68be1) already exists"
  severity: blocker
  test: 5
  artifacts: ["backend/src/app/db/models.py", "backend/src/app/pipeline/segment.py", "backend/src/app/db/migrations/versions/", "backend/src/app/workers/translate_worker.py", "backend/src/app/services/glossary_service.py", "backend/src/app/services/export_service.py", "backend/src/app/api/routes/segments.py"]
  missing:
    - "Compound PK on segments: (job_id, id) instead of just id — preserves D-06 deterministic id while allowing same content across jobs"
    - "Alembic migration: drop segments_pkey, add new compound PK (job_id, id)"
    - "Update segment_flags FK: reference (segment_id) needs change — likely add segment_flags.job_id, FK to (segments.job_id, segments.id)"
    - "Verify all queries that look up segment by id alone still work (segments.py PATCH, run_post_check) — most filter by job_id already"
    - "Re-test re-upload scenario after migration"
