import { defineConfig } from "@playwright/test";

const baseURL = process.env.TASTEDUEL_TEST_WEB_URL || "http://127.0.0.1:3003";
const target = new URL(baseURL);
if (
  target.protocol !== "http:" ||
  !["127.0.0.1", "localhost"].includes(target.hostname)
) {
  throw new Error(
    "Solo recovery intercepted checks require a loopback web server.",
  );
}
export default defineConfig({
  testDir: "tests/e2e",
  testMatch: "tasteduel-solo.spec.ts",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  outputDir: "test-results/tasteduel-solo",
  reporter: [
    ["list"],
    ["json", { outputFile: ".data/tasteduel-solo/browser-review.json" }],
    [
      "html",
      { outputFolder: "playwright-report/tasteduel-solo", open: "never" },
    ],
  ],
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
