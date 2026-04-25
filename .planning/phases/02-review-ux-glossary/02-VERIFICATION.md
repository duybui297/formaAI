---
phase: 02-review-ux-glossary
verified: 2026-04-25T18:00:00Z
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
    - "Visible focus ring: SegmentRow changed from ring-1 ring-violet-200 to ring-2 ring-violet-500 bg-violet-50 (plan 13, commit 7c8f4f9)"
    - "data-focused attribute added to SegmentRow outer div for programmatic scroll and test selection (plan 13, commit 7c8f4f9)"
    - "ctrl+shift+p additive binding added to useReviewKeyboard (enableOnFormTags: [textarea]) — vscode-style shortcut works from inside textarea; ? binding preserved (plan 13, commit 3126ad6)"
    - "Escape blur via setTimeout(0) — cross-browser reliable, replaces synchronous activeElement.blur() (plan 13, commit 3126ad6)"
    - "KeyboardHelpPanel SHORTCUTS display updated to '? / Ctrl+Shift+P' (plan 13, commit 3126ad6)"
    - "PT Mono replaced by JetBrains Mono with vietnamese subset — all 4 fonts (Inter, Roboto, Montserrat, JetBrains Mono) load vietnamese subset (plan 14, commit 7f7ab21)"
    - "CSS variable --font-pt-mono preserved for backwards compat — SegmentRow.tsx unchanged (plan 14, commit 7f7ab21)"
    - "CLAUDE.md paper-skill font convention updated to document JetBrains Mono (plan 14, commit 0446ee9)"
    - "WR-01 code review fix: onEdit and onRegenerate added to hotkey dep arrays — eliminates stale closure risk (REVIEW-FIX wave 13, commit eb0d049)"
    - "WR-02 code review fix: aria-label='Close keyboard shortcuts panel' added to KeyboardHelpPanel close button (REVIEW-FIX wave 13, commit 1ebac45)"
  gaps_remaining: []
  regressions: []
  advisory_items:
    - "WR-01 (code review, pre-wave13): PATCH/regenerate still use .limit(1) without job_id scoping — silently targets wrong job on duplicate segment hash. Deferred to Phase 3 URL migration. Not a goal failure."
    - "WR-02 (code review, pre-wave13): Migration backfill for segment_job_id is non-deterministic on PK-collision rows. Low-risk for fresh PoC DB. Not a goal failure."
    - "WR-03 (code review, pre-wave13): Worker segment insert not idempotent — crash-restart causes IntegrityError. Addressed by session.rollback() guard; full ON CONFLICT fix deferred. Not a goal failure."
    - "WR-04 (code review, pre-wave13): URL.revokeObjectURL races download on Safari/Firefox — setTimeout fix recommended. Not a goal failure."
    - "IN-01 (code review, pre-wave13): SegmentFlag.segment relationship missing explicit foreign_keys for compound FK. Cosmetic/fragility risk. Not a goal failure."
    - "IN-02 (code review, pre-wave13): test_segment_pk_collision.py tests missing @pytest.mark.asyncio decorator — rely on asyncio_mode=auto. Not a goal failure."
    - "IN-03 (code review, pre-wave13): update_glossary_name mutates ORM object in-place (g.name = name). Style violation per immutability rule. Not a goal failure."
    - "IN-02 (code review, wave13): onToggleHelp not in dep arrays for ? and ctrl+shift+p bindings — safe if parent uses useCallback (stable-ref assumption); left with comment per D-02-17. Not a goal failure."
    - "IN-03 (code review, wave13): WR-03 inline comment in SegmentRow.tsx references stale review-cycle number — cosmetic; does not affect correctness. Not a goal failure."
    - "IN-04 (code review, wave13): '? / Ctrl+Shift+P' label uses Windows/Linux convention; may be slightly misleading on macOS. Acceptable for internal PoC. Not a goal failure."
    - "IN-01 (code review, wave13): inter font variable applied to body while other font vars are on html — inconsistent but functionally harmless. Not a goal failure."
