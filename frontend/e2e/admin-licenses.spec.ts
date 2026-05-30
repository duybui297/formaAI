/**
 * TASK-3.1: Admin Dashboard — License Lifecycle Management
 *
 * All /api/* routes are mocked with page.route() so the test suite is
 * fully hermetic — no running backend or database required.
 *
 * Auth: the middleware checks for the "forma_access_token" cookie.
 * We inject it via browserContext.addCookies() and stub /api/auth/me.
 */

import { test, expect, type Page, type BrowserContext } from "@playwright/test";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const NOW = "2026-05-29T00:00:00.000Z";
const EXP = "2027-05-29T00:00:00.000Z";

const LICENSES = [
  {
    id: "lic-1",
    key_masked: "****-****-****-AB12",
    tier: "starter",
    status: "active",
    customer_id: "alice@acme.com",
    max_devices: 1,
    issued_at: NOW,
    activated_at: NOW,
    expired_at: EXP,
  },
  {
    id: "lic-2",
    key_masked: "****-****-****-CD34",
    tier: "professional",
    status: "suspended",
    customer_id: "bob@corp.io",
    max_devices: 5,
    issued_at: NOW,
    activated_at: NOW,
    expired_at: EXP,
  },
  {
    id: "lic-3",
    key_masked: "****-****-****-EF56",
    tier: "enterprise",
    status: "active",
    customer_id: "eve@enterprise.co",
    max_devices: 99,
    issued_at: NOW,
    activated_at: null,
    expired_at: null,
  },
];

const ACTIVITIES = [
  {
    id: "act-1",
    license_id: "lic-1",
    action: "created",
    actor: "admin@system",
    detail: "License provisioned",
    created_at: NOW,
  },
  {
    id: "act-2",
    license_id: "lic-1",
    action: "activated",
    actor: "alice@acme.com",
    detail: null,
    created_at: NOW,
  },
];

const CREATED_LICENSE = {
  id: "lic-new",
  key_masked: "****-****-****-ZZ99",
  tier: "professional",
  status: "active",
  customer_id: "new@test.com",
  max_devices: 1,
  issued_at: NOW,
  activated_at: null,
  expired_at: null,
};

const FAKE_TOKEN = "test-admin-jwt-token";

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
  // Auth /me endpoint — always returns an admin user
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "admin-1",
        email: "admin@test.com",
        full_name: "Test Admin",
        is_active: true,
        is_superuser: true,
      }),
    })
  );

  // Health check (sidebar)
  await page.route("**/api/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    })
  );

  // Auth refresh (in case token refresh fires)
  await page.route("**/api/auth/refresh", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: FAKE_TOKEN }),
    })
  );
}

async function stubLicenseList(page: Page, licenses = LICENSES) {
  await page.route(
    (url) =>
      url.pathname === "/api/admin/licenses" ||
      url.pathname.startsWith("/api/admin/licenses?"),
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          licenses,
          total: licenses.length,
          page: 1,
          page_size: 20,
        }),
      })
  );
}

async function stubLicenseDetail(page: Page, id = "lic-1") {
  await page.route(
    (url) => url.pathname === `/api/admin/licenses/${id}`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(LICENSES.find((l) => l.id === id) ?? LICENSES[0]),
      })
  );
}

async function stubActivities(page: Page, licenseId = "lic-1") {
  await page.route(
    (url) =>
      url.pathname === `/api/admin/licenses/${licenseId}/activities`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(ACTIVITIES),
      })
  );
}

// ---------------------------------------------------------------------------
// 3.1-a: table lists masked sortable
// ---------------------------------------------------------------------------

test("table lists masked sortable", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);
  await stubLicenseList(page);

  await page.goto("/admin/licenses");

  // Page heading
  await expect(page.getByRole("heading", { name: /License Management/i })).toBeVisible();

  // All 3 rows render
  const rows = page.getByTestId("license-row");
  await expect(rows).toHaveCount(3);

  // Masked key is rendered and actually masked (starts with ****)
  const maskedKeys = page.getByTestId("masked-key");
  await expect(maskedKeys).toHaveCount(3);
  const firstKey = await maskedKeys.first().textContent();
  expect(firstKey).toMatch(/^\*{4}-/);

  // Tier badges present
  const tierBadges = page.getByTestId("tier-badge");
  await expect(tierBadges).toHaveCount(3);

  // Status chips present
  const statusChips = page.getByTestId("status-chip");
  await expect(statusChips).toHaveCount(3);

  // Tier badge values
  const tierTexts = await tierBadges.allTextContents();
  expect(tierTexts).toContain("Starter");
  expect(tierTexts).toContain("Professional");
  expect(tierTexts).toContain("Enterprise");

  // Status chip values
  const statusTexts = await statusChips.allTextContents();
  expect(statusTexts).toContain("Active");
  expect(statusTexts).toContain("Suspended");

  // Sort header: clicking "Issued" toggles sort direction in URL
  const sortIssuedBtn = page.getByTestId("sort-issued_at");
  await expect(sortIssuedBtn).toBeVisible();
  await sortIssuedBtn.click();
  await expect(page).toHaveURL(/sort_by=issued_at/);

  // Clicking again toggles sort_dir
  await sortIssuedBtn.click();
  // Either asc or desc present (depends on previous state)
  const url = page.url();
  expect(url).toMatch(/sort_dir=(asc|desc)/);

  // Pagination controls render
  await expect(page.getByTestId("page-prev")).toBeVisible();
  await expect(page.getByTestId("page-next")).toBeVisible();

  // Previous button disabled on page 1
  await expect(page.getByTestId("page-prev")).toBeDisabled();
});

