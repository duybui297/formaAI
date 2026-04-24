---
phase: "02"
plan: "01"
subsystem: test-infrastructure
tags: [test-scaffolding, npm-deps, shadcn, tailwind, xfail-stubs]
dependency_graph:
  requires: []
  provides:
    - react-virtuoso@4.18.6 in frontend/package.json
    - react-hotkeys-hook@5.2.4 in frontend/package.json
    - shadcn textarea/input/popover/command components
    - paper-ink + paper-accent tailwind color tokens
    - make_glossary / make_glossary_term / make_segment_flag fixtures in conftest.py
    - 8 backend xfail test stubs (Waves 1-3 red phase contracts)
    - 4 frontend todo test stubs (Waves 1-3 red phase contracts)
  affects:
    - "backend/tests/**" (all future plans consume conftest fixtures)
    - "frontend/src/components/ui/**" (Plans 05-06 build on shadcn components)
    - "frontend/tailwind.config.ts" (paper-ink/paper-accent referenced in Phase 2 component styles)
tech_stack:
  added:
    - react-virtuoso@4.18.6 (virtualized list for SegmentTable — REV-01)
    - react-hotkeys-hook@5.2.4 (keyboard nav j/k/n/e — REV-01)
    - shadcn/ui: textarea, input, popover, command components
  patterns:
    - xfail stubs as living contracts (test names locked before implementation)
    - late-import model references in conftest so fixtures load before models exist
    - commit()+refresh() in factory fixtures for API-test visibility across sessions
key_files:
  created:
    - frontend/src/components/ui/textarea.tsx
    - frontend/src/components/ui/input.tsx
    - frontend/src/components/ui/popover.tsx
    - frontend/src/components/ui/command.tsx
    - frontend/src/__tests__/FlagBadge.test.tsx
    - frontend/src/__tests__/SegmentTable.test.tsx
    - frontend/src/__tests__/useSegments.test.ts
    - frontend/src/__tests__/GlossarySelect.test.tsx
    - backend/tests/api/test_glossaries.py
    - backend/tests/api/test_segments.py
    - backend/tests/services/test_glossary_service.py
    - backend/tests/services/test_csv_import.py
    - backend/tests/services/test_tbx_import.py
    - backend/tests/services/test_post_check.py
    - backend/tests/services/test_export_service.py
    - backend/tests/workers/test_worker_glossary.py
  modified:
    - frontend/package.json (react-virtuoso, react-hotkeys-hook added)
    - frontend/package-lock.json
    - frontend/tailwind.config.ts (paper-ink, paper-accent added)
    - backend/tests/conftest.py (3 factory fixtures appended)
decisions:
  - "commit()+refresh() in make_glossary and make_glossary_term so API-level tests using a separate session can see newly created rows; flush() is insufficient across sessions"
  - "late imports inside factory functions (from app.db.models import Glossary inside _make()) so conftest.py loads successfully before Plan 02 adds the models to models.py"
  - "it.todo() for frontend stubs (not it.skip) so vitest reports them as todo/skipped without failing; 20 todo tests, exit 0 confirmed"
  - "test_expansion_ratio_overflow_flag uses a real Segment DB row (not FakeSeg) to satisfy FK constraint for SegmentFlag and allow expansion_ratio write-back to the DB"
metrics:
  duration: "~12 minutes"
  completed: "2026-04-25"
  tasks_completed: 4
  tasks_total: 4
  files_created: 20
  files_modified: 4
---

# Phase 2 Plan 01: Deps + Test Scaffolding Summary

Wave 0 infrastructure: npm deps, shadcn UI components, paper color tokens, and all Wave 0 test stub files installed so later waves have their red-phase contracts ready.

## What Was Done

**Task 1 — npm deps + shadcn + tailwind tokens**

Installed `react-virtuoso@4.18.6` and `react-hotkeys-hook@5.2.4` into `frontend/package.json`. Added four shadcn components via `npx shadcn@latest add textarea input popover command`. Applied `paper-ink: "#111111"` and `paper-accent: "#8B5CF6"` to `theme.extend.colors` in `tailwind.config.ts` per D-02-27/28.