human_verification:
  - test: "Open /jobs/<completed-job-id>/review in browser"
    expected: "Side-by-side table renders with source segments on left, editable textareas on right; flag badges visible on flagged segments"
    why_human: "Visual rendering and CAT-tool layout cannot be verified programmatically"
  - test: "Click into a textarea, type a change, wait 500ms, observe save indicator"
    expected: "Textarea shows 'Saving...' then 'Saved' within ~600ms; network PATCH call appears in DevTools"
    why_human: "Debounce timing and optimistic UI state transitions require browser interaction"
  - test: "UAT Test 3 round 3 — keyboard shortcuts full retest after plans 13 + REVIEW-FIX wave 13"
    expected: "(a) j/k move segment focus AND show visible violet ring + bg-violet-50 on current row; (b) ? (single keypress, no Shift) toggles keyboard help panel; (c) ctrl+shift+p from inside a textarea also toggles panel; (d) Escape blurs the active textarea reliably"
    why_human: "All three sub-issues were addressed by plan 13 and code review fixes — focus ring (ring-2 ring-violet-500), ctrl+shift+p binding with enableOnFormTags, setTimeout(0) Escape blur. Browser re-verification required to confirm UAT Test 3 passes in round 3."
  - test: "Click Export on a completed job in review page"
    expected: "Browser triggers a DOCX file download; re-clicking does not corrupt segment state; any error shows specific detail message not 'Unknown error'"
    why_human: "File download and idempotency require browser and live backend. UAT Test 4 previously passed in round 2 — regression check only."
  - test: "Re-upload the same document as a second job, open its review page, click Export"
    expected: "Second job translates without PK collision error; Export succeeds; review page shows segments"
    why_human: "Compound PK fix (UAT Test 5) passed in round 2 — regression check only. Cannot verify without live PostgreSQL + worker."
  - test: "Verify Vietnamese diacritics render correctly in segment cells after plan 14 font swap"
    expected: "Vietnamese source text (tone marks: ắ, ề, ộ, etc.) renders without tofu or fallback glyph errors in both body text and source-cell monospace font"
    why_human: "JetBrains Mono with vietnamese subset is now loaded; visual font rendering requires browser. This was the side observation from UAT Test 5 round 2 — now addressed by plan 14."
  - test: "Create a glossary via UI, add a term pair, attach to upload, translate a document"
    expected: "Glossary terms appear in job; segments with glossary violations show violet 'GLOSSARY' badge"
    why_human: "End-to-end glossary injection requires live DashScope connection and real translation output"
  - test: "Import a CSV file of term pairs via /glossaries/<id> page"
    expected: "Terms are parsed and appear in the terms table; duplicate terms trigger dedup logic"
    why_human: "CSV import flow and dedup behavior require browser file picker and live backend. UAT Test 6 passed in round 2 — regression check only."
---

# Phase 2: Review UX + Glossary Verification Report

**Phase Goal:** The full DOCX workflow gains the two highest-value demo differentiators: a CAT-tool-style segment editor where reviewers can inline-correct translations before export, and a glossary system that injects company-specific terminology via the `qwen-mt-turbo` `terminology` API and flags violations post-translation.
**Verified:** 2026-04-25T18:00:00Z
**Status:** human_needed
**Re-verification:** Yes — gap closure round 3 (plans 13 + 14 + REVIEW-FIX wave 13), building on plans 08-12 from prior rounds

---

## Re-verification Summary (Round 3: Plans 13 + 14 + REVIEW-FIX wave 13)

Plans 13 and 14 executed after the round-2 verification cycle (`human_needed`, `5/5`). These targeted the remaining UAT Test 3 sub-issues (visible focus ring, keyboard shortcut accessibility from textarea, Escape blur) and the VN font side-observation from UAT Test 5. REVIEW-FIX wave 13 closed two code-review warnings against the plan-13 code.

