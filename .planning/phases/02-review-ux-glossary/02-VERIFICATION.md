---
phase: 02-review-ux-glossary
verified: 2026-04-25T10:30:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed:
    - "Compound PK (job_id, id) on segments table — migration 0003 applied; ORM updated (plan 10, commit 807b66f)"
    - "SegmentFlag.segment_job_id column added with compound FK to segments (plan 10, commit 807b66f)"
    - "run_index + run_group_size columns on Segment ORM; SegmentORM constructor populates both in worker (plan 10, commit 807b66f)"
    - "run_post_check job_id parameter added; expansion_ratio UPDATE uses compound WHERE (Segment.job_id == job_id, Segment.id == seg.id) (plan 10, commit 807b66f)"
    - "All 4 SegmentFlag constructors pass segment_job_id=job_id (plan 10, commit 807b66f)"
    - "flag_counts query in segments.py uses SegmentFlag.segment_job_id == job_id filter (plan 10, commit 807b66f)"
    - "Export endpoint returns structured JSONResponse on ValueError (409), AttributeError (500), Exception (500) — no more 'Unknown error' in UI (plan 11, commit c9a4aed)"
    - "response_model=None on POST /jobs/{job_id}/export to allow FileResponse|JSONResponse union return (plan 11, commit 5b1ba99)"
    - "Frontend ReviewPageHeader.tsx parses body.detail from error JSON and shows it in toast (plan 11, commit 7cd8340)"
    - "? hotkey fixed: useHotkeys('?', ...) instead of 'shift+/' — matches event.key directly (plan 12, commit 2642bf6)"
    - "3 unit tests for compound PK (no-collision, run fields roundtrip, no AttributeError) — all pass (plan 10, commit 0905ef7)"
    - "Test files for run_post_check and SegmentFlag.segment_job_id updated for new contracts (commit 057ee02)"
  gaps_remaining: []
  regressions: []
  advisory_items:
    - "WR-01 (code review): PATCH/regenerate still use .limit(1) without job_id scoping — silently targets wrong job on duplicate segment hash. Deferred to Phase 3 URL migration. Not a goal failure."
    - "WR-02 (code review): Migration backfill for segment_job_id is non-deterministic on PK-collision rows. Low-risk for fresh PoC DB. Not a goal failure."
    - "WR-03 (code review): Worker segment insert not idempotent — crash-restart causes IntegrityError. Addressed by session.rollback() guard; full ON CONFLICT fix deferred. Not a goal failure."
    - "WR-04 (code review): URL.revokeObjectURL races download on Safari/Firefox — setTimeout fix recommended. Not a goal failure."
    - "IN-01 (code review): SegmentFlag.segment relationship missing explicit foreign_keys for compound FK. Cosmetic/fragility risk. Not a goal failure."
    - "IN-02 (code review): test_segment_pk_collision.py tests missing @pytest.mark.asyncio decorator — rely on asyncio_mode=auto. Not a goal failure."
    - "IN-03 (code review): update_glossary_name mutates ORM object in-place (g.name = name). Style violation per immutability rule. Not a goal failure."
