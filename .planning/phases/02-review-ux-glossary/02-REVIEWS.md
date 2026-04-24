---
phase: 2
reviewers: [claude]
reviewed_at: 2026-04-24T18:41:33Z
plans_reviewed: [02-01-deps-test-scaffolding-PLAN.md,02-02-db-migration-models-PLAN.md,02-03-glossary-backend-PLAN.md,02-04-segment-export-backend-PLAN.md,02-05-glossary-frontend-PLAN.md,02-06-review-frontend-PLAN.md,02-07-integration-docs-PLAN.md]
---

# Cross-AI Plan Review — Phase 2

## Claude Review

# Phase 2 Plan Review — AI Translation PoC

Caveman mode on, but review needs substance. Writing normal review style per mode rules.

---

## Overall Summary

Plans are thorough, well-sequenced, and leverage Phase 1 patterns correctly. Decision traceability (D-02-XX refs) excellent. Wave structure sound. But multiple **HIGH-severity bugs** will block execution as written: missing migration task in Plan 02, Radix `SelectItem value=""` throw in Plan 05, missing PATCH-term endpoint (frontend calls it, backend doesn't expose it), cross-session test bugs in Plan 01, React Fragment key warning in Plan 06, and a parallel-wave dependency gap between Plans 03/04. Goal achievement likely once bugs fixed; reviewer should block-merge on the HIGH items.

---

## Plan 01 — deps-test-scaffolding

**Summary:** Solid Wave 0 setup. Installs `react-virtuoso@4.18.6` + `react-hotkeys-hook@5.2.4`, adds 4 shadcn components, applies paper tokens, creates 8 backend + 4 frontend test stubs.

**Strengths**
- Late imports in conftest fixtures so models-not-yet-extended doesn't break collection
- `xfail(strict=False)` lets feature plans gradually flip xfail→pass without suite failure
- typeui.sh fallback path documented (CLI tested at v0.1.0, interactive)

**Concerns**

- **[HIGH] Cross-session data invisibility in API stubs.** `test_list_glossaries_filtered_by_pair`, `test_delete_glossary` use `make_glossary` factory (flush-only, no commit) then call `client.get/delete`. The test `client` fixture uses a **different** session; committed data won't be visible to the HTTP handler. These will fail even after Plan 03 lands. Fix: factory must commit OR test must use `client`-scoped session injection pattern (see how Phase 1 test_jobs.py handles this — match that shape).
- **[MEDIUM] `test_post_check.py` stubs use `FakeSeg` class, not DB rows.** `run_post_check` does `update(Segment).where(Segment.id == seg.id)` — silently updates 0 rows in SQLite. Tests only assert flag rows, so they pass, but expansion_ratio write isn't actually exercised. Consider adding one test that creates a real Segment row and asserts expansion_ratio persists.
- **[LOW] `conftest.py` verify command greps for "no tests ran|0 errors"** — ambiguous; pytest `--collect-only` output format varies by version. Use `--co -q` exit code instead.

**Suggestions**
- Add a test that creates a real `Segment` via an extended `make_segment` fixture, so expansion_ratio DB writes are tested (currently untested by stubs)
- Document that `client` fixture must be session-compatible with `make_glossary` (or switch factories to commit)

**Risk:** MEDIUM — HIGH-severity bug on cross-session visibility will surface in Wave 1.

---

## Plan 02 — db-migration-models

**Summary:** Extends `models.py` with Glossary/GlossaryTerm/SegmentFlag, adds migration 0002, adds `expansion_ratio_thresholds` config.

**Strengths**
- `native_enum=False` correctly set (avoids Pitfall 3 from RESEARCH)
- Column-type choices right: `JSON` (not `JSONB`) for SQLite compat; `Float` for ratio
- `ondelete="SET NULL"` on `Job.glossary_id` correctly preserves historical jobs

**Concerns**

- **[HIGH] Task 2 is missing entirely.** Tasks jump from Task 1 (models) to Task 3 (config). Migration file `0002_phase2_glossary_flags.py` is referenced in frontmatter `files_modified`, in `must_haves.artifacts`, in Task 1's verify command, and in `<done>` criteria — but **no task body defines how it's produced**. Executor will either auto-run `alembic revision --autogenerate` (risky — autogenerate misses `UniqueConstraint`, enum native_enum=False, and composite indexes) or fail outright. Fix: insert an explicit Task 2 that hand-writes the migration per RESEARCH Section 6 template.
- **[MEDIUM] No down-revision resolution.** Plan says `down_revision = 'e0e8f781ec72'` but also "(or the actual first migration ID)". Executor must run `alembic heads` first to confirm. Document as an explicit step.
- **[LOW] Plan title claims "Task 2: DB fixtures" in plan 02-02-PLAN per ROADMAP, but task body doesn't include it.** Fixtures landed in Plan 01 conftest instead — acceptable but causes confusion.
- **[LOW] `expansion_thresholds_dict` raises JSONDecodeError on malformed env var at property-access time.** Threat T-02-02-01 calls for startup-time validation via `@field_validator` — not implemented in the action block.

**Suggestions**
- Insert explicit Task 2 with full migration body (don't rely on autogenerate)
- Add `@field_validator` on `expansion_ratio_thresholds` for fail-fast JSON validation
- Add a sanity-check grep in verify: `grep -q "native_enum=False" backend/src/app/db/migrations/versions/0002_*.py`

**Risk:** HIGH — missing migration task body will block Wave 1 entirely.

---

## Plan 03 — glossary-backend

**Summary:** Full glossary CRUD service + routes + CSV/TBX parsers + `run_post_check` + upload extension.

**Strengths**
- `run_post_check` co-located with glossary service (per D-02-07/08) — good cohesion
- CSV parser handles BOM (`utf-8-sig`) and header variants correctly
- TBX parser supports both TBX-Core (`tig`) and TBX-Basic (`ntig/termGrp`)
- Glossary-violation check correctly gates on `src_term in source_text` (avoids false positives where term isn't in source)

**Concerns**

- **[HIGH] `llm_refusal` detector produces high false-positive rate.** `translated.strip() == source.strip()` flags legitimate identical translations (brand names like "AICore", numerics, proper nouns). `len(translated) < 3` flags valid short translations ("yes"/"no"/"OK"/"Có"/"不"). Demo will surface many spurious refusal flags. Fix: only trip refusal if source is ≥ ~8 chars AND identical, OR add a language-pair shouldn't-be-identical heuristic.
- **[HIGH] Missing `PATCH /glossaries/{id}/terms/{term_id}` endpoint.** Plan 05 TermsTable spec says "clicking Pencil replaces row with inline Input fields + Save → PATCH `/api/glossaries/{glossaryId}/terms/{termId}`". Plan 03 only exposes POST/DELETE for terms, no PATCH. Frontend will 404. Add it to Task 2.
- **[HIGH] Parallel-wave dependency gap.** Plan 04 depends_on `["02-02"]`. Plan 04 Task 3 imports `run_post_check` from `glossary_service.py` (created by Plan 03). If Waves execute plans 03 and 04 in parallel, Plan 04's worker edit can land before Plan 03's service file exists → ImportError. Add `"02-03"` to Plan 04's `depends_on`, or serialize.
- **[MEDIUM] `placeholder_mismatch` and `llm_refusal` severity set to `block`** but CONTEXT D-02-09 explicitly says "Phase 2 uses `warn` for all four types". Pick one source of truth — update either CONTEXT or plan.
- **[MEDIUM] `import_csv_terms` uses per-row `flush/rollback` loop.** On PostgreSQL, IntegrityError rolls the whole statement back into aborted state — subsequent flushes fail unless inside a savepoint. RESEARCH flags this; plan mentions the `pg_insert().on_conflict_do_nothing()` alternative as a note but doesn't adopt it. For PoC demo with small CSVs this survives, but flag as tech debt.
- **[MEDIUM] `run_post_check` calls `update(Segment)` inside per-segment loop** — one SQL round-trip per segment for expansion_ratio. For 1000-segment batches this is 1000 statements. Bulk-update with `CASE WHEN` or pre-compute then single UPDATE would be faster. OK for PoC but noted.
- **[LOW] No 413/422 on oversized TBX** in `parse_tbx_minimal` itself — only at route level. `ET.fromstring` on malicious deeply-nested XML could DoS; ElementTree default parser is reasonable but `defusedxml` would be standard hardening.
- **[LOW] `update_glossary_name` service returns `Glossary`, but `rename_glossary_endpoint` in routes expects None→404. Double-check the `if g is None` branch works.** Should be fine since `update_glossary_name` returns None on not-found.

**Suggestions**
- Soften llm_refusal: skip when `len(source.strip()) < 8` OR when source contains only ASCII letters/digits with no language-specific glyphs
- Add `PATCH /glossaries/{id}/terms/{term_id}` route + service function
- Update Plan 04 `depends_on: ["02-02", "02-03"]`
- Resolve severity inconsistency (CONTEXT vs plan)
- Consider `defusedxml.ElementTree` for TBX parsing

**Risk:** HIGH — multiple HIGH-severity issues (llm_refusal FP, missing PATCH, parallel-wave gap).

---

## Plan 04 — segment-export-backend

**Summary:** `export_service.py` with WeakValueDictionary advisory lock, `segments.py` route (GET/PATCH/regenerate), `export.py` route, worker extension.

**Strengths**
- Advisory lock correctly uses mutex-protected `WeakValueDictionary` get-or-create — no race
- `edited_text if is not None else translated_text` honors Pitfall 5 (empty-string edit)
- Export is read-only w.r.t. segment rows (REV-06)
- Status-gate via `_EXPORTABLE_STATUSES` mirrors Phase 1 download pattern

**Concerns**

- **[HIGH] Same parallel-wave dependency gap as Plan 03 above.** Plan 04 imports `load_glossary_terms_for_job` and `run_post_check` from `glossary_service.py` (Plan 03). `depends_on` must include `"02-03"`.
- **[MEDIUM] Regenerate endpoint doesn't validate segment belongs to a reviewable job by ID lineage.** It looks up segment, then looks up segment's job, then checks job status. Good. But PATCH `/segments/{id}` has NO job-state check at all — user can edit segments on a `queued` or `running` job, causing race with the worker writing `translated_text`. Add: `if job.status not in _REVIEWABLE_STATUSES: raise 409`.
- **[MEDIUM] Worker extension inserts `await run_post_check(...)` inside `_translate_one_batch`** but plan says "find exact variable names (`batch_segs`, `translated_map`, `ctx`)". If Phase 1 worker uses different names or scopes session differently, executor has to improvise. This is where plans go wrong. Provide a `grep -n "glossary=None" backend/src/app/workers/translate_worker.py` in `read_first` so executor locates the exact line.
- **[MEDIUM] `export_service.py` saves DOCX directly to final path (`doc.save(output_path)`).** Python-docx `save` isn't atomic; a concurrent reader (e.g., download endpoint) could read a half-written file. Fix: write to `output.docx.tmp`, then `os.replace(tmp, final)`.
- **[LOW] `segments.py` `list_segments` loads all segments for job, no pagination.** RESEARCH resolved this as acceptable for <2000 segments. Add a defensive 413 or hard cap if `len(segments) > 10_000`.
- **[LOW] `translate_batch` signature assumption.** Plan imports `from app.llm.translator import translate_batch` and calls `translate_batch(client=llm_client, segments=[...], source_lang=..., target_lang=..., glossary=...)`. If Phase 1 translator has a different signature (e.g., takes `source_segments` or `batch`), regenerate will NameError/TypeError. `read_first` should grep the signature.
- **[LOW] `request.app.state.llm_client` assumed to exist.** Phase 1 may not set this in lifespan. Plan 04 Task 2 should add a verification or set it in lifespan if missing.

**Suggestions**
- Add `"02-03"` to `depends_on`
- Gate PATCH on `_REVIEWABLE_STATUSES` (same as regenerate)
- Atomic write via tmp+rename in `export_service.export_job`
- Add explicit grep commands in `read_first` for `translate_batch` signature and `glossary=None` line number

**Risk:** MEDIUM-HIGH — parallel-wave gap is blocking; others surface during execution but recoverable.

---

## Plan 05 — glossary-frontend

**Summary:** Types extension, paper fonts in layout, FlagBadge, GlossarySelect, NavBar update, /glossaries pages, TermsTable, CSVUpload, UploadForm extension.

**Strengths**
- Response-shape unwrap (`data.glossaries`) documented as CRITICAL in multiple places — defends against a common bug
- Component analogs map cleanly to Phase 1 counterparts
- Paper font loading via `next/font/google` with CSS variables — no CDN dependency

**Concerns**

- **[HIGH] `<SelectItem value="">` will throw at runtime.** Radix UI Select has an explicit runtime check: `A <Select.Item /> must have a value prop that is not an empty string.` This is in the "None" option of `GlossarySelect`. Fix: use a sentinel like `value="__none__"` and map to `""`/null in `onChange`, OR omit the SelectItem and handle empty-state via placeholder.
- **[HIGH] TermsTable edit path calls `PATCH /api/glossaries/{glossaryId}/terms/{termId}`** — that endpoint does not exist in Plan 03. Either (a) Plan 03 must add PATCH term route, or (b) edit means delete+create (documented as such). Currently silently broken.
- **[MEDIUM] `window.confirm("Delete glossary…")` in GlossaryList violates UI-SPEC** which mandates `DeleteGlossaryDialog` modal with specific copy ("This will permanently delete '{name}'…"). Swap to shadcn Dialog.
- **[MEDIUM] `onCreated: () => void` breaks Phase 1 consumers** if any exist. None mentioned, but document as breaking change in phase summary.
- **[MEDIUM] UploadForm formData appends `glossary_id` only when non-empty** — good. But GlossarySelect `onChange("")` when user picks "None" leaves `glossaryId === ""` → not appended → treated as "no glossary". Semantics correct but depends on Radix behavior after the `value=""` fix.
- **[LOW] GlossaryList Name column spec says link to detail page, but code pattern not shown.** Easy for executor to miss.
- **[LOW] CSVUploadButton resets input via `e.target.value = ""`** — good for re-import of same file. Spec it explicitly.
- **[LOW] No loading/error state for /glossaries/[id] page.** 404 handling not addressed.

**Suggestions**
- Replace `<SelectItem value="">` with sentinel pattern (blocker bug)
- Either add PATCH /terms endpoint in Plan 03 or rewrite TermsTable edit as delete+create
- Replace `window.confirm` with DeleteGlossaryDialog (use UI-SPEC copy verbatim)
- Add explicit `<Link href={`/glossaries/${g.id}`}>{g.name}</Link>` to GlossaryList column

**Risk:** HIGH — two HIGH-severity blockers (Radix throw, missing PATCH endpoint) both will surface immediately on first manual test.

---

## Plan 06 — review-frontend

**Summary:** `useSegments`/`useReviewKeyboard` hooks, SegmentTable (Virtuoso), SegmentRow (debounced), ReviewFilterBar, ReviewPageHeader, KeyboardHelpPanel, /jobs/[id]/review page.

**Strengths**
- TanStack v5 optimistic mutation pattern correct (`cancelQueries` → `setQueryData` → `onError` rollback → `onSettled` invalidate)
- Virtuoso explicit height via `calc(100vh - 168px)` (avoids Pitfall 1)
- `edited_text !== null` explicit check in `displayValue` (Pitfall 5)
- Keyboard hook properly uses `enableOnFormTags: ["textarea"]` only for `escape`

**Concerns**

- **[HIGH] `KeyboardHelpPanel` Fragment-in-map has wrong key placement.**
  ```tsx
  {SHORTCUTS.map(({ key, action }) => (
    <>
      <kbd key={`key-${key}`}>...</kbd>
      <span key={`action-${key}`}>...</span>
    </>
  ))}
  ```
  React requires `key` on the top-level element returned from `map`, not on children. The fragment itself has no key. Fix: `<Fragment key={key}>...</Fragment>` (imported from React). Console error today, may fail lint/CI gate.
- **[HIGH] SegmentRow `saveState` never flips back to "idle" on PATCH error.** `handleChange` sets `saveState = "saving"`; success handler flips to "saved"; onError from `useSegmentPatch` only triggers cache rollback + toast but doesn't touch SegmentRow's local state. Stuck in perpetual "Saving…" until next keystroke. Fix: pass `onError` option to `.mutate()` call that resets `saveState` to "idle".
- **[MEDIUM] Race: `onSettled` invalidates query → refetch → parent re-renders → `useEffect` in SegmentRow overwrites `localValue` if user is mid-typing.** Narrow window but real. Mitigation: skip the `useEffect` overwrite if `saveState === "saving"` (i.e., user is actively editing).
- **[MEDIUM] `editingRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map())` never cleared on job change.** Virtuoso unmounts rows out of viewport → `ref(null)` removes them — but Map entries for stale segments remain. Memory leak over long sessions. Low impact for PoC.
- **[MEDIUM] `useHotkeys("shift+/", ...)`** requires user to hold Shift + press `/`. The Plan 07 E2E test calls `page.press("?")` — Playwright's key parsing may not synthesize the Shift modifier. Verify manually; likely needs `page.press("Shift+/")` instead.
- **[MEDIUM] `useSegmentRegenerate.onSuccess` does `setQueryData` to patch translated_text**, then `onSettled` invalidates and refetches — refetch will overwrite with server truth, which is fine but the optimistic patch is redundant. Minor.
- **[LOW] Filter bar `sticky top-[120px]`** — hardcoded offset. Should match header heights (nav 56 + review header 64 = 120). Confirm numbers line up; drift will cause visual overlap.
- **[LOW] `useHotkeys("?", ...)` listed in UI-SPEC** but Plan 06 binds `shift+/`. These aren't the same key binding in react-hotkeys-hook (though they produce the same physical input). Test manually.
- **[LOW] Export filename regex `/(\.\w+)?$/`** replaces trailing extension including the dot-group. For `"report.docx"` → `"report_translated.docx"`. For `"no_ext_file"` → `"no_ext_file_translated.docx"`. OK. Edge: double-extension files like `"doc.final.docx"` → `"doc.final_translated.docx"` — acceptable.
- **[LOW] SegmentRow uses `onClick={onFocus}` on the row div** — but clicks inside the Textarea will bubble and call `onFocus` too. Currently this just sets focusedIndex, which is fine, but semantic intent mixes "click row to focus" with "click textarea to edit". Stop-propagation on Textarea would be cleaner.

**Suggestions**
- Fix Fragment key: `import { Fragment } from "react"` → `<Fragment key={key}>`
- Add `onError` option in SegmentRow's `.mutate()` call to reset `saveState`
- Guard SegmentRow's `useEffect` with `if (saveState !== "saving")`
- Verify keyboard binding empirically (manual + E2E)

**Risk:** MEDIUM — blockers are small fixes but shipping uncorrected will cause user-visible bugs (stuck "Saving…", console errors).

---

## Plan 07 — integration-docs

**Summary:** Playwright E2E happy-path, REQUIREMENTS/ROADMAP/CLAUDE.md housekeeping, VALIDATION.md population.

**Strengths**
- Conditional test skips (via `test.skip()`) when no completed job exists — resilient
- Full integration flow marked `test.skip` with comment — doesn't block CI
- VALIDATION.md table is comprehensive (23 rows, 7 plans)

**Concerns**

- **[MEDIUM] `page.locator("body").press("?")`** may not trigger `useHotkeys("shift+/", ...)` in Plan 06. Playwright's `press("?")` may synthesize via a different key event than a physical Shift+/. Use `page.press("body", "Shift+Slash")` or confirm empirically.
- **[LOW] `test.skip()` inside an async test function with conditional logic** is a Playwright anti-pattern in some versions — `test.skip()` should be called at test-definition time or via fixture. The in-body `test.skip()` call with early return pattern works but is fragile. Prefer `test.skip(condition, reason)` at top of test.
- **[LOW] ROADMAP.md progress table update** mentions only Phase 2 row (`0/7`) — Phase 3 row should be updated to reflect new plan count (`0/TBD` stays since Phase 3 not planned). OK as-is.
- **[LOW] VALIDATION.md sets `nyquist_compliant: true` before any plan executes** — by design of GSD workflow, but semantically the map describes intent, not reality. Document this.
- **[LOW] CLAUDE.md note is appended but position in file not specified.** Could end up in an odd spot. Specify "under `## Conventions` heading, create `### Frontend` subsection if absent".

**Suggestions**
- Verify keyboard E2E binding empirically; adjust to `Shift+Slash` if needed
- Replace inline `test.skip()` with `test.skip(!completedJob, "no completed job in test env")` at the start of the test
- Pin CLAUDE.md insertion point explicitly

**Risk:** LOW — this plan is documentation + one fragile E2E test. Core workflows covered elsewhere.

---

## Cross-Plan Issues

| Severity | Issue | Affects | Fix |
|---|---|---|---|
| HIGH | Plan 02 missing migration task body | Plan 02 | Add explicit Task 2 hand-writing 0002 migration |
| HIGH | Plan 04 imports from Plan 03 but depends only on 02-02 → parallel-wave race | Plan 04 | Add `"02-03"` to Plan 04 `depends_on` |
| HIGH | Radix `SelectItem value=""` throws | Plan 05 | Use sentinel `__none__` or restructure |
| HIGH | TermsTable PATCH endpoint missing backend-side | Plans 03, 05 | Add PATCH term route to Plan 03 |
| HIGH | `llm_refusal` false-positive rate (identical-source/short-text) | Plan 03 | Gate on source length ≥ 8 or add language-specific heuristic |
| HIGH | Cross-session data invisibility in API test stubs | Plan 01 | Make factories commit OR share session with test client |
| HIGH | SegmentRow "Saving…" stuck on PATCH error | Plan 06 | onError callback resets saveState |
| HIGH | KeyboardHelpPanel Fragment missing `key` | Plan 06 | Use `<Fragment key={key}>` |
| MEDIUM | `placeholder_mismatch`/`llm_refusal` severity (block) contradicts CONTEXT D-02-09 (warn) | Plan 03, CONTEXT | Pick one |
| MEDIUM | PATCH /segments/{id} doesn't check job state → race with worker | Plan 04 | Add job-state gate |
| MEDIUM | Non-atomic DOCX write in export | Plan 04 | Write tmp + os.replace |
| MEDIUM | GlossaryList uses `window.confirm` vs UI-SPEC's DeleteGlossaryDialog | Plan 05 | Use shadcn Dialog |
| MEDIUM | Playwright `press("?")` vs `useHotkeys("shift+/")` | Plans 06, 07 | Verify empirically |

---

## Goal-Backward Achievement Check

| Success Criterion | Plan Coverage | Status |
|---|---|---|
| 1. Create named glossary, add term pairs (manual/CSV/TBX), list/edit/delete via UI | Plans 03 + 05 | ⚠ missing PATCH term endpoint; Radix SelectItem bug blocks UI |
| 2. Glossary passed to qwen-mt-turbo via `terminology`; post-translation violation flags | Plans 03 + 04 worker | ✓ on path; llm_refusal FP rate threatens demo cleanness |
| 3. Side-by-side editor with debounced persist + per-segment regenerate | Plans 04 + 06 | ⚠ Saving-stuck bug; Fragment-key warning; PATCH no job-state gate |
| 4. Segment flags visible; expansion ratio shown | Plans 03 + 04 + 06 | ✓ structurally correct |
| 5. Export reassembles `edited_text ?? translated_text`; idempotent | Plan 04 | ✓ Pitfall 5 honored; ⚠ non-atomic write |

All 5 goals reachable once HIGH issues fixed. Goal 1 has the most blockers in its path.

---

## Risk Assessment

**Overall: MEDIUM-HIGH**

Justification:
- Architecture, decisions, and cross-plan flow are sound. Research quality high.
- Eight HIGH-severity issues span six of seven plans. None are architectural — all are specific bugs/gaps that will surface immediately on execution. Fixable in a single follow-up pass.
- Parallel-wave dependency gap (Plan 04 on Plan 03) is the most dangerous because it's an ordering bug that may not reproduce every run.
- `llm_refusal` false-positive rate is the most demo-reputation-risky issue — flagging "AICore" or "Yes" across a 200-segment document will tank the "look at our quality gates" narrative.

**Recommended gates before execution:**
1. Fix Plan 02 missing migration task (blocks Wave 1)
2. Fix Plan 05 Radix `SelectItem` + add PATCH term endpoint to Plan 03 (blocks Plan 05 manual test)
3. Reserialize Plan 04 on Plan 03 OR merge them (removes parallel-wave hazard)
4. Tighten `llm_refusal` detector (protects demo quality)
5. Fix Plan 06 Fragment key + Saving-state reset (protects UX polish)

All other MEDIUM/LOW issues can ride as follow-ups without blocking execution.

---

## Consensus Summary

Single-reviewer run — no cross-AI consensus to synthesize. Findings above are Claude CLI's independent read.

### Agreed Concerns (reviewer's top HIGH-severity)
1. Plan 02 missing explicit migration-file task (blocks Wave 1).
2. Plan 05 Radix `SelectItem value=""` throw; Plan 03 missing PATCH term endpoint (blocks glossary UI path).
3. Plan 04 file-overlap / parallel-wave hazard with Plan 03 (even though revision added run_post_check to Plan 03).
4. Plan 01 cross-session test fixtures will fail under API client session isolation.
5. `llm_refusal` heuristic (translated==source OR len<3) flags common short terms — demo-risky.

### Divergent Views
N/A (single reviewer).

### Recommended Gates Before `/gsd-execute-phase 2`
1. Fix Plan 02 missing migration task.
2. Fix Plan 05 Radix `SelectItem` + add PATCH `/glossaries/{id}/terms/{term_id}` to Plan 03.
3. Reserialize Plan 04 on Plan 03 (wave 2) OR confirm zero file overlap.
4. Tighten `llm_refusal` detector (exclude short acronyms, proper-noun pass-through).
5. Fix Plan 06 Fragment key + Saving-state reset.
