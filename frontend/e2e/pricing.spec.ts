/**
 * TASK-3.3: Pricing → Self-serve License (behaviors 3.3-c, 3.3-d)
 *
 * All /api/* routes are mocked with page.route() — no running backend required.
 *
 * /pricing is under the (app) route group, behind the middleware auth guard.
 * Auth: the middleware checks for the "forma_access_token" cookie.
 * We inject it via browserContext.addCookies() and stub /api/auth/me.
 *
 * Verification commands:
 *   cd frontend && npx playwright test e2e/pricing.spec.ts -g 'plan checkout issues key'
 *   cd frontend && npx playwright test e2e/pricing.spec.ts -g 'plans aligned to tiers'
 */

import { test, expect, type Page, type BrowserContext } from "@playwright/test";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const FAKE_TOKEN = "test-pricing-jwt-token";

const CHECKOUT_FIXTURE = {
  raw_key: "TEST-KEY-1234-5678",
  tier: "PRO",
  status: "PENDING",
  id: "lic-checkout-1",
  issued_at: "2026-05-30T00:00:00.000Z",
  expired_at: null,
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
  await page.route("**/api/auth/me", (route) =>
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

  await page.route("**/api/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    })
  );

  await page.route("**/api/auth/refresh", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: FAKE_TOKEN }),
    })
  );
}

// ---------------------------------------------------------------------------
// 3.3-c: plan checkout issues key
// ---------------------------------------------------------------------------

test("plan checkout issues key", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);

  // Track whether the checkout endpoint was actually called
  let checkoutCalled = false;
  let checkoutBody: unknown = null;

  await page.route("**/api/licenses/checkout", async (route) => {
    checkoutCalled = true;
    checkoutBody = JSON.parse(route.request().postData() ?? "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(CHECKOUT_FIXTURE),
    });
  });

  await page.goto("/pricing");

  // Click the Pro plan CTA button
  const proBtn = page.getByTestId("checkout-btn-pro");
  await expect(proBtn).toBeVisible();
  await proBtn.click();

  // Assert checkout endpoint was called
  await page.waitForFunction(() => true); // yield to network
  expect(checkoutCalled).toBe(true);
  expect((checkoutBody as { plan?: string })?.plan).toBe("pro");

  // Assert one-time key dialog is visible
  const dialog = page.getByTestId("one-time-key-dialog");
  await expect(dialog).toBeVisible();

  // Assert the raw key is displayed
  const keyDisplay = page.getByTestId("raw-key-display");
  await expect(keyDisplay).toBeVisible();
  await expect(keyDisplay).toHaveValue("TEST-KEY-1234-5678");

  // Assert an /activate link is present in the dialog
  const activateLink = page.getByTestId("activate-link");
  await expect(activateLink).toBeVisible();
  await expect(activateLink).toHaveAttribute("href", "/activate");
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
