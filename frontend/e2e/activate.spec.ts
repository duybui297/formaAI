/**
 * TASK-3.2: Client Activation Screen & Expiry Warning Banner
 *
 * All /api/* routes are mocked with page.route() — no running backend required.
 *
 * /activate is a PUBLIC route (no auth cookie needed — same as /login).
 * For banner tests, we need the (app) shell, so we use auth + /dashboard stub.
 *
 * Auth: the middleware checks for the "forma_access_token" cookie.
 * We inject it via browserContext.addCookies() and stub /api/auth/me.
 */

import { test, expect, type Page, type BrowserContext } from "@playwright/test";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const FAKE_TOKEN = "test-jwt-token-3.2";

const SUCCESS_RESPONSE = {
  tier: "professional",
  expiry: "2027-06-01T00:00:00.000Z",
  status: "active",
  features: ["Translation", "Glossary", "Priority Support"],
};

/** Expiry 3 days from now (< 7 days → banner shows) */
function expiryInDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

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
// 3.2-a: autoformat and submit
// ---------------------------------------------------------------------------

test("autoformat and submit", async ({ page }) => {
  // /activate is public — no auth cookie required
  let capturedBody: unknown = null;

  await page.route("**/api/licenses/activate", async (route) => {
    capturedBody = JSON.parse(route.request().postData() ?? "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SUCCESS_RESPONSE),
    });
  });

  await page.goto("/activate");

  // Page renders
  await expect(page.getByRole("heading", { name: /Activate License/i })).toBeVisible();

  const input = page.getByTestId("license-key-input");
  await expect(input).toBeVisible();

  // Type raw key without hyphens — expect auto-format to insert them
  await input.fill("ABCD1234EFGH5678");
  // After fill, input should show formatted value ABCD-1234-EFGH-5678
  const formatted = await input.inputValue();
  expect(formatted).toBe("ABCD-1234-EFGH-5678");

  // Submit
  const submitBtn = page.getByTestId("activate-submit");
  await expect(submitBtn).toBeEnabled();
  await submitBtn.click();

  // POST was called
  await page.waitForResponse("**/api/licenses/activate");
  expect(capturedBody).toMatchObject({ raw_key: "ABCD-1234-EFGH-5678" });

  // Success card appears
  await expect(page.getByTestId("activate-success")).toBeVisible();
});

// ---------------------------------------------------------------------------
// 3.2-b: success and error states
// ---------------------------------------------------------------------------

