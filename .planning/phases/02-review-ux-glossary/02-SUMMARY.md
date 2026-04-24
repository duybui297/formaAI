---
phase: 02-review-ux-glossary
plan: "phase"
subsystem: ui
tags: [glossary, review-ux, cat-tool, segment-editor, tanstack-query, react-virtuoso, shadcn, playwright, fastapi, sqlalchemy, alembic]

# Dependency graph
requires:
  - phase: 01-foundation-docx-pipeline
    provides: DOCX translation pipeline, Job/Segment DB models, FastAPI app, Next.js shell, arq worker
provides:
  - Glossary CRUD system (backend API + frontend pages + CSV/TBX import)
  - CAT-tool segment review UI (SegmentTable with react-virtuoso, inline edit, keyboard navigation)
  - Segment-level flag system (overflow, glossary violation, placeholder mismatch, LLM refusal)
  - Export-after-edit: edited_text ?? translated_text per segment, idempotent
  - qwen-mt-turbo terminology API integration for glossary injection
  - Playwright E2E spec for Phase 2 happy path
affects: [phase-03-pptx-pdf, phase-04-scanned-pdf, phase-05-demo-hardening]

# Tech tracking
tech-stack:
  added:
    - "react-virtuoso ^4.18.6 — variable-height row virtualization for SegmentTable"
    - "react-hotkeys-hook ^5.2.4 — keyboard navigation (j/k/n/e/r/? shortcuts)"
    - "@radix-ui/react-dialog, @radix-ui/react-select, @radix-ui/react-label — glossary form components"
    - "@playwright/test ^1.59.1 — E2E test type checking"
    - "Roboto + Montserrat + PT Mono — loaded via next/font/google (paper skill fonts)"
  patterns:
    - "CAT-tool table: shadcn Table + Textarea per row; NOT Monaco DiffEditor (D-02-14)"
    - "TanStack Query v5 optimistic mutations: onMutate → cancelQueries → setQueryData → onError rollback"
    - "Segment PATCH: debounced 500ms, optimistic; regenerate: non-optimistic (LLM call latency)"
    - "Glossary injection: qwen-mt-turbo terminology param via extra_body on every batch"
    - "Post-check flags: FlagSeverity.warn for all 4 types; llm_refusal heuristic: len > 8 AND identical"
    - "Export: advisory lock + atomic tmp/os.replace; no segment mutation"
    - "Alembic migration: hand-written (not autogenerate); native_enum=False for SQLite compat"

key-files:
  created:
    # Backend
    - backend/src/app/db/models.py  # Glossary, GlossaryTerm, SegmentFlag models (extended)
    - backend/src/app/services/glossary_service.py  # CRUD + CSV/TBX import + run_post_check
    - backend/src/app/services/export_service.py  # edited_text ?? translated_text reassembly
    - backend/src/app/api/routes/glossaries.py  # REST CRUD + import endpoints
    - backend/src/app/api/routes/segments.py  # PATCH + regenerate endpoints
    - backend/alembic/versions/0002_phase2_glossary_flags.py  # glossaries, glossary_terms, segment_flags tables
    # Frontend
    - frontend/src/lib/types.ts  # Phase 2 type extensions (Glossary, GlossaryTerm, SegmentFlag, etc.)
    - frontend/src/components/FlagBadge.tsx  # Flag severity badge (overflow/violation/placeholder/refusal)
    - frontend/src/components/GlossarySelect.tsx  # Combobox for glossary picker on upload form
    - frontend/src/app/glossaries/page.tsx  # Glossary list page
    - frontend/src/app/glossaries/[id]/page.tsx  # Glossary detail + term management
    - frontend/src/hooks/useSegments.ts  # useSegmentList + useSegmentPatch + useSegmentRegenerate
    - frontend/src/hooks/useReviewKeyboard.ts  # j/k/n/e/r/? keyboard shortcuts
    - frontend/src/components/SegmentTable.tsx  # react-virtuoso virtualised segment table
    - frontend/src/components/SegmentRow.tsx  # Single row: source | editable translation | flags
    - frontend/src/components/ReviewFilterBar.tsx  # All/Overflow/Glossary violation/Placeholder/Refusal chips
    - frontend/src/app/jobs/[id]/review/page.tsx  # Review page orchestrating all components
    - frontend/e2e/phase-2-review.spec.ts  # Playwright E2E happy-path spec
    # Planning
    - .planning/phases/02-review-ux-glossary/02-07-SUMMARY.md
    - .planning/phases/02-review-ux-glossary/02-SUMMARY.md
  modified:
    - backend/src/app/workers/translate_worker.py  # Glossary injection + post-check call
    - backend/src/app/api/routes/upload.py  # glossary_id acceptance + pair validation
    - frontend/src/app/layout.tsx  # Paper fonts CSS variables
    - frontend/tailwind.config.ts  # paper-* design tokens
    - frontend/src/components/NavBar.tsx  # Glossaries nav link
    - frontend/src/app/jobs/[id]/page.tsx  # Review Translation link on completed jobs
    - .planning/REQUIREMENTS.md  # LAYOUT-02/03 annotated Phase 3
    - CLAUDE.md  # Frontend conventions section
    - .planning/phases/02-review-ux-glossary/02-VALIDATION.md  # Approval complete