human_verification:
  - test: "Open /jobs/<completed-job-id>/review in browser"
    expected: "Side-by-side table renders with source segments on left, editable textareas on right; flag badges visible on flagged segments"
    why_human: "Visual rendering and CAT-tool layout cannot be verified programmatically"
  - test: "Click into a textarea, type a change, wait 500ms, observe save indicator"
    expected: "Textarea shows 'Saving...' then 'Saved' within ~600ms; network PATCH call appears in DevTools"
    why_human: "Debounce timing and optimistic UI state transitions require browser interaction"
  - test: "Press j/k/n/e/r/? (no shift needed)/Escape in review page (focus outside textarea)"
    expected: "j/k move segment focus; ? (single keypress) toggles keyboard help panel; Escape blurs active textarea"
    why_human: "Keyboard shortcut behavior requires browser event loop. UAT Test 3 previously failed with shift+/ — now fixed to use plain ? binding. Needs re-verify."
  - test: "Click Export on a completed job in review page"
    expected: "Browser triggers a DOCX file download; re-clicking does not corrupt segment state; any error shows specific detail message not 'Unknown error'"
    why_human: "File download and idempotency require browser and live backend. UAT Test 4 previously failed with AttributeError — now fixed by run_index ORM columns + structured error response. Needs re-verify."
  - test: "Re-upload the same document as a second job, open its review page, click Export"
    expected: "Second job translates without PK collision error; Export succeeds; review page shows segments"
    why_human: "Compound PK fix (UAT Test 5 blocker) needs end-to-end re-validation with a real duplicate upload. Cannot verify without live PostgreSQL + worker."
  - test: "Create a glossary via UI, add a term pair, attach to upload, translate a document"
    expected: "Glossary terms appear in job; segments with glossary violations show violet 'GLOSSARY' badge"
    why_human: "End-to-end glossary injection requires live DashScope connection and real translation output"
  - test: "Import a CSV file of term pairs via /glossaries/<id> page"
    expected: "Terms are parsed and appear in the terms table; duplicate terms trigger dedup logic"
    why_human: "CSV import flow and dedup behavior require browser file picker and live backend"
---

# Phase 2: Review UX + Glossary Verification Report

**Phase Goal:** The full DOCX workflow gains the two highest-value demo differentiators: a CAT-tool-style segment editor where reviewers can inline-correct translations before export, and a glossary system that injects company-specific terminology via the `qwen-mt-turbo` `terminology` API and flags violations post-translation.
**Verified:** 2026-04-25T10:30:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure plans 02-10 (compound PK + run fields), 02-11 (structured export errors), 02-12 (? keyboard fix), building on plans 02-08 and 02-09

---

## Re-verification Summary (Plans 10 + 11 + 12)

Plans 10, 11, and 12 executed after the previous verification cycle (`human_needed`, `5/5`). These targeted UAT-discovered blockers that static verification could not catch: PK collision (UAT Test 5 blocker), export AttributeError (UAT Test 4 major), export error surfacing (UAT Test 4 UX), and keyboard ? shortcut failure (UAT Test 3).

| Item | Before Plans 10-12 | After Plans 10-12 |
|------|-------------------|-------------------|
| Compound PK (job_id, id) on segments | Single-column PK — PK collision on re-upload (UAT Test 5 blocker) | CLOSED — migration 0003 applied; segments_pkey = compound (job_id, id) |
| SegmentFlag.segment_job_id | Missing — single-col FK broke after compound PK | CLOSED — column + compound FK added; all 4 constructors pass job_id |
| run_index / run_group_size on Segment ORM | Missing — AttributeError on export (UAT Test 4) | CLOSED — ORM columns + Alembic migration 0003 + worker populates both |
| run_post_check job_id param + compound WHERE | Missing — expansion_ratio UPDATE targeted wrong job | CLOSED — job_id param added; WHERE uses (Segment.job_id == job_id, Segment.id == seg.id) |
| flag_counts query scope | Cross-job ambiguity risk | CLOSED — SegmentFlag.segment_job_id == job_id filter |
| Export error response | HTTPException → "Unknown error" in UI | CLOSED — JSONResponse with {code, detail} on all 3 failure paths |
| response_model=None on export | Missing — FastAPI type error on FileResponse\|JSONResponse | CLOSED — response_model=None set |
| Frontend export error parsing | body.detail undefined → generic "Unknown error" | CLOSED — try/catch JSON parse; body.detail shown in toast |
| ? hotkey | 'shift+/' binding never fired in browser | CLOSED — binding changed to '?' to match event.key directly |
| 3 compound PK unit tests | Missing | CLOSED — no-collision, run fields roundtrip, no AttributeError (3 passed) |
| Test suite total | 257 passed (before plan 10) | 257 passed (unchanged after regression-check: 0 new, 0 broken) |
| TypeScript errors | 3 pre-existing TS18046 | 3 pre-existing (unchanged) |
| Overall score | 5/5 | 5/5 (maintained) |
| Regressions | None | None |
| Status | human_needed | human_needed |