test("success and error states", async ({ page }) => {
  // ---- SUCCESS STATE ----
  await page.route("**/api/licenses/activate", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SUCCESS_RESPONSE),
    })
  );

  await page.goto("/activate");

  await page.getByTestId("license-key-input").fill("GOOD-KEY1-GOOD-KEY2");
  await page.getByTestId("activate-submit").click();
  await page.waitForResponse("**/api/licenses/activate");

  const successCard = page.getByTestId("activate-success");
  await expect(successCard).toBeVisible();

  // Tier displayed
  await expect(page.getByTestId("success-tier")).toContainText("Professional");

  // Expiry displayed (some date text)
  await expect(page.getByTestId("success-expiry")).not.toBeEmpty();

  // Features listed
  const featuresEl = page.getByTestId("success-features");
  await expect(featuresEl).toContainText("Translation");
  await expect(featuresEl).toContainText("Glossary");

  // ---- INVALID_KEY — RED ----
  await page.unroute("**/api/licenses/activate");
  await page.route("**/api/licenses/activate", (route) =>
    route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({ code: "INVALID_KEY", message: "Invalid license key." }),
    })
  );

  // Navigate fresh
  await page.goto("/activate");
  await page.getByTestId("license-key-input").fill("BAAD-BAAD-BAAD-BAAD");
  await page.getByTestId("activate-submit").click();
  await page.waitForResponse("**/api/licenses/activate");

  const errorEl = page.getByTestId("activate-error");
  await expect(errorEl).toBeVisible();
  // data-variant="red" on error container
  await expect(errorEl).toHaveAttribute("data-variant", "red");
  await expect(errorEl).toHaveAttribute("data-code", "INVALID_KEY");

  // ---- ALREADY_ACTIVATED — AMBER ----
  await page.unroute("**/api/licenses/activate");
  await page.route("**/api/licenses/activate", (route) =>
    route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        code: "ALREADY_ACTIVATED",
        message: "Already activated on another device.",
      }),
    })
  );

  await page.goto("/activate");
  await page.getByTestId("license-key-input").fill("USED-USED-USED-USED");
  await page.getByTestId("activate-submit").click();
  await page.waitForResponse("**/api/licenses/activate");

  const alreadyEl = page.getByTestId("activate-error");
  await expect(alreadyEl).toBeVisible();
  await expect(alreadyEl).toHaveAttribute("data-variant", "amber");
  await expect(alreadyEl).toHaveAttribute("data-code", "ALREADY_ACTIVATED");

  // ---- EXPIRED — RED + renewal link ----
  await page.unroute("**/api/licenses/activate");
  await page.route("**/api/licenses/activate", (route) =>
    route.fulfill({
      status: 410,
      contentType: "application/json",
      body: JSON.stringify({
        code: "EXPIRED",
        message: "This license key has expired.",
      }),
    })
  );

  await page.goto("/activate");
  await page.getByTestId("license-key-input").fill("EXPR-EXPR-EXPR-EXPR");
  await page.getByTestId("activate-submit").click();
  await page.waitForResponse("**/api/licenses/activate");

  const expiredEl = page.getByTestId("activate-error");
  await expect(expiredEl).toBeVisible();
  await expect(expiredEl).toHaveAttribute("data-variant", "red");
  await expect(expiredEl).toHaveAttribute("data-code", "EXPIRED");
  // Renewal link shown for EXPIRED only
  await expect(page.getByTestId("renewal-link")).toBeVisible();
});

// ---------------------------------------------------------------------------
// 3.2-c: expiry warning banner
// ---------------------------------------------------------------------------

test("expiry warning banner", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);

  // Stub dashboard and admin routes so the (app) shell renders without errors
  await page.route("**/api/admin/licenses**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ licenses: [], total: 0, page: 1, page_size: 20 }),
    })
  );

  await page.route("**/api/jobs**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] }),
    })
  );

  await page.goto("/dashboard");

  // No banner without license in localStorage
  await expect(page.getByTestId("expiry-banner")).not.toBeVisible();

  // Inject a license expiring in 3 days (< 7 → banner should appear)
  const nearExpiryLicense = {
    tier: "starter",
    expiry: expiryInDays(3),
    status: "active",
    features: ["Translation"],
  };

  await page.evaluate((lic) => {
    localStorage.setItem("forma_license", JSON.stringify(lic));
  }, nearExpiryLicense);

  // Reload so ExpiryBanner reads localStorage on mount
  await page.reload();
  await stubBaseRoutes(page);
  await page.route("**/api/admin/licenses**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ licenses: [], total: 0, page: 1, page_size: 20 }),
    })
  );
  await page.route("**/api/jobs**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] }),
    })
  );

  const banner = page.getByTestId("expiry-banner");
  await expect(banner).toBeVisible();
  // data-days reflects remaining days
  const daysAttr = await banner.getAttribute("data-days");
  expect(Number(daysAttr)).toBeLessThan(7);

  // Banner renewal link NOT shown (not yet expired)
  await expect(page.getByTestId("banner-renewal-link")).not.toBeVisible();

  // ---- EXPIRED: days <= 0 → renewal link shows ----
  const expiredLicense = {
    tier: "starter",
    expiry: expiryInDays(-1), // yesterday
    status: "expired",
    features: [],
  };

  await page.evaluate((lic) => {
    localStorage.setItem("forma_license", JSON.stringify(lic));
    localStorage.removeItem("forma_expiry_banner_dismissed");
  }, expiredLicense);

  await page.reload();
  await stubBaseRoutes(page);
  await page.route("**/api/admin/licenses**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ licenses: [], total: 0, page: 1, page_size: 20 }),
    })
  );
  await page.route("**/api/jobs**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] }),
    })
  );

  await expect(page.getByTestId("expiry-banner")).toBeVisible();
  await expect(page.getByTestId("expiry-banner")).toHaveAttribute("data-expired", "true");
  await expect(page.getByTestId("banner-renewal-link")).toBeVisible();
});

