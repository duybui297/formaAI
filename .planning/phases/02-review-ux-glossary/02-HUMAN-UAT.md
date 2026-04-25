---
status: partial
phase: 02-review-ux-glossary
source: [02-VERIFICATION.md]
started: 2026-04-25T03:45:00Z
updated: 2026-04-25T13:50:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Review page visual rendering
expected: Side-by-side table renders with source segments on left, editable textareas on right; flag badges visible on flagged segments
result: [pending]

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
