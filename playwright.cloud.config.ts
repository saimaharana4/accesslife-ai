import { defineConfig } from "@playwright/test";

const enabled = process.env.TASTEDUEL_CLOUD_BROWSER_ENABLED === "true";
const baseURL =
  process.env.TASTEDUEL_CANDIDATE_ORIGIN || "https://candidate.invalid";
if (enabled) {
  const origin = new URL(baseURL);
  if (
    origin.protocol !== "https:" ||
    origin.origin !== baseURL ||
    !origin.hostname.endsWith(".run.app") ||
    !process.env.TASTEDUEL_CANDIDATE_ID_TOKEN ||
    !process.env.TASTEDUEL_CLOUD_SEED
  )
    throw new Error(
      "Cloud browser checks require an approved exact HTTPS Cloud Run origin, in-memory identity token and bounded seed.",
    );
}

export default defineConfig({
  testDir: "tests/e2e",
  testMatch: "tasteduel-cloud.spec.ts",
  timeout: 240_000,
  expect: { timeout: 20_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "test-results/tasteduel-cloud",
  use: {
    baseURL,
    browserName: "chromium",
    reducedMotion: "reduce",
    // Network traces/HAR can persist identity tokens and private provider evidence.
    trace: "off",
    video: "off",
    screenshot: "off",
  },
});