| Item | Before Round 3 | After Round 3 |
|------|----------------|---------------|
| j/k focus ring visible | ring-1 ring-violet-200 (near-invisible) | CLOSED — ring-2 ring-violet-500 bg-violet-50 (plan 13, commit 7c8f4f9) |
| data-focused attribute on SegmentRow | missing | CLOSED — data-focused="true" on outer div (plan 13, commit 7c8f4f9) |
| Help panel hotkey from textarea | ? only works outside form elements | CLOSED — ctrl+shift+p added with enableOnFormTags: ["textarea"]; ? preserved (plan 13, commit 3126ad6) |
| Escape blur reliability | synchronous blur() may not fire cross-browser | CLOSED — setTimeout(0) pattern (plan 13, commit 3126ad6) |
| KeyboardHelpPanel help text | shows "?" only | CLOSED — now shows "? / Ctrl+Shift+P" (plan 13, commit 3126ad6) |
| WR-01 stale closure (onEdit/onRegenerate) | dep arrays missing onEdit/onRegenerate | CLOSED — [focusedIndex, onEdit] and [focusedIndex, onRegenerate] (wave 13 fix, commit eb0d049) |
| WR-02 aria-label on close button | no aria-label on icon-only button | CLOSED — aria-label="Close keyboard shortcuts panel" (wave 13 fix, commit 1ebac45) |
| Vietnamese font coverage | PT Mono: no VN subset on Google Fonts | CLOSED — JetBrains Mono with vietnamese subset; --font-pt-mono CSS var preserved (plan 14, commit 7f7ab21) |
| CLAUDE.md font convention | PT Mono noted as source-cell font | CLOSED — updated to JetBrains Mono with rationale (plan 14, commit 0446ee9) |
| TypeScript errors | 3 pre-existing TS18046 | 3 pre-existing (unchanged — out of scope) |
| Overall score | 5/5 | 5/5 (maintained) |
| Regressions | None | None |
| Status | human_needed | human_needed (UAT Test 3 round 3 + VN font visual re-verify pending) |

**What changed:** Plans 13 and 14 + REVIEW-FIX wave 13 close all identified static gaps. The 5/5 static verification score is maintained with zero regressions. Status remains `human_needed` because UAT Test 3 (keyboard UX) requires browser round-3 retest of the specific fixes, and VN font rendering requires visual confirmation in browser. Tests 1, 2, 4, 5, 6, 7 all passed in UAT round 2 and are regression-check items only.

