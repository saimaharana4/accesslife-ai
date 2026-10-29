// Synthetic-only private stdin handoff. Never write cookies or storageState.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "@playwright/test";

let stage = "read-private-handoff";
let browser;
try {
  let input = "";
  for await (const chunk of process.stdin) {
    input += chunk;
    assert(input.length < 2000);
  }
  const payload = JSON.parse(input);
  assert(/^[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}$/.test(payload.cookie));
  assert(/^[0-9a-f-]{36}$/.test(payload.game_id));
  const origin = "http://127.0.0.1:3003";
  let cookies = [
    {
      name: "tasteduel_session",
      value: payload.cookie,
      url: origin,
      httpOnly: true,
      secure: false,
      sameSite: "Lax",
    },
  ];
  const counts = { answer: 0, advance: 0, save: 0 };
  const unexpected = [];
  const errors = [];
  const dir = ".data/tasteduel-solo/browser-restart";
  await mkdir(dir, { recursive: true });

  async function launch() {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: "reduce",
    });
    await context.addCookies(cookies);
    await context.route("**/*", (route) => {
      const url = new URL(route.request().url());
      if (["http:", "https:"].includes(url.protocol) && url.origin !== origin) {
        unexpected.push(url.origin);
        return route.abort("blockedbyclient");
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.name));
    page.on("request", (request) => {
      const path = new URL(request.url()).pathname;
      if (request.method() !== "POST") return;
      if (path.endsWith("/answer")) counts.answer++;
      if (path.endsWith("/advance")) counts.advance++;
      if (path === "/api/v1/discoveries") counts.save++;
    });
    return { context, page };
  }
  async function waitVisible(locator) {
    await locator.waitFor({ state: "visible", timeout: 20_000 });
  }
  async function close(context) {
    cookies = await context.cookies(); // In-memory only; no storageState artifacts.
    await browser.close();
    browser = undefined;
  }

  stage = "first-browser-answer-and-explicit-save";
  let { context, page } = await launch();
  await page.goto(`${origin}/g/${payload.game_id}`);
  await waitVisible(page.getByTestId("choice-card").first());
  assert.match(
    await page.getByTestId("live-game").innerText(),
    /DEVELOPMENT FIXTURE.*NO LIVE QLOO/s,
  );
  await page.getByTestId("choice-card").first().click();
  await waitVisible(page.getByTestId("reveal-panel"));
  const score = await page.getByTestId("live-score").innerText();
  const firstQuestion = await page.getByTestId("live-question").innerText();
  await page.getByTestId("discovery-reveal").locator("summary").click();
  await page
    .getByRole("button", { name: /^Save discovery:/ })
    .first()
    .click();
  await waitVisible(
    page.getByRole("button", { name: /^Remove discovery:/ }).first(),
  );
  await close(context);

  stage = "second-browser-restores-accepted-reveal-and-save";
  ({ context, page } = await launch());
  await page.goto(`${origin}/g/${payload.game_id}`);
  await waitVisible(page.getByTestId("reveal-panel"));
  assert.equal(await page.getByTestId("live-score").innerText(), score);
  assert.equal(
    await page.getByTestId("live-question").innerText(),
    firstQuestion,
  );
  await page.getByTestId("discovery-reveal").locator("summary").click();
  await waitVisible(
    page.getByRole("button", { name: /^Remove discovery:/ }).first(),
  );
  assert.equal(counts.answer, 1);
  assert.equal(counts.save, 1);
  await page.screenshot({
    path: `${dir}/01-restarted-accepted-reveal.png`,
    fullPage: true,
    animations: "disabled",
  });
  await page.getByTestId("next-action").click();
  await waitVisible(
    page.getByRole("group", { name: "Round 2 of 5", exact: true }),
  );
  await close(context);

  stage = "third-browser-restores-accepted-next";
  ({ context, page } = await launch());
  await page.goto(`${origin}/g/${payload.game_id}`);
  await waitVisible(
    page.getByRole("group", { name: "Round 2 of 5", exact: true }),
  );
  assert.equal(await page.getByTestId("reveal-panel").count(), 0);
  assert.equal(await page.getByTestId("live-score").innerText(), score);
  await page.screenshot({
    path: `${dir}/02-restarted-explicit-next.png`,
    fullPage: true,
    animations: "disabled",
  });
  assert.deepEqual(counts, { answer: 1, advance: 1, save: 1 });
  assert.deepEqual(unexpected, []);
  assert.deepEqual(errors, []);
  await close(context);
  const report = {
    synthetic_only: true,
    real_same_origin_forwarding: true,
    chromium_process_launches: 3,
    accepted_answer_restored: true,
    accepted_next_restored: true,
    explicit_discovery_save_restored: true,
    stable_server_score: true,
    mutation_counts: counts,
    external_browser_requests: 0,
    cookie_files_written: false,
  };
  await writeFile(
    `${dir}/verification.json`,
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report));
} catch (error) {
  console.log(
    JSON.stringify({
      status: "failed",
      stage,
      safe_error_type: error?.name ?? "Error",
      credential_payload_logged: false,
    }),
  );
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
}