// ---------------------------------------------------------------------------
// 3.1-b: create one-time key copy
// ---------------------------------------------------------------------------

test("create one-time key copy", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);
  await stubLicenseList(page);

  // Stub the POST /admin/licenses endpoint
  let postedBody: unknown = null;
  await page.route("**/api/admin/licenses", async (route) => {
    if (route.request().method() === "POST") {
      postedBody = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          license: CREATED_LICENSE,
          raw_key: "PROF-TEST-KEY-ZZ99",
        }),
      });
    } else {
      // GET list
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          licenses: LICENSES,
          total: LICENSES.length,
          page: 1,
          page_size: 20,
        }),
      });
    }
  });

  await page.goto("/admin/licenses");

  // Open create dialog
  const createBtn = page.getByTestId("create-license-button");
  await expect(createBtn).toBeVisible();
  await createBtn.click();

  // Dialog is visible
  const dialog = page.getByTestId("create-license-dialog");
  await expect(dialog).toBeVisible();

  // Tier select is present
  await expect(page.getByTestId("tier-select")).toBeVisible();

  // Fill customer ID
  await page.getByTestId("customer-id-input").fill("new@test.com");

  // Submit
  await page.getByTestId("create-license-submit").click();

  // One-time key dialog appears
  const keyDialog = page.getByTestId("one-time-key-dialog");
  await expect(keyDialog).toBeVisible();

  // Raw key is displayed
  const keyInput = page.getByTestId("raw-key-display");
  await expect(keyInput).toBeVisible();
  const keyValue = await keyInput.inputValue();
  expect(keyValue).toBe("PROF-TEST-KEY-ZZ99");

  // Copy button is present and clickable
  const copyBtn = page.getByTestId("copy-key-button");
  await expect(copyBtn).toBeVisible();
  // Grant clipboard permissions
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await copyBtn.click();

  // Copy success message appears
  await expect(page.getByTestId("copy-success")).toBeVisible();

  // Verify the POST was made with the expected fields
  expect(postedBody).toMatchObject({ tier: "starter", customer_id: "new@test.com" });

  // Close the dialog
  await page.getByTestId("close-key-dialog").click();
  await expect(keyDialog).not.toBeVisible();
});

// ---------------------------------------------------------------------------
// 3.1-c: filters persist in url
// ---------------------------------------------------------------------------

test("filters persist in url", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);

  // Track what filter params the list was called with
  const calledParams: string[] = [];
  await page.route(
    (url) =>
      url.pathname === "/api/admin/licenses" ||
      url.pathname.startsWith("/api/admin/licenses"),
    (route) => {
      calledParams.push(route.request().url());
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          licenses: LICENSES.filter((l) => {
            const url = new URL(route.request().url());
            const tierFilter = url.searchParams.get("tier");
            const statusFilter = url.searchParams.get("status");
            return (
              (!tierFilter || l.tier === tierFilter) &&
              (!statusFilter || l.status === statusFilter)
            );
          }),
          total: 1,
          page: 1,
          page_size: 20,
        }),
      });
    }
  );

  await page.goto("/admin/licenses");

  // ---- Tier filter ----
  const tierSelect = page.getByTestId("filter-tier");
  await expect(tierSelect).toBeVisible();

  // Click the tier select trigger and choose "Professional"
  await tierSelect.click();
  await page.getByRole("option", { name: "Professional" }).click();

  // URL should now contain tier=professional
  await expect(page).toHaveURL(/tier=professional/);

  // ---- Status filter ----
  const statusSelect = page.getByTestId("filter-status");
  await expect(statusSelect).toBeVisible();
  await statusSelect.click();
  await page.getByRole("option", { name: "Active" }).click();

  // URL should contain both filters
  await expect(page).toHaveURL(/tier=professional/);
  await expect(page).toHaveURL(/status=active/);

  // ---- Date filter ----
  const issuedAfterInput = page.getByTestId("filter-issued-after");
  await expect(issuedAfterInput).toBeVisible();
  await issuedAfterInput.fill("2026-01-01");

  // URL persists issued_after
  await expect(page).toHaveURL(/issued_after=2026-01-01/);

  // ---- Survive reload ----
  const urlBeforeReload = page.url();
  await page.goto(urlBeforeReload);

  // After reload, filters are still in the URL
  await expect(page).toHaveURL(/tier=professional/);
  await expect(page).toHaveURL(/status=active/);
  await expect(page).toHaveURL(/issued_after=2026-01-01/);

  // Filter controls reflect the persisted values
  // The select trigger should display "Professional"
  await expect(tierSelect).toContainText("Professional");
  await expect(statusSelect).toContainText("Active");
});

