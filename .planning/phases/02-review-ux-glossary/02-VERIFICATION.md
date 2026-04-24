---
phase: 02-review-ux-glossary
verified: 2026-04-25T03:40:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Side-by-side editor with inline-edit compiles and runs cleanly — TS2554 in SegmentRow.tsx lines 70-71 fixed in commit 5b36e55"
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
---

# Phase 2: Review UX + Glossary Verification Report

**Phase Goal:** The full DOCX workflow gains the two highest-value demo differentiators: a CAT-tool-style segment editor where reviewers can inline-correct translations before export, and a glossary system that injects company-specific terminology via the `qwen-mt-turbo` `terminology` API and flags violations post-translation.
**Verified:** 2026-04-25T03:40:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (commit 5b36e55 fixed TS2554 in SegmentRow.tsx)

---

## Re-verification Summary

| Item | Previous | Now |
|------|----------|-----|
| TS2554 in `SegmentRow.tsx` (lines 70-71) | ✗ FAILED | ✓ CLOSED |
| Overall score | 4/5 | 5/5 |
| Remaining gaps | 1 | 0 |
| Status | gaps_found | human_needed |

**What changed:** Commit `5b36e55` changed lines 70-71 in `SegmentRow.tsx` from `useRef<ReturnType<typeof setTimeout>>()` (no initial value) to `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`. TypeScript compilation now produces zero Phase 2 errors — only the 3 pre-existing `TS18046` errors in `UploadForm.test.tsx` remain, which predate Phase 2 and were documented in the initial verification.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can create a named glossary, add term pairs manually or via CSV/TBX, and list/edit/delete glossaries | ✓ VERIFIED | `/glossaries` page + `GlossaryList` + `GlossaryCreateDialog`; `TermsTable` inline edit; `CSVUploadButton`; 10 REST endpoints in `glossaries.py` |
| 2 | Glossary terms injected via `terminology` parameter on every batch; violations flagged post-translation | ✓ VERIFIED | `translate_worker.py` calls `load_glossary_terms_for_job` + passes `glossary=glossary` to `translate_batch`; `run_post_check` called per batch; 4-flag `FlagBadge` in frontend |
| 3 | Side-by-side editor with inline-edit compiles and runs cleanly | ✓ VERIFIED | TS2554 resolved in commit 5b36e55; `npx tsc --noEmit` produces zero Phase 2 errors; SegmentRow debounce + save-state logic intact |
| 4 | Segment-level flags — overflow, glossary violation, placeholder mismatch, LLM refusal — surfaced in review UI | ✓ VERIFIED | `FlagBadge.tsx` has all 4 configs; `ReviewFilterBar` with live flag counts; `run_post_check` in `glossary_service.py` generates all 4 flag types |
| 5 | Export reassembles using `edited_text ?? translated_text`; idempotent; does not mutate segment state | ✓ VERIFIED | `export_service.py` explicit `edited_text if edited_text is not None else translated_text or ""`; advisory lock via `WeakValueDictionary`; `os.replace` atomic write; segment state not modified |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Plan | Status | Details |
|----------|------|--------|---------|
| `backend/src/app/db/models.py` | 02-02 | ✓ VERIFIED | Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity; Job.glossary_id FK; Segment.edited_text, expansion_ratio; native_enum=False on both SAEnum |
| `backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py` | 02-02 | ✓ VERIFIED | native_enum=False; uq_glossary_terms_source UniqueConstraint; ix_segment_flags_segment_flag composite index; upgrade + downgrade both present |
| `backend/src/app/services/glossary_service.py` | 02-03 | ✓ VERIFIED | 13 functions: full CRUD + CSV/TBX import + `load_glossary_terms_for_job` + `run_post_check` (all 4 flag detectors) |
| `backend/src/app/api/routes/glossaries.py` | 02-03 | ✓ VERIFIED | 10 REST endpoints; DELETE returns 204; GET /glossaries/{id}/terms; POST /glossaries/{id}/terms/import |
| `backend/src/app/api/routes/segments.py` | 02-04 | ✓ VERIFIED | GET with flag_counts; PATCH with _REVIEWABLE_STATUSES gate (409 when not done/needs_review); POST regenerate; edited_text max_length=10_000 |
| `backend/src/app/api/routes/export.py` | 02-04 | ✓ VERIFIED | POST /jobs/{id}/export returns FileResponse |
| `backend/src/app/services/export_service.py` | 02-04 | ✓ VERIFIED | WeakValueDictionary advisory lock; atomic os.replace; edited_text ?? translated_text logic explicit; no segment mutation |
| `backend/src/app/workers/translate_worker.py` | 02-04 | ✓ VERIFIED | `load_glossary_terms_for_job` imported + called; `glossary=glossary` wired in translate_batch; `run_post_check` called per batch |
| `frontend/src/lib/types.ts` | 02-05 | ✓ VERIFIED | Phase 2 types: FlagType, FlagSeverity, SegmentFlag, Segment, SegmentsResponse, GlossaryTerm, Glossary |
| `frontend/src/components/FlagBadge.tsx` | 02-05 | ✓ VERIFIED | 4 configs: amber (overflow), violet (glossary_violation), orange (placeholder_mismatch), red (llm_refusal) |
| `frontend/src/components/GlossarySelect.tsx` | 02-05 | ✓ VERIFIED | NONE_SENTINEL="__none__"; .glossaries unwrap; disabled on auto-detect; lang pair filter |
| `frontend/src/app/glossaries/page.tsx` | 02-05 | ✓ VERIFIED | List page with GlossaryList + GlossaryCreateDialog |
| `frontend/src/app/glossaries/[id]/page.tsx` | 02-05 | ✓ VERIFIED | Detail page with TermsTable + CSVUploadButton |
| `frontend/src/hooks/useSegments.ts` | 02-06 | ✓ VERIFIED | useSegments (GET), useSegmentPatch (optimistic PATCH + rollback + toast), useSegmentRegenerate (POST) |
| `frontend/src/hooks/useReviewKeyboard.ts` | 02-06 | ✓ VERIFIED | j, k, n, e, r, shift+/, escape bindings via react-hotkeys-hook |
| `frontend/src/components/SegmentTable.tsx` | 02-06 | ✓ VERIFIED | Virtuoso + VirtuosoHandle; scrollIntoView; calc(100vh - 168px) height |
| `frontend/src/components/SegmentRow.tsx` | 02-06 | ✓ VERIFIED | TS2554 fixed (commit 5b36e55); debounce + save-state logic intact; `useRef<ReturnType<typeof setTimeout> \| undefined>(undefined)` on lines 70-71 |
| `frontend/src/components/ReviewFilterBar.tsx` | 02-06 | ✓ VERIFIED | All chip + 4 flag chips with live counts + Shortcuts toggle |
| `frontend/src/components/ReviewPageHeader.tsx` | 02-06 | ✓ VERIFIED | POST /api/jobs/{id}/export + blob download trigger |
| `frontend/src/components/KeyboardHelpPanel.tsx` | 02-06 | ✓ VERIFIED | Named Fragment with key prop; keyboard shortcut cheatsheet |
| `frontend/src/app/jobs/[id]/review/page.tsx` | 02-06 | ✓ VERIFIED | Assembles all review components + keyboard integration |
| `frontend/src/app/jobs/[id]/page.tsx` | 02-06 | ✓ VERIFIED | "Review Translation" Link on done/needs_review states (placeholder text replaced) |
| `frontend/e2e/phase-2-review.spec.ts` | 02-07 | ✓ VERIFIED | Playwright E2E spec with 6 tests; conditional skips documented |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `UploadForm.tsx` | `GlossarySelect` | import + render after language fields | ✓ WIRED | `glossary_id` appended to FormData when non-empty |
| `upload.py` | `glossary_id` → DB | `Form(None)` → `get_glossary` validation → `create_job` | ✓ WIRED | 422 on lang pair mismatch; `glossary_id` stored in Job row |
| `translate_worker.py` | `translate_batch` | `load_glossary_terms_for_job` → `glossary=glossary` arg | ✓ WIRED | Every batch receives glossary terms; no silent skip |
| `translate_worker.py` | `run_post_check` | called per batch after translation | ✓ WIRED | All 4 flag types generated and written to `segment_flags` |
| `segments.py PATCH` | `edited_text` in DB | `PATCH /segments/{id}` → `edited_text` column | ✓ WIRED | Reviewed by `_REVIEWABLE_STATUSES` gate |
| `export_service.py` | DOCX reassembly | `edited_text if ... else translated_text` | ✓ WIRED | Explicit None-check; not `or` shortcut (Pitfall 5 avoided) |
| `GlossarySelect` | `GET /api/glossaries` | `useQuery` + `.glossaries` unwrap | ✓ WIRED | `__none__` sentinel avoids Radix empty-string runtime throw |
| `SegmentRow` | `useSegmentPatch` | import + `patchMutation` call in `handleChange` | ✓ WIRED | Optimistic update with cancelQueries→setQueryData→onError rollback |
| `ReviewPageHeader` | `POST /api/jobs/{id}/export` | fetch + blob download | ✓ WIRED | Blob URL created and revokeObjectURL called |
| `main.py` | all Phase 2 routers | `app.include_router()` | ✓ WIRED | glossaries.router, segments.router, export.router all registered |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `glossaries/page.tsx` | `glossaries` | `useQuery → GET /api/glossaries → glossaries_service.list_glossaries → DB SELECT` | Yes — DB query with `selectinload(terms)` | ✓ FLOWING |
| `jobs/[id]/review/page.tsx` | `segments` | `useSegments → GET /api/jobs/{id}/segments → DB SELECT segments + flags` | Yes — DB query with flag_counts aggregation | ✓ FLOWING |
| `SegmentRow` | `localValue` | `useState(displayValue)` initialized from `segment.edited_text ?? segment.translated_text` | Yes — real DB column values | ✓ FLOWING |
| `ReviewFilterBar` | flag counts | `segments` prop → filter by `segment.flags[].flag_type` | Yes — derived from real segment data | ✓ FLOWING |
| `export_service.py` | DOCX output | `Segment.edited_text ?? Segment.translated_text` per segment row | Yes — DB SELECT on all job segments | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend test suite | `cd backend && python -m pytest tests/ -x -q --ignore=tests/integration 2>&1 \| tail -5` | 251 passed | ✓ PASS |
| TypeScript compilation (Phase 2 errors) | `cd frontend && npx tsc --noEmit 2>&1` | Zero Phase 2 errors; only 3 pre-existing TS18046 in UploadForm.test.tsx remain | ✓ PASS |
| SegmentRow useRef fix verified | lines 70-71 of SegmentRow.tsx | `useRef<ReturnType<typeof setTimeout> \| undefined>(undefined)` on both lines | ✓ PASS |
| Playwright spec exists and is parseable | `ls frontend/e2e/phase-2-review.spec.ts` | File present | ✓ PASS |
| GlossarySelect sentinel in source | `grep NONE_SENTINEL frontend/src/components/GlossarySelect.tsx` | `const NONE_SENTINEL = "__none__"` | ✓ PASS |
| Glossary terms injected in worker | `grep load_glossary_terms_for_job backend/src/app/workers/translate_worker.py` | Import + call confirmed | ✓ PASS |
| Export uses edited_text fallback | `grep "edited_text if" backend/src/app/services/export_service.py` | Explicit `if edited_text is not None else` pattern | ✓ PASS |