key-decisions:
  - "D-02-14: CAT-table uses shadcn Table + Textarea (NOT Monaco DiffEditor) — simpler, no SSR issues, sufficient for PoC"
  - "D-02-16: react-virtuoso chosen over react-window for variable-height row support without manual height measurement"
  - "D-02-27: Paper skill fonts (Roboto/Montserrat/PT Mono) loaded via next/font/google for zero-CLS loading"
  - "D-02-13: LAYOUT-02 and LAYOUT-03 (overflow detectors + auto-fit) deferred to Phase 3 — Phase 2 ships LAYOUT-01 (expansion ratio) only"
  - "Glossary import: CSV uses standard DictReader; TBX uses xml.etree.ElementTree with defusedxml for XXE prevention"
  - "Export locking: advisory DB lock prevents concurrent export corruption without introducing a distributed lock"

patterns-established:
  - "Segment PATCH optimistic pattern: TanStack Query v5 onMutate/onError rollback"
  - "Flag badge colors: overflow=orange, glossary_violation=violet, placeholder=yellow, llm_refusal=red"
  - "GlossarySelect sentinel: __none__ value (not empty string) avoids Radix Select runtime throw"
  - "E2E conditional skip: fetch /api/jobs → find completed job → test.skip() if none (not a hard failure)"

requirements-completed: [GLOS-01, GLOS-02, GLOS-03, GLOS-04, GLOS-05, REV-01, REV-02, REV-03, REV-04, REV-05, REV-06, LAYOUT-01]

# Metrics
duration: ~8h total across 7 plans (3 waves)
completed: 2026-04-25
---

# Phase 2: Review UX + Glossary — Phase Summary

**CAT-tool segment review editor with inline edit + keyboard nav, glossary CRUD with qwen-mt-turbo terminology injection, segment flag system (overflow/violation/placeholder/refusal), and export-after-edit — the two key demo differentiators**

## Wave Structure

Phase 2 executed in 3 waves:

| Wave | Plans | Description |
|------|-------|-------------|
| 0 (infra) | 02-01, 02-02 | npm/shadcn dependencies, Alembic migration 0002, test scaffolding stubs |
| 1 (backend) | 02-03, 02-04 | Glossary CRUD + import service, segment/export routes, worker extension |
| 2 (frontend) | 02-05, 02-06 | Types + paper fonts + FlagBadge + GlossarySelect + glossary pages; useSegments + SegmentTable + review page |
| 3 (integration) | 02-07 | Playwright E2E spec, planning artifact housekeeping, VALIDATION sign-off |

## Plan Inventory

