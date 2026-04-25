---
phase: 2
slug: review-ux-glossary
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-24
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (backend); vitest + Playwright (frontend, Phase 1 stack) |
| **Config file** | `backend/pyproject.toml` [tool.pytest.ini_options]; `frontend/vitest.config.ts` |
| **Quick run command** | `cd backend && uv run pytest -m "unit or integration" -q` |
| **Full suite command** | `cd backend && uv run pytest --cov=src/app --cov-fail-under=80 && cd ../frontend && pnpm vitest run && pnpm playwright test` |
| **Estimated runtime** | backend ~40s / frontend vitest ~15s / e2e ~90s |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/<touched>/ -q` (scoped quick run)
- **After every plan wave:** Run full suite for that surface (backend pytest or frontend vitest+playwright)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds for scoped quick run

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 01 | 0 | infrastructure | — | Paper tokens in tailwind.config.ts; no secrets | wave-0 | `grep -q '"paper-ink"' frontend/tailwind.config.ts && grep -q '"paper-accent"' frontend/tailwind.config.ts` | tailwind.config.ts | ⬜ pending |
| 02-01-T2 | 01 | 0 | infrastructure | — | make_glossary/make_glossary_term use commit() not flush(); visible across sessions | wave-0 | `uv run --directory backend pytest backend/tests/conftest.py --collect-only -q 2>&1; echo "exit:$?"` | conftest.py | ⬜ pending |
| 02-01-T2-migration | 01 | 0 | infrastructure | — | N/A | wave-0 | `uv run --directory backend alembic upgrade head && uv run --directory backend alembic downgrade -1` | alembic migration | ⬜ pending |
| 02-01-T3 | 01 | 0 | infrastructure | — | xfail stubs only; expansion_ratio test uses real Segment DB row; llm_refusal uses len > 8 heuristic | wave-0 | `uv run --directory backend pytest backend/tests/services/test_post_check.py --collect-only -q 2>&1 \| tail -5` | test_post_check.py | ⬜ pending |
| 02-01-T3-glossary | 01 | 0 | infrastructure | — | xfail stubs include test_update_term and test_update_term_not_found_returns_none | wave-0 | `uv run --directory backend pytest backend/tests/services/test_glossary_service.py --collect-only -q 2>&1 \| tail -5` | test_glossary_service.py | ⬜ pending |
| 02-02-T1 | 02 | 0 | infrastructure | — | SQLite native_enum=False on all SAEnum columns; hand-written (not autogenerate) | wave-0 | `uv run --directory backend alembic upgrade head` | migration file | ⬜ pending |
| 02-02-T2 | 02 | 0 | infrastructure | — | Fixture factories no real external calls | wave-0 | `uv run --directory backend pytest backend/tests/fixtures/ -x -q` | fixture files | ⬜ pending |
| 02-03-T1 | 03 | 1 | GLOS-01, GLOS-02, GLOS-03, GLOS-04, GLOS-05 | T-02-03-01, T-02-03-02 | run_post_check: all 4 flag types use FlagSeverity.warn; llm_refusal heuristic: len > 8 AND identical; min-2-char guard; XML no external entity expand | unit | `uv run --directory backend pytest backend/tests/services/test_glossary_service.py backend/tests/services/test_csv_import.py backend/tests/services/test_tbx_import.py backend/tests/services/test_post_check.py -x -q 2>&1 \| tail -10` | glossary_service.py | ⬜ pending |
| 02-03-T2 | 03 | 1 | GLOS-01, GLOS-02, GLOS-05 | T-02-03-03, T-02-03-04 | GET /glossaries returns {"glossaries":[]} wrapped; 404 not 403 on unknown id | integration | `uv run --directory backend pytest backend/tests/api/test_glossaries.py -x -q 2>&1 \| tail -10` | glossaries.py route | ⬜ pending |
| 02-03-T2-patch | 03 | 1 | GLOS-01, GLOS-05 | T-02-03-03 | PATCH /glossaries/{id}/terms/{term_id} returns updated term; 404 on unknown term_id | integration | `uv run --directory backend pytest backend/tests/services/test_glossary_service.py::test_update_term -x -q 2>&1 \| tail -5` | glossaries.py route | ⬜ pending |
| 02-03-T3 | 03 | 1 | GLOS-01, GLOS-05 | T-02-03-03 | Pair mismatch → 422; no SQL injection via glossary_id FK | integration | `grep -n "glossary_id" backend/src/app/api/routes/upload.py backend/src/app/services/job_service.py` | upload.py, job_service.py | ⬜ pending |
| 02-04-T1 | 04 | 1 | REV-05, REV-06 | T-02-04-03, T-02-04-04 | Advisory lock; edited_text="" respected (Pitfall 5); atomic write (tmp + os.replace); no segment mutation | unit | `uv run --directory backend pytest backend/tests/services/test_export_service.py -x -q 2>&1 \| tail -10` | export_service.py | ⬜ pending |
| 02-04-T2 | 04 | 1 | REV-01, REV-02, REV-04 | T-02-04-01, T-02-04-02 | edited_text max 10000; PATCH /segments/{id} rejects non-reviewable job status (409); regenerate validates job state before LLM call | integration | `uv run --directory backend pytest backend/tests/api/test_segments.py -x -q 2>&1 \| tail -10` | segments.py, export.py | ⬜ pending |
| 02-04-T3 | 04 | 1 | GLOS-03, GLOS-04, LAYOUT-01 | T-02-04-05 | run_post_check imported from glossary_service (NOT defined in worker) | unit | `uv run --directory backend pytest backend/tests/workers/test_worker_glossary.py -x -q 2>&1 \| tail -10 && grep "def run_post_check" backend/src/app/workers/translate_worker.py \| wc -l` | translate_worker.py | ⬜ pending |
| 02-05-T1 | 05 | 2 | GLOS-01, GLOS-05 | — | Phase 2 types appended; Phase 1 exports preserved | unit | `cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 \| head -30` | types.ts, layout.tsx | ⬜ pending |
| 02-05-T2 | 05 | 2 | GLOS-01, GLOS-05 | T-02-05-01 | GlossarySelect uses __none__ sentinel (not value="") on SelectItem to avoid Radix runtime throw; no raw HTML | unit | `cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 \| head -30` | FlagBadge.tsx, GlossarySelect.tsx, NavBar.tsx | ⬜ pending |
| 02-05-T3 | 05 | 2 | GLOS-01, GLOS-02, GLOS-05 | T-02-05-03 | glossaries/page.tsx queryFn extracts .glossaries; GlossaryCreateDialog.onCreated: () => void | unit | `cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 \| head -40` | glossaries pages + components | ⬜ pending |
| 02-06-T1 | 06 | 2 | REV-01, REV-02, REV-04 | — | useSegmentPatch: explicit null check for edited_text (Pitfall 5); no optimistic mutation on regenerate; per-call onError resets saveState to idle | unit | `cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 \| head -30` | useSegments.ts, useReviewKeyboard.ts | ⬜ pending |
| 02-06-T2 | 06 | 2 | REV-01, REV-03 | T-02-05-01 | SegmentRow textarea no raw HTML; flag badge colors match UI-SPEC; KeyboardHelpPanel uses named Fragment import (not <> shorthand) for key prop | unit | `cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 \| head -30` | SegmentTable.tsx, SegmentRow.tsx, ReviewFilterBar.tsx | ⬜ pending |
| 02-06-T3 | 06 | 2 | REV-01, REV-02, REV-04, REV-05 | — | Review page link present on job detail; no navigation regression | unit | `cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 \| head -30` | review/page.tsx, jobs/[id]/page.tsx | ⬜ pending |
| 02-07-T1 | 07 | 3 | REV-01, REV-02, REV-04, REV-05, GLOS-01 | — | E2E: no secrets in spec; test uses env-var base URL | e2e | `cd /home/thu/dev/projects/ai-translation/frontend && pnpm playwright test e2e/phase-2-review.spec.ts --reporter=list 2>&1 \| tail -20` | phase-2-review.spec.ts | ⬜ pending |
| 02-07-T2 | 07 | 3 | infrastructure | — | REQUIREMENTS.md updated; ROADMAP.md 7-plan list; CLAUDE.md conventions added | docs | `grep -q "LAYOUT-02" .planning/REQUIREMENTS.md && grep -q "Phase 3" .planning/REQUIREMENTS.md` | REQUIREMENTS.md, ROADMAP.md, CLAUDE.md | ⬜ pending |
| 02-07-T3 | 07 | 3 | infrastructure | — | nyquist_compliant: true set in this file | docs | `grep -q "nyquist_compliant: true" .planning/phases/02-review-ux-glossary/02-VALIDATION.md` | 02-VALIDATION.md | ⬜ pending |
| 02-08-T1 | 08 | 8 | REV-01, REV-04, GLOS-04 | T-02-08-01 | Tests run RED before implementation; no DashScope calls; SQLite in-memory | unit (TDD RED) | `cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/workers/test_segment_persistence.py -x -q 2>&1 \| tail -15` | test_segment_persistence.py | ⬜ pending |
| 02-08-T2 | 08 | 8 | REV-01, REV-02, REV-04, REV-05, GLOS-04, GLOS-05 | T-02-08-01, T-02-08-02 | session.add_all for ORM segments; await session.rollback() before transition_to_failed; no FK violation possible | unit (TDD GREEN) | `cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/workers/test_segment_persistence.py tests/workers/test_worker_glossary.py -x -q 2>&1 \| tail -15` | translate_worker.py | ⬜ pending |
| 02-09-T1 | 09 | 9 | GLOS-01, GLOS-05 | T-02-09-01 | glossary_id in _job_to_dict is server-generated UUID; term_count from server count not client array | unit | `cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 \| grep -v UploadForm \| head -10` | types.ts, jobs.py | ⬜ pending |
| 02-09-T2 | 09 | 9 | GLOS-01, REV-01, REV-02 | T-02-09-02 | NavBar renders on glossary routes; isMountedRef guard uses useRef (not useState) to avoid re-renders | unit | `cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 \| grep -v UploadForm \| head -10` | glossaries/page.tsx, GlossaryList.tsx, SegmentRow.tsx, useReviewKeyboard.ts | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Infrastructure Wave 0 must land before any feature waves execute.

- [ ] `backend/tests/fixtures/glossary_fixtures.py` — factory fixtures for `Glossary`, `GlossaryTerm`, `SegmentFlag`
- [ ] `backend/tests/fixtures/segment_fixtures.py` — extend Phase 1 segment factory with `edited_text`, `expansion_ratio`
- [ ] `backend/alembic/versions/XXXX_phase2_glossary_and_flags.py` — single migration: `glossaries`, `glossary_terms`, `segment_flags` tables + `segments.edited_text`, `segments.expansion_ratio`, `jobs.glossary_id` columns. Downgrade path must reverse all. SQLite-compat: `native_enum=False` on all SAEnum columns.
- [ ] `backend/tests/services/test_post_check.py` — 5 xfail stubs: overflow (real Segment DB row), glossary_violation, placeholder_mismatch, llm_refusal (len > 8 AND identical), short_term_skip. xfail reason: "Requires Plan 03 run_post_check implementation"
- [ ] `backend/tests/services/test_glossary_service.py` — stubs including test_update_term, test_update_term_not_found_returns_none
- [ ] `backend/tests/test_glossary_crud.py` — stubs for GLOS-01, GLOS-02, GLOS-05
- [ ] `backend/tests/test_glossary_injection.py` — stubs for GLOS-03 (terminology param passes through)
- [ ] `backend/tests/test_glossary_violation.py` — stubs for GLOS-04 (post-check produces flags)
- [ ] `backend/tests/test_segment_edit.py` — stubs for REV-02 (PATCH persistence)
- [ ] `backend/tests/test_segment_regenerate.py` — stubs for REV-04 (single-segment re-translate)
- [ ] `backend/tests/test_export_idempotency.py` — stubs for REV-05, REV-06 (export uses edited_text ?? translated_text)
- [ ] `backend/tests/test_expansion_ratio.py` — stubs for LAYOUT-01 (per-pair threshold, flag emitted)
- [ ] `backend/tests/test_upload_glossary.py` — stubs for UPLD-04 (glossary_id persisted on job, 422 on pair mismatch)
- [ ] `frontend/src/app/jobs/[id]/review/__tests__/SegmentTable.test.tsx` — render + keyboard nav stub (REV-01)
- [ ] `frontend/src/app/jobs/[id]/review/__tests__/optimistic-edit.test.tsx` — TanStack optimistic update + rollback (REV-02)
- [ ] `frontend/src/app/glossaries/__tests__/GlossaryList.test.tsx` — CRUD UI stubs (GLOS-01)
- [ ] `frontend/e2e/phase-2-review.spec.ts` — happy path: upload → complete → review → edit → export

*If framework install needed: confirmed already installed in Phase 1 (pytest, vitest, playwright). Only dependency additions: react-virtuoso, react-hotkeys-hook on frontend.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Paper design tokens visually applied (font rendering + color hierarchy) | design system | Visual / typography quality not programmable | Load `/jobs/{id}/review` + `/glossaries`, confirm Roboto body / Montserrat heading / PT Mono source cells, violet `#8B5CF6` on primary CTA, slate-50 page background |
| WCAG contrast on glossary-violation flag badge | design system | Requires a contrast tool, not a unit test | Use axe DevTools or WebAIM on `text-violet-700` on `bg-violet-50` combo — must hit 4.5:1 AA |
| CAT-tool UX feel (row height, sticky header, keyboard nav smoothness) | REV-01 | Subjective reviewer experience | Translate a 200+ segment DOCX, drive `j/k/n/e/r` without touching the mouse, confirm scroll-into-view and focus ring are not janky |
| Regenerate produces different output than original | REV-04 | Non-deterministic LLM output; can only assert "not empty" programmatically | Regenerate a segment, confirm the translated_text changes OR matches on stable cases; edited_text preserved |
| Export round-trip fidelity (paragraph runs, bold/italic, tables, etc.) | REV-05 | Requires human comparison vs Phase 1 baseline | Export a job with mixed edited + translated segments, open in Word, compare visually |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — populated by planner
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s for scoped runs
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** complete — verified by Plan 02-07 executor (2026-04-25)
**Gap closure plans added:** 2026-04-25 — Plans 08-09 close UAT blockers (Gap 1, Gap 2) and advisory items
