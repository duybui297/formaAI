---
status: partial
phase: 04-scanned-pdf-ocr
source: [04-VERIFICATION.md]
started: 2026-04-28T15:55:00Z
updated: 2026-04-28T15:55:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Bilingual PDF visual fidelity
expected: Bilingual PDF page width is 2x source page width. Left side reproduces the scanned page image faithfully. Right side renders translated text in the corresponding region bbox positions. Font is legible at >=8pt. Noto CJK characters render correctly for Japanese/Chinese output.
result: [pending]

### 2. Low-confidence banner + review UI
expected: Amber banner with AlertTriangle icon appears at top of review page. Banner shows page numbers as clickable links. Clicking a page number scrolls the segment table to the first segment of that page. Confidence chips on affected segments show red (<50%) or amber (50-70%) coloring.
result: [pending]

### 3. Source cell editing and image preview
expected: Source cell becomes editable textarea on double-click. Edits debounced-PATCH at 500ms. "Discard source edit" button appears. Press 'i' to toggle image preview (page PNG crop appears above row). Press Shift+E to activate source edit via keyboard.
result: [pending]

### 4. Three-artifact download dropdown
expected: Each option (Bilingual PDF, Translated PDF, Translated DOCX) triggers download via GET /api/jobs/{id}/artifacts?artifact={type}. All three files download successfully. Bilingual PDF opens as side-by-side layout. DOCX opens with translated text and correct heading structure.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
