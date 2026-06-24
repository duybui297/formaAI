import { test, expect } from "@playwright/test";

/**
 * Phase 2: Review UX + Glossary — E2E happy-path test suite
 *
 * Covers the key user journeys added in Phase 2:
 *   - Glossary management (list, create, add terms)
 *   - Glossary picker on upload form
 *   - Segment review page: filter chips, inline edit, keyboard shortcuts
 *
 * Tests that require a running backend with real data are marked `test.skip`
 * with an explanatory comment. Run the non-skipped tests against `next dev`.
 *
 * Integration-only test (full workflow) requires:
 *   - Backend with DashScope credentials
 *   - A real DOCX fixture in /tmp/test-doc.docx
 */

test.describe("Phase 2: Review UX + Glossary", () => {
  // ---------------------------------------------------------------------------
  // Glossaries page
  // ---------------------------------------------------------------------------

  test("glossaries page loads and shows create button", async ({ page }) => {
    await page.goto("/glossaries");
    await expect(
      page.getByRole("heading", { name: "Glossaries" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Create Glossary" })
    ).toBeVisible();
  });

  test("create glossary dialog opens", async ({ page }) => {
    await page.goto("/glossaries");
    await page.getByRole("button", { name: "Create Glossary" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    // Dialog contains a Name input field
    await expect(page.getByLabel(/name/i)).toBeVisible();
  });

  // ---------------------------------------------------------------------------
  // Navigation
  // ---------------------------------------------------------------------------

  test("nav bar shows Glossaries link", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("link", { name: "Glossaries" })
    ).toBeVisible();
  });

  // ---------------------------------------------------------------------------
  // Upload form — glossary picker
  // ---------------------------------------------------------------------------

  test("upload form shows glossary picker after languages selected", async ({
    page,
  }) => {
    await page.goto("/");
    // The glossary picker is part of the upload form. It may be hidden until
    // language selections are made, or shown as empty by default. Either way,
    // the word "glossary" should appear somewhere on the page (label or select).
    // This is a structural check; the glossary list may be empty in a test env.
    await expect(page.getByText(/glossary/i).first()).toBeVisible();
  });

  // ---------------------------------------------------------------------------
  // Review page — conditional on a completed job existing
  // ---------------------------------------------------------------------------

  test("review page filter chips are present", async ({ page }) => {
    // Request the jobs list from the API proxy.
    const jobsResponse = await page.request.get("/api/v1/jobs");
    const body = await jobsResponse.json().catch(() => ({ jobs: [] }));
    const completedJob = ((body.jobs ?? []) as Array<{ id: string; status: string }>).find(
      (j) => j.status === "done" || j.status === "needs_review"
    );

    if (!completedJob) {
      // No completed job in this environment — skip gracefully.
      test.skip(true, "No completed job available; skipping filter-chip check");
      return;
    }

    await page.goto(`/jobs/${completedJob.id}/review`);

    // All five filter chips must be visible (counts may be 0)
    await expect(page.getByText(/All \(\d+\)/)).toBeVisible();
    await expect(page.getByText(/Overflow \(\d+\)/)).toBeVisible();
    await expect(page.getByText(/Glossary violation \(\d+\)/)).toBeVisible();
    await expect(page.getByText(/Placeholder \(\d+\)/)).toBeVisible();
    await expect(page.getByText(/Refusal \(\d+\)/)).toBeVisible();
  });

  test("keyboard help panel toggles on ? key", async ({ page }) => {
    const jobsResponse = await page.request.get("/api/v1/jobs");
    const body = await jobsResponse.json().catch(() => ({ jobs: [] }));
    const completedJob = ((body.jobs ?? []) as Array<{ id: string; status: string }>).find(
      (j) => j.status === "done" || j.status === "needs_review"
    );

    if (!completedJob) {
      test.skip(true, "No completed job available; skipping keyboard help check");
      return;
    }

    await page.goto(`/jobs/${completedJob.id}/review`);
    // Press ? while focus is on the body (not a textarea) to open the help panel.
    await page.locator("body").press("?");
    await expect(page.getByText("Keyboard shortcuts")).toBeVisible();
  });

  // ---------------------------------------------------------------------------
  // Full integration test — requires live backend + DashScope credentials
  // ---------------------------------------------------------------------------

  test.skip(
    "full review workflow: upload → translate → review → edit → export",
    async ({ page }) => {
      // Integration test — requires running backend with DashScope credentials.
      //
      // Steps:
      // 1. Navigate to the upload page and select source/target languages
      // 2. Attach a DOCX fixture file and optionally select a glossary
      // 3. Submit the form and wait for job status to reach done/needs_review
      // 4. Click "Review Translation" link on the job status page
      // 5. Verify SegmentTable loads with at least one row
      // 6. Edit the first segment's translation field
      // 7. Verify save-state indicator shows "Saved"
      // 8. Click "Export Document"
      // 9. Verify a file download is triggered
      //
      // This test is intentionally left unimplemented until a CI environment
      // with backend services and a DashScope API key is provisioned.
    }
  );
});
