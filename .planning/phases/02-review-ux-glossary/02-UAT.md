---
status: complete
phase: 02-review-ux-glossary
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md, 02-05-SUMMARY.md, 02-06-SUMMARY.md, 02-07-SUMMARY.md]
started: 2026-04-25T05:25:00Z
updated: 2026-04-25T05:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Review page visual rendering
expected: Side-by-side table renders with source segments left, editable textareas right; flag badges visible on flagged segments
result: issue
reported: "Review page renders with empty state (No segments with this flag type) for ALL completed jobs. Segments are NEVER persisted to the segments DB table — translate_worker translates in-memory but never calls session.add(Segment(...)). Affects every Phase 2 review feature."
severity: blocker

### 2. Debounce edit + save indicator
expected: Textarea shows "Saving…" then "Saved" within ~600ms; PATCH call appears in DevTools
result: blocked
blocked_by: prior-phase
reason: "Cannot test inline editing — no segment rows exist in DB (see Test 1 root cause)."

### 3. Keyboard shortcuts (j/k/n/e/r/?/Esc)
expected: j/k move segment focus; ? toggles keyboard help panel; Esc blurs textarea
result: pass

### 4. Export DOCX file download
expected: Browser triggers DOCX download; re-clicking does not corrupt segment state
result: pass
reason: "POST /jobs/{id}/export → 200, valid DOCX (36 KB). Idempotent atomic write per export_service. NOTE: edited_text fallback path untested because segments table is empty."

### 5. End-to-end glossary injection (live DashScope)
expected: Glossary terms appear in job; segments with glossary violations show violet GLOSSARY badge
result: issue
reported: "Worker glossary path crashes with FK violation: 'insert or update on table segment_flags violates foreign key constraint segment_flags_segment_id_fkey'. Cascading PendingRollbackError leaves job stuck in 'running' state (transition_to_failed reuses the same broken session). Glossary terminology DOES inject (DashScope receives the terminology param), but post_check explodes when overflow detected."
severity: blocker

### 6. CSV import flow
expected: Browser file picker accepts CSV; dedup enforced via UniqueConstraint; parsed rows appear in terms table
result: pass
reason: "Imported 3 terms (hello/xin chào/greeting, goodbye/tạm biệt, thank you/cảm ơn/polite) from .playwright-mcp/uat-glossary.csv. Terms appear in terms table immediately."

## Summary

total: 6
passed: 3
issues: 2
blocked: 1
pending: 0
skipped: 0

## Gaps

- truth: "Translated segments are persisted to the segments DB table so the review page can display them"
  status: failed
  reason: "User reported: Review page shows empty state for every completed job. translate_worker.py never calls session.add() for Segment rows. The Segment ORM model exists, run_post_check tries to UPDATE Segment rows (silently no-ops on missing rows) and INSERT SegmentFlag rows (fails with FK violation when there's a flaggable batch)."
  severity: blocker
  test: 1
  artifacts:
    - backend/src/app/workers/translate_worker.py
    - backend/src/app/services/glossary_service.py
  missing:
    - "session.add(Segment(...)) for each parsed segment before translation begins"
    - "session.commit() after persisting segments so post_check can UPDATE/INSERT against real rows"
    - "Optionally: explicit batch persistence in pack-batches stage so progress survives mid-job restart"

- truth: "Worker recovers gracefully when run_post_check raises so the job transitions to failed (not stuck in running)"
  status: failed
  reason: "User reported: ForeignKeyViolationError → PendingRollbackError cascade. transition_to_failed calls get_job on the same broken session, raising again. Job sits at status=running forever."
  severity: blocker
  test: 5
  artifacts:
    - backend/src/app/workers/translate_worker.py
    - backend/src/app/services/job_service.py
  missing:
    - "session.rollback() (or fresh session) before calling transition_to_failed in the outer except handler"
    - "Or: defer FK constraints / ensure segments persisted before flags can reference them (preferred — fixes both gaps with one change)"

## Acknowledged Gaps

The following defects were observed during UAT but are advisory (not blocking goal achievement):

- **NavBar missing on /glossaries routes** — Banner with "AI Translation" + Upload/Jobs/Glossaries nav appears on /jobs/{id}/review but is absent on /glossaries and /glossaries/{id}. Layout/route inconsistency.
- **IN-03 confirmed (Terms column shows "—" not count)** — `frontend/src/components/glossary/GlossaryList.tsx` reads `g.terms?.length ?? "—"` but list API returns `term_count` (not the `terms` array). Fix: display `g.term_count ?? 0`.
- **GET /jobs/{id} response omits glossary_id** — DB row has glossary_id, but Job response schema doesn't expose it. Frontend can't tell whether a glossary is attached. Add `glossary_id: str | None` to JobResponse Pydantic model.

## Infrastructure Notes

UAT setup required these one-time fixes (not Phase 2 defects but hardened for future runs):
1. Alembic 0002 migration not applied — ran `alembic upgrade head` against running postgres container
2. Web container stale node_modules — copied host package.json/lock into container, ran `npm install --legacy-peer-deps`
3. arq worker doesn't hot-reload — `docker compose up -d --force-recreate worker` after Phase 2 code merge
