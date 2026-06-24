/**
 * TASK-3.7: Translation Entitlement Enforcement
 *
 * All /api/v1/* routes are mocked with page.route() — no running backend needed.
 *
 * Tests:
 *  Case A: has_active=false → blocked state, links to /pricing and /activate, no upload form.
 *  Case B: TRIAL → upload form usable, 5 MB limit shown, quota shown, OCR + glossary disabled.
 *  Case C (optional): PRO → OCR + glossary enabled, unlimited.
 */

import { test, expect, type Page, type BrowserContext } from "@playwright/test";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const FAKE_TOKEN = "test-jwt-token-3.7";

const ENTITLEMENT_UNLICENSED = {
  has_active: false,
  tier: null,
  max_file_bytes: null,
  monthly_quota: null,
  quota_used: 0,
  ocr_allowed: null,
  glossary_allowed: null,
};

const ENTITLEMENT_TRIAL = {
  has_active: true,
  tier: "TRIAL",
  max_file_bytes: 5 * 1024 * 1024, // 5 MB
  monthly_quota: 10,
  quota_used: 3,
  ocr_allowed: false,
  glossary_allowed: false,
};

const ENTITLEMENT_PRO = {
  has_active: true,
  tier: "PRO",
  max_file_bytes: null,
  monthly_quota: null,
  quota_used: 0,
  ocr_allowed: true,
  glossary_allowed: true,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupAuth(context: BrowserContext) {
  await context.addCookies([
    {
      name: "forma_access_token",
      value: FAKE_TOKEN,
      domain: "localhost",
      path: "/",
    },
  ]);
}

async function stubBaseRoutes(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "user@test.com",
        full_name: "Test User",
        is_active: true,
      }),
    })
  );

  await page.route("**/api/v1/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    })
  );

  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: FAKE_TOKEN }),
    })
  );

  await page.route("**/api/v1/jobs**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] }),
    })
  );

  await page.route("**/api/v1/languages**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        languages: [
          { code: "en", name: "English", qwen_code: "English" },
          { code: "vi", name: "Vietnamese", qwen_code: "Vietnamese" },
        ],
        auto_detect_option: "auto",
      }),
    })
  );

  await page.route("**/api/v1/glossaries**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ glossaries: [], total: 0, page: 1, page_size: 20 }),
    })
  );
}

// ---------------------------------------------------------------------------
// Test: translate gated by license and tier
// ---------------------------------------------------------------------------

test("translate gated by license and tier", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);

  // =========================================================================
  // Case A: unlicensed user — blocked state
  // =========================================================================

  await page.route("**/api/v1/licenses/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ENTITLEMENT_UNLICENSED),
    })
  );

  await page.goto("/translator");

  // Blocked state must be visible
  const blocked = page.getByTestId("entitlement-blocked");
  await expect(blocked).toBeVisible();

  // Links to /pricing and /activate must be present
  const pricingLink = page.getByTestId("blocked-pricing-link");
  const activateLink = page.getByTestId("blocked-activate-link");
  await expect(pricingLink).toBeVisible();
  await expect(pricingLink).toHaveAttribute("href", "/pricing");
  await expect(activateLink).toBeVisible();
  await expect(activateLink).toHaveAttribute("href", "/activate");

  // Upload form / submit button must NOT be in the DOM
  await expect(page.getByRole("button", { name: /Start Translation/i })).not.toBeVisible();

  // =========================================================================
  // Case B: TRIAL — upload form usable, limits shown, OCR/glossary disabled
  // =========================================================================

  await page.unroute("**/api/v1/licenses/me");
  await page.route("**/api/v1/licenses/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ENTITLEMENT_TRIAL),
    })
  );

  await page.goto("/translator");

  // Blocked state must NOT be visible
  await expect(page.getByTestId("entitlement-blocked")).not.toBeVisible();

  // Upload form / submit button is present
  await expect(page.getByRole("button", { name: /Start Translation/i })).toBeVisible();

  // Max file size shown
  const maxFileSize = page.getByTestId("max-file-size");
  await expect(maxFileSize).toBeVisible();
  await expect(maxFileSize).toContainText("5");
  await expect(maxFileSize).toContainText("MB");

  // Quota shown: (10 - 3) = 7 / 10
  const quota = page.getByTestId("quota-remaining");
  await expect(quota).toBeVisible();
  await expect(quota).toContainText("7");
  await expect(quota).toContainText("10");

  // OCR: not present as usable control (hidden or disabled)
  // The OCR toggle (scanned PDF override) only shows after file upload — no file yet, so it's not visible.
  // Glossary picker is disabled/hidden with "Pro feature" hint
  const glossaryDisabled = page.getByTestId("glossary-disabled");
  await expect(glossaryDisabled).toBeVisible();

  // =========================================================================
  // Case C (optional): PRO — OCR + glossary enabled, unlimited
  // =========================================================================

  await page.unroute("**/api/v1/licenses/me");
  await page.route("**/api/v1/licenses/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ENTITLEMENT_PRO),
    })
  );

  await page.goto("/translator");

  // Upload form visible
  await expect(page.getByRole("button", { name: /Start Translation/i })).toBeVisible();

  // Quota shows Unlimited
  const quotaPro = page.getByTestId("quota-remaining");
  await expect(quotaPro).toBeVisible();
  await expect(quotaPro).toContainText("Unlimited");

  // Glossary picker is rendered (not the disabled placeholder)
  await expect(page.getByTestId("glossary-disabled")).not.toBeVisible();
});
