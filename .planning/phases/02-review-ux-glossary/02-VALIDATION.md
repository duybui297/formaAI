---
phase: 2
slug: review-ux-glossary
status: draft
nyquist_compliant: false
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

> Populated by `gsd-planner` when PLAN.md files are generated. One row per task.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | infrastructure | — | N/A | wave-0 | `uv pip install react-virtuoso react-hotkeys-hook && npx typeui.sh pull paper` (pseudo — see plan) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Planner responsibility: expand this table with every task from every PLAN.md before plan-checker runs.*

---

## Wave 0 Requirements

> Infrastructure Wave 0 must land before any feature waves execute.

- [ ] `backend/tests/fixtures/glossary_fixtures.py` — factory fixtures for `Glossary`, `GlossaryTerm`, `SegmentFlag`
- [ ] `backend/tests/fixtures/segment_fixtures.py` — extend Phase 1 segment factory with `edited_text`, `expansion_ratio`
- [ ] `backend/alembic/versions/XXXX_phase2_glossary_and_flags.py` — single migration: `glossaries`, `glossary_terms`, `segment_flags` tables + `segments.edited_text`, `segments.expansion_ratio`, `jobs.glossary_id` columns. Downgrade path must reverse all.
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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies — populated by planner
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for scoped runs
- [ ] `nyquist_compliant: true` set in frontmatter after planner fills the map

**Approval:** pending
