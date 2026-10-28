import { test, expect, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { writeFile } from "node:fs/promises";
import { createResponseAudit } from "../browser-contracts/cloud-response-audit.mjs";

const slug = process.env.TASTEDUEL_CLOUD_REPLAY_SLUG;
test.skip(
  !slug,
  "Requires an existing authorized frozen challenge; never generates one.",
);

test("provider-free protected cloud replay: network, evidence, save and identical independent five", async ({
  browser,
  baseURL,
}, info) => {
  if (!slug || !/^[A-Za-z0-9_-]{22,80}$/.test(slug) || !baseURL)
    throw new Error("Reviewed challenge required");
  const token = process.env.TASTEDUEL_CANDIDATE_ID_TOKEN!;
  const origin = new URL(baseURL).origin;
  const audit = createResponseAudit(token);
  const findings = audit.findings;
  const controlled = new Map<string, Promise<void>>();
  const unavailable: {
    method: string;
    path: string;
    status: number;
    failed: boolean;
  }[] = [];
  const checks: Promise<void>[] = [];
  const owners: string[] = [];
  const games: string[] = [];
  const frozen: { names: string[][]; winner: string[] }[] = [];
  const scores: number[] = [];
  let forbiddenGenerationRequests = 0;
  async function evidence(name: string, data: unknown) {
    await writeFile(info.outputPath(name), JSON.stringify(data, null, 2));
  }
  async function inspect(page: Page, name: string) {
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    for (const image of await page.locator('img[src^="/art/"]').all())
      expect(
        await image.evaluate(
          (element: HTMLImageElement) => element.naturalWidth,
        ),
      ).toBeGreaterThan(0);
    const axe = await new AxeBuilder({ page }).analyze();
    await evidence(name + "-axe.json", {
      violations: axe.violations.map(({ id, impact }) => ({ id, impact })),
      passes: axe.passes.length,
    });
    expect(axe.violations).toEqual([]);
    await page.screenshot({
      path: info.outputPath(name + ".png"),
      fullPage: true,
      animations: "disabled",
    });
  }
  for (let guest = 0; guest < 2; guest++) {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: "reduce",
    });
    await context.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== origin) return route.continue();
      if (
        (url.pathname === "/api/v1/games" &&
          route.request().method() === "POST") ||
        url.pathname.endsWith("/entities/search")
      ) {
        forbiddenGenerationRequests++;
        return route.abort("blockedbyclient");
      }
      return route.continue({
        headers: {
          ...route.request().headers(),
          "X-Serverless-Authorization": `Bearer ${token}`,
        },
      });
    });
    const page = await context.newPage();
    page.on("response", (response) => {
      const url = new URL(response.url());
      if (url.origin !== origin || !url.pathname.startsWith("/api/v1/")) return;
      checks.push(
        (async () => {
          let text: string;
          try {
            text = await response.text();
          } catch {
            const key = response.request().headers()["idempotency-key"];
            await controlled.get(key);
            if (!audit.unavailable(key))
              unavailable.push({
                method: response.request().method(),
                path: url.pathname,
                status: response.status(),
                failed: Boolean(response.request().failure()),
              });
            return;
          }
          if (
            response.status() === 204 &&
            response.request().method() === "DELETE" &&
            !text
          )
            return;
          audit.inspect(text);
        })(),
      );
    });
    try {
      await page.goto(`${baseURL}/c/${slug}`);
      await expect(page.getByTestId("challenge-invitation")).toBeVisible();
      await page.waitForLoadState("networkidle");
      if (guest === 0) await inspect(page, "provider-free-invitation");
      const start = page.getByRole("button", { name: /Play these five/ });
      await start.focus();
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(/\/g\/[0-9a-f-]+$/);
      const game = new URL(page.url()).pathname.split("/").at(-1)!;
      games.push(game);
      const cookie = (await context.cookies(origin)).find(
        (entry) => entry.name === "tasteduel_session",
      );
      const owner = cookie?.value.split(".", 1)[0];
      if (!owner || !/^[0-9a-f-]{36}$/.test(owner))
        throw new Error("Private session reference unavailable");
      owners.push(owner);
      if (guest === 0) {
        let answerLost = false,
          nextLost = false;
        async function lose(route: Route) {
          const key = route.request().headers()["idempotency-key"];
          const work = route
            .fetch({
              headers: {
                ...route.request().headers(),
                "X-Serverless-Authorization": `Bearer ${token}`,
              },
            })
            .catch(() => {
              throw new Error(
                "Controlled authenticated request failed; diagnostics redacted",
              );
            })
            .then(async (accepted) => {
              expect(accepted.ok()).toBe(true);
              expect(audit.confirmControlled(key, await accepted.text())).toBe(
                true,
              );
            });
          controlled.set(
            key,
            work.catch(() => {}),
          );
          await work;
          await route.abort("failed");
        }
        await page.route("**/api/v1/games/*/answer", async (route) => {
          if (answerLost) return route.fallback();
          answerLost = true;
          await lose(route);
        });
        await page.route("**/api/v1/games/*/advance", async (route) => {
          if (nextLost) return route.fallback();
          nextLost = true;
          await lose(route);
        });
      }
      async function state() {
        return page.evaluate(
          async (id) =>
            (await fetch(`/api/v1/games/${id}`, { cache: "no-store" })).json(),
          game,
        );
      }
      let score = 0;
      for (let ordinal = 1; ordinal <= 5; ordinal++) {
        await expect(page.getByTestId("choice-card").first()).toBeEnabled();
        const before = await state();
        expect(before.mode).toBe("fixed");
        expect(before.current_round.state).toBe("unanswered");
        expect(before.current_round.ordinal).toBe(ordinal);
        expect(before.source).toBe("qloo");
        expect(before.curator_mode).toBe("genuine_agent");
        const names = before.current_round.choices.map(
          (choice: { entity: { name: string; type: string } }) => [
            choice.entity.name,
            choice.entity.type,
          ],
        );
        if (guest === 1) expect(names).toEqual(frozen[ordinal - 1].names);
        await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
        if (guest === 0 && ordinal === 1) {
          await page.setViewportSize({ width: 320, height: 844 });
          await inspect(page, "provider-free-320-unanswered");
          await page.setViewportSize({ width: 1440, height: 1000 });
          await inspect(page, "provider-free-desktop-unanswered");
          await page.setViewportSize({ width: 390, height: 844 });
        }
        const choice = page.getByTestId("choice-card").nth(guest);
        await choice.focus();
        await page.keyboard.press("Enter");
        if (guest === 0 && ordinal === 1) {
          await page.waitForLoadState("networkidle");
          await Promise.all(checks);
          await page.reload({ waitUntil: "domcontentloaded" });
        }
        await expect(page.getByTestId("reveal-panel")).toBeVisible();
        const after = await state();
        const reveal = after.current_round;
        expect(reveal.state).toBe("revealed");
        score += Number(reveal.correct);
        const winner = reveal.choices.find(
          (entry: { id: string }) => entry.id === reveal.winning_choice_id,
        ).entity;
        if (guest === 0)
          frozen.push({ names, winner: [winner.name, winner.type] });
        else
          expect([winner.name, winner.type]).toEqual(
            frozen[ordinal - 1].winner,
          );
        const why = page.getByTestId("why-this-duel").locator("summary");
        await why.focus();
        await page.keyboard.press("Enter");
        await expect(page.getByTestId("why-this-duel")).toContainText(
          /Qloo ranked/,
        );
        if (guest === 0 && ordinal === 1)
          await inspect(page, "provider-free-mobile-reveal");
        const next = page.getByTestId("next-action");
        await next.focus();
        await page.keyboard.press("Enter");
        if (guest === 0 && ordinal === 1) {
          await page.waitForLoadState("networkidle");
          await Promise.all(checks);
          await page.reload({ waitUntil: "domcontentloaded" });
        }
      }
      await expect(page.getByTestId("fixed-replay-result")).toBeVisible();
      expect((await state()).score).toBe(score);
      scores.push(score);
      const curation = page
        .getByTestId("curation-disclosure")
        .locator("summary");
      await curation.focus();
      await page.keyboard.press("Enter");
      const explore = page
        .locator("summary")
        .filter({ hasText: "Explore answered choices" });
      await explore.focus();
      await page.keyboard.press("Enter");
      const save = page
        .getByRole("button", { name: /^Save discovery:/ })
        .first();
      await save.focus();
      await page.keyboard.press("Enter");
      await expect(
        page.getByRole("button", { name: /^Remove discovery:/ }),
      ).toBeVisible();
      await inspect(page, `provider-free-guest${guest + 1}-result`);
      await page.reload();
      await expect(
        page.getByRole("button", { name: /^Remove discovery:/ }),
      ).toBeVisible();
      await page.waitForLoadState("networkidle");
      await Promise.all(checks);
    } finally {
      await context.close();
    }
  }
  await evidence("provider-free-network.json", {
    findings,
    unavailable,
    forbiddenGenerationRequests,
    independent_scores: scores,
    exact_five: true,
    new_qloo_calls: 0,
    new_vertex_calls: 0,
    confirmed_accepted_response_losses: audit.confirmedControlled,
    expected_unavailable_controlled_bodies: audit.expectedUnavailable,
  });
  await evidence("private-replay-recovery-refs.json", {
    guest_session_ids: owners,
    guest_game_ids: games,
    challenge_slug: slug,
  });
  expect(scores[0] + scores[1]).toBe(5);
  expect(forbiddenGenerationRequests).toBe(0);
  expect(audit.confirmedControlled).toBe(2);
  expect(findings).toEqual([]);
  expect(unavailable).toEqual([]);
});