// ---------------------------------------------------------------------------
// 3.1-d: bulk actions and detail drawer
// ---------------------------------------------------------------------------

test("bulk actions and detail drawer", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page);
  await stubLicenseList(page);
  await stubActivities(page, "lic-1");

  // Stub bulk suspend
  let suspendBody: unknown = null;
  await page.route("**/api/admin/licenses/suspend", async (route) => {
    suspendBody = JSON.parse(route.request().postData() ?? "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true }),
    });
  });

  // Stub bulk revoke
  let revokeBody: unknown = null;
  await page.route("**/api/admin/licenses/revoke", async (route) => {
    revokeBody = JSON.parse(route.request().postData() ?? "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true }),
    });
  });

  // Stub extend expiry
  await page.route("**/api/admin/licenses/lic-1/extend", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...LICENSES[0], expired_at: "2028-01-01T00:00:00.000Z" }),
    });
  });

  // Stub activities for detail drawer
  await page.route("**/api/admin/licenses/lic-1/activities", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ACTIVITIES),
    })
  );

  await page.goto("/admin/licenses");

  // ---- Multi-select ----
  const rows = page.getByTestId("license-row");
  await expect(rows).toHaveCount(3);

  // Select first two checkboxes
  const firstCheckbox = page.getByTestId(`select-lic-1`);
  const secondCheckbox = page.getByTestId(`select-lic-2`);
  await firstCheckbox.click();
  await secondCheckbox.click();

  // Bulk actions bar appears
  const bulkBar = page.getByTestId("bulk-actions-bar");
  await expect(bulkBar).toBeVisible();
  await expect(bulkBar).toContainText("2 selected");

  // ---- Bulk Suspend ----
  const suspendBtn = page.getByTestId("bulk-suspend");
  await expect(suspendBtn).toBeVisible();
  await suspendBtn.click();

  // Wait for suspend to fire and confirm the request body
  await page.waitForResponse("**/api/admin/licenses/suspend");
  expect(suspendBody).toMatchObject({ ids: expect.arrayContaining(["lic-1", "lic-2"]) });

  // After suspend, selection is cleared
  await expect(bulkBar).not.toBeVisible();

  // Re-select for revoke test
  await firstCheckbox.click();
  await expect(bulkBar).toBeVisible();

  // ---- Bulk Revoke ----
  const revokeBtn = page.getByTestId("bulk-revoke");
  await expect(revokeBtn).toBeVisible();

  // Handle the confirm() dialog
  page.on("dialog", (dialog) => dialog.accept());
  await revokeBtn.click();

  await page.waitForResponse("**/api/admin/licenses/revoke");
  expect(revokeBody).toMatchObject({ ids: expect.arrayContaining(["lic-1"]) });

  // ---- Detail drawer ----
  // Click first row to open drawer
  await rows.first().click();

  const drawer = page.getByTestId("license-detail-drawer");
  await expect(drawer).toBeVisible();

  // Activity timeline is present
  const timeline = page.getByTestId("activity-timeline");
  await expect(timeline).toBeVisible();

  // At least one activity entry
  const activityItems = timeline.locator("li");
  await expect(activityItems).toHaveCount(ACTIVITIES.length);

  // First activity shows "created"
  await expect(activityItems.first()).toContainText("created");

  // Extend Expiry button present
  const extendBtn = page.getByTestId("extend-expiry-button");
  await expect(extendBtn).toBeVisible();

  // Click Extend Expiry to reveal form
  await extendBtn.click();
  const extendForm = page.getByTestId("extend-expiry-form");
  await expect(extendForm).toBeVisible();

  // Fill a date and submit
  const extendDateInput = page.getByTestId("extend-date-input");
  await extendDateInput.fill("2028-01-01");

  const extendSubmitBtn = page.getByTestId("extend-expiry-submit");
  await expect(extendSubmitBtn).toBeEnabled();
  await extendSubmitBtn.click();

  await page.waitForResponse("**/api/admin/licenses/lic-1/extend");

  // Extend form closes after success
  await expect(extendForm).not.toBeVisible();

  // Close drawer — use the footer Close button (not the dialog X)
  await drawer.getByRole("button", { name: "Close" }).first().click();
  await expect(drawer).not.toBeVisible();
});

// ---------------------------------------------------------------------------
// Admin route guard (added with the AppSidebar role-gating fix)
// ---------------------------------------------------------------------------

test("non-admin redirected from admin", async ({ page, context }) => {
  await setupAuth(context);
  // /me as a NON-admin user (is_superuser false)
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "user@test.com",
        full_name: "Regular User",
        is_active: true,
        is_superuser: false,
      }),
    })
  );
  await page.route("**/api/health", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  );

  await page.goto("/admin/licenses");
  // AdminLayout guard must bounce a non-admin to /dashboard
  await page.waitForURL("**/dashboard", { timeout: 10000 });
  expect(page.url()).toContain("/dashboard");
});
