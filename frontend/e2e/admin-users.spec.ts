/**
 * TASK-3.6: Admin User Management
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

const USERS = [
  {
    id: "user-1",
    email: "admin@test.com",
    full_name: "Test Admin",
    is_active: true,
    is_superuser: true,
    created_at: NOW,
  },
  {
    id: "user-2",
    email: "alice@test.com",
    full_name: "Alice User",
    is_active: true,
    is_superuser: false,
    created_at: NOW,
  },
  {
    id: "user-3",
    email: "bob@test.com",
    full_name: null,
    is_active: false,
    is_superuser: false,
    created_at: NOW,
  },
];

const ME_ADMIN = {
  id: "admin-1",
  email: "admin@test.com",
  full_name: "Test Admin",
  is_active: true,
  is_superuser: true,
};

const ME_USER = {
  id: "user-99",
  email: "regular@test.com",
  full_name: "Regular User",
  is_active: true,
  is_superuser: false,
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

async function stubBaseRoutes(page: Page, meOverride = ME_ADMIN) {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(meOverride),
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

async function stubUserList(page: Page, users = USERS) {
  await page.route(
    (url) =>
      url.pathname === "/api/admin/users" ||
      url.pathname.startsWith("/api/admin/users"),
    (route) => {
      // Only intercept GET requests here (not PATCH/DELETE)
      if (route.request().method() !== "GET") {
        return route.continue();
      }
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          users,
          total: users.length,
          page: 1,
          page_size: 20,
        }),
      });
    }
  );
}

// ---------------------------------------------------------------------------
// 3.6-f: users tab visible admin only
// ---------------------------------------------------------------------------

test("users tab visible admin only", async ({ page, context }) => {
  await setupAuth(context);

  // --- Admin sees Users tab ---
  await stubBaseRoutes(page, ME_ADMIN);
  await stubUserList(page);

  await page.goto("/admin/users");

  // Users nav link should be visible in the sidebar
  const usersNavLink = page.getByRole("link", { name: /^Users$/ });
  await expect(usersNavLink).toBeVisible();
  // It should point to /admin/users
  const href = await usersNavLink.getAttribute("href");
  expect(href).toBe("/admin/users");

  // Page should load and show User Management heading
  await expect(
    page.getByRole("heading", { name: /User Management/i })
  ).toBeVisible();

  // --- Non-admin does NOT see Users tab, gets redirected from /admin/users ---
  // Create a fresh page for the non-admin test
  const page2 = await context.newPage();

  await page2.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(ME_USER),
    })
  );
  await page2.route("**/api/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    })
  );
  await page2.route("**/api/auth/refresh", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: FAKE_TOKEN }),
    })
  );

  // Non-admin navigates to a regular page and checks sidebar
  await page2.goto("/dashboard");

  // Users tab should NOT be visible for non-admin
  const usersNavLink2 = page2.getByRole("link", { name: /^Users$/ });
  await expect(usersNavLink2).not.toBeVisible();

  // Navigating directly to /admin/users should redirect to /dashboard
  await page2.goto("/admin/users");
  await page2.waitForURL("**/dashboard", { timeout: 10000 });
  expect(page2.url()).toContain("/dashboard");

  await page2.close();
});

// ---------------------------------------------------------------------------
// 3.6-g: list create and row actions
// ---------------------------------------------------------------------------

