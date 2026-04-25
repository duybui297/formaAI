---
phase: 02-review-ux-glossary
verified: 2026-04-25T07:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5
  gaps_closed:
    - "Segment ORM rows now persisted to DB before translate loop — review page can display segments (plan 08, commit fdae1d6)"
    - "translated_text written to DB per-segment after each batch (plan 08, commit fdae1d6)"
    - "session.rollback() guard before transition_to_failed prevents stuck-running jobs when run_post_check raises (plan 08, commit fdae1d6)"
    - "NavBar rendered on /glossaries and /glossaries/[id] routes (plan 09, commit 81da5b9)"
    - "GlossaryList renders g.term_count instead of g.terms?.length — terms column no longer shows dash (plan 09, commit 81da5b9)"
    - "GET /jobs/{id} response includes glossary_id field (plan 09, commit 3ea683f)"
    - "useReviewKeyboard j/k hotkeys guard segmentCount === 0 — no Virtuoso scroll to -1 on empty list (plan 09, commit 81da5b9)"
    - "SegmentRow isMountedRef guard prevents stale setSaveState calls on Virtuoso-unmounted rows (plan 09, commit 81da5b9)"
    - "Glossary.term_count, SegmentsResponse.flag_counts, JobProgress.glossary_id added to types.ts (plan 09, commit 3ea683f)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Open /jobs/<completed-job-id>/review in browser"
    expected: "Side-by-side table renders with source segments on left, editable textareas on right; flag badges visible on flagged segments"
    why_human: "Visual rendering and CAT-tool layout cannot be verified programmatically"
  - test: "Click into a textarea, type a change, wait 500ms, observe save indicator"
    expected: "Textarea shows 'Saving...' then 'Saved' within ~600ms; network PATCH call appears in DevTools"
    why_human: "Debounce timing and optimistic UI state transitions require browser interaction"
  - test: "Press j/k/n/e/r/shift+?/Escape in review page (focus outside textarea)"
    expected: "j/k move segment focus; shift+? toggles keyboard help panel; Escape blurs active textarea"
    why_human: "Keyboard shortcut behavior requires browser event loop"
  - test: "Click Export on a completed job in review page"
    expected: "Browser triggers a DOCX file download; re-clicking does not corrupt segment state"
    why_human: "File download and idempotency require browser and live backend"
  - test: "Create a glossary via UI, add a term pair, attach to upload, translate a document"
    expected: "Glossary terms appear in job; segments with glossary violations show violet 'GLOSSARY' badge"
    why_human: "End-to-end glossary injection requires live DashScope connection and real translation output"
  - test: "Import a CSV file of term pairs via /glossaries/<id> page"
    expected: "Terms are parsed and appear in the terms table; duplicate terms trigger dedup logic"
    why_human: "CSV import flow and dedup behavior require browser file picker and live backend"
  - test: "Verify segments appear in review page after running a real translation job end-to-end"
    expected: "Review page shows source and translated segments (not empty); glossary violation badges appear where applicable"
    why_human: "Requires a live translation job to exercise the plan 08 ORM persistence path with real data"
---

# Phase 2: Review UX + Glossary Verification Report

**Phase Goal:** The full DOCX workflow gains the two highest-value demo differentiators: a CAT-tool-style segment editor where reviewers can inline-correct translations before export, and a glossary system that injects company-specific terminology via the `qwen-mt-turbo` `terminology` API and flags violations post-translation.
**Verified:** 2026-04-25T07:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure plans 02-08 and 02-09 (segment persistence, session recovery, and UX polish fixes)

---

## Re-verification Summary (Plans 08 + 09)

Plans 08 and 09 executed after the previous verification cycle (`human_needed`, `5/5`). Both were gap-closure plans targeting runtime bugs and UAT-reported UX issues that the previous static verification could not detect.

