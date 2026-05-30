/**
 * TASK-3.4: User Registration — behaviors 3.4-d and 3.4-e
 *
 * All /api/* routes are mocked with page.route() — no running backend required.
 *
 * /register is a PUBLIC AUTH_ROUTE (middleware.ts).
 * On success, the page calls registerApi → loginApi → /api/auth/me, then
 * router.push("/translator").
 *
 * 3.4-d: register success — valid form → account created → lands in app
 * 3.4-e: register validation — password mismatch → inline error, no navigation
 */

import { test, expect, type Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FAKE_TOKEN = "test-jwt-token-3.4";

const FAKE_USER = {
  id: "user-3.4",
  email: "newuser@example.com",
  full_name: "New User",
  is_active: true,
  is_superuser: false,
};

// ---------------------------------------------------------------------------
// Stub helpers
// ---------------------------------------------------------------------------

/** Stub all routes needed after a successful register+login flow */
async function stubPostRegisterRoutes(page: Page) {
  // The page calls /api/auth/register (via authFetch which prepends /api)
  await page.route("**/api/auth/register", (route) =>
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ message: "User created successfully" }),
    })
  );

  // The page calls /api/auth/login after registration
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: FAKE_TOKEN }),
    })
  );

  // The page fetches /api/auth/me after getting the token
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_USER),
    })
  );

  // App shell may call these
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
// 3.4-d: register success
// ---------------------------------------------------------------------------

test("register success", async ({ page }) => {
  await stubPostRegisterRoutes(page);

  await page.goto("/register");

  // Confirm the page renders
  await expect(page.getByRole("heading", { name: /Create your account/i })).toBeVisible();

  // Fill the form
  await page.fill("#full_name", "New User");
  await page.fill("#email", "newuser@example.com");
  await page.fill("#password", "SecurePass123");
  await page.fill("#confirmPassword", "SecurePass123");

  // Submit
  await page.click('button[type="submit"]');

  // After register + login + me, router.push("/translator") fires
  // Middleware will allow access since the cookie/token is set
  await page.waitForURL("**/translator", { timeout: 15000 });
  expect(page.url()).toContain("/translator");
});

// ---------------------------------------------------------------------------
// 3.4-e: register validation
// ---------------------------------------------------------------------------

test("register validation", async ({ page }) => {
  // Track whether register endpoint was called — it must NOT be
  let registerCalled = false;
  await page.route("**/api/auth/register", (route) => {
    registerCalled = true;
    // Fulfill anyway to avoid hanging, but the test asserts it was never reached
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });

  await page.goto("/register");

  await expect(page.getByRole("heading", { name: /Create your account/i })).toBeVisible();

  // Fill with mismatched passwords
  await page.fill("#full_name", "Some User");
  await page.fill("#email", "someuser@example.com");
  await page.fill("#password", "Password123");
  await page.fill("#confirmPassword", "DifferentPass456");

  // Submit
  await page.click('button[type="submit"]');

  // Inline error must be visible
  await expect(page.getByText("Passwords do not match")).toBeVisible();

  // URL must stay on /register — no navigation happened
  expect(page.url()).toContain("/register");

  // Register API must NOT have been called
  expect(registerCalled).toBe(false);
});