**Closure assessment:** This is the final automated verification round for Phase 2. After UAT round 3 confirms Test 3 and VN font, Phase 2 can be marked complete.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can create a named glossary, add term pairs manually or via CSV/TBX, and list/edit/delete glossaries | VERIFIED | `/glossaries` page + `GlossaryList` + `GlossaryCreateDialog`; `TermsTable` inline edit; `CSVUploadButton`; 10 REST endpoints in `glossaries.py` |
| 2 | Glossary terms injected via `terminology` parameter on every batch; violations flagged post-translation | VERIFIED | `translate_worker.py` calls `load_glossary_terms_for_job` + passes `glossary=glossary` to `translate_batch`; `run_post_check` called per batch with `job_id`; all 4-flag types in `FlagBadge`; compound WHERE on expansion_ratio UPDATE (plan 10) |
| 3 | Side-by-side editor with inline-edit compiles and runs cleanly | VERIFIED | TS2554 resolved (commit 5b36e55); `npx tsc --noEmit` produces only 3 pre-existing TS18046 in UploadForm.test.tsx; `SegmentRow` debounce + save-state + `isMountedRef` guard intact; `ring-2 ring-violet-500` focus ring present (plan 13); dep arrays corrected (REVIEW-FIX wave 13) |
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
| `frontend/src/hooks/useReviewKeyboard.ts` | 02-06, 02-09, 02-12, 02-13, REVIEW-FIX-wave13 | VERIFIED | j/k/n/e/r/Escape bindings; `segmentCount === 0` guard; `useHotkeys("?", ...)` — plan 12 fix; `ctrl+shift+p` with `enableOnFormTags: ["textarea"]` — plan 13; `setTimeout(0)` Escape blur — plan 13; `[focusedIndex, onEdit]` + `[focusedIndex, onRegenerate]` dep arrays — REVIEW-FIX wave 13 |
| `frontend/src/components/SegmentTable.tsx` | 02-06 | VERIFIED | Virtuoso + VirtuosoHandle; scrollIntoView |
| `frontend/src/components/SegmentRow.tsx` | 02-06, 02-09, 02-13 | VERIFIED | `isMountedRef` guard; debounce + save-state; `ring-2 ring-violet-500 bg-violet-50` focus ring; `data-focused` attribute — plan 13 |
| `frontend/src/components/ReviewFilterBar.tsx` | 02-06 | VERIFIED | All chip + 4 flag chips with live counts + Shortcuts toggle |
| `frontend/src/components/ReviewPageHeader.tsx` | 02-06, 02-11 | VERIFIED | POST /api/jobs/{id}/export; try/catch JSON parse of error body; `body?.detail` shown in toast; fallback generic message if non-JSON |
| `frontend/src/components/KeyboardHelpPanel.tsx` | 02-06, 02-13, REVIEW-FIX-wave13 | VERIFIED | Shows `{ key: "? / Ctrl+Shift+P", action: "Toggle this panel" }` — updated plan 13; `aria-label="Close keyboard shortcuts panel"` on close button — REVIEW-FIX wave 13 |
| `frontend/src/app/jobs/[id]/review/page.tsx` | 02-06 | VERIFIED | Assembles all review components + keyboard integration |
| `frontend/src/app/jobs/[id]/page.tsx` | 02-06 | VERIFIED | "Review Translation" Link on done/needs_review |
| `frontend/src/app/layout.tsx` | 02-06, 02-14 | VERIFIED | Inter/Roboto/Montserrat/JetBrains Mono all load vietnamese subset; `--font-pt-mono` CSS var assigned to JetBrains Mono for backwards compat |
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
| `useReviewKeyboard.ts` | `ctrl+shift+p` hotkey | `useHotkeys("ctrl+shift+p", ..., { enableOnFormTags: ["textarea"] })` | WIRED | Plan 13: vscode-style binding works from inside textarea |
| `useReviewKeyboard.ts` | Escape blur | `setTimeout(() => el.blur(), 0)` | WIRED | Plan 13: cross-browser reliable via setTimeout(0) |
| `useReviewKeyboard.ts` | `e` hotkey dep array | `[focusedIndex, onEdit]` | WIRED | REVIEW-FIX wave 13: stale closure risk eliminated |
| `useReviewKeyboard.ts` | `r` hotkey dep array | `[focusedIndex, onRegenerate]` | WIRED | REVIEW-FIX wave 13: stale closure risk eliminated |
| `SegmentRow` | focus ring | `ring-2 ring-violet-500 bg-violet-50` when isFocused | WIRED | Plan 13: visible violet ring + bg tint replaces near-invisible ring-1 ring-violet-200 |
| `SegmentRow` | `data-focused` attr | `data-focused={isFocused ? "true" : undefined}` | WIRED | Plan 13: programmatic scroll-to and test selection |
| `KeyboardHelpPanel` | close button accessibility | `aria-label="Close keyboard shortcuts panel"` | WIRED | REVIEW-FIX wave 13: screen reader accessible |
| `layout.tsx` | JetBrains Mono | `JetBrains_Mono({ subsets: ["latin", "vietnamese"], variable: "--font-pt-mono" })` | WIRED | Plan 14: VN diacritics covered; CSS var preserved for SegmentRow.tsx |
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
| ring-2 ring-violet-500 focus ring | `grep "ring-2 ring-violet-500 bg-violet-50" frontend/src/components/SegmentRow.tsx` | 1 match (line 136) | PASS |
| data-focused attr on SegmentRow | `grep "data-focused" frontend/src/components/SegmentRow.tsx` | 1 match on outer div | PASS |
| ring-1 ring-violet-200 removed | `grep "ring-1 ring-violet-200" frontend/src/components/SegmentRow.tsx` | 0 matches | PASS |
| ctrl+shift+p with enableOnFormTags | `grep "ctrl+shift+p" frontend/src/hooks/useReviewKeyboard.ts` | 1 match with enableOnFormTags: ["textarea"] | PASS |
| setTimeout Escape blur | `grep "setTimeout" frontend/src/hooks/useReviewKeyboard.ts` | 1 match inside escape handler | PASS |
| 8 useHotkeys calls total | `grep -c "useHotkeys" frontend/src/hooks/useReviewKeyboard.ts` | 8 (j, k, n, e, r, ?, ctrl+shift+p, escape) | PASS |
| onEdit in e-hotkey dep array | `grep "\[focusedIndex, onEdit\]" frontend/src/hooks/useReviewKeyboard.ts` | 1 match | PASS |
| onRegenerate in r-hotkey dep array | `grep "\[focusedIndex, onRegenerate\]" frontend/src/hooks/useReviewKeyboard.ts` | 1 match | PASS |
| aria-label on close button | `grep "aria-label" frontend/src/components/KeyboardHelpPanel.tsx` | 1 match — "Close keyboard shortcuts panel" | PASS |
| ? / Ctrl+Shift+P in shortcuts display | `grep "Ctrl+Shift+P" frontend/src/components/KeyboardHelpPanel.tsx` | 1 match in SHORTCUTS array | PASS |
| JetBrains_Mono import in layout | `grep "JetBrains_Mono" frontend/src/app/layout.tsx` | 2 matches (import + const) | PASS |
| vietnamese subset in layout | `grep -c "vietnamese" frontend/src/app/layout.tsx` | 6 matches (4 subsets + comment refs) | PASS |
| PT_Mono removed from layout | `grep "PT_Mono" frontend/src/app/layout.tsx` | 0 matches | PASS |
| --font-pt-mono CSS var preserved | `grep "\-\-font-pt-mono" frontend/src/app/layout.tsx` | 2 matches (comment + variable) | PASS |
| SegmentRow still uses --font-pt-mono | `grep "font-pt-mono" frontend/src/components/SegmentRow.tsx` | 1 match (unchanged consumer) | PASS |
| compound PK in models.py | `grep "primary_key=True" backend/src/app/db/models.py` | Two primary_key=True entries on Segment (id + job_id) | PASS |
| run_index / run_group_size on ORM Segment | `grep "run_index\|run_group_size" backend/src/app/db/models.py` | Lines 129-130 (mapped columns) | PASS |
| segment_job_id in SegmentFlag ORM | `grep "segment_job_id" backend/src/app/db/models.py` | mapped_column String(36) nullable=False + ForeignKeyConstraint | PASS |
| All 4 SegmentFlag constructors pass segment_job_id | `grep "segment_job_id=job_id" backend/src/app/services/glossary_service.py` | 4 matches (lines 442, 463, 479, 496) | PASS |
| Compound WHERE on expansion_ratio UPDATE | `grep -A2 "where.*job_id.*Segment.id" backend/src/app/services/glossary_service.py` | Segment.job_id == job_id, Segment.id == seg.id | PASS |
| flag_counts query scoped by segment_job_id | `grep "segment_job_id == job_id" backend/src/app/api/routes/segments.py` | Line 93 | PASS |
| Export JSONResponse on errors | `grep -c "JSONResponse" backend/src/app/api/routes/export.py` | 4 (import + 3 returns) | PASS |
| Export response_model=None | `grep "response_model=None" backend/src/app/api/routes/export.py` | Line 23 | PASS |
| Frontend parses body.detail | `grep "body?.detail" frontend/src/components/ReviewPageHeader.tsx` | Line 28 | PASS |
| ? hotkey not shift+/ | `grep '"shift+/"' frontend/src/hooks/useReviewKeyboard.ts` | 0 matches | PASS |
| ? hotkey binding present | `grep '"?"' frontend/src/hooks/useReviewKeyboard.ts` | 2 matches (comment + useHotkeys call) | PASS |
| session.rollback in worker | `grep "await session.rollback" backend/src/app/workers/translate_worker.py` | Match at line 462 | PASS |
| run_index in SegmentORM constructor | `grep "run_index=seg.run_index" backend/src/app/workers/translate_worker.py` | Line 318 | PASS |
| Commits plan 13 + 14 + REVIEW-FIX wave 13 | `git log --oneline \| head -10` | 7c8f4f9 (ring-2 focus ring), 3126ad6 (ctrl+shift+p + setTimeout), 7f7ab21 (JetBrains Mono), eb0d049 (dep arrays WR-01), 1ebac45 (aria-label WR-02) | PASS |

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
| REV-03 | 02-04, 02-06, 02-12, 02-13 | Re-translate individual segment | SATISFIED | POST /segments/{id}/regenerate; useSegmentRegenerate hook; ? hotkey fixed (plan 12); ctrl+shift+p + Escape blur added (plan 13) |
| REV-04 | 02-04, 02-06 | Segment-level flags visible in review UI | SATISFIED | FlagBadge (4 types); ReviewFilterBar with job-scoped live counts (plan 10) |
| REV-05 | 02-04, 02-06, 02-10, 02-11 | Overflow detection with expansion ratio | SATISFIED | expansion_ratio column; overflow FlagType; compound WHERE on UPDATE (plan 10) |
| REV-06 | 02-04, 02-06, 02-10, 02-11 | Export uses edited_text ?? translated_text; idempotent | SATISFIED | Explicit None-check; no segment mutation; run_index AttributeError eliminated (plan 10); structured errors (plan 11) |
| LAYOUT-01 | 02-06 | CAT-tool layout with expansion ratio | SATISFIED | SegmentTable with react-virtuoso; expansion_ratio surfaced; visible focus ring (plan 13) |