**Task 2 — conftest.py Phase 2 fixtures**

Appended three factory fixtures to `backend/tests/conftest.py`:
- `make_glossary(db_session)` — creates a `Glossary` row; uses `commit()+refresh()` for cross-session visibility
- `make_glossary_term(db_session)` — creates a `GlossaryTerm` row; uses `commit()+refresh()`
- `make_segment_flag(db_session)` — creates a `SegmentFlag` row; uses `flush()` (same-session only needed)

All three use late imports (`from app.db.models import X` inside the inner `_make()`) so `conftest.py` loads without error before Plan 02 extends `models.py`.

**Task 3 — backend test stubs (8 files, 30 tests, all xfail)**

| File | Coverage | Tests |
|------|----------|-------|
| `test_glossaries.py` | GLOS-01, GLOS-05 | 5 |
| `test_segments.py` | REV-02, REV-04 | 3 |
| `test_glossary_service.py` | GLOS-01 service, update_term | 5 |
| `test_csv_import.py` | GLOS-02 CSV (BOM, aliases, short-term) | 5 |
| `test_tbx_import.py` | GLOS-02 TBX | 2 |
| `test_post_check.py` | GLOS-04, LAYOUT-01 (5 flag types) | 5 |
| `test_export_service.py` | REV-05, REV-06 | 3 |
| `test_worker_glossary.py` | GLOS-03 | 2 |

Notable: `test_post_check.py` has 5 stubs covering `glossary_violation`, short-term-skip, `overflow` (with real Segment DB row for FK safety), `placeholder_mismatch`, and `llm_refusal` (documented `len > 8 AND identical` heuristic).

**Task 4 — frontend test stubs (4 files, 20 todo tests)**

| File | Coverage |
|------|----------|
| `FlagBadge.test.tsx` | REV-03 (5 todo) |
| `SegmentTable.test.tsx` | REV-01 incl. j/k/n/e keyboard nav (6 todo) |
| `useSegments.test.ts` | REV-02 optimistic update + rollback (4 todo) |
| `GlossarySelect.test.tsx` | UPLD-04 pair-filtered glossary (5 todo) |

## Verification Results

- `npm --prefix frontend run test` — exit 0, 34 passed + 20 todo
- `uv run --extra test python -m pytest tests/ -m "not integration" -x -q --no-cov` — 142 passed, 29 xfailed, 1 xpassed, exit 0
- All 4 shadcn components present at `frontend/src/components/ui/`
- `paper-ink` and `paper-accent` confirmed in `tailwind.config.ts`

## Commits

| Hash | Task | Description |
|------|------|-------------|
| `19dffb7` | Task 1 | chore(deps): install react-virtuoso + react-hotkeys-hook; add shadcn + paper tokens |
| `e961625` | Task 2 | test(phase-2): extend conftest with factory fixtures |
| `51317dd` | Task 3 | test(phase-2): add backend Wave 0 test stubs |
| `cd2bae4` | Task 4 | test(phase-2): add frontend Wave 0 test stubs |

## Deviations from Plan

None — plan executed exactly as written. The `typeui.sh pull paper` command was not available (as expected per plan instructions); the manual fallback was applied directly.

## Known Stubs

All stubs are intentional scaffolding — they are xfail/todo, not broken functionality. Each stub's target plan is documented inline. No production-visible stubs.

## Threat Flags

None — this plan creates test files and installs vetted npm packages only. No new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

Files verified present:
- `frontend/src/components/ui/textarea.tsx` — FOUND
- `frontend/src/components/ui/input.tsx` — FOUND
- `frontend/src/components/ui/popover.tsx` — FOUND
- `frontend/src/components/ui/command.tsx` — FOUND
- `backend/tests/conftest.py` (3 fixtures) — FOUND
- All 8 backend test stubs — FOUND
- All 4 frontend test stubs — FOUND

Commits verified:
- `19dffb7` — FOUND
- `e961625` — FOUND
- `51317dd` — FOUND
- `cd2bae4` — FOUND