test("list create and row actions", async ({ page, context }) => {
  await setupAuth(context);
  await stubBaseRoutes(page, ME_ADMIN);

  // Use ME_ADMIN id "admin-1" which matches USERS[0] id "user-1"? No — use a
  // separate admin id so we can also test own-row disabling.
  // ME_ADMIN.id = "admin-1"; USERS[0].id = "user-1".
  // To test own-row disabling, add a user whose id matches ME_ADMIN.id.
  const usersWithSelf = [
    {
      id: "admin-1", // matches ME_ADMIN.id
      email: "admin@test.com",
      full_name: "Test Admin",
      is_active: true,
      is_superuser: true,
      created_at: NOW,
    },
    ...USERS.slice(1),
  ];

  // Track GET calls separately from mutations
  let listCallCount = 0;
  await page.route(
    (url) => url.pathname === "/api/admin/users",
    (route) => {
      if (route.request().method() === "GET") {
        listCallCount++;
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            users: usersWithSelf,
            total: usersWithSelf.length,
            page: 1,
            page_size: 20,
          }),
        });
      } else {
        route.continue();
      }
    }
  );

  await page.goto("/admin/users");

  // ---- Table renders rows ----
  await expect(page.getByRole("heading", { name: /User Management/i })).toBeVisible();

  // All users render
  for (const user of usersWithSelf) {
    await expect(page.getByTestId(`user-row-${user.id}`)).toBeVisible();
  }

  // Role badges present
  const roleBadges = page.getByTestId("role-badge");
  await expect(roleBadges).toHaveCount(usersWithSelf.length);
  const roleTexts = await roleBadges.allTextContents();
  expect(roleTexts).toContain("Admin");
  expect(roleTexts).toContain("User");

  // Active chips present
  const activeChips = page.getByTestId("active-chip");
  await expect(activeChips).toHaveCount(usersWithSelf.length);
  const chipTexts = await activeChips.allTextContents();
  expect(chipTexts).toContain("Active");
  expect(chipTexts).toContain("Inactive");

  // Pagination controls render
  await expect(page.getByTestId("page-prev")).toBeVisible();
  await expect(page.getByTestId("page-next")).toBeVisible();
  await expect(page.getByTestId("page-prev")).toBeDisabled();

  // ---- Own row actions are disabled ----
  const selfDeactivateBtn = page.getByTestId("deactivate-admin-1");
  await expect(selfDeactivateBtn).toBeDisabled();
  const selfDemoteBtn = page.getByTestId("demote-admin-1");
  await expect(selfDemoteBtn).toBeDisabled();
  const selfDeleteBtn = page.getByTestId("delete-admin-1");
  await expect(selfDeleteBtn).toBeDisabled();

  // ---- Create user dialog ----
  let postedBody: unknown = null;
  await page.route("**/api/admin/users", async (route) => {
    if (route.request().method() === "POST") {
      postedBody = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "user-new",
          email: "new@test.com",
          full_name: "New User",
          is_active: true,
          is_superuser: false,
          created_at: NOW,
        }),
      });
    } else {
      await route.continue();
    }
  });

  await page.getByTestId("create-user-button").click();
  const dialog = page.getByTestId("create-user-dialog");
  await expect(dialog).toBeVisible();

  await page.getByTestId("email-input").fill("new@test.com");
  await page.getByTestId("full-name-input").fill("New User");
  await page.getByTestId("password-input").fill("password123");
  // role stays "user" by default

  await page.getByTestId("create-user-submit").click();

  // Dialog closes after success
  await expect(dialog).not.toBeVisible();

  // POST was called with correct fields
  expect(postedBody).toMatchObject({
    email: "new@test.com",
    full_name: "New User",
    password: "password123",
    is_superuser: false,
  });

  // List was re-fetched (invalidation)
  expect(listCallCount).toBeGreaterThan(1);

  // ---- Deactivate action (user-2) ----
  let patchedId: string | null = null;
  let patchBody: unknown = null;
  await page.route("**/api/admin/users/user-2", async (route) => {
    if (route.request().method() === "PATCH") {
      patchedId = "user-2";
      patchBody = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...usersWithSelf[1], is_active: false }),
      });
    } else {
      await route.continue();
    }
  });

  await page.getByTestId("deactivate-user-2").click();
  await page.waitForResponse("**/api/admin/users/user-2");
  expect(patchedId).toBe("user-2");
  expect(patchBody).toMatchObject({ is_active: false });

  // ---- Promote action (user-2) ----
  patchedId = null;
  patchBody = null;
  await page.route("**/api/admin/users/user-2", async (route) => {
    if (route.request().method() === "PATCH") {
      patchedId = "user-2";
      patchBody = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...usersWithSelf[1], is_superuser: true }),
      });
    } else {
      await route.continue();
    }
  });

  await page.getByTestId("promote-user-2").click();
  await page.waitForResponse("**/api/admin/users/user-2");
  expect(patchedId).toBe("user-2");
  expect(patchBody).toMatchObject({ is_superuser: true });

  // ---- Delete action (user-3) ----
  let deletedId: string | null = null;
  await page.route("**/api/admin/users/user-3", async (route) => {
    if (route.request().method() === "DELETE") {
      deletedId = "user-3";
      await route.fulfill({ status: 204 });
    } else {
      await route.continue();
    }
  });

  await page.getByTestId("delete-user-3").click();

  // Confirm dialog appears
  const confirmDialog = page.getByTestId("confirm-delete-dialog");
  await expect(confirmDialog).toBeVisible();

  await page.getByTestId("confirm-delete-submit").click();
  await page.waitForResponse("**/api/admin/users/user-3");
  expect(deletedId).toBe("user-3");
});