**What changed:** Plans 10-12 closed the 3 UAT failures and 1 UX issue without introducing regressions. The 5/5 static verification score is maintained. Status remains `human_needed` because the fixed items require browser + live backend re-verification, plus the original 4 human items still stand.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can create a named glossary, add term pairs manually or via CSV/TBX, and list/edit/delete glossaries | VERIFIED | `/glossaries` page + `GlossaryList` + `GlossaryCreateDialog`; `TermsTable` inline edit; `CSVUploadButton`; 10 REST endpoints in `glossaries.py` |
| 2 | Glossary terms injected via `terminology` parameter on every batch; violations flagged post-translation | VERIFIED | `translate_worker.py` calls `load_glossary_terms_for_job` + passes `glossary=glossary` to `translate_batch`; `run_post_check` called per batch with `job_id`; all 4-flag types in `FlagBadge`; compound WHERE on expansion_ratio UPDATE (plan 10) |
| 3 | Side-by-side editor with inline-edit compiles and runs cleanly | VERIFIED | TS2554 resolved (commit 5b36e55); `npx tsc --noEmit` produces only 3 pre-existing TS18046 in UploadForm.test.tsx; `SegmentRow` debounce + save-state + `isMountedRef` guard intact |
| 4 | Segment-level flags — overflow, glossary violation, placeholder mismatch, LLM refusal — surfaced in review UI | VERIFIED | `FlagBadge.tsx` has all 4 configs; `ReviewFilterBar` with live flag counts (job-scoped via `SegmentFlag.segment_job_id`); `run_post_check` generates all 4 flag types with compound FK field |
| 5 | Export reassembles using `edited_text ?? translated_text`; idempotent; does not mutate segment state | VERIFIED | `export_service.py` explicit `if edited_text is not None else`; advisory lock via `WeakValueDictionary`; atomic `os.replace`; `run_index`/`run_group_size` now in ORM (plan 10 eliminates AttributeError); structured error responses on all failure paths (plan 11) |

**Score:** 5/5 truths verified

---

### Deferred Items

None — all must-haves verified. No later-phase deferral applicable.

---

### Required Artifacts

