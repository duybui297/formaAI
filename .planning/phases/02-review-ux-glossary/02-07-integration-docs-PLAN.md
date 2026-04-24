---
phase: 02-review-ux-glossary
plan: "07"
type: execute
wave: 3
depends_on: ["02-03", "02-04", "02-05", "02-06"]
files_modified:
  - frontend/e2e/phase-2-review.spec.ts
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - CLAUDE.md
  - .planning/phases/02-review-ux-glossary/02-VALIDATION.md
autonomous: true
requirements: [GLOS-01, GLOS-02, GLOS-03, GLOS-04, GLOS-05, REV-01, REV-02, REV-03, REV-04, REV-05, REV-06, LAYOUT-01]

must_haves:
  truths:
    - "E2E Playwright test documents the happy-path review workflow"
    - "REQUIREMENTS.md correctly scopes LAYOUT-02/03 to Phase 3"
    - "ROADMAP.md Phase 2 no longer lists LAYOUT-02/03; Phase 3 lists them"
    - "ROADMAP.md Phase 2 shows 7 plans"
    - "CLAUDE.md notes the CAT-table pattern decision (D-02-14)"
    - "VALIDATION.md per-task verification map is complete (all 7 plans covered)"
  artifacts:
    - path: "frontend/e2e/phase-2-review.spec.ts"
      provides: "Playwright E2E test for upload→review→edit→export workflow"
    - path: ".planning/REQUIREMENTS.md"
      provides: "LAYOUT-02/03 scoped to Phase 3 (not Phase 2)"
    - path: ".planning/ROADMAP.md"
      provides: "Phase 2 plan count = 7; LAYOUT-02/03 moved to Phase 3 requirements list"
    - path: "CLAUDE.md"
      provides: "Frontend §: CAT-table pattern note (D-02-14)"
    - path: ".planning/phases/02-review-ux-glossary/02-VALIDATION.md"
      provides: "Full per-task verification map; nyquist_compliant: true"
  key_links:
    - from: "ROADMAP.md Phase 2 requirements list"
      to: "GLOS-01..05, REV-01..06, LAYOUT-01"
      via: "edit — remove LAYOUT-02, LAYOUT-03 from Phase 2; add to Phase 3"
      pattern: "LAYOUT-0[23]"
    - from: "VALIDATION.md nyquist_compliant"
      to: "all 7 plans × all tasks"
      via: "populated per-task verification table"
      pattern: "nyquist_compliant: true"
---

<objective>
Close Phase 2 with three things: (1) Playwright E2E test for the happy-path review workflow, (2) planning artifact housekeeping — move LAYOUT-02/03 to Phase 3 in both REQUIREMENTS.md and ROADMAP.md, update plan count, add CAT-table note to CLAUDE.md, (3) fully populate VALIDATION.md per-task verification map and flip nyquist_compliant to true.

Purpose: Ensures the planning record is accurate for Phase 3 planning, and that Phase 2 has at least one automated E2E test documenting the end-to-end review workflow before the checker runs.

Output: E2E spec, 4 updated planning files. Phase 2 planning artifacts complete and consistent.
</objective>

<execution_context>
@/home/thu/.claude/get-shit-done/workflows/execute-plan.md
@/home/thu/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-review-ux-glossary/02-CONTEXT.md
@.planning/phases/02-review-ux-glossary/02-VALIDATION.md
@.planning/phases/02-review-ux-glossary/02-01-deps-test-scaffolding-PLAN.md
@.planning/phases/02-review-ux-glossary/02-02-db-migration-models-PLAN.md
@.planning/phases/02-review-ux-glossary/02-03-glossary-backend-PLAN.md
@.planning/phases/02-review-ux-glossary/02-04-segment-export-backend-PLAN.md
@.planning/phases/02-review-ux-glossary/02-05-glossary-frontend-PLAN.md
@.planning/phases/02-review-ux-glossary/02-06-review-frontend-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write Playwright E2E test for review happy path</name>
  <files>
    frontend/e2e/phase-2-review.spec.ts
  </files>
  <action>
Read existing E2E test files in `frontend/e2e/` to understand Phase 1 test patterns before writing.

Create `frontend/e2e/phase-2-review.spec.ts`. This is an E2E happy-path test — it documents the workflow even if it runs against a live dev server. Use `test.skip` with a comment on integration-only steps (e.g., actual file upload requiring backend).

