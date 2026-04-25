---
status: diagnosed
phase: 02-review-ux-glossary
source: [02-VERIFICATION.md]
started: 2026-04-25T03:45:00Z
updated: 2026-04-25T21:50:00Z
---

## Current Test

[testing complete — 8/9 pass; test 9 textarea-edit affordance logged for cosmetic closure round]

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
expected: |
  j/k move segment focus and show visible violet ring on current row;
  ? OR Ctrl+Shift+P toggles keyboard help panel (Ctrl+Shift+P also works from inside textarea);
  Escape blurs active textarea
result: pass
side_observation: "textarea when edit is not good UI (need to highlight or white box or something) — logged as test 9"
prior_attempts:
  - round: 1
    reported: "shift+? cannot work; j/k combination not good for UX"
    fix: "02-12 — useHotkeys('?')"
    outcome: "did not address j/k focus visibility, still broken in browser"
  - round: 2
    reported: "j/k no visible focus highlight; ? still requires shift; Escape doesn't blur"
    fix: |
      02-13:
      - SegmentRow.tsx: ring-2 ring-violet-500 bg-violet-50 + data-focused
      - useReviewKeyboard.ts: additive ctrl+shift+p binding (enableOnFormTags textarea), Escape blur via setTimeout(blur, 0)
      - KeyboardHelpPanel.tsx: label updated to "? / Ctrl+Shift+P"
    applied_in: ["02-13-SUMMARY.md"]

### 4. Export DOCX file download
expected: Browser triggers a DOCX file download; re-clicking does not corrupt segment state
result: pass
prior_attempt:
  reported: "error banner Export failed - Unknown error. Try again."
  diagnosis: "AttributeError: 'Segment' object has no attribute 'run_index' at export_service.py:102"
  fix: |
    02-10 added run_index + run_group_size columns to ORM Segment.
    Worker line 305-321 populates from dataclass.
    02-11 surfaces structured JSON {code, detail} on failure.
    02-REVIEW-FIX WR-04: revokeObjectURL deferred 100ms (Safari/Firefox race).
  applied_in: ["02-10-SUMMARY.md", "02-11-SUMMARY.md", "02-REVIEW-FIX.md"]

### 5. End-to-end glossary injection
expected: Glossary terms appear in job; segments with glossary violations show violet "GLOSSARY" badge; re-upload same content does not collide
result: pass
note: "PK collision fix verified — re-upload same content works"
side_observation: "Vietnamese glyphs render incorrectly in segment cells (paper-skill PT Mono / Roboto missing VN tone marks?). New issue logged separately."
prior_attempt:
  reported: "Translation Failed: sqlalchemy IntegrityError UniqueViolationError on segments_pkey"
  diagnosis: "global PK on segments.id collided across jobs (deterministic D-06 hash)"
  fix: |
    02-10 migrated segments PK to compound (job_id, id).
    SegmentFlag uses compound FK (segment_job_id, segment_id).
    Migration 0003 applied to live Postgres.
    02-REVIEW-FIX WR-03: worker insert wrapped in try/except IntegrityError → idempotent on retry.
  applied_in: ["02-10-SUMMARY.md", "02-REVIEW-FIX.md"]

### 6. CSV import flow
expected: Browser file picker accepts CSV; dedup enforced via UniqueConstraint; parsed rows appear in terms table
result: pass
note: "duplicates rejected as expected"

### 7. End-to-end segment persistence
expected: Real translation job (non-mocked) completes; review page displays translated segments; review-page Export downloads DOCX; glossary violation badges appear on relevant segments when glossary attached
result: pass
prior_attempt:
  reported: "review page can show segment but still cannot download (can still download unedited but translated document in the job page)"
  fix: "inherits test 4 fix (02-10 + 02-11) — run_index now on ORM, export reassembles correctly"
  applied_in: ["02-10-SUMMARY.md", "02-11-SUMMARY.md"]
cross_ref_test: 4

### 8. Vietnamese font rendering
expected: |
  Vietnamese diacritics (ắ, ề, ộ, ý, ữ) render correctly in body text, headings, and source-cell monospace font.
  No tofu boxes or fallback substitution glyphs visible.
result: pass

### 9. Textarea active-edit visual state
expected: |
  When user clicks/focuses a target segment textarea to edit, it shows clear visual contrast vs surrounding read-only cells: white bg, distinct ring, padding cue, OR similar "this is editable now" affordance. Should NOT blend with the row.