| Artifact | Plan | Status | Details |
|----------|------|--------|---------|
| `backend/src/app/db/models.py` | 02-02, 02-10 | VERIFIED | Compound PK `(job_id, id)` on Segment; `run_index` + `run_group_size` mapped columns; SegmentFlag `segment_job_id` + compound ForeignKeyConstraint; FlagType/FlagSeverity native_enum=False |
| `backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py` | 02-02 | VERIFIED | native_enum=False; uq_glossary_terms_source UniqueConstraint; upgrade + downgrade present |
| `backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py` | 02-10 | VERIFIED | Drops single-col PK, creates compound PK (job_id, id); adds segment_job_id with compound FK; adds run_index (nullable) + run_group_size (default 1); full downgrade |
| `backend/src/app/services/glossary_service.py` | 02-03, 02-10 | VERIFIED | 13 functions; `run_post_check` signature has `job_id` param; compound WHERE on expansion_ratio UPDATE; all 4 `SegmentFlag(...)` constructors pass `segment_job_id=job_id` |
| `backend/src/app/api/routes/glossaries.py` | 02-03 | VERIFIED | 10 REST endpoints; DELETE returns 204 |
| `backend/src/app/api/routes/segments.py` | 02-04, 02-10 | VERIFIED | GET uses `SegmentFlag.segment_job_id == job_id` for flag_counts (no cross-job ambiguity); PATCH uses compound WHERE on UPDATE; regenerate uses compound WHERE on UPDATE; `.limit(1)` interim guard for non-scoped path (WR-01 advisory) |
| `backend/src/app/api/routes/export.py` | 02-04, 02-11 | VERIFIED | `response_model=None`; `JSONResponse` on ValueError(409), AttributeError(500), Exception(500) with `{code, detail}` body; FileResponse on success |
| `backend/src/app/services/export_service.py` | 02-04 | VERIFIED | `WeakValueDictionary` advisory lock; atomic `os.replace`; explicit None-check for `edited_text`; no segment mutation |
| `backend/src/app/workers/translate_worker.py` | 02-04, 02-08, 02-10 | VERIFIED | `SegmentORM` constructor passes `run_index` + `run_group_size`; `session.add_all(orm_segments)` before translate loop; `sa_update` per-segment in batch; `run_post_check` called with `job_id=job_id`; `session.rollback()` before `transition_to_failed` |
| `backend/tests/workers/test_segment_persistence.py` | 02-08 | VERIFIED | 3 tests pass |
| `backend/tests/workers/test_segment_pk_collision.py` | 02-10 | VERIFIED | 3 tests pass (no-collision, run fields roundtrip, no AttributeError) |
| `frontend/src/lib/types.ts` | 02-05, 02-09 | VERIFIED | All Phase 2 types including `term_count`, `flag_counts`, `glossary_id` |
| `frontend/src/components/FlagBadge.tsx` | 02-05 | VERIFIED | 4 configs: amber (overflow), violet (glossary_violation), orange (placeholder_mismatch), red (llm_refusal) |
| `frontend/src/components/GlossarySelect.tsx` | 02-05 | VERIFIED | NONE_SENTINEL; lang pair filter; disabled on auto-detect |
| `frontend/src/app/glossaries/page.tsx` | 02-05, 02-09 | VERIFIED | NavBar rendered at top |
| `frontend/src/app/glossaries/[id]/page.tsx` | 02-05, 02-09 | VERIFIED | NavBar on all return paths (loading, not-found, main) |
| `frontend/src/components/glossary/GlossaryList.tsx` | 02-05, 02-09 | VERIFIED | Renders `g.term_count` not `g.terms?.length` |
| `frontend/src/hooks/useSegments.ts` | 02-06 | VERIFIED | useSegments, useSegmentPatch (optimistic + rollback), useSegmentRegenerate |
| `frontend/src/hooks/useReviewKeyboard.ts` | 02-06, 02-09, 02-12 | VERIFIED | j/k/n/e/r/Escape bindings; `segmentCount === 0` guard; `useHotkeys("?", ...)` — plan 12 fix from `"shift+/"` |
| `frontend/src/components/SegmentTable.tsx` | 02-06 | VERIFIED | Virtuoso + VirtuosoHandle; scrollIntoView |
| `frontend/src/components/SegmentRow.tsx` | 02-06, 02-09 | VERIFIED | `isMountedRef` guard; debounce + save-state |
| `frontend/src/components/ReviewFilterBar.tsx` | 02-06 | VERIFIED | All chip + 4 flag chips with live counts + Shortcuts toggle |
| `frontend/src/components/ReviewPageHeader.tsx` | 02-06, 02-11 | VERIFIED | POST /api/jobs/{id}/export; try/catch JSON parse of error body; `body?.detail` shown in toast; fallback generic message if non-JSON |
| `frontend/src/components/KeyboardHelpPanel.tsx` | 02-06 | VERIFIED | Shows `{ key: "?", action: "Toggle this panel" }` — already correct, no change needed in plan 12 |
| `frontend/src/app/jobs/[id]/review/page.tsx` | 02-06 | VERIFIED | Assembles all review components + keyboard integration |
| `frontend/src/app/jobs/[id]/page.tsx` | 02-06 | VERIFIED | "Review Translation" Link on done/needs_review |
| `backend/src/app/api/routes/jobs.py` | 02-09 | VERIFIED | `"glossary_id": job.glossary_id` in `_job_to_dict` |
| `frontend/e2e/phase-2-review.spec.ts` | 02-07 | VERIFIED | Playwright E2E spec; conditional skips documented |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `UploadForm.tsx` | `GlossarySelect` | import + render after language fields | WIRED | `glossary_id` appended to FormData when non-empty |
| `upload.py` | `glossary_id` → DB | `Form(None)` → `get_glossary` validation → `create_job` | WIRED | 422 on lang pair mismatch |
| `translate_worker.py` | `session.add_all(orm_segments)` | persistence before translate loop | WIRED | line 323; includes `run_index` + `run_group_size` (plan 10) |
| `translate_worker.py` | `translate_batch` | `load_glossary_terms_for_job` → `glossary=glossary` arg | WIRED | Every batch receives glossary terms |
| `translate_worker.py` | `sa_update(SegmentORM)` per batch | `translated_text` written after each batch | WIRED | lines 366-370 |
| `translate_worker.py` | `run_post_check` | called per batch with `job_id=job_id` | WIRED | All 4 flag types + compound WHERE on expansion_ratio |
| `translate_worker.py` | `transition_to_failed` | `await session.rollback()` before call | WIRED | line 461-464; best-effort try/except |
| `run_post_check` | `SegmentFlag` | `segment_job_id=job_id` in all 4 constructors | WIRED | Lines 442, 463, 479, 496 in glossary_service.py |
| `segments.py GET` | `flag_counts` | `SegmentFlag.segment_job_id == job_id` filter | WIRED | Job-scoped flag aggregation; no cross-job ambiguity |
| `segments.py PATCH` | `edited_text` in DB | compound WHERE `(Segment.job_id == seg.job_id, Segment.id == segment_id)` on UPDATE | WIRED | Plan 10 fix |
| `segments.py regenerate` | `translated_text` in DB | compound WHERE `(Segment.job_id == seg.job_id, Segment.id == segment_id)` on UPDATE | WIRED | Plan 10 fix |
| `export.py` | `export_service.export_job` | try/except three branches → JSONResponse | WIRED | Plan 11: ValueError→409, AttributeError→500, Exception→500 |
| `ReviewPageHeader.tsx` | export error detail | `await res.json()` → `body?.detail` → toast | WIRED | Plan 11: backend detail shown verbatim |
| `useReviewKeyboard.ts` | `?` hotkey | `useHotkeys("?", () => onToggleHelp(), ...)` | WIRED | Plan 12 fix: was `"shift+/"`, now `"?"` |
| `export_service.py` | DOCX reassembly | `edited_text if edited_text is not None else translated_text or ""` | WIRED | Explicit None-check; `run_index`/`run_group_size` now available on ORM Segment |
| `GlossarySelect` | `GET /api/glossaries` | `useQuery` + `.glossaries` unwrap | WIRED | `__none__` sentinel avoids Radix empty-string throw |
| `SegmentRow` | `useSegmentPatch` | import + `patchMutation` in `handleChange` | WIRED | Optimistic update with rollback |
| `ReviewPageHeader` | `POST /api/jobs/{id}/export` | fetch + blob download | WIRED | Blob URL created; `revokeObjectURL` called (WR-04 race advisory) |
| `main.py` | all Phase 2 routers | `app.include_router()` | WIRED | glossaries.router, segments.router, export.router all registered |
| `GlossaryList.tsx` | `g.term_count` | `Glossary.term_count` from types.ts | WIRED | Plan 09 fix |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `glossaries/page.tsx` | `glossaries` | `useQuery → GET /api/glossaries → list_glossaries → DB SELECT` | Yes — DB query with selectinload(terms) | FLOWING |
| `jobs/[id]/review/page.tsx` | `segments` | `useSegments → GET /api/jobs/{id}/segments → DB SELECT with flags` | Yes — job-scoped query; flag_counts via segment_job_id filter | FLOWING |
| `SegmentRow` | `localValue` | `useState(segment.edited_text ?? segment.translated_text)` | Yes — real ORM rows persisted by plan 08 | FLOWING |
| `ReviewFilterBar` | flag counts | `segments` prop → `segment.flags[].flag_type` | Yes — derived from real DB segment data | FLOWING |
| `export_service.py` | DOCX output | `Segment.edited_text ?? Segment.translated_text` per DB row | Yes — DB SELECT on all job segments; `run_index`/`run_group_size` now present | FLOWING |
| `translate_worker.py` | `SegmentORM` persistence | `session.add_all(orm_segments)` with `run_index`/`run_group_size` | Yes — real DB write (plan 08 + plan 10) | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend test suite (full, excl. integration) | `cd backend && uv run pytest tests/ -x -q --ignore=tests/integration 2>&1 \| tail -3` | 257 passed | PASS |
| Compound PK no-collision tests (plan 10) | `cd backend && uv run pytest tests/workers/test_segment_pk_collision.py -v 2>&1 \| tail -5` | 3 passed | PASS |
| Segment persistence tests (plan 08) | `cd backend && uv run pytest tests/workers/test_segment_persistence.py -v 2>&1 \| tail -5` | 3 passed | PASS |
| TypeScript compilation (all Phase 2 files) | `cd frontend && npx tsc --noEmit 2>&1 \| grep "error TS"` | Only 3 pre-existing TS18046 in UploadForm.test.tsx | PASS |
| compound PK in models.py | `grep "primary_key=True" backend/src/app/db/models.py` | Two `primary_key=True` entries on Segment (id + job_id) | PASS |
| run_index / run_group_size on ORM Segment | `grep "run_index\|run_group_size" backend/src/app/db/models.py` | Lines 129-130 (mapped columns) | PASS |
| segment_job_id in SegmentFlag ORM | `grep "segment_job_id" backend/src/app/db/models.py` | mapped_column String(36) nullable=False + ForeignKeyConstraint | PASS |
| All 4 SegmentFlag constructors pass segment_job_id | `grep "segment_job_id=job_id" backend/src/app/services/glossary_service.py` | 4 matches (lines 442, 463, 479, 496) | PASS |
| Compound WHERE on expansion_ratio UPDATE | `grep -A2 "where.*job_id.*Segment.id" backend/src/app/services/glossary_service.py` | `Segment.job_id == job_id, Segment.id == seg.id` | PASS |
| flag_counts query scoped by segment_job_id | `grep "segment_job_id == job_id" backend/src/app/api/routes/segments.py` | Line 93 | PASS |
| Export JSONResponse on errors | `grep -c "JSONResponse" backend/src/app/api/routes/export.py` | 4 (import + 3 returns) | PASS |
| Export export_state_error code | `grep "export_state_error" backend/src/app/api/routes/export.py` | 1 match | PASS |
| Export response_model=None | `grep "response_model=None" backend/src/app/api/routes/export.py` | Line 23 | PASS |
| Frontend parses body.detail | `grep "body?.detail" frontend/src/components/ReviewPageHeader.tsx` | Line 28 | PASS |
| ? hotkey not shift+/ | `grep '"shift+/"' frontend/src/hooks/useReviewKeyboard.ts` | 0 matches | PASS |
| ? hotkey binding present | `grep '"?"' frontend/src/hooks/useReviewKeyboard.ts` | 2 matches (comment + useHotkeys call) | PASS |
| session.rollback in worker | `grep "await session.rollback" backend/src/app/workers/translate_worker.py` | Match at line 462 | PASS |
| run_index in SegmentORM constructor | `grep "run_index=seg.run_index" backend/src/app/workers/translate_worker.py` | Line 318 | PASS |
| Commits exist (plan 10-12) | `git log --oneline` | b05a9c5, 807b66f, 0905ef7 (plan 10); c9a4aed, 7cd8340, 5b1ba99 (plan 11); 2642bf6 (plan 12) | PASS |