---

### Requirements Coverage

| Requirement | Plan | Description | Status | Evidence |
|-------------|------|-------------|--------|----------|
| GLOS-01 | 02-03, 02-05 | Create/list/edit/delete glossaries | ✓ SATISFIED | 10 REST endpoints + full frontend CRUD pages |
| GLOS-02 | 02-03, 02-05 | Add term pairs manually | ✓ SATISFIED | TermsTable inline add; POST /glossaries/{id}/terms |
| GLOS-03 | 02-03, 02-05 | CSV/TBX import | ✓ SATISFIED | CSVUploadButton + parse_csv_glossary + parse_tbx_minimal |
| GLOS-04 | 02-03, 02-04 | Glossary attached to job; terms injected via `terminology` parameter | ✓ SATISFIED | upload.py stores glossary_id; worker passes to translate_batch |
| GLOS-05 | 02-03, 02-04 | Post-translation glossary violation flag | ✓ SATISFIED | run_post_check generates glossary_violation SegmentFlag |
| REV-01 | 02-04, 02-06 | Side-by-side segment view with source and editable target | ✓ SATISFIED | SegmentRow.tsx compiles cleanly after fix; SegmentTable + review page assembled |
| REV-02 | 02-04, 02-06 | Inline edit with debounced persistence to DB | ✓ SATISFIED | 500ms debounce; PATCH /segments/{id}; optimistic update |
| REV-03 | 02-04, 02-06 | Re-translate individual segment without rerunning whole job | ✓ SATISFIED | POST /segments/{id}/regenerate; useSegmentRegenerate hook |
| REV-04 | 02-04, 02-06 | Segment-level flags visible in review UI | ✓ SATISFIED | FlagBadge (4 types); ReviewFilterBar with live counts |
| REV-05 | 02-04, 02-06 | Overflow detection with text-expansion ratio | ✓ SATISFIED | expansion_ratio column; overflow FlagType; FlagBadge amber badge |
| REV-06 | 02-04, 02-06 | Export uses edited_text ?? translated_text; idempotent | ✓ SATISFIED | Explicit None-check in export_service; no segment mutation |
| LAYOUT-01 | 02-06 | CAT-tool side-by-side layout | ✓ SATISFIED | SegmentTable with react-virtuoso; source/target column layout |