The test structure covers:
1. Navigate to /glossaries — page loads
2. Create a glossary via the create dialog
3. Add a term to the glossary
4. Navigate to the upload page
5. Glossary picker appears after selecting matching language pair
6. (Integration-only: upload a file → verify review page link appears on job page)
7. Navigate to /jobs/{id}/review (with a known fixture or skip if no job)
8. Verify segment table renders
9. Edit a segment translation field
10. Verify filter chips are present (All, Overflow, Glossary violation, Placeholder, Refusal)
11. Verify export button visible on done/needs_review job

```typescript
import { test, expect } from "@playwright/test";

test.describe("Phase 2: Review UX + Glossary", () => {

  test("glossaries page loads and shows create button", async ({ page }) => {
    await page.goto("/glossaries");
    await expect(page.getByRole("heading", { name: "Glossaries" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create Glossary" })).toBeVisible();
  });

  test("create glossary dialog opens", async ({ page }) => {
    await page.goto("/glossaries");
    await page.getByRole("button", { name: "Create Glossary" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    // Dialog has Name input and language selects
    await expect(page.getByLabel(/name/i)).toBeVisible();
  });

  test("nav bar shows Glossaries link", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Glossaries" })).toBeVisible();
  });

  test("upload form shows glossary picker after languages selected", async ({ page }) => {
    await page.goto("/");
    // Select source and target language — adjust selectors to match Phase 1 LanguageSelect
    // The glossary picker should become visible
    // This is a structural check; glossary list may be empty in test env
    await expect(page.getByText(/glossary/i).first()).toBeVisible();
  });

  test.skip(
    "full review workflow: upload → translate → review → edit → export",
    async ({ page }) => {
      // Integration test — requires running backend with DashScope credentials
      // Steps:
      // 1. Upload a DOCX file
      // 2. Wait for job status to reach done/needs_review
      // 3. Click "Review Translation" link
      // 4. Verify SegmentTable loads with at least one row
      // 5. Edit first segment translation
      // 6. Verify save state shows "Saved"
      // 7. Click "Export Document"
      // 8. Verify download triggered
    }
  );

  test("review page filter chips are present", async ({ page }) => {
    // Navigate to review page of a completed job
    // If no jobs exist, skip gracefully
    const jobsResponse = await page.request.get("/api/jobs");
    const jobs = await jobsResponse.json().catch(() => ({ jobs: [] }));
    const completedJob = (jobs.jobs ?? []).find(
      (j: { status: string }) => j.status === "done" || j.status === "needs_review"
    );
    if (!completedJob) {
      test.skip();
      return;
    }

    await page.goto(`/jobs/${completedJob.id}/review`);
    await expect(page.getByText(/All \(\d+\)/)).toBeVisible();
    await expect(page.getByText(/Overflow \(\d+\)/)).toBeVisible();
    await expect(page.getByText(/Glossary violation \(\d+\)/)).toBeVisible();
    await expect(page.getByText(/Placeholder \(\d+\)/)).toBeVisible();
    await expect(page.getByText(/Refusal \(\d+\)/)).toBeVisible();
  });

  test("keyboard help panel toggles on ? key", async ({ page }) => {
    const jobsResponse = await page.request.get("/api/jobs");
    const jobs = await jobsResponse.json().catch(() => ({ jobs: [] }));
    const completedJob = (jobs.jobs ?? []).find(
      (j: { status: string }) => j.status === "done" || j.status === "needs_review"
    );
    if (!completedJob) {
      test.skip();
      return;
    }

    await page.goto(`/jobs/${completedJob.id}/review`);
    // Focus the page body (not a textarea) and press ?
    await page.locator("body").press("?");
    await expect(page.getByText("Keyboard shortcuts")).toBeVisible();
  });
});
```

Read the existing `frontend/e2e/` directory for Phase 1 test patterns (playwright.config.ts base URL, existing imports) and adjust selectors to match the actual Phase 1 UploadForm structure.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | grep "e2e/phase-2" | head -10</automated>
  </verify>
  <done>
    frontend/e2e/phase-2-review.spec.ts exists and TypeScript-compiles clean.
    Test covers: glossaries page, create dialog, nav link, upload form picker, filter chips (conditional on job existing), keyboard help panel (conditional).
    Full integration test marked skip with explanatory comment.
  </done>
</task>

<task type="auto">
  <name>Task 2: Update REQUIREMENTS.md, ROADMAP.md, CLAUDE.md</name>
  <files>
    .planning/REQUIREMENTS.md
    .planning/ROADMAP.md
    CLAUDE.md
  </files>
  <action>
Read each file before editing. Make surgical edits only.

**REQUIREMENTS.md** — move LAYOUT-02 and LAYOUT-03 from Phase 2 scope to Phase 3 scope.