| Item | Before Plans 08/09 | After Plans 08/09 |
|------|-------------------|-------------------|
| Segment ORM rows persisted to DB before translate loop | Runtime bug (GAP) | CLOSED — `session.add_all(orm_segments)` at line 321 in `translate_worker.py` |
| translated_text written per-segment after batch | Runtime bug (GAP) | CLOSED — `sa_update(SegmentORM).values(translated_text=translated)` per batch |
| Session recovery (stuck-running jobs) | Runtime bug (GAP) | CLOSED — `await session.rollback()` before `transition_to_failed` |
| NavBar on /glossaries pages | UX gap | CLOSED — NavBar imported and rendered in both glossary pages |
| GlossaryList term count (showed "—") | IN-03 bug | CLOSED — `g.term_count` instead of `g.terms?.length` |
| GET /jobs/{id} includes glossary_id | Missing field | CLOSED — `"glossary_id": job.glossary_id` in `_job_to_dict` |
| Keyboard nav crash on empty filter | WR-02 bug | CLOSED — `if (segmentCount === 0) return` in j/k handlers |
| Stale setSaveState on unmounted SegmentRow | WR-03 memory leak | CLOSED — `isMountedRef` guard in mutation callbacks |
| Type completeness (term_count, flag_counts, glossary_id) | Missing fields | CLOSED — all three added to `types.ts` |
| Overall score | 5/5 | 5/5 (maintained) |
| Regressions | None | None |
| Status | human_needed | human_needed |
| Test suite | 251 passed | 254 passed (+3 new segment persistence tests) |
| TypeScript errors | 3 pre-existing | 3 pre-existing (unchanged) |