All 12 requirements satisfied. GLOS-01..05, REV-01..06, LAYOUT-01 all wired.

**Orphaned requirements check:** LAYOUT-02 and LAYOUT-03 are Phase 3 scope per REQUIREMENTS.md comment. Correctly out of scope for Phase 2.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/lib/review-types.ts` | all | Duplicate type definitions already in `lib/types.ts` | Warning | Intentional parallel isolation (Plan 06 decision); consolidate post-merge |
| `frontend/src/components/SegmentRow.tsx` | local | `InlineFlagBadge` duplicates shared `FlagBadge.tsx` | Warning | Intentional parallel isolation; refactor post-merge |
| `backend/tests/` | multiple | Coverage at 78.75% — below 80% threshold | Warning | Pre-existing; not a functional blocker |
| `backend/src/app/api/routes/segments.py` | 121, 165 | `.limit(1)` without job_id scoping on PATCH/regenerate | Warning | WR-01 (code review): silently targets wrong job on duplicate segment hash; TODO comment present; deferred to Phase 3 URL migration |
| `backend/src/app/db/migrations/versions/0003_...py` | 52-59 | Non-deterministic backfill when segment.id maps to multiple jobs | Warning | WR-02 (code review): low-risk for fresh PoC DB |
| `backend/src/app/workers/translate_worker.py` | 323-324 | Segment insertion not idempotent on crash-restart | Warning | WR-03 (code review): session.rollback() guard mitigates |
| `frontend/src/components/ReviewPageHeader.tsx` | 43-44 | `URL.revokeObjectURL` called synchronously after `a.click()` | Warning | WR-04 (code review): race on Safari/Firefox |
| `frontend/src/hooks/useReviewKeyboard.ts` | 75, 79 | `onToggleHelp` not in dep arrays for ? and ctrl+shift+p | Info | IN-02 (wave13 review): safe if parent uses useCallback; stable-ref assumption documented in comment |
| `frontend/src/components/SegmentRow.tsx` | 112 | Stale review-cycle comment `WR-03` | Info | IN-03 (wave13 review): cosmetic; does not affect correctness |
| `frontend/src/app/layout.tsx` | 46-47 | `inter` variable on `<body>`, other vars on `<html>` | Info | IN-01 (wave13 review): functionally harmless inconsistency |

No blocker anti-patterns. All warnings are intentional isolation decisions, pre-existing issues, or advisory items from code review explicitly noted as non-goal-failures.

---

### Human Verification Required

#### 1. Review page visual rendering

**Test:** Open `/jobs/<completed-job-id>/review` in browser after running a translation job.
**Expected:** Side-by-side table renders with source segments on left, editable textareas on right; flag badges appear on flagged segments; virtualized scrolling works smoothly.
**Why human:** Visual layout and CAT-tool appearance cannot be verified programmatically. Passed in UAT round 2 — regression check.

#### 2. Debounced inline edit + save indicator

**Test:** Click into a translation textarea, type a change, wait ~600ms, observe UI.
**Expected:** "Saving..." appears within 500ms of typing; "Saved" appears after successful PATCH; network PATCH call visible in DevTools.
**Why human:** Debounce timing and optimistic UI state transitions require browser interaction. Passed in UAT round 2 — regression check.

#### 3. Keyboard shortcuts — UAT round 3 (primary open item)

**Test:** With focus outside a textarea, press `?` (single keypress, no Shift), then press `Ctrl+Shift+P` from inside a textarea. Navigate with j/k and observe row highlight. Press Escape while a textarea has focus.
**Expected:**
- `?` toggles keyboard help panel (plain keypress, no modifier needed)
- `Ctrl+Shift+P` toggles help panel from inside a textarea (plan 13: `enableOnFormTags: ["textarea"]`)
- j/k navigation shows a clearly visible violet ring + bg-violet-50 on the current row (plan 13: `ring-2 ring-violet-500 bg-violet-50`)
- Escape blurs the active textarea reliably (plan 13: `setTimeout(0)` pattern)
**Why human:** All three sub-issues from UAT round 2 Test 3 were addressed by plan 13 (commits 7c8f4f9, 3126ad6) and REVIEW-FIX wave 13 (commits eb0d049, 1ebac45). This is the critical UAT round 3 retest that unblocks phase completion.

#### 4. Export DOCX file download

**Test:** Click Export on a completed job in the review page; observe toast on error; re-click Export after editing a segment.
**Expected:** Export succeeds with DOCX download; any failure shows specific `body.detail` message; re-click produces fresh download; segment state unchanged.
**Why human:** Passed in UAT round 2 — regression check only.

#### 5. Re-upload same document

**Test:** Upload the same DOCX file as two separate jobs. Open review page and Export on the second job.
**Expected:** Second job translates without PK collision error; both jobs have separate segment rows; Export succeeds.
**Why human:** Passed in UAT round 2 — regression check only. Cannot verify without live PostgreSQL + arq worker.

#### 6. Vietnamese diacritics rendering — UAT round 3 item

**Test:** Open a job with Vietnamese source text in the review page. Check segment cells and body text.
**Expected:** Vietnamese tone marks (ắ, ề, ộ, ước, etc.) render correctly with no tofu or glyph substitution errors. Both Roboto (body), Montserrat (headings), and JetBrains Mono (source cells) should display Vietnamese correctly.
**Why human:** Plan 14 swapped PT Mono for JetBrains Mono with the `vietnamese` subset. All four fonts in `layout.tsx` now load `vietnamese`. Visual rendering requires browser — was a side observation in UAT Test 5 round 2, now addressed.

#### 7. End-to-end glossary injection

**Test:** Create a glossary with term pair ("công ty" → "company"), attach to upload, translate a DOCX containing "công ty".
**Expected:** Translated segments respect the term; any segment where "company" is absent gets a violet "GLOSSARY" flag badge.
**Why human:** Requires live DashScope connection and real translation output.

#### 8. CSV import flow

**Test:** Navigate to `/glossaries/<id>`, upload a valid CSV of term pairs.
**Expected:** Terms parsed and appear in TermsTable; duplicate source terms do not create duplicate rows.
**Why human:** Passed in UAT round 2 — regression check only.

---

### Known Technical Debt (not gaps)

- `review-types.ts` duplicates types from `types.ts` — intentional parallel isolation per Plan 06; consolidate at merge
- `InlineFlagBadge` in `SegmentRow.tsx` duplicates `FlagBadge.tsx` — same reason; refactor at merge
- Coverage at 78.75% — pre-existing; below 80% minimum; not a functional blocker for PoC
- 3 pre-existing `TS18046` errors in `UploadForm.test.tsx` — predate Phase 2
- `PATCH /segments/{id}` / `POST /segments/{id}/regenerate` use `.limit(1)` without job_id scoping (WR-01) — deferred to Phase 3 URL migration
- `update_glossary_name` mutates ORM in-place (IN-03) — style violation; functional but not immutable pattern
- `URL.revokeObjectURL` races download on Safari/Firefox (WR-04) — setTimeout fix recommended before demo
- `onToggleHelp` not in dep arrays for `?` / `ctrl+shift+p` bindings (IN-02 wave13) — safe with stable-ref parent assumption; documented by comment

---

## Phase 2 Closure Status

Phase 2 is the largest, most-iterated phase in this milestone. After 14 execution plans, 2 REVIEW-FIX iterations, and 2+ UAT rounds:

- **5/5 must-haves** verified statically
- **12/12 requirements** satisfied (GLOS-01..05, REV-01..06, LAYOUT-01)
- **All UAT round 2 failures closed:** Tests 1, 2, 4, 5, 6, 7 passed; Test 3 sub-issues addressed by plans 13 + REVIEW-FIX wave 13
- **VN font gap** addressed by plan 14

**Remaining before complete:** UAT round 3 must confirm:
1. Test 3 (keyboard UX) passes with the plan 13 + REVIEW-FIX wave 13 code
2. VN font renders correctly (plan 14)

No further automated gap closure is anticipated. Phase 2 can be marked complete after UAT round 3 confirmation.

---

_Verified: 2026-04-25T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Round: 3 (re-verification after gap closure plans 13 + 14 + REVIEW-FIX wave 13)_
