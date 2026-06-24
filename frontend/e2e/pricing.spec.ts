/**
 * TASK-3.3 / TASK-3.5: Pricing page behaviors
 *
 * All /api/v1/* routes are mocked with page.route() — no running backend required.
 *
 * /pricing is under the (app) route group, behind the middleware auth guard.
 * Auth: the middleware checks for the "forma_access_token" cookie.
 * We inject it via browserContext.addCookies() and stub /api/v1/auth/me.
 *
 * Verification commands:
 *   cd frontend && npx playwright test e2e/pricing.spec.ts -g 'plan opens lead capture'
 *   cd frontend && npx playwright test e2e/pricing.spec.ts -g 'plans aligned to tiers'
 */

import { test, expect, type Page, type BrowserContext } from "@playwright/test";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const FAKE_TOKEN = "test-pricing-jwt-token";

const LEAD_FIXTURE = {
  id: "lead-1",
  email: "test@example.com",
  plan: "pro",
  created_at: "2026-05-30T00:00:00.000Z",
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
}

// ---------------------------------------------------------------------------
// 3.3-c: plan opens lead capture
// ---------------------------------------------------------------------------

test("plan opens lead capture", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);

  // Track leads endpoint call and capture request body
  let leadCalled = false;
  let leadBody: unknown = null;

  await page.route("**/api/v1/leads", async (route) => {
    leadCalled = true;
    leadBody = JSON.parse(route.request().postData() ?? "{}");
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(LEAD_FIXTURE),
    });
  });

  // Assert NO checkout endpoint is called
  let checkoutCalled = false;
  await page.route("**/api/v1/licenses/checkout", async (route) => {
    checkoutCalled = true;
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });

  await page.goto("/pricing");

  // Click the Pro plan CTA button
  const proBtn = page.getByTestId("checkout-btn-pro");
  await expect(proBtn).toBeVisible();
  await proBtn.click();

  // Assert lead-capture dialog appears (NOT one-time key dialog)
  const dialog = page.getByTestId("lead-capture-dialog");
  await expect(dialog).toBeVisible();

  // Assert NO license key dialog / raw key is shown
  await expect(page.getByTestId("one-time-key-dialog")).not.toBeVisible();
  await expect(page.getByTestId("raw-key-display")).not.toBeVisible();

  // Assert checkout was NOT called
  expect(checkoutCalled).toBe(false);

  // Fill in email and submit
  const emailInput = page.getByTestId("lead-email-input");
  await expect(emailInput).toBeVisible();
  await emailInput.fill("test@example.com");

  const submitBtn = page.getByTestId("lead-capture-submit");
  await expect(submitBtn).toBeEnabled();
  await submitBtn.click();

  // Wait for POST /api/v1/leads
  await page.waitForResponse("**/api/v1/leads");

  // Assert leads endpoint was called with correct body
  expect(leadCalled).toBe(true);
  expect((leadBody as { email?: string; plan?: string })?.email).toBe("test@example.com");
  expect((leadBody as { email?: string; plan?: string })?.plan).toBe("pro");

  // Assert thank-you state shown
  const successEl = page.getByTestId("lead-capture-success");
  await expect(successEl).toBeVisible();

  // Assert no raw key is ever shown
  await expect(page.getByTestId("raw-key-display")).not.toBeVisible();
  await expect(page.getByTestId("one-time-key-dialog")).not.toBeVisible();
});

// ---------------------------------------------------------------------------
// 3.3-d: plans aligned to tiers
// ---------------------------------------------------------------------------

test("plans aligned to tiers", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);

  await page.goto("/pricing");

  // Assert each plan card exposes the correct tier via data-tier attribute
  const freeCard = page.locator("[data-plan='free']");
  await expect(freeCard).toBeVisible();
  await expect(freeCard).toHaveAttribute("data-tier", "TRIAL");

  const proCard = page.locator("[data-plan='pro']");
  await expect(proCard).toBeVisible();
  await expect(proCard).toHaveAttribute("data-tier", "PRO");

  const businessCard = page.locator("[data-plan='business']");
  await expect(businessCard).toBeVisible();
  await expect(businessCard).toHaveAttribute("data-tier", "ENTERPRISE");

  // Also assert the visible tier labels are present
  await expect(freeCard.getByText("License: TRIAL")).toBeVisible();
  await expect(proCard.getByText("License: PRO")).toBeVisible();
  await expect(businessCard.getByText("License: ENTERPRISE")).toBeVisible();
});