// ---------------------------------------------------------------------------
// 3.2-d: banner dismiss persists
// ---------------------------------------------------------------------------

test("banner dismiss persists", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);

  await page.route("**/api/admin/licenses**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ licenses: [], total: 0, page: 1, page_size: 20 }),
    })
  );
  await page.route("**/api/jobs**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] }),
    })
  );

  // Seed a near-expiry license and clear dismissed state
  const nearExpiryLicense = {
    tier: "professional",
    expiry: expiryInDays(2),
    status: "active",
    features: ["Translation"],
  };

  await page.goto("/dashboard");

  await page.evaluate((lic) => {
    localStorage.setItem("forma_license", JSON.stringify(lic));
    localStorage.removeItem("forma_expiry_banner_dismissed");
  }, nearExpiryLicense);

  await page.reload();
  await stubBaseRoutes(page);
  await page.route("**/api/admin/licenses**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ licenses: [], total: 0, page: 1, page_size: 20 }),
    })
  );
  await page.route("**/api/jobs**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] }),
    })
  );

  // Banner should be visible
  const banner = page.getByTestId("expiry-banner");
  await expect(banner).toBeVisible();

  // Click dismiss
  await page.getByTestId("expiry-banner-dismiss").click();

  // Banner gone immediately
  await expect(banner).not.toBeVisible();

  // localStorage dismiss key is set
  const dismissedValue = await page.evaluate(() =>
    localStorage.getItem("forma_expiry_banner_dismissed")
  );
  expect(dismissedValue).not.toBeNull();

  // Reload — banner stays hidden (persisted dismiss)
  await page.reload();
  await stubBaseRoutes(page);
  await page.route("**/api/admin/licenses**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ licenses: [], total: 0, page: 1, page_size: 20 }),
    })
  );
  await page.route("**/api/jobs**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] }),
    })
  );

  await expect(page.getByTestId("expiry-banner")).not.toBeVisible();
});

// ---------------------------------------------------------------------------
// 3.5-d: activate success contract
// ---------------------------------------------------------------------------

test("activate success contract", async ({ page }) => {
  // /activate is public — no auth cookie required
  const ACTIVATE_RESPONSE = {
    id: "lic-abc123",
    tier: "pro",
    status: "active",
    activated_at: "2026-05-30T10:00:00.000Z",
    expired_at: "2027-05-30T10:00:00.000Z",
    expiry: "2027-05-30T10:00:00.000Z",
    features: ["Translation", "Glossary", "Priority Support"],
  };

  let capturedBody: unknown = null;

  await page.route("**/api/licenses/activate", async (route) => {
    capturedBody = JSON.parse(route.request().postData() ?? "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ACTIVATE_RESPONSE),
    });
  });

  await page.goto("/activate");

  const input = page.getByTestId("license-key-input");
  await expect(input).toBeVisible();
  await input.fill("GOOD-KEY1-GOOD-KEY2");

  const submitBtn = page.getByTestId("activate-submit");
  await expect(submitBtn).toBeEnabled();
  await submitBtn.click();

  await page.waitForResponse("**/api/licenses/activate");

  // Assert request body uses raw_key (not key)
  expect((capturedBody as Record<string, unknown>)?.raw_key).toBe("GOOD-KEY1-GOOD-KEY2");
  expect((capturedBody as Record<string, unknown>)?.key).toBeUndefined();

  // Assert success view renders
  const successCard = page.getByTestId("activate-success");
  await expect(successCard).toBeVisible();

  // Assert tier is rendered (capitalized from "pro" → "Pro")
  await expect(page.getByTestId("success-tier")).toContainText("Pro");

  // Assert expiry is rendered
  await expect(page.getByTestId("success-expiry")).not.toBeEmpty();

  // Assert at least one feature is rendered
  const featuresEl = page.getByTestId("success-features");
  await expect(featuresEl).toBeVisible();
  await expect(featuresEl).toContainText("Translation");
});
