/**
 * US-1.1: Email + Password Signup — e2e behaviors
 *
 * All /api/* routes are mocked with page.route() — no running backend required.
 *
 * /signup is a PUBLIC AUTH_ROUTE (middleware.ts).
 * On success, the page calls signupApi → /api/v1/auth/signup, then shows
 * a "Check your email" success state (no auto-login — user must verify email first).
 *
 * US-1.1-d: signup success — valid form → 201 → "Check your email" page visible
 * US-1.1-e: signup validation — password mismatch / weak password → inline error, no API call
 * US-1.1-f: duplicate email → 409 with "Email already registered. Sign in?"
 */

import { test, expect, type Page } from "@playwright/test";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const VALID_PASSWORD = "SecurePass123"; // 8+ chars, 1 uppercase, 1 digit
const NEW_EMAIL = "newuser@example.com";

// ---------------------------------------------------------------------------
// Stub helpers
// ---------------------------------------------------------------------------

/** Stub all routes needed for a successful signup flow */
async function stubPostSignupRoutes(page: Page) {
  // The page calls /api/v1/auth/signup (via authFetch which prepends /api)
  await page.route("**/api/v1/auth/signup", (route) =>
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-new",
        email: NEW_EMAIL,
        full_name: "New User",
        is_active: true,
        is_superuser: false,
        message:
          "Account created. Please check your email to verify your address.",
      }),
    })
  );
}

// ---------------------------------------------------------------------------
// US-1.1-d: signup success → "Check your email" page
// ---------------------------------------------------------------------------

test("signup success shows check your email state", async ({ page }) => {
  await stubPostSignupRoutes(page);

  await page.goto("/signup");

  await expect(
    page.getByRole("heading", { name: /Create your account/i })
  ).toBeVisible();

  await page.fill("#full_name", "New User");
  await page.fill("#email", NEW_EMAIL);
  await page.fill("#password", VALID_PASSWORD);
  await page.fill("#confirmPassword", VALID_PASSWORD);

  await page.click('button[type="submit"]');

  // After successful signup, show the "Check your email" success state
  await expect(
    page.getByRole("heading", { name: /Check your email/i })
  ).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(NEW_EMAIL)).toBeVisible();
});

// ---------------------------------------------------------------------------
// US-1.1-e: signup validation — password mismatch
// ---------------------------------------------------------------------------

test("signup validation — password mismatch", async ({ page }) => {
  let signupCalled = false;
  await page.route("**/api/v1/auth/signup", (route) => {
    signupCalled = true;
    route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });

  await page.goto("/signup");

  await expect(
    page.getByRole("heading", { name: /Create your account/i })
  ).toBeVisible();

  await page.fill("#full_name", "Some User");
  await page.fill("#email", "someuser@example.com");
  await page.fill("#password", VALID_PASSWORD);
  await page.fill("#confirmPassword", "DifferentPass456");

  await page.click('button[type="submit"]');

  await expect(page.getByText("Passwords do not match")).toBeVisible();

  expect(page.url()).toContain("/signup");
  expect(signupCalled).toBe(false);
});

test("signup validation — weak password", async ({ page }) => {
  let signupCalled = false;
  await page.route("**/api/v1/auth/signup", (route) => {
    signupCalled = true;
    route.fulfill({ status: 201, body: "{}" });
  });

  await page.goto("/signup");

  await page.fill("#full_name", "Some User");
  await page.fill("#email", "weakpw@example.com");
  await page.fill("#password", "weakpassword"); // no uppercase, no digit
  await page.fill("#confirmPassword", "weakpassword");

  await page.click('button[type="submit"]');

  await expect(
    page.getByText(/at least one uppercase letter/i)
  ).toBeVisible();

  expect(signupCalled).toBe(false);
});

test("signup duplicate email — server 409 message", async ({ page }) => {
  await page.route("**/api/v1/auth/signup", (route) =>
    route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Email already registered. Sign in?",
      }),
    })
  );

  await page.goto("/signup");
  await page.fill("#full_name", "Dup User");
  await page.fill("#email", "existing@example.com");
  await page.fill("#password", VALID_PASSWORD);
  await page.fill("#confirmPassword", VALID_PASSWORD);

  await page.click('button[type="submit"]');

  await expect(
    page.getByText(/Email already registered\. Sign in\?/i)
  ).toBeVisible();
});