result: issue
reported: "textarea when edit is not good UI (need to highlight or white box or something like that)"
severity: minor
discovered_during: "round 3 retest of test 3"
prior_attempt:
  reported: "current font is errored when display vietnamese (paper-skill PT Mono / Roboto subsets missing 'vietnamese')"
  fix: |
    02-14:
    - layout.tsx: Roboto + Montserrat subsets include 'vietnamese'
    - PT Mono → JetBrains Mono (PT Mono lacks vietnamese subset on Google Fonts)
    - CSS var --font-pt-mono preserved → SegmentRow.tsx unchanged
    - CLAUDE.md font convention updated
  applied_in: ["02-14-SUMMARY.md"]

## Summary

total: 9
passed: 8
issues: 1
partial: 0
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
  status: superseded
  reason: "Prior round: shift+? not firing; j/k UX complaint. 02-12 changed binding to '?' but retest still fails."
  severity: major
  test: 3
  artifacts: ["frontend/src/hooks/useReviewKeyboard.ts", "frontend/src/components/KeyboardHelpPanel.tsx"]
  missing: ["correct ? key detection", "evaluate j/k vs alternative nav"]
  superseded_by: "second-round gap below"

- truth: "Review-page keyboard nav is usable: visible focus on current segment, help panel opens without modifier gymnastics, Escape blurs active textarea"
  status: failed
  reason: "User reported (retest): j/k moves not highlighting current segment; ? still requires shift; Escape does not blur"
  severity: major
  test: 3
  artifacts:
    - "frontend/src/hooks/useReviewKeyboard.ts"
    - "frontend/src/components/KeyboardHelpPanel.tsx"
    - "frontend/src/components/SegmentRow.tsx"
    - "frontend/src/components/SegmentTable.tsx"
  missing:
    - "Visible focus ring or row highlight on the j/k-focused segment (SegmentRow needs data-focused state, ring-2 ring-primary or similar)"
    - "Help-panel hotkey changed to a non-shifted key OR explicit modifier combo. User proposes ctrl+shift+p (vscode-style command palette)"
    - "Escape handler must call (document.activeElement as HTMLTextAreaElement)?.blur() — current implementation may not actually blur"
    - "Verify each binding works in browser end-to-end, not just unit tests"
  user_proposal: "ctrl+shift+p for help panel toggle (vscode convention)"

- truth: "Export downloads a DOCX assembled from edited_text ?? translated_text; idempotent re-export"
  status: resolved
  reason: "02-10 added run_index/run_group_size to ORM + worker; 02-11 surfaces structured JSON; retest passed"
  severity: major
  test: 4
  artifacts: ["02-10-SUMMARY.md", "02-11-SUMMARY.md", "02-REVIEW-FIX.md"]
  missing: []

- truth: "Vietnamese diacritics render correctly in segment cells (and other UI text)"
  status: failed
  reason: "User retest observation: VN glyphs error in display"
  severity: major
  test: 5
  artifacts:
    - "frontend/src/app/layout.tsx (next/font/google config)"
    - "frontend/src/components/SegmentRow.tsx (PT Mono cell)"
    - "frontend/tailwind.config.ts (font-family stack)"
  missing:
    - "Verify next/font/google subsets includes 'vietnamese' for Roboto, Montserrat, PT Mono"
    - "If PT Mono lacks VN coverage, swap source-cell font for one with full VN diacritic support (JetBrains Mono, IBM Plex Mono, or Roboto Mono)"
    - "Check fallback font stack — must include sans-serif system fallback before generic"
  user_observation: "current font is errored when display vietnamese"

- truth: "Translation job persists segments without PK collision when re-uploading documents"
  status: resolved
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

- truth: "When user clicks/focuses target textarea to edit, it shows clear visual contrast vs surrounding read-only cells (white bg, distinct ring, padding cue)"
  status: failed
  reason: "User reported: textarea when edit is not good UI (need to highlight or white box or something)"
  severity: minor
  test: 9
  artifacts:
    - "frontend/src/components/SegmentRow.tsx (TargetCell textarea)"
  missing:
    - "Apply :focus-within or :focus styles to target-cell textarea — examples: bg-white, ring-2 ring-violet-400, shadow-sm"
    - "Distinguish read-only target cell (current state: blends with row) from active edit (should be visibly distinct)"
    - "Optional: subtle animation/transition on focus for polish"
  discovered_during: "round 3 retest of test 3"
