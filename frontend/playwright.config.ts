import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for AI Translation frontend.
 * Tests run against the Next.js dev server (no real backend needed —
 * each spec uses page.route() to stub /api/* calls).
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "list",
  timeout: 30000,
  use: {
    baseURL: "http://localhost:3001",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "PORT=3001 npm run dev",
    url: "http://localhost:3001",
    reuseExistingServer: false,
    timeout: 120000,
    env: {
      // Disable backend proxying for e2e — all /api/* calls are mocked
      BACKEND_URL: "http://localhost:9999",
      PORT: "3001",
    },
  },
});