**What changed:** Plans 08 and 09 closed 9 runtime gaps and UX issues without introducing any regressions. The 5/5 static verification score is maintained. Status remains `human_needed` because all 6 previous human verification items still require browser + live backend testing.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can create a named glossary, add term pairs manually or via CSV/TBX, and list/edit/delete glossaries | VERIFIED | `/glossaries` page + `GlossaryList` + `GlossaryCreateDialog`; `TermsTable` inline edit; `CSVUploadButton`; 10 REST endpoints in `glossaries.py` |
| 2 | Glossary terms injected via `terminology` parameter on every batch; violations flagged post-translation | VERIFIED | `translate_worker.py` calls `load_glossary_terms_for_job` + passes `glossary=glossary` to `translate_batch`; `run_post_check` called per batch; 4-flag `FlagBadge` in frontend |
| 3 | Side-by-side editor with inline-edit compiles and runs cleanly | VERIFIED | TS2554 resolved in commit 5b36e55; `npx tsc --noEmit` produces zero Phase 2 errors; SegmentRow debounce + save-state logic intact; isMountedRef guard added (plan 09) |
| 4 | Segment-level flags — overflow, glossary violation, placeholder mismatch, LLM refusal — surfaced in review UI | VERIFIED | `FlagBadge.tsx` has all 4 configs; `ReviewFilterBar` with live flag counts; `run_post_check` in `glossary_service.py` generates all 4 flag types |
| 5 | Export reassembles using `edited_text ?? translated_text`; idempotent; does not mutate segment state | VERIFIED | `export_service.py` explicit `edited_text if edited_text is not None else translated_text or ""`; advisory lock via `WeakValueDictionary`; `os.replace` atomic write; segment state not modified |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Plan | Status | Details |
|----------|------|--------|---------|
| `backend/src/app/db/models.py` | 02-02 | VERIFIED | Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity; Job.glossary_id FK; Segment.edited_text, expansion_ratio; native_enum=False on both SAEnum |
| `backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py` | 02-02 | VERIFIED | native_enum=False; uq_glossary_terms_source UniqueConstraint; ix_segment_flags_segment_flag composite index; upgrade + downgrade both present |
| `backend/src/app/services/glossary_service.py` | 02-03 | VERIFIED | 13 functions: full CRUD + CSV/TBX import + `load_glossary_terms_for_job` + `run_post_check` (all 4 flag detectors) |
| `backend/src/app/api/routes/glossaries.py` | 02-03 | VERIFIED | 10 REST endpoints; DELETE returns 204; GET /glossaries/{id}/terms; POST /glossaries/{id}/terms/import |
| `backend/src/app/api/routes/segments.py` | 02-04 | VERIFIED | GET with flag_counts; PATCH with _REVIEWABLE_STATUSES gate (409 when not done/needs_review); POST regenerate; edited_text max_length=10_000 |
| `backend/src/app/api/routes/export.py` | 02-04 | VERIFIED | POST /jobs/{id}/export returns FileResponse |
| `backend/src/app/services/export_service.py` | 02-04 | VERIFIED | WeakValueDictionary advisory lock; atomic os.replace; edited_text ?? translated_text logic explicit; no segment mutation |
| `backend/src/app/workers/translate_worker.py` | 02-04, 02-08 | VERIFIED | `load_glossary_terms_for_job` imported + called; `glossary=glossary` wired in translate_batch; `run_post_check` called per batch; `session.add_all(orm_segments)` before translate loop (plan 08); `sa_update` per-segment in batch; `session.rollback()` before `transition_to_failed` (plan 08) |
| `backend/tests/workers/test_segment_persistence.py` | 02-08 | VERIFIED | 3 tests: persistence count, translated_text non-null, failed-job status; all pass (commit e48088c RED, fdae1d6 GREEN) |
| `frontend/src/lib/types.ts` | 02-05, 02-09 | VERIFIED | Phase 2 types: FlagType, FlagSeverity, SegmentFlag, Segment, SegmentsResponse (+ flag_counts), GlossaryTerm, Glossary (+ term_count), JobProgress (+ glossary_id) |
| `frontend/src/components/FlagBadge.tsx` | 02-05 | VERIFIED | 4 configs: amber (overflow), violet (glossary_violation), orange (placeholder_mismatch), red (llm_refusal) |
| `frontend/src/components/GlossarySelect.tsx` | 02-05 | VERIFIED | NONE_SENTINEL="__none__"; .glossaries unwrap; disabled on auto-detect; lang pair filter |
| `frontend/src/app/glossaries/page.tsx` | 02-05, 02-09 | VERIFIED | List page with GlossaryList + GlossaryCreateDialog; NavBar rendered at top (plan 09) |
| `frontend/src/app/glossaries/[id]/page.tsx` | 02-05, 02-09 | VERIFIED | Detail page with TermsTable + CSVUploadButton; NavBar on all return paths — loading, not-found, main (plan 09) |
| `frontend/src/components/glossary/GlossaryList.tsx` | 02-05, 02-09 | VERIFIED | Renders `g.term_count` (not `g.terms?.length`) — IN-03 fix applied (plan 09) |
| `frontend/src/hooks/useSegments.ts` | 02-06 | VERIFIED | useSegments (GET), useSegmentPatch (optimistic PATCH + rollback + toast), useSegmentRegenerate (POST) |
| `frontend/src/hooks/useReviewKeyboard.ts` | 02-06, 02-09 | VERIFIED | j, k, n, e, r, shift+/, escape bindings; j/k guard `if (segmentCount === 0) return` on both handlers (plan 09, WR-02) |
| `frontend/src/components/SegmentTable.tsx` | 02-06 | VERIFIED | Virtuoso + VirtuosoHandle; scrollIntoView; calc(100vh - 168px) height |
| `frontend/src/components/SegmentRow.tsx` | 02-06, 02-09 | VERIFIED | TS2554 fixed (commit 5b36e55); `isMountedRef` guard on mutation callbacks (plan 09, WR-03); debounce + save-state logic intact |
| `frontend/src/components/ReviewFilterBar.tsx` | 02-06 | VERIFIED | All chip + 4 flag chips with live counts + Shortcuts toggle |
| `frontend/src/components/ReviewPageHeader.tsx` | 02-06 | VERIFIED | POST /api/jobs/{id}/export + blob download trigger |
| `frontend/src/components/KeyboardHelpPanel.tsx` | 02-06 | VERIFIED | Named Fragment with key prop; keyboard shortcut cheatsheet |
| `frontend/src/app/jobs/[id]/review/page.tsx` | 02-06 | VERIFIED | Assembles all review components + keyboard integration |
| `frontend/src/app/jobs/[id]/page.tsx` | 02-06 | VERIFIED | "Review Translation" Link on done/needs_review states (placeholder text replaced) |
| `backend/src/app/api/routes/jobs.py` | 02-09 | VERIFIED | `_job_to_dict` includes `"glossary_id": job.glossary_id` (plan 09) |
| `frontend/e2e/phase-2-review.spec.ts` | 02-07 | VERIFIED | Playwright E2E spec with 6 tests; conditional skips documented |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `UploadForm.tsx` | `GlossarySelect` | import + render after language fields | WIRED | `glossary_id` appended to FormData when non-empty |
| `upload.py` | `glossary_id` → DB | `Form(None)` → `get_glossary` validation → `create_job` | WIRED | 422 on lang pair mismatch; `glossary_id` stored in Job row |
| `translate_worker.py` | `session.add_all(orm_segments)` | persistence before translate loop | WIRED | line 321; `SegmentORM` alias imported (plan 08) |
| `translate_worker.py` | `translate_batch` | `load_glossary_terms_for_job` → `glossary=glossary` arg | WIRED | Every batch receives glossary terms; no silent skip |
| `translate_worker.py` | `sa_update(SegmentORM)` per batch | `translated_text` written after each batch | WIRED | lines 365-367; `sa_update` imported at module level (plan 08) |
| `translate_worker.py` | `run_post_check` | called per batch after translation | WIRED | All 4 flag types generated and written to `segment_flags` |
| `translate_worker.py` | `transition_to_failed` | `await session.rollback()` before call in except handler | WIRED | line 459; best-effort try/except wrap (plan 08) |
| `segments.py PATCH` | `edited_text` in DB | `PATCH /segments/{id}` → `edited_text` column | WIRED | Reviewed by `_REVIEWABLE_STATUSES` gate |
| `export_service.py` | DOCX reassembly | `edited_text if ... else translated_text` | WIRED | Explicit None-check; not `or` shortcut (Pitfall 5 avoided) |
| `GlossarySelect` | `GET /api/glossaries` | `useQuery` + `.glossaries` unwrap | WIRED | `__none__` sentinel avoids Radix empty-string runtime throw |
| `SegmentRow` | `useSegmentPatch` | import + `patchMutation` call in `handleChange` | WIRED | Optimistic update with cancelQueries→setQueryData→onError rollback |
| `ReviewPageHeader` | `POST /api/jobs/{id}/export` | fetch + blob download | WIRED | Blob URL created and revokeObjectURL called |
| `main.py` | all Phase 2 routers | `app.include_router()` | WIRED | glossaries.router, segments.router, export.router all registered |
| `jobs.py _job_to_dict` | `glossary_id` in response | `"glossary_id": job.glossary_id` | WIRED | plan 09 — frontend JobProgress type updated to match |
| `GlossaryList.tsx` | `g.term_count` | `Glossary.term_count` from types.ts | WIRED | plan 09 — renders correct count from list API (not broken terms array) |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `glossaries/page.tsx` | `glossaries` | `useQuery → GET /api/glossaries → glossaries_service.list_glossaries → DB SELECT` | Yes — DB query with `selectinload(terms)` | FLOWING |
| `jobs/[id]/review/page.tsx` | `segments` | `useSegments → GET /api/jobs/{id}/segments → DB SELECT segments + flags` | Yes — DB query with flag_counts aggregation | FLOWING |
| `SegmentRow` | `localValue` | `useState(displayValue)` initialized from `segment.edited_text ?? segment.translated_text` | Yes — real DB column values (ORM rows now persisted by plan 08) | FLOWING |
| `ReviewFilterBar` | flag counts | `segments` prop → filter by `segment.flags[].flag_type` | Yes — derived from real segment data | FLOWING |
| `export_service.py` | DOCX output | `Segment.edited_text ?? Segment.translated_text` per segment row | Yes — DB SELECT on all job segments | FLOWING |
| `translate_worker.py` | `SegmentORM` persistence | `session.add_all(orm_segments)` before translate loop | Yes — real DB write from pipeline dataclass objects (plan 08) | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend test suite (full, excl. integration) | `cd backend && uv run pytest tests/ -x -q --ignore=tests/integration 2>&1 \| tail -3` | 254 passed | PASS |
| New segment persistence tests (plan 08) | `cd backend && uv run pytest tests/workers/test_segment_persistence.py -v 2>&1 \| grep PASSED` | 3 PASSED | PASS |
| TypeScript compilation (all Phase 2 files) | `cd frontend && npx tsc --noEmit 2>&1 \| grep "error TS"` | Only 3 pre-existing TS18046 in UploadForm.test.tsx | PASS |
| SegmentRow useRef fix still intact | lines 70-71 of SegmentRow.tsx | `useRef<ReturnType<typeof setTimeout> \| undefined>(undefined)` on both lines | PASS |
| isMountedRef guard in SegmentRow | `grep "isMountedRef" SegmentRow.tsx` | 6 matches: declaration + cleanup + 2 onSuccess guards + 1 onError guard + reset | PASS |
| segmentCount=0 guard in keyboard hook | `grep "segmentCount === 0" useReviewKeyboard.ts` | 2 matches (j and k handlers) | PASS |
| NavBar on glossaries page | `grep "NavBar" frontend/src/app/glossaries/page.tsx` | Import + render confirmed | PASS |
| NavBar on glossary detail page | `grep "NavBar" frontend/src/app/glossaries/[id]/page.tsx` | 4 matches (import + 3 render paths) | PASS |
| GlossaryList uses term_count | `grep "term_count" frontend/src/components/glossary/GlossaryList.tsx` | `{g.term_count}` on line 55 | PASS |
| Old broken pattern gone | `grep "terms?.length" frontend/src/components/glossary/GlossaryList.tsx` | No match | PASS |
| glossary_id in jobs.py response | `grep "glossary_id" backend/src/app/api/routes/jobs.py` | `"glossary_id": job.glossary_id` on line 50 | PASS |
| session.add_all in worker | `grep "session.add_all" backend/src/app/workers/translate_worker.py` | Match at line 321 | PASS |
| session.rollback in worker | `grep "await session.rollback" backend/src/app/workers/translate_worker.py` | Match at line 459 | PASS |
| Export uses edited_text fallback | `grep "edited_text if" backend/src/app/services/export_service.py` | Explicit `if edited_text is not None else` pattern | PASS |
| Commits exist | `git log --oneline` | e48088c (test RED), fdae1d6 (fix GREEN), 3ea683f (types+backend), 81da5b9 (frontend polish) | PASS |