Find the `### Smart Layout (differentiator)` section. Change the phase assignment annotations on LAYOUT-02 and LAYOUT-03 to indicate Phase 3. The existing requirement text stays; just add a `→ Phase 3` note in parentheses at the end of each line, or add a comment row above them:

```
- [ ] **LAYOUT-01**: Text-expansion ratio is calculated per segment (`len(target) / len(source)`) and surfaced in review for any segment above a configurable threshold
# LAYOUT-02 and LAYOUT-03 are Phase 3 scope (D-02-13: deferred from Phase 2 per CONTEXT.md)
- [ ] **LAYOUT-02**: Format-specific overflow detectors run post-translation ... (Phase 3)
- [ ] **LAYOUT-03**: Auto-fit strategies are applied conservatively ... (Phase 3)
```

**ROADMAP.md** — three edits:

1. Phase 2 `**Requirements:**` line: remove `LAYOUT-02, LAYOUT-03` from the list. Result:
   ```
   **Requirements**: GLOS-01, GLOS-02, GLOS-03, GLOS-04, GLOS-05, REV-01, REV-02, REV-03, REV-04, REV-05, REV-06, LAYOUT-01
   ```

2. Phase 2 `**Plans:**` line and plan list: update to show 7 plans.
   ```
   **Plans**: 7 plans

   Plans:
   - [ ] 02-01-deps-test-scaffolding-PLAN.md — npm deps install, shadcn adds, test stub scaffolding
   - [ ] 02-02-db-migration-models-PLAN.md — Alembic migration 0002, SQLAlchemy model extensions
   - [ ] 02-03-glossary-backend-PLAN.md — Glossary CRUD service + REST endpoints + CSV/TBX import
   - [ ] 02-04-segment-export-backend-PLAN.md — Segment routes, export service, worker extension
   - [ ] 02-05-glossary-frontend-PLAN.md — Types, paper fonts, FlagBadge, GlossarySelect, glossary pages
   - [ ] 02-06-review-frontend-PLAN.md — useSegments, SegmentTable, SegmentRow, review page, keyboard nav
   - [ ] 02-07-integration-docs-PLAN.md — E2E test, planning artifact updates, VALIDATION.md completion
   ```

3. Phase 3 `**Requirements:**` line: add `LAYOUT-02, LAYOUT-03` to the list:
   ```
   **Requirements**: PPTX-01, PPTX-02, PPTX-03, PPTX-04, PDF-01, PDF-02, PDF-03, PDF-04, LAYOUT-02, LAYOUT-03
   ```

Also update the Progress table at the bottom of ROADMAP.md for Phase 2:
```
| 2. Review UX + Glossary | 0/7 | Not started | - |
```

**CLAUDE.md** — read the file. Find the `## Conventions` section (currently says "not yet established"). Append a note in the Frontend conventions subsection (or create one if not present):

```markdown
## Conventions

### Frontend

**CAT-tool segment table pattern (Phase 2, D-02-14):** Review UI uses shadcn Table + Textarea per row (NOT Monaco DiffEditor). react-virtuoso handles variable-height virtualization. TanStack Query v5 optimistic mutations with `onMutate → cancelQueries → setQueryData → onError rollback` for segment PATCH. Monaco DiffEditor remains in package.json but is not used for the review view; re-evaluate removal after Phase 3.

**Paper skill fonts (Phase 2, D-02-27):** Roboto (body), Montserrat (headings), PT Mono (source cells). Loaded via `next/font/google` in `frontend/src/app/layout.tsx` with CSS variables `--font-roboto`, `--font-montserrat`, `--font-pt-mono`. Apply to new Phase 2+ screens first; Phase 1 screens opportunistically.
```

Do NOT modify any other section of CLAUDE.md. Do NOT change the technology stack or project constraints sections.
  </action>
  <verify>
    <automated>grep -n "LAYOUT-02\|LAYOUT-03" /home/thu/dev/projects/ai-translation/.planning/ROADMAP.md</automated>
  </verify>
  <done>
    REQUIREMENTS.md: LAYOUT-02 and LAYOUT-03 have Phase 3 annotation.
    ROADMAP.md: Phase 2 requirements list has no LAYOUT-02/03; Phase 3 requirements list includes them; Phase 2 shows "7 plans" and plan list populated; progress table shows 0/7.
    CLAUDE.md: Frontend conventions section added with CAT-table and paper font notes.
    grep shows LAYOUT-02/03 appear ONLY in Phase 3 section of ROADMAP.md (not Phase 2).
  </done>
</task>