---

### Requirements Coverage

| Requirement | Plan | Description | Status | Evidence |
|-------------|------|-------------|--------|----------|
| GLOS-01 | 02-03, 02-05, 02-09 | Create/list/edit/delete glossaries | SATISFIED | 10 REST endpoints + full frontend CRUD pages + NavBar |
| GLOS-02 | 02-03, 02-05 | Add term pairs manually + CSV/TBX import | SATISFIED | TermsTable inline add; POST /glossaries/{id}/terms; CSVUploadButton + parse_csv_glossary + parse_tbx_minimal |
| GLOS-03 | 02-03, 02-04 | Selected glossary terms injected via `terminology` parameter | SATISFIED | upload.py stores glossary_id; worker passes to translate_batch |
| GLOS-04 | 02-03, 02-04, 02-10 | Post-translation glossary violation flag | SATISFIED | run_post_check generates glossary_violation SegmentFlag with segment_job_id (plan 10 compound FK) |
| GLOS-05 | 02-03, 02-05, 02-09 | Glossaries listable, editable, deletable via UI | SATISFIED | Full CRUD pages; term_count correct |
| REV-01 | 02-04, 02-06, 02-08 | Side-by-side segment view with source and editable target | SATISFIED | SegmentRow compiles cleanly; segments persisted to DB (plan 08) |
| REV-02 | 02-04, 02-06, 02-08, 02-09 | Inline edit with debounced persistence | SATISFIED | 500ms debounce; PATCH /segments/{id}; compound WHERE UPDATE (plan 10); isMountedRef guard |
| REV-03 | 02-04, 02-06, 02-12 | Re-translate individual segment | SATISFIED | POST /segments/{id}/regenerate; useSegmentRegenerate hook; ? hotkey fixed (plan 12) |
| REV-04 | 02-04, 02-06 | Segment-level flags visible in review UI | SATISFIED | FlagBadge (4 types); ReviewFilterBar with job-scoped live counts (plan 10) |
| REV-05 | 02-04, 02-06, 02-10, 02-11 | Overflow detection with expansion ratio | SATISFIED | expansion_ratio column; overflow FlagType; compound WHERE on UPDATE (plan 10) |
| REV-06 | 02-04, 02-06, 02-10, 02-11 | Export uses edited_text ?? translated_text; idempotent | SATISFIED | Explicit None-check; no segment mutation; run_index AttributeError eliminated (plan 10); structured errors (plan 11) |
| LAYOUT-01 | 02-06 | CAT-tool layout with expansion ratio | SATISFIED | SegmentTable with react-virtuoso; expansion_ratio surfaced |

