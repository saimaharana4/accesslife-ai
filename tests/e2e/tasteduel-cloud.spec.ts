import {
  test,
  expect,
  type BrowserContext,
  type Page,
  type TestInfo,
  type Locator,
} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { ApiSchemas } from "../../apps/web/src/lib/api/contracts";

const enabled = process.env.TASTEDUEL_CLOUD_BROWSER_ENABLED === "true";
test.skip(
  !enabled,
  "Cloud gameplay requires a separately approved tiny live budget and protected candidate URL.",
);

async function tabTo(page: Page, control: Locator) {
  for (let index = 0; index < 36; index++) {
    if (await control.evaluate((element) => element === document.activeElement))
      return;
    await page.keyboard.press("Tab");
  }
  await expect(control).toBeFocused();
}

async function inspect(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBe(true);
  expect(
    await page.evaluate(
      () =>
        Math.max(
          document.body.scrollWidth,
          document.documentElement.scrollWidth,
        ) <=
        innerWidth + 1,
    ),
  ).toBe(true);
  const scan = await new AxeBuilder({ page }).analyze();
  // Screenshots are private ignored evidence. Keep only aggregate axe findings,
  // rather than serializing a live page's full proprietary entity metadata.
  await info.attach(`${name}-axe-counts.json`, {
    body: JSON.stringify({
      violations: scan.violations.map(({ id, impact, nodes }) => ({
        id,
        impact,
        affected_nodes: nodes.length,
      })),
      passes: scan.passes.length,
    }),
    contentType: "application/json",
  });
  expect
    .soft(
      scan.violations.map(({ id, impact }) => ({ id, impact })),
      `${name}: complete axe scan`,
    )
    .toEqual([]);
  await page.screenshot({
    path: info.outputPath(`${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
}

test("protected cloud: one real curated solo, accepted-response recovery and identical friend five", async ({
  browser,
  baseURL,
}, info) => {
  if (!baseURL) throw new Error("Explicit candidate origin required");
  const token = process.env.TASTEDUEL_CANDIDATE_ID_TOKEN;
  if (!token) throw new Error("Candidate identity unavailable");
  const origin = new URL(baseURL).origin;
  const responseFindings: string[] = [];
  const timings: {
    operation: string;
    milliseconds: number;
    condition: string;
  }[] = [];
  const observed = {
    search: 0,
    generation: 0,
    answer: 0,
    advance: 0,
    replay: 0,
  };
  const checks: Promise<void>[] = [];
  const contexts: BrowserContext[] = [];

  async function context(viewport: { width: number; height: number }) {
    const session = await browser.newContext({
      viewport,
      reducedMotion: "reduce",
    });
    contexts.push(session);
    // Scope authentication to this exact reviewed origin. Do not configure
    // global extraHTTPHeaders, which could attach credentials to third parties.
    await session.route("**/*", async (route) => {
      if (new URL(route.request().url()).origin !== origin)
        return route.continue();
      await route.continue({
        headers: {
          ...route.request().headers(),
          "X-Serverless-Authorization": `Bearer ${token}`,
        },
      });
    });
    session.on("page", (page) => {
      page.on("response", (response) => {
        const url = new URL(response.url());
        if (url.origin !== origin || !url.pathname.startsWith("/api/v1/"))
          return;
        const method = response.request().method();
        if (url.pathname.endsWith("/entities/search")) observed.search++;
        if (method === "POST" && url.pathname === "/api/v1/games")
          observed.generation++;
        if (method === "POST" && url.pathname.endsWith("/answer"))
          observed.answer++;
        if (method === "POST" && url.pathname.endsWith("/advance"))
          observed.advance++;
        if (method === "POST" && url.pathname.endsWith("/plays"))
          observed.replay++;
        checks.push(
          (async () => {
            try {
              const text = await response.text();
              if (
                /raw_payload|private_pool|answer_key|thought_signature|chain_of_thought|query_context_hash|"affinity"|hack_[a-z0-9]{20}|sk-proj-/i.test(
                  text,
                )
              )
                responseFindings.push(
                  "Forbidden private field in browser API response",
                );
              if (text.includes(token!))
                responseFindings.push(
                  "Candidate IAM credential echoed in browser response",
                );
              const body = JSON.parse(text);
              if (
                body.current_round?.state === "unanswered" &&
                /winning_choice_id|selected_choice_id|curation_summary/.test(
                  JSON.stringify(body.current_round),
                )
              )
                responseFindings.push("Pre-answer reveal metadata");
            } catch {
              if (response.status() < 500)
                responseFindings.push(
                  "Unexpected non-JSON browser API response",
                );
            }
          })(),
        );
      });
    });
    return session;
  }

  async function read<T>(page: Page, path: string): Promise<T> {
    return page.evaluate(async (path) => {
      const response = await fetch(`/api/v1${path}`, { cache: "no-store" });
      if (!response.ok)
        throw new Error(`Saved public state unavailable: ${response.status}`);
      return response.json();
    }, path);
  }

  const creator = await context({ width: 1440, height: 1000 });
  const page = await creator.newPage();
  try {
    const firstNavigation = performance.now();
    await page.goto(baseURL);
    await expect(
      page.getByRole("combobox", { name: "Choose your favourite" }),
    ).toBeEnabled();
    timings.push({
      operation: "landing",
      milliseconds: performance.now() - firstNavigation,
      condition: "first observed external navigation; service coldness unknown",
    });
    await inspect(page, info, "desktop-landing");
    const input = page.getByRole("combobox", { name: "Choose your favourite" });
    if (process.env.TASTEDUEL_CLOUD_SEED_TYPE === "movie")
      await page.getByRole("radio", { name: "Film", exact: true }).check();
    await tabTo(page, input);
    await input.fill(process.env.TASTEDUEL_CLOUD_SEED!);
    await expect(page.getByRole("option").first()).toBeVisible();
    await page.keyboard.press("ArrowDown");
    await expect(input).toHaveAttribute("aria-activedescendant", /\S+/);
    await page.keyboard.press("Enter");
    await tabTo(page, page.getByTestId("start-duel"));
    const generationStart = performance.now();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/g\/[0-9a-f-]+$/);
    await expect(page.getByTestId("choice-card").first()).toBeEnabled();
    timings.push({
      operation: "generation",
      milliseconds: performance.now() - generationStart,
      condition:
        "one external real-provider game; no automatic generation retry",
    });
    const gameId = new URL(page.url()).pathname.split("/").at(-1)!;
    const frozen: ApiSchemas["RevealedRoundPublic"][] = [];

    // Deliberately lose exactly one accepted answer and one accepted Next
    // response; retries restore authoritative state, never regenerate a game.
    let lostAnswer = false,
      lostAdvance = false;
    await page.route("**/api/v1/games/*/answer", async (route) => {
      if (new URL(route.request().url()).origin !== origin)
        return route.fallback();
      if (lostAnswer) return route.fallback();
      lostAnswer = true;
      const accepted = await route
        .fetch({
          headers: {
            ...route.request().headers(),
            "X-Serverless-Authorization": `Bearer ${token}`,
          },
        })
        .catch(() => {
          throw new Error(
            "Controlled answer request could not confirm acceptance; diagnostics redacted",
          );
        });
      expect(accepted.ok()).toBe(true);
      await route.abort("failed");
    });
    await page.route("**/api/v1/games/*/advance", async (route) => {
      if (new URL(route.request().url()).origin !== origin)
        return route.fallback();
      if (lostAdvance) return route.fallback();
      lostAdvance = true;
      const accepted = await route
        .fetch({
          headers: {
            ...route.request().headers(),
            "X-Serverless-Authorization": `Bearer ${token}`,
          },
        })
        .catch(() => {
          throw new Error(
            "Controlled advance request could not confirm acceptance; diagnostics redacted",
          );
        });
      expect(accepted.ok()).toBe(true);
      await route.abort("failed");
    });

    async function recover() {
      const button = page
        .getByRole("button", { name: /check saved game|retry|recover/i })
        .first();
      await expect(button).toBeVisible();
      await tabTo(page, button);
      await page.keyboard.press("Enter");
    }
    for (let ordinal = 1; ordinal <= 5; ordinal++) {
      const state = await read<ApiSchemas["GamePublic"]>(
        page,
        `/games/${gameId}`,
      );
      expect(state.current_round?.state).toBe("unanswered");
      expect(state.current_round?.ordinal).toBe(ordinal);
      expect(state.current_round?.source).toBe("qloo");
      expect(state.curator_mode).toBe("genuine_agent");
      await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
      if (ordinal === 1) {
        await inspect(page, info, "desktop-unanswered");
        await page.setViewportSize({ width: 390, height: 844 });
        await inspect(page, info, "mobile-unanswered");
        await page.setViewportSize({ width: 320, height: 844 });
        await inspect(page, info, "reflow-unanswered");
      }
      const answerStart = performance.now();
      await tabTo(page, page.getByTestId("choice-card").first());
      await page.keyboard.press("Enter");
      if (ordinal === 1) await recover();
      await expect(page.getByTestId("reveal-panel")).toBeVisible();
      timings.push({
        operation: "answer_to_reveal",
        milliseconds: performance.now() - answerStart,
        condition:
          ordinal === 1
            ? "accepted response deliberately lost plus recovery"
            : "external warm-path browser latency including focus/paint; not server-handler p95",
      });
      const revealed = (
        await read<ApiSchemas["GamePublic"]>(page, `/games/${gameId}`)
      ).current_round;
      if (revealed?.state !== "revealed")
        throw new Error("Accepted round did not restore its reveal");
      frozen.push(revealed);
      const why = page.getByTestId("why-this-duel");
      await tabTo(page, why.locator("summary"));
      await page.keyboard.press("Enter");
      await expect(why).toContainText(/Qloo ranked/);
      if (ordinal === 1) {
        await inspect(page, info, "reflow-reveal");
        await page.setViewportSize({ width: 390, height: 844 });
        await inspect(page, info, "mobile-reveal");
        await page.reload();
        await expect(page.getByTestId("reveal-panel")).toBeVisible();
      }
      await tabTo(page, page.getByTestId("next-action"));
      await page.keyboard.press("Enter");
      if (ordinal === 1) await recover();
      if (ordinal < 5)
        await expect(
          page.getByRole("group", {
            name: `Round ${ordinal + 1} of 5`,
            exact: true,
          }),
        ).toBeVisible();
    }
    await expect(page).toHaveURL(new RegExp(`/results/${gameId}$`));
    const result = await read<ApiSchemas["GameResultPublic"]>(
      page,
      `/games/${gameId}/results`,
    );
    expect(result.score).toBe(frozen.filter((round) => round.correct).length);
    expect(
      new Set(
        frozen.flatMap((round) =>
          round.choices.map((choice) => choice.entity.id),
        ),
      ).size,
    ).toBe(10);
    await inspect(page, info, "mobile-result");
    const save = page.getByRole("button", { name: /^Save discovery:/ }).first();
    await tabTo(page, save);
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("button", { name: /^Remove discovery:/ }).first(),
    ).toBeVisible();
    await page.setViewportSize({ width: 1440, height: 1000 });
    await inspect(page, info, "desktop-result");
    await tabTo(
      page,
      page.getByRole("button", { name: /Create friend challenge/ }),
    );
    await page.keyboard.press("Enter");
    const invitation = page.getByRole("link", {
      name: "View invitation",
      exact: true,
    });
    await expect(invitation).toBeVisible();
    const sharePath = await invitation.getAttribute("href");
    if (!sharePath || !/^\/c\/[A-Za-z0-9_-]{22,80}$/.test(sharePath))
      throw new Error("Invalid fixed invitation path");
    const friend = await context({ width: 390, height: 844 });
    const friendPage = await friend.newPage();
    await friendPage.goto(`${baseURL}${sharePath}`);
    await expect(friendPage.getByTestId("challenge-invitation")).toBeVisible();
    await expect(friendPage.getByTestId("choice-card")).toHaveCount(0);
    await inspect(friendPage, info, "mobile-invitation");
    const invitationHtml = await friendPage.content();
    expect(
      /answer_key|private_pool|thought_signature|chain_of_thought|hack_[a-z0-9]{20}|sk-proj-/i.test(
        invitationHtml,
      ),
    ).toBe(false);
    expect(invitationHtml.includes(token)).toBe(false);
    for (const title of frozen.flatMap((round) =>
      round.choices.map((choice) => choice.entity.name),
    ))
      expect(invitationHtml.includes(title)).toBe(false);
    const isolation = await friendPage.evaluate(async (gameId) => {
      const response = await fetch(`/api/v1/games/${gameId}`, {
        cache: "no-store",
      });
      return { status: response.status, body: await response.text() };
    }, gameId);
    expect([401, 404]).toContain(isolation.status);
    expect(
      /winning_choice_id|"choices"|private_pool/.test(isolation.body),
    ).toBe(false);
    const ogPage = await friend.newPage();
    await ogPage.setViewportSize({ width: 1200, height: 630 });
    const ogResponse = await ogPage.goto(`${baseURL}${sharePath}/social`);
    expect(ogResponse?.status()).toBe(200);
    expect(ogResponse?.headers()["content-type"]).toMatch(/^image\//);
    await ogPage.screenshot({
      path: info.outputPath("original-artwork-social.png"),
      fullPage: true,
    });
    await ogPage.close();
    const startFriend = friendPage.getByRole("button", {
      name: /Play these five/,
    });
    await tabTo(friendPage, startFriend);
    await friendPage.keyboard.press("Enter");
    await expect(friendPage).toHaveURL(/\/g\/[0-9a-f-]+$/);
    const friendGame = new URL(friendPage.url()).pathname.split("/").at(-1)!;
    expect(friendGame).not.toBe(gameId);
    for (let index = 0; index < 5; index++) {
      await expect(friendPage.getByTestId("choice-card").first()).toBeEnabled();
      const state = await read<ApiSchemas["GamePublic"]>(
        friendPage,
        `/games/${friendGame}`,
      );
      expect(state.mode).toBe("fixed");
      expect(
        state.current_round?.choices.map((choice) => choice.entity.id),
      ).toEqual(frozen[index].choices.map((choice) => choice.entity.id));
      await tabTo(friendPage, friendPage.getByTestId("choice-card").first());
      await friendPage.keyboard.press("Enter");
      await expect(friendPage.getByTestId("reveal-panel")).toBeVisible();
      const accepted = (
        await read<ApiSchemas["GamePublic"]>(friendPage, `/games/${friendGame}`)
      ).current_round;
      if (accepted?.state !== "revealed")
        throw new Error("Friend answer reveal unavailable");
      const winner = accepted.choices.find(
        (choice) => choice.id === accepted.winning_choice_id,
      )?.entity.id;
      const originalWinner = frozen[index].choices.find(
        (choice) => choice.id === frozen[index].winning_choice_id,
      )?.entity.id;
      expect(winner).toBe(originalWinner);
      await tabTo(friendPage, friendPage.getByTestId("next-action"));
      await friendPage.keyboard.press("Enter");
    }
    await expect(friendPage.getByTestId("fixed-replay-result")).toBeVisible();
    const friendResult = await read<ApiSchemas["GameResultPublic"]>(
      friendPage,
      `/games/${friendGame}/results`,
    );
    expect(friendResult.score).toBe(result.score);
    await inspect(friendPage, info, "mobile-fixed-result");
    await friendPage.goto(`${baseURL}/c/nonexistent_capability_1234567890`);
    await expect(
      friendPage.getByRole("heading", { name: /INVITATION NOT FOUND/ }),
    ).toBeVisible();
    await inspect(friendPage, info, "mobile-missing-challenge");
    if (process.env.TASTEDUEL_CLOUD_EXPIRED_SLUG) {
      const slug = process.env.TASTEDUEL_CLOUD_EXPIRED_SLUG;
      if (!/^[A-Za-z0-9_-]{22,80}$/.test(slug))
        throw new Error("Invalid controlled expired challenge reference");
      await friendPage.goto(`${baseURL}/c/${slug}`);
      await expect(
        friendPage.getByRole("heading", { name: /THIS FIVE HAS EXPIRED/ }),
      ).toBeVisible();
      await inspect(friendPage, info, "mobile-expired-challenge");
    }
    await Promise.all(checks);
    expect(responseFindings).toEqual([]);
    expect(observed.generation).toBe(1);
    expect(observed.search).toBeLessThanOrEqual(2);
    expect(observed.replay).toBe(1);
    await info.attach("external-summary.json", {
      body: JSON.stringify(
        {
          observed,
          timings,
          real_rounds: 5,
          distinct_contestants: 10,
          exact_replay: true,
          source: "qloo",
          curator: "genuine_agent",
          raw_payloads_retained: false,
          server_coldness_verified: false,
          human_playtest: false,
        },
        null,
        2,
      ),
      contentType: "application/json",
    });
  } finally {
    await Promise.all(contexts.map((session) => session.close()));
  }
});
