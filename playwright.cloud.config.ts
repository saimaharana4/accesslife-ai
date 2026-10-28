import { defineConfig } from "@playwright/test";
import { cloudBrowserAccess } from "./tests/browser-contracts/cloud-browser-access.mjs";

const enabled = process.env.TASTEDUEL_CLOUD_BROWSER_ENABLED === "true";
const baseURL =
  process.env.TASTEDUEL_CANDIDATE_ORIGIN || "https://candidate.invalid";
if (enabled) {
  cloudBrowserAccess(process.env);
  if (!process.env.TASTEDUEL_CLOUD_SEED)
    throw new Error("Cloud browser checks require the approved bounded seed");
}

export default defineConfig({
  testDir: "tests/e2e",
  testMatch:
    process.env.TASTEDUEL_CLOUD_ACCESS_MODE === "public"
      ? ["tasteduel-cloud.spec.ts"]
      : [
          "tasteduel-cloud.spec.ts",
          "tasteduel-cloud-replay.spec.ts",
          "tasteduel-cloud-postchecks.spec.ts",
        ],
  timeout: 420_000,
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