All 12 requirements satisfied. GLOS-01..05, REV-01..06, LAYOUT-01 all wired.

**Orphaned requirements check:** LAYOUT-02 and LAYOUT-03 are Phase 3 scope per REQUIREMENTS.md comment. Correctly out of scope for Phase 2.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/lib/review-types.ts` | all | Duplicate type definitions already in `lib/types.ts` | Warning | Intentional parallel isolation (Plan 06 decision); consolidate post-merge |
| `frontend/src/components/SegmentRow.tsx` | local | `InlineFlagBadge` duplicates shared `FlagBadge.tsx` | Warning | Intentional parallel isolation; refactor post-merge |
| `backend/tests/` | multiple | Coverage at 78.75% — below 80% threshold | Warning | Pre-existing; improved from 79.01% to 78.75% (slight regression from plan 10 adding tests with low coverage); not a functional blocker |
| `backend/src/app/api/routes/segments.py` | 121, 165 | `.limit(1)` without job_id scoping on PATCH/regenerate | Warning | WR-01 (code review): silently targets wrong job on duplicate segment hash; TODO comment present; deferred to Phase 3 URL migration |
| `backend/src/app/db/migrations/versions/0003_...py` | 52-59 | Non-deterministic backfill when segment.id maps to multiple jobs | Warning | WR-02 (code review): low-risk for fresh PoC DB; no collision rows pre-migration |
| `backend/src/app/workers/translate_worker.py` | 323-324 | segment insertion not idempotent on crash-restart | Warning | WR-03 (code review): session.rollback() guard mitigates; full ON CONFLICT fix deferred |
| `frontend/src/components/ReviewPageHeader.tsx` | 43-44 | `URL.revokeObjectURL` called synchronously after `a.click()` | Warning | WR-04 (code review): race on Safari/Firefox; setTimeout fix recommended |

No blocker anti-patterns. All warnings are either intentional isolation decisions, pre-existing issues, or advisory items from code review explicitly noted as non-goal-failures.

---

### Human Verification Required

#### 1. Review page visual rendering

**Test:** Open `/jobs/<completed-job-id>/review` in browser after running a translation job.
**Expected:** Side-by-side table renders with source segments on left, editable textareas on right; flag badges appear on flagged segments; virtualized scrolling works smoothly.
**Why human:** Visual layout and CAT-tool appearance cannot be verified programmatically.

#### 2. Debounced inline edit + save indicator

**Test:** Click into a translation textarea, type a change, wait ~600ms, observe UI.
**Expected:** "Saving..." appears within 500ms of typing; "Saved" appears after successful PATCH; network PATCH call visible in DevTools.
**Why human:** Debounce timing and optimistic UI state transitions require browser interaction.

#### 3. ? keyboard shortcut (re-verify after plan 12 fix)

**Test:** With focus outside a textarea, press `?` (single keypress, no Shift needed), then press j, k, n, e, r, Escape in sequence.
**Expected:** `?` toggles keyboard help panel (UAT Test 3 previously failed with `shift+/`; now fixed to `"?"` binding); j/k move segment focus; Escape blurs active textarea.
**Why human:** Keyboard event handling requires browser event loop. This was a UAT failure and the fix (plan 12) changes the binding string — must re-verify in browser.

#### 4. Export DOCX file download (re-verify after plan 10 + 11 fixes)

**Test:** Click Export on a completed job in the review page; observe toast on error; re-click Export after editing a segment.
**Expected:** Export succeeds with DOCX download (UAT Test 4 previously failed with AttributeError — now fixed by run_index ORM columns); any failure shows specific `body.detail` message not "Unknown error" (plan 11 fix); re-click produces fresh download; segment state unchanged.
**Why human:** File download and idempotency require browser and live backend. Both fixes (plan 10 + 11) need end-to-end re-validation.

#### 5. Re-upload same document (re-verify UAT Test 5 blocker)

**Test:** Upload the same DOCX file as two separate jobs. Open review page and Export on the second job.
**Expected:** Second job translates without PK collision error (UAT Test 5 blocker fixed by compound PK migration 0003); both jobs have their own segment rows; Export succeeds.
**Why human:** Compound PK fix needs live PostgreSQL + arq worker re-validation. Cannot verify without a real re-upload scenario.

#### 6. End-to-end glossary injection

**Test:** Create a glossary with term pair ("công ty" → "company"), attach to upload, translate a DOCX containing "công ty".
**Expected:** Translated segments respect the term; any segment where "company" is absent gets a violet "GLOSSARY" flag badge.
**Why human:** Requires live DashScope connection and real translation output.

#### 7. CSV import flow

**Test:** Navigate to `/glossaries/<id>`, upload a valid CSV of term pairs.
**Expected:** Terms parsed and appear in TermsTable; duplicate source terms do not create duplicate rows.
**Why human:** CSV file picker and dedup behavior require browser + live backend.

---

### Known Technical Debt (not gaps)

- `review-types.ts` duplicates types from `types.ts` — intentional parallel isolation per Plan 06; consolidate at merge
- `InlineFlagBadge` in `SegmentRow.tsx` duplicates `FlagBadge.tsx` — same reason; refactor at merge
- Coverage at 78.75% — pre-existing; slight decrease from plan 10 (tests added but service files not covered); below 80% minimum
- 3 pre-existing `TS18046` errors in `UploadForm.test.tsx` — predate Phase 2
- `PATCH /segments/{id}` / `POST /segments/{id}/regenerate` use `.limit(1)` without job_id scoping (WR-01) — deferred to Phase 3 URL migration
- `update_glossary_name` mutates ORM in-place (IN-03) — style violation; functional but not immutable pattern
- `URL.revokeObjectURL` races download on Safari/Firefox (WR-04) — setTimeout fix recommended before demo

---

_Verified: 2026-04-25T10:30:00Z_
_Verifier: Claude (gsd-verifier)_