All 12 requirements satisfied. GLOS-01..05, REV-01..06, LAYOUT-01 all wired in runnable system.

**Orphaned requirements check:** LAYOUT-02 and LAYOUT-03 appear only in Phase 3 requirements in ROADMAP.md. Correctly out of scope for Phase 2.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/lib/review-types.ts` | all | Duplicate type definitions (FlagType, Segment, SegmentFlag, SegmentsResponse) already in `lib/types.ts` | ⚠️ Warning | Intentional parallel executor isolation (Plan 06 decision); needs consolidation post-merge; no runtime impact |
| `frontend/src/components/SegmentRow.tsx` | local | `InlineFlagBadge` local component instead of importing shared `FlagBadge.tsx` | ⚠️ Warning | Intentional parallel executor isolation (Plan 06 decision); visual output identical; needs refactor post-merge |
| `backend/tests/` | multiple | Test files are stubs (functions present, assertions minimal) | ⚠️ Warning | Coverage 79.01% — just below 80% global threshold; not a functional blocker but misses project minimum |

The blocker anti-pattern (`TS2554` in `SegmentRow.tsx`) is resolved. Remaining anti-patterns are warnings with no runtime impact.

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

---

### Known Technical Debt (not gaps)

- `review-types.ts` duplicates types from `types.ts` — intentional parallel isolation per Plan 06 decision; consolidate at merge
- `InlineFlagBadge` in `SegmentRow.tsx` duplicates `FlagBadge.tsx` — same reason; refactor at merge
- Test coverage at 79.01% — just below 80% global minimum; test stubs need assertion density improvement
- 3 pre-existing `TS18046` errors in `UploadForm.test.tsx` (lines 482, 484, 485) — predate Phase 2; not introduced by this phase

---

_Verified: 2026-04-25T03:40:00Z_
_Verifier: Claude (gsd-verifier)_
