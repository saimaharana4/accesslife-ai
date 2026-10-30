import { defineConfig } from "@playwright/test";
const baseURL = process.env.TASTEDUEL_TEST_WEB_URL || "http://127.0.0.1:3001";
const target = new URL(baseURL);
if (
  target.protocol !== "http:" ||
  !["127.0.0.1", "localhost"].includes(target.hostname)
)
  throw new Error("Accessibility synthetic checks require loopback.");
export default defineConfig({
  testDir: "e2e",
  testMatch: "tasteduel-audit.spec.ts",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  outputDir: "../test-results/tasteduel-audit",
  // Screenshot and failure evidence use Playwright's guaranteed per-test output directory.
  reporter: [["list"]],
  use: {
    baseURL,
    browserName: "chromium",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    {
      name: "mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
    {
      name: "reflow",
      use: {
        viewport: { width: 320, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
