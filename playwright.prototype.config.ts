import { defineConfig } from "@playwright/test";

const baseURL = process.env.TASTEDUEL_PROTOTYPE_URL || "http://127.0.0.1:3001";
const target = new URL(baseURL);
if (
  target.protocol !== "http:" ||
  !["127.0.0.1", "localhost", "[::1]"].includes(target.hostname)
) {
  throw new Error("Prototype verification is restricted to the local preview.");
}

export default defineConfig({
  testDir: "tests/e2e",
  testMatch: "tasteduel-prototype.spec.ts",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  outputDir: "test-results/tasteduel-prototype",
  reporter: [
    ["list"],
    [
      "html",
      { outputFolder: "playwright-report/tasteduel-prototype", open: "never" },
    ],
  ],
  use: {
    baseURL,
    browserName: "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    reducedMotion: "reduce",
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
