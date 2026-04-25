---
status: partial
phase: 02-review-ux-glossary
source: [02-VERIFICATION.md]
started: 2026-04-25T03:45:00Z
updated: 2026-04-25T13:50:00Z
---

## Current Test

number: 1
name: Review page visual rendering
expected: |
  Side-by-side table renders with source segments on left, editable textareas on right; flag badges visible on flagged segments
awaiting: user response (retest after worker restart)

## Tests

### 1. Review page visual rendering
expected: Side-by-side table renders with source segments on left, editable textareas on right; flag badges visible on flagged segments
result: [pending]
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
result: [pending]

### 3. Keyboard shortcuts
expected: j/k move segment focus; shift+? toggles keyboard help panel; Escape blurs active textarea
result: [pending]

### 4. Export DOCX file download
expected: Browser triggers a DOCX file download; re-clicking does not corrupt segment state
result: [pending]

### 5. End-to-end glossary injection
expected: Glossary terms appear in job; segments with glossary violations show violet "GLOSSARY" badge
result: [pending]

### 6. CSV import flow
expected: Browser file picker accepts CSV; dedup enforced via UniqueConstraint; parsed rows appear in terms table
result: [pending]

### 7. End-to-end segment persistence
expected: Real translation job (non-mocked) completes; review page displays translated segments (not empty); glossary violation badges appear on relevant segments when glossary attached
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
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