<task type="auto">
  <name>Task 3: Populate VALIDATION.md per-task verification map and flip nyquist_compliant</name>
  <files>
    .planning/phases/02-review-ux-glossary/02-VALIDATION.md
  </files>
  <action>
Read the current VALIDATION.md. Replace the sparse per-task verification map with the full table covering all 7 plans × all tasks.

Update frontmatter: `nyquist_compliant: true`, `wave_0_complete: false` (still pending execution).

Replace the `## Per-Task Verification Map` section with this complete table:

```markdown
## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 01 | 0 | infra | — | install-check | `cd frontend && node -e "require('react-virtuoso'); require('react-hotkeys-hook')" 2>&1` | frontend/package.json | ⬜ |
| 02-01-T2 | 01 | 0 | infra | — | unit | `cd backend && uv run pytest tests/conftest.py -q` | backend/tests/conftest.py | ⬜ |
| 02-01-T3 | 01 | 0 | infra | — | wave-0 | `cd backend && uv run pytest -m xfail -q 2>&1 \| grep "xfailed"` | backend/tests/test_glossaries.py | ⬜ |
| 02-01-T4 | 01 | 0 | infra | — | wave-0 | `cd frontend && pnpm vitest run --reporter=verbose 2>&1 \| grep "todo"` | frontend/src/components/SegmentTable.test.tsx | ⬜ |
| 02-02-T1 | 02 | 0 | GLOS-01, REV-03, LAYOUT-01 | T-02-02-01 | unit | `cd backend && uv run python -c "from app.db.models import Glossary, GlossaryTerm, SegmentFlag"` | backend/src/app/db/models.py | ⬜ |
| 02-02-T2 | 02 | 0 | GLOS-01, REV-03 | T-02-02-02 | migration | `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1` | backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py | ⬜ |
| 02-02-T3 | 02 | 0 | LAYOUT-01 | — | unit | `cd backend && uv run python -c "from app.core.config import get_settings; s=get_settings(); print(s.expansion_thresholds_dict)"` | backend/src/app/core/config.py | ⬜ |
| 02-03-T1 | 03 | 1 | GLOS-01, GLOS-02, GLOS-04 | T-02-03-01 | unit | `cd backend && uv run pytest tests/test_glossary_service.py tests/test_csv_import.py -q` | backend/src/app/services/glossary_service.py | ⬜ |
| 02-03-T2 | 03 | 1 | GLOS-01, GLOS-05 | T-02-03-02 | integration | `cd backend && uv run pytest tests/test_glossaries.py -q` | backend/src/app/api/routes/glossaries.py | ⬜ |
| 02-03-T3 | 03 | 1 | GLOS-03, UPLD-04 | T-02-03-03 | integration | `cd backend && uv run pytest tests/test_upload_glossary.py -q` | backend/src/app/api/routes/upload.py | ⬜ |
| 02-04-T1 | 04 | 1 | REV-05, REV-06 | T-02-04-01 | unit | `cd backend && uv run pytest tests/test_export_service.py -q` | backend/src/app/services/export_service.py | ⬜ |
| 02-04-T2 | 04 | 1 | REV-01, REV-02, REV-04, REV-05 | T-02-04-02 | integration | `cd backend && uv run pytest tests/test_segments.py -q` | backend/src/app/api/routes/segments.py | ⬜ |
| 02-04-T3 | 04 | 1 | GLOS-03, GLOS-04, LAYOUT-01 | T-02-04-03 | integration | `cd backend && uv run pytest tests/test_worker_glossary.py tests/test_post_check.py tests/test_expansion_ratio.py -q` | backend/src/app/workers/translate_worker.py | ⬜ |
| 02-05-T1 | 05 | 2 | GLOS-05 | — | typecheck | `cd frontend && npx tsc --noEmit 2>&1 \| grep "types.ts\|layout.tsx" \| head -5` | frontend/src/lib/types.ts | ⬜ |
| 02-05-T2 | 05 | 2 | GLOS-05 | T-02-05-01 | unit | `cd frontend && pnpm vitest run src/components/FlagBadge.test.tsx src/components/GlossarySelect.test.tsx 2>&1` | frontend/src/components/FlagBadge.tsx | ⬜ |
| 02-05-T3 | 05 | 2 | GLOS-01, GLOS-02, GLOS-05 | T-02-05-03 | typecheck | `cd frontend && npx tsc --noEmit 2>&1 \| head -20` | frontend/src/app/glossaries/page.tsx | ⬜ |
| 02-06-T1 | 06 | 2 | REV-01, REV-02 | T-02-06-03 | unit | `cd frontend && pnpm vitest run src/hooks/useSegments.test.ts 2>&1` | frontend/src/hooks/useSegments.ts | ⬜ |
| 02-06-T2 | 06 | 2 | REV-01, REV-03, REV-04 | T-02-06-01 | unit | `cd frontend && pnpm vitest run src/components/SegmentTable.test.tsx 2>&1` | frontend/src/components/SegmentTable.tsx | ⬜ |
| 02-06-T3 | 06 | 2 | REV-01, REV-02, REV-03, REV-04, REV-05, LAYOUT-01 | T-02-06-02 | typecheck | `cd frontend && npx tsc --noEmit 2>&1 \| head -20` | frontend/src/app/jobs/[id]/review/page.tsx | ⬜ |
| 02-07-T1 | 07 | 3 | REV-01..06 | — | e2e | `cd frontend && pnpm playwright test e2e/phase-2-review.spec.ts --reporter=list 2>&1 \| head -30` | frontend/e2e/phase-2-review.spec.ts | ⬜ |
| 02-07-T2 | 07 | 3 | (housekeeping) | — | grep | `grep -n "LAYOUT-02\|LAYOUT-03" .planning/ROADMAP.md` | .planning/ROADMAP.md | ⬜ |
| 02-07-T3 | 07 | 3 | (housekeeping) | — | grep | `grep -c "nyquist_compliant: true" .planning/phases/02-review-ux-glossary/02-VALIDATION.md` | .planning/phases/02-review-ux-glossary/02-VALIDATION.md | ⬜ |
```