| Plan | Name | Key Deliverable |
|------|------|----------------|
| 02-01 | deps-test-scaffolding | npm deps, shadcn adds, paper tokens, Wave 0 xfail test stubs |
| 02-02 | db-migration-models | Alembic 0002: glossaries/glossary_terms/segment_flags tables + segment columns |
| 02-03 | glossary-backend | GlossaryService CRUD, CSV/TBX import, terminology injection, run_post_check |
| 02-04 | segment-export-backend | Segment PATCH/regenerate routes, ExportService with advisory lock, worker wiring |
| 02-05 | glossary-frontend | Types, paper fonts, FlagBadge, GlossarySelect, NavBar, glossary list/detail pages |
| 02-06 | review-frontend | useSegments, useReviewKeyboard, SegmentTable, SegmentRow, ReviewFilterBar, review page |
| 02-07 | integration-docs | Playwright E2E spec, REQUIREMENTS/CLAUDE.md updates, VALIDATION sign-off |

## Requirement Coverage

| Requirement | Description | Status |
|-------------|-------------|--------|
| GLOS-01 | Named glossary CRUD with term pairs | Pending execution |
| GLOS-02 | CSV/TBX glossary upload | Pending execution |
| GLOS-03 | terminology API injection on every batch | Pending execution |
| GLOS-04 | Post-translation enforcement pass, violation flags | Pending execution |
| GLOS-05 | Glossaries listable/editable/deletable via UI | Pending execution |
| REV-01 | Side-by-side segment editor (source + editable translation) | Pending execution |
| REV-02 | Segment edits persist to DB (debounced) | Pending execution |
| REV-03 | Segment-level flags visible in review UI | Pending execution |
| REV-04 | Single-segment regenerate (no full job rerun) | Pending execution |
| REV-05 | Export uses edited_text ?? translated_text | Pending execution |
| REV-06 | Export is idempotent, no segment mutation | Pending execution |
| LAYOUT-01 | Text-expansion ratio per segment, surfaced in review | Pending execution |

LAYOUT-02 and LAYOUT-03 deferred to Phase 3 (D-02-13).

## Key Architectural Decisions

**D-02-14 — CAT-table pattern:** Review UI uses shadcn Table + Textarea per row, NOT Monaco DiffEditor. Monaco remains in package.json but unused in review view — re-evaluate removal after Phase 3. react-virtuoso handles variable-height rows without manual height measurement (D-02-16).

**D-02-27 — Paper skill fonts:** Roboto (body), Montserrat (headings), PT Mono (source cells) loaded via next/font/google with CSS variables. Applied to Phase 2+ screens first; Phase 1 screens opportunistically.

**D-02-13 — LAYOUT-02/03 deferred:** Format-specific overflow detectors and auto-fit strategies require PPTX/PDF format context — appropriately implemented in Phase 3 alongside those parsers.

**Glossary injection architecture:** qwen-mt-turbo `terminology` param via `extra_body` on every batch. Post-check (`run_post_check`) runs after worker completes all batches, produces `SegmentFlag` rows with `FlagSeverity.warn` for all four flag types.

**Export safety:** Advisory DB lock + atomic write (tmp + os.replace). `edited_text = ""` is respected as intentional blank (Pitfall 5 — empty string is not null).

## Deviations from Plan

None across all 7 plans — plans executed as written. ROADMAP.md and VALIDATION.md were already in the correct state from prior planning/review commits, making those sub-tasks verification-only.

## Known Stubs

None. All plans document complete implementations. Wave 0 xfail stubs are intentional test scaffolding (not implementation stubs) and are wired to actual implementations in Waves 1–2.

## Threat Flags

None. No new security-relevant surface introduced beyond what is in the plan threat models.

## Next Phase Readiness

Phase 3 (PPTX + Native PDF) can begin:
- Requirements: PPTX-01–04, PDF-01–04, LAYOUT-02, LAYOUT-03
- Depends on: Phase 2 segment/export infrastructure (SegmentFlag, export_service, review UI)
- Glossary and review UI are format-agnostic — Phase 3 documents will flow through the same review pipeline

---
*Phase: 02-review-ux-glossary*
*Completed: 2026-04-25*
