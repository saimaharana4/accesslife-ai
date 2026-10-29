// One explicitly requested real journey. No traces, cookies or payload captures.
import { chromium, expect } from "@playwright/test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
if (!process.argv.includes("--run-live"))
  throw new Error("Explicit --run-live required");
const artifacts = path.resolve(".data/tasteduel-integration");
const ledger = async () =>
  JSON.parse(await readFile(path.join(artifacts, "live-budget.json"), "utf8"));
const initial = await ledger();
if (initial.closed || initial.qloo_reserved >= initial.qloo_ceiling)
  throw new Error("Live budget closed/exhausted");
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: "reduce",
});
const page = await context.newPage();
const checks = [],
  pending = [],
  problems = [];
const origin = process.env.TASTEDUEL_LIVE_WEB_URL ?? "http://127.0.0.1:3001";
if (!["http://127.0.0.1:3001", "http://127.0.0.1:3003"].includes(origin))
  throw new Error("Use reviewed loopback preview origin");
const counts = { search: 0, create: 0, answer: 0, advance: 0 };
page.on("pageerror", () => problems.push("browser_exception"));
await page.route("**/*", (route) => {
  const url = new URL(route.request().url());
  if (["http:", "https:"].includes(url.protocol) && url.origin !== origin) {
    problems.push("external_browser_destination");
    return route.abort();
  }
  return route.continue();
});
page.on("response", (response) => {
  if (!response.url().includes("/api/v1/")) return;
  pending.push(
    (async () => {
      const url = new URL(response.url());
      const method = response.request().method();
      if (url.pathname.endsWith("entities/search")) counts.search++;
      if (url.pathname === "/api/v1/games" && method === "POST")
        counts.create++;
      if (url.pathname.endsWith("/answer")) counts.answer++;
      if (url.pathname.endsWith("/advance")) counts.advance++;
      const body = await response.json();
      if (
        /api[_-]?key|raw_payload|private_pool|query\.affinity|thought_signature|answer_key|affinity_value/i.test(
          JSON.stringify(body),
        )
      )
        problems.push("forbidden_public_field");
      const round =
        body.current_round ?? (body.state === "unanswered" ? body : null);
      if (round?.state === "unanswered") {
        for (const forbidden of [
          "winning_choice_id",
          "selected_choice_id",
          "correct",
          "rank",
          "affinity",
          "curation_summary",
          "evidence",
        ])
          if (Object.hasOwn(round, forbidden)) problems.push("pre_answer_leak");
        if (round.choices?.length !== 2) problems.push("invalid_choices");
      }
      checks.push({
        path: url.pathname.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/gi, "GAME"),
        method,
        status: response.status(),
      });
    })().catch(() => problems.push("unreadable_public_response")),
  );
});
const screenshots = [];
async function capture(state) {
  for (const [label, width, height] of [
    ["desktop", 1440, 1000],
    ["mobile", 390, 844],
    ["reflow", 320, 844],
  ]) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => document.fonts.ready);
    await expect
      .poll(() =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      )
      .toBe(true);
    const name = `${state}-${label}.png`;
    await page.screenshot({
      path: path.join(artifacts, name),
      fullPage: true,
      animations: "disabled",
    });
    screenshots.push(name);
  }
}
let success = false;
try {
  await page.goto(origin);
  const input = page.getByRole("combobox", { name: "Choose your favourite" });
  await input.fill("Radiohead");
  await expect(
    page.getByRole("option", { name: /Radiohead/i }).first(),
  ).toBeVisible({
    timeout: 15000,
  });
  await page.keyboard.press("ArrowDown");
  await expect(input).toHaveAttribute("aria-activedescendant", /.+/);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("start-duel")).toBeEnabled();
  await capture("01-seed");
  await page.getByTestId("start-duel").click();
  await expect(page.getByTestId("choice-card").first()).toBeEnabled({
    timeout: 35000,
  });
  await expect(page.getByTestId("live-game")).toContainText(/Qloo/);
  await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
  const afterGeneration = await ledger();
  await capture("02-playable");
  for (let round = 1; round <= 5; round++) {
    await expect(
      page.getByRole("group", { name: `Round ${round} of 5`, exact: true }),
    ).toBeVisible();
    await page.getByTestId("choice-card").first().focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("reveal-panel")).toBeVisible();
    const disclosure = page.getByTestId("why-this-duel");
    await disclosure.locator("summary").focus();
    await page.keyboard.press("Enter");
    await expect(disclosure).toContainText("Qloo ranked");
    if (round === 1) {
      await capture("03-reveal");
      await page.reload();
      await expect(page.getByTestId("reveal-panel")).toBeVisible();
    }
    await page.getByTestId("next-action").focus();
    await page.keyboard.press("Enter");
  }
  await expect(page.getByTestId("result-ticket")).toBeVisible();
  await expect(page.locator(".ticket-top")).toContainText("AGENT CURATED");
  await capture("04-result");
  await Promise.all(pending);
  const final = await ledger();
  if (
    afterGeneration.qloo_dispatched !== final.qloo_dispatched ||
    afterGeneration.vertex_dispatched !== final.vertex_dispatched
  )
    problems.push("provider_calls_during_gameplay");
  if (counts.create !== 1 || counts.answer !== 5 || counts.advance !== 5)
    problems.push("unexpected_mutation_count");
  if (problems.length) throw new Error("Live public-boundary checks failed");
  success = true;
  await writeFile(
    path.join(artifacts, "browser-summary.json"),
    JSON.stringify(
      {
        status: "passed",
        source: "genuine_qloo",
        curatorLabel: await page.locator(".ticket-top").innerText(),
        score: await page.getByTestId("live-score").innerText(),
        counts,
        publicChecks: checks,
        screenshots,
        noProviderCallsOnAnswerOrNext: true,
        noExternalBrowserRequests: true,
        noPreAnswerFieldsObserved: true,
        qlooDispatched: final.qloo_dispatched,
        vertexDispatched: final.vertex_dispatched,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    JSON.stringify({
      status: "passed",
      counts,
      screenshots: screenshots.length,
      qloo: final.qloo_dispatched,
      vertex: final.vertex_dispatched,
    }),
  );
} finally {
  if (!success) {
    await page
      .screenshot({
        path: path.join(artifacts, "interrupted-browser.png"),
        fullPage: true,
      })
      .catch(() => {});
    console.log(JSON.stringify({ status: "incomplete", problems, counts }));
  }
  await browser.close();
}