---

### Requirements Coverage

| Requirement | Plan | Description | Status | Evidence |
|-------------|------|-------------|--------|----------|
| GLOS-01 | 02-03, 02-05, 02-09 | Create/list/edit/delete glossaries | SATISFIED | 10 REST endpoints + full frontend CRUD pages + NavBar fix |
| GLOS-02 | 02-03, 02-05 | Add term pairs manually + CSV/TBX import | SATISFIED | TermsTable inline add; POST /glossaries/{id}/terms; CSVUploadButton + parse_csv_glossary + parse_tbx_minimal |
| GLOS-03 | 02-03, 02-04 | Selected glossary terms injected via `terminology` parameter | SATISFIED | upload.py stores glossary_id; worker passes to translate_batch |
| GLOS-04 | 02-03, 02-04 | Post-translation glossary violation flag | SATISFIED | run_post_check generates glossary_violation SegmentFlag |
| GLOS-05 | 02-03, 02-05, 02-09 | Glossaries listable, editable, deletable via UI | SATISFIED | Full CRUD pages; term_count now shows correctly (not "—") |
| REV-01 | 02-04, 02-06, 02-08 | Side-by-side segment view with source and editable target | SATISFIED | SegmentRow compiles cleanly; segments now persisted to DB (plan 08 unblocks display) |
| REV-02 | 02-04, 02-06, 02-08, 02-09 | Inline edit with debounced persistence to DB | SATISFIED | 500ms debounce; PATCH /segments/{id}; optimistic update; isMountedRef guard (plan 09) |
| REV-03 | 02-04, 02-06 | Re-translate individual segment without rerunning whole job | SATISFIED | POST /segments/{id}/regenerate; useSegmentRegenerate hook |
| REV-04 | 02-04, 02-06 | Segment-level flags visible in review UI | SATISFIED | FlagBadge (4 types); ReviewFilterBar with live counts |
| REV-05 | 02-04, 02-06 | Overflow detection with text-expansion ratio | SATISFIED | expansion_ratio column; overflow FlagType; FlagBadge amber badge |
| REV-06 | 02-04, 02-06 | Export uses edited_text ?? translated_text; idempotent | SATISFIED | Explicit None-check in export_service; no segment mutation |
| LAYOUT-01 | 02-06 | CAT-tool side-by-side layout with expansion ratio | SATISFIED | SegmentTable with react-virtuoso; source/target column layout; expansion_ratio surfaced |