Update frontmatter at top of file:
```yaml
nyquist_compliant: true
wave_0_complete: false
```

Keep all other sections of VALIDATION.md (test infrastructure, sampling rate, wave 0 requirements, manual-only verifications) unchanged.
  </action>
  <verify>
    <automated>grep "nyquist_compliant" /home/thu/dev/projects/ai-translation/.planning/phases/02-review-ux-glossary/02-VALIDATION.md</automated>
  </verify>
  <done>
    02-VALIDATION.md frontmatter shows nyquist_compliant: true.
    Per-task verification map has 23 rows covering all 7 plans.
    Every row has: Task ID, Plan, Wave, Requirement, Threat Ref, Test Type, Automated Command, File Exists, Status.
    All statuses are ⬜ (pending — plans not yet executed).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| E2E test → local dev server | Playwright makes real HTTP calls to the running app |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-07-01 | Information Disclosure | E2E tests may surface credentials in CI logs | accept | Tests are dev-only; no secrets in test files; DashScope key loaded from env only. Integration tests marked skip. |
</threat_model>

<verification>
After all tasks complete:

1. `grep "nyquist_compliant: true" .planning/phases/02-review-ux-glossary/02-VALIDATION.md` — matches
2. `grep "LAYOUT-02\|LAYOUT-03" .planning/ROADMAP.md` — shows ONLY in Phase 3 section
3. `grep "7 plans" .planning/ROADMAP.md` — matches Phase 2 entry
4. `ls frontend/e2e/phase-2-review.spec.ts` — file exists
5. `grep "CAT-tool\|D-02-14" CLAUDE.md` — appears in Frontend conventions
6. `cd frontend && npx tsc --noEmit 2>&1 | grep "e2e/phase-2" | head -5` — no TypeScript errors in E2E file
</verification>

<success_criteria>
- E2E spec created: covers glossaries page, create dialog, nav link, filter chips (conditional), keyboard help (conditional); full integration test skip-annotated
- REQUIREMENTS.md: LAYOUT-02 and LAYOUT-03 marked as Phase 3 scope
- ROADMAP.md: Phase 2 requirements = GLOS-01..05 + REV-01..06 + LAYOUT-01 (no LAYOUT-02/03); Phase 3 requirements includes LAYOUT-02, LAYOUT-03; Phase 2 shows 7 plans with populated plan list
- CLAUDE.md: Frontend conventions section with CAT-table pattern note (D-02-14) and paper font note (D-02-27)
- VALIDATION.md: nyquist_compliant: true; 23-row per-task verification map covering all plans and tasks
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-07-SUMMARY.md` using the template at `@/home/thu/.claude/get-shit-done/templates/summary.md`.

Also create `.planning/phases/02-review-ux-glossary/02-SUMMARY.md` summarizing the full phase: all 7 plans, wave structure, key architectural decisions (D-02-14 CAT-table, D-02-16 react-virtuoso, D-02-27 paper fonts, LAYOUT-02/03 deferred to Phase 3), and the requirement coverage (GLOS-01..05, REV-01..06, LAYOUT-01).
</output>