All 12 requirements satisfied. GLOS-01..05, REV-01..06, LAYOUT-01 all wired in runnable system.

**Orphaned requirements check:** LAYOUT-02 and LAYOUT-03 appear only in Phase 3 requirements in ROADMAP.md (explicitly noted in REQUIREMENTS.md comment). Correctly out of scope for Phase 2.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/lib/review-types.ts` | all | Duplicate type definitions (FlagType, Segment, SegmentFlag, SegmentsResponse) already in `lib/types.ts` | Warning | Intentional parallel executor isolation (Plan 06 decision); needs consolidation post-merge; no runtime impact |
| `frontend/src/components/SegmentRow.tsx` | local | `InlineFlagBadge` local component instead of importing shared `FlagBadge.tsx` | Warning | Intentional parallel executor isolation (Plan 06 decision); visual output identical; needs refactor post-merge |
| `backend/tests/` | multiple | Test coverage at 79.38% — below 80% project threshold | Warning | Pre-existing before Phase 2; new tests in plan 08 improved from 79.01% to 79.38%; not a functional blocker |

No blocker anti-patterns remain. All previous blockers resolved.

---

### Human Verification Required

#### 1. Review page visual rendering

**Test:** Open `/jobs/<completed-job-id>/review` in browser after running a translation job.
**Expected:** Side-by-side table renders with source segments on left, editable textareas on right; flag badges (amber/violet/orange/red) appear on flagged segments; virtualized scrolling works smoothly on large documents.
**Why human:** Visual layout and CAT-tool appearance cannot be verified programmatically.

#### 2. Debounced inline edit + save indicator

**Test:** Click into a translation textarea, type a change, wait ~600ms, observe UI.
**Expected:** "Saving..." appears within 500ms of typing; "Saved" appears after successful PATCH; network PATCH call visible in DevTools with the edited text in payload.
**Why human:** Debounce timing and optimistic UI state transitions require browser interaction.

#### 3. Keyboard shortcuts

**Test:** With focus outside a textarea, press j, k, n, e, r, Shift+?, Escape in sequence.
**Expected:** j/k move segment focus (Virtuoso scrollIntoView); Shift+? toggles keyboard help panel; Escape blurs active textarea.
**Why human:** Keyboard event handling requires browser event loop.

#### 4. Export DOCX file download

**Test:** Click Export on a completed job in the review page; re-click Export after editing a segment.
**Expected:** First click triggers DOCX download; re-click produces a fresh download reflecting the edited segment; segment state in review page is unchanged (idempotent).
**Why human:** File download and idempotency require browser and live backend.

#### 5. End-to-end glossary injection

**Test:** Create a glossary with term pair ("công ty" → "company"), attach to upload, translate a DOCX containing "công ty", open review page.
**Expected:** Translated segments respect the term; any segment where "company" is absent gets a violet "GLOSSARY" flag badge in the review UI.
**Why human:** Requires live DashScope connection and real translation output to verify terminology injection and violation detection.

#### 6. CSV import flow

**Test:** Navigate to `/glossaries/<id>`, upload a valid CSV of term pairs.
**Expected:** Terms parsed and appear in TermsTable; duplicate source terms do not create duplicate rows (uq_glossary_terms_source UniqueConstraint enforced).
**Why human:** CSV file picker and dedup behavior require browser + live backend.

#### 7. End-to-end segment persistence verification

**Test:** Run a real translation job (not mocked) end-to-end; open the review page.
**Expected:** Review page displays the translated segments (not empty); glossary violation badges appear on relevant segments if a glossary was attached.
**Why human:** Plan 08 fixes the segment persistence path (which was untested in production runtime prior to the plan). Unit tests confirm the ORM write path but cannot substitute for a real job run through arq + PostgreSQL.

---

### Known Technical Debt (not gaps)

- `review-types.ts` duplicates types from `types.ts` — intentional parallel isolation per Plan 06 decision; consolidate at merge
- `InlineFlagBadge` in `SegmentRow.tsx` duplicates `FlagBadge.tsx` — same reason; refactor at merge
- Test coverage at 79.38% — just below 80% global minimum; test stubs need assertion density improvement (pre-existing)
- 3 pre-existing `TS18046` errors in `UploadForm.test.tsx` (lines 482, 484, 485) — predate Phase 2; not introduced by this phase

---

_Verified: 2026-04-25T07:00:00Z_
_Verifier: Claude (gsd-verifier)_
