/** Intercepted synthetic API only. These tests never establish live provider coverage. */
import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type BrowserContext,
  type Page,
  type TestInfo,
  type Locator,
} from "@playwright/test";
import type { components } from "../../apps/web/src/lib/api/schema";

type S = components["schemas"];
const SLUG = "SYNTHETIC_P13_opaque_no_real_share_link_1234567890";
const GAME = "bc79d442-53b8-481b-a603-b625c72185d6";
const expiry = "2099-01-01T00:00:00Z";
const stamp = "2026-10-26T15:00:00Z";
const identifier = (n: number) =>
  `7ca50344-f3d3-4bb3-bf6a-${n.toString(16).padStart(12, "0")}`;
const seed: S["EntityPublic"] = {
  id: identifier(1),
  name: "SYNTHETIC chosen favourite",
  type: "artist",
  source: "fixture",
  artwork: null,
};
const pairs = Array.from(
  { length: 5 },
  (_, ordinal) =>
    [0, 1].map((side): S["ChoicePublic"] => ({
      id: identifier(100 + ordinal * 2 + side),
      entity: {
        id: identifier(200 + ordinal * 2 + side),
        name:
          ordinal === 0 && side === 0
            ? "SYNTHETIC The Very Long Film About Unexpected Evenings Beyond the Last City and Quiet Conversations"
            : `SYNTHETIC discovery ${ordinal + 1}${side ? "B" : "A"}`,
        type: "movie",
        source: "fixture",
        artwork: null,
      },
    })) as S["PlayableRoundPublic"]["choices"],
);

async function harness(
  context: BrowserContext,
  origin: string,
  opts: {
    loseAnswer?: boolean;
    loseAdvance?: boolean;
    loseSave?: boolean;
    expired?: boolean;
    expiredSaved?: boolean;
    fixed?: boolean;
    interrupted?: boolean;
    challengeExpired?: boolean;
    sourceMode?: S["CuratorMode"];
    summarySource?: S["RankingSource"];
  } = {},
) {
  let ordinal = 1,
    revision = 1,
    complete = false,
    active = true,
    offline = false;
  const answers: S["RevealedRoundPublic"][] = [];
  const saved = new Map<string, S["DiscoveryPublic"]>();
  const keys = {
    answer: [] as string[],
    advance: [] as string[],
    save: [] as string[],
  };
  const requests: string[] = [],
    unexpected: string[] = [],
    errors: string[] = [];
  const observePage = (page: Page) =>
    page.on("pageerror", (error) => errors.push(error.message));
  for (const page of context.pages()) observePage(page);
  context.on("page", observePage);
  function round(): S["PlayableRoundPublic"] | S["RevealedRoundPublic"] {
    return (
      answers[ordinal - 1] ?? {
        state: "unanswered",
        game_id: GAME,
        round_id: identifier(500 + ordinal),
        revision,
        ordinal,
        total: 5,
        seed,
        source: "fixture",
        target_type: "movie",
        question: "Which synthetic film ranks higher?",
        choices: pairs[ordinal - 1],
      }
    );
  }
  function game(): S["GamePublic"] {
    return {
      game_id: GAME,
      phase: complete ? "completed" : "playing",
      mode: opts.fixed ? "fixed" : "solo",
      seed,
      source: "fixture",
      curator_mode: "fixture",
      current_ordinal: ordinal,
      answered_count: answers.length,
      revision,
      score: answers.filter((a) => a.correct).length,
      total: 5,
      expires_at: expiry,
      current_round: complete ? null : round(),
    };
  }
  await context.route("**/*", async (route) => {
    const req = route.request(),
      url = new URL(req.url());
    if (!["http:", "https:"].includes(url.protocol)) return route.continue();
    if (url.origin !== origin) {
      unexpected.push(url.origin + url.pathname);
      return route.abort("blockedbyclient");
    }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace("/api/v1", ""),
      method = req.method();
    requests.push(`${method} ${path}`);
    if (offline) return route.abort("internetdisconnected");
    const reply = (value: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(value),
        headers: { "Cache-Control": "no-store" },
      });
    const fail = (code: string, status: number) =>
      reply(
        {
          error: {
            code,
            message:
              code === "GAME_EXPIRED"
                ? "This game has expired. Start a fresh game."
                : "This anonymous session is no longer available.",
            retryable: false,
            request_id: identifier(999),
            field_errors: [],
            retry_after_seconds: null,
          },
        } satisfies S["ErrorEnvelope"],
        status,
      );
    if (path === "/sessions/current" && method === "DELETE") {
      active = false;
      saved.clear();
      return route.fulfill({ status: 204 });
    }
    if (!active) return fail("SESSION_REQUIRED", 401);
    if (path === "/sessions/current" || path === "/sessions")
      return reply(
        {
          active: true,
          expires_at: expiry,
          resumable_game_ids: [GAME],
        } satisfies S["SessionPublic"],
        method === "POST" ? 201 : 200,
      );
    if (opts.expired && path.startsWith(`/games/${GAME}`))
      return fail("GAME_EXPIRED", 410);
    if (path === "/entities/search")
      return reply({
        status: "needs_input",
        results: [
          seed,
          {
            ...seed,
            id: identifier(88),
            name: "SYNTHETIC alternate artist",
            disambiguation: "Different synthetic identity",
          },
        ],
      });
    if (path === `/challenges/${SLUG}`) {
      if (opts.challengeExpired) return fail("CHALLENGE_EXPIRED", 410);
      return reply({
        slug: SLUG,
        seed,
        creator_score: 3,
        total: 5,
        source: "fixture",
        expires_at: expiry,
      });
    }
    if (path === `/challenges/${SLUG}/plays`) return reply(game(), 201);
    if (path === "/games" && method === "POST") return reply(game(), 201);
    if (opts.interrupted && path === `/games/${GAME}`)
      return fail("NOT_FOUND", 404);
    if (path === `/games/${GAME}/generation`)
      return reply({
        game_id: GAME,
        status: "generation_interrupted",
        recovery_action: "retry_same_request",
        retry_after_seconds: null,
      });
    if (path === `/games/${GAME}`) return reply(game());
    if (path === `/games/${GAME}/results`)
      return reply({
        game_id: GAME,
        phase: "completed",
        source: "fixture",
        curator_mode: "fixture",
        score: answers.filter((a) => a.correct).length,
        total: 5,
        expires_at: expiry,
        answered_rounds: answers,
        discoveries: [...saved.values()],
      } satisfies Partial<S["GameResultPublic"]>);
    if (path === `/games/${GAME}/answer` && method === "POST") {
      keys.answer.push(req.headers()["idempotency-key"] ?? "");
      const body = req.postDataJSON() as S["AnswerRequest"];
      if (!answers[ordinal - 1]) {
        expect(body.round_id).toBe(identifier(500 + ordinal));
        const winning = pairs[ordinal - 1][ordinal % 2].id;
        const correct = body.choice_id === winning;
        revision++;
        answers.push({
          state: "revealed",
          game_id: GAME,
          round_id: body.round_id,
          ordinal,
          total: 5,
          revision,
          source: "fixture",
          seed,
          target_type: "movie",
          choices: pairs[ordinal - 1],
          selected_choice_id: body.choice_id,
          winning_choice_id: winning,
          correct,
          cumulative_score:
            answers.filter((a) => a.correct).length + Number(correct),
          accepted_at: stamp,
          evidence: {
            source: "fixture",
            context: { seed, target_type: "movie", retrieved_at: stamp },
            supported_explanation: null,
          },
          curation_summary:
            ordinal === 5
              ? {
                  source: opts.summarySource ?? "fixture",
                  curator_mode: opts.sourceMode ?? "fixture",
                  candidate_count_received: 14,
                  bounded_correction_count: 1,
                  five_round_path_verified: true,
                  rejection_counts: { near_tie: 2 },
                  target_domains: ["movie"],
                  status: "succeeded",
                }
              : null,
        });
      }
      if (opts.loseAnswer && keys.answer.length === 1)
        return route.abort("failed");
      return reply(round());
    }
    if (path === `/games/${GAME}/advance` && method === "POST") {
      keys.advance.push(req.headers()["idempotency-key"] ?? "");
      const body = req.postDataJSON() as S["AdvanceRequest"];
      if (body.answered_round_id === identifier(500 + ordinal)) {
        revision++;
        if (ordinal === 5) complete = true;
        else ordinal++;
      }
      if (opts.loseAdvance && keys.advance.length === 1)
        return route.abort("failed");
      return reply(game());
    }
    if (path === "/discoveries" && method === "GET")
      return reply({
        discoveries: [...saved.values()],
        expired_count: opts.expiredSaved ? 1 : 0,
        session_expires_at: expiry,
      } satisfies S["DiscoveriesPublic"]);
    if (path === "/discoveries" && method === "POST") {
      keys.save.push(req.headers()["idempotency-key"] ?? "");
      const body = req.postDataJSON() as S["DiscoveryCreateRequest"];
      const entity = answers
        .flatMap((a) => a.choices)
        .find((c) => c.entity.id === body.entity_id)?.entity;
      expect(entity, "Only answered contestants may be saved").toBeTruthy();
      const discovery: S["DiscoveryPublic"] = {
        entity: entity!,
        saved_at: stamp,
        expires_at: expiry,
      };
      saved.set(body.entity_id, discovery);
      if (opts.loseSave && keys.save.length === 1) return route.abort("failed");
      return reply(discovery, 201);
    }
    if (path.startsWith("/discoveries/") && method === "DELETE") {
      saved.delete(path.split("/").pop()!);
      return route.fulfill({ status: 204 });
    }
    unexpected.push(`${method} ${path}`);
    return fail("NOT_FOUND", 404);
  });
  return {
    answers,
    saved,
    keys,
    requests,
    setOffline: (value: boolean) => {
      offline = value;
    },
    check: () => {
      expect(unexpected).toEqual([]);
      expect(errors).toEqual([]);
    },
  };
}

async function tabTo(page: Page, target: Locator) {
  for (let n = 0; n < 40; n++) {
    if (await target.evaluate((el) => el === document.activeElement)) return;
    await page.keyboard.press("Tab");
  }
  await expect(target).toBeFocused();
}
async function inspect(page: Page, info: TestInfo, state: string) {
  await page.evaluate(() => document.fonts.ready);
  const fonts = await page.evaluate(() => ({
    status: document.fonts.status,
    body: getComputedStyle(document.body).fontFamily,
    heading: document.querySelector("h1")
      ? getComputedStyle(document.querySelector("h1")!).fontFamily
      : null,
    loaded: Array.from(document.fonts)
      .filter((face) => face.status === "loaded")
      .map((face) => face.family),
  }));
  expect(fonts.status).toBe("loaded");
  expect(fonts.body).toContain("bodyFont");
  await info.attach(`${state}-font-loading.json`, {
    body: JSON.stringify(fonts, null, 2),
    contentType: "application/json",
  });
  expect(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBe(true);
  const widths = await page.evaluate(() => ({
    root: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    view: innerWidth,
  }));
  expect(widths.root).toBeLessThanOrEqual(widths.view + 1);
  expect(widths.body).toBeLessThanOrEqual(widths.view + 1);
  const bounds = await page
    .locator(
      ".button,.live-discoveries button,.guest-session-controls summary,[data-testid='discovery-reveal'] > summary,.discovery-explore > summary,.why-this-duel > summary,.seed-toggle,.seed-input,.seed-option,.wordmark,.header-nav a",
    )
    .evaluateAll((nodes) =>
      nodes
        .map((node) => ({
          label: node.getAttribute("aria-label") || node.textContent,
          width: node.getBoundingClientRect().width,
          height: node.getBoundingClientRect().height,
        }))
        .filter((node) => node.width && node.height),
    );
  for (const target of bounds) {
    expect(
      target.width,
      `${target.label}: target width`,
    ).toBeGreaterThanOrEqual(48);
    expect(
      target.height,
      `${target.label}: target height`,
    ).toBeGreaterThanOrEqual(48);
  }
  const combinations = await page
    .locator(
      "h1,h2,p,summary,.button,.choice-title,.choice-kind,.choice-selection,.fixture-badge,.arena-score",
    )
    .evaluateAll((nodes) => {
      function rgb(s: string) {
        const parts = s.match(/[\d.]+/g)?.map(Number) ?? [];
        return parts.length >= 3 ? parts : [0, 0, 0, 0];
      }
      function lum(a: number[]) {
        return a
          .slice(0, 3)
          .map((x) => x / 255)
          .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
          .reduce((s, x, i) => s + x * [0.2126, 0.7152, 0.0722][i], 0);
      }
      return nodes
        .filter(
          (n) =>
            n.getBoundingClientRect().width && n.getBoundingClientRect().height,
        )
        .map((n) => {
          const style = getComputedStyle(n);
          let parent: Element | null = n;
          let bg = [0, 0, 0, 0];
          let complex = false;
          while (parent && (bg[3] ?? 1) < 1) {
            const computed = getComputedStyle(parent);
            if (computed.backgroundImage !== "none") complex = true;
            const next = rgb(computed.backgroundColor);
            if ((next[3] ?? 1) >= 1) bg = next;
            parent = parent.parentElement;
          }
          const fg = rgb(style.color);
          const l1 = lum(fg),
            l2 = lum(bg);
          return {
            text: n.textContent?.trim().slice(0, 90),
            foreground: style.color,
            background: bg,
            complexBackground: complex,
            disabled: Boolean(n.closest(":disabled,[aria-disabled=true]")),
            font: style.fontFamily,
            fontSize: style.fontSize,
            ratio: Number(
              ((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)).toFixed(
                2,
              ),
            ),
          };
        });
    });
  await info.attach(`${state}-computed-colours.json`, {
    body: JSON.stringify(combinations, null, 2),
    contentType: "application/json",
  });
  await page.screenshot({
    path: info.outputPath(`${state}.png`),
    fullPage: true,
    animations: "disabled",
  });
  const axe = await new AxeBuilder({ page }).analyze();
  await info.attach(`${state}-axe.json`, {
    body: JSON.stringify(axe, null, 2),
    contentType: "application/json",
  });
  expect(axe.violations).toEqual([]);
}

for (const fixed of [false, true]) {
  test(`${fixed ? "fixed" : "solo"}: full keyboard five, source-safe evidence, stable focus and result`, async ({
    page,
    context,
    baseURL,
  }, info) => {
    const h = await harness(context, new URL(baseURL!).origin, { fixed });
    await page.goto("/");
    await expect(page.getByRole("combobox")).toBeEnabled();
    await inspect(page, info, "01-landing");
    const input = page.getByRole("combobox", { name: "Choose your favourite" });
    await tabTo(page, input);
    await page.keyboard.type("Synthetic");
    await expect(page.getByRole("option")).toHaveCount(2);
    const searchToggle = page.getByRole("button", {
      name: "Show search results",
    });
    const chevron = searchToggle.locator("svg.seed-toggle-icon");
    await expect(chevron).toBeVisible();
    await expect(chevron.locator("path")).toHaveAttribute("d", "m6 9 6 6 6-6");
    const iconBox = await chevron.boundingBox();
    expect(iconBox?.width).toBeGreaterThanOrEqual(16);
    expect(iconBox?.height).toBeGreaterThanOrEqual(16);
    await expect(searchToggle).toHaveAttribute("aria-expanded", "true");
    await searchToggle.click();
    await expect(searchToggle).toHaveAttribute("aria-expanded", "false");
    await searchToggle.click();
    await expect(searchToggle).toHaveAttribute("aria-expanded", "true");
    await expect(chevron).toHaveCSS("transform", "matrix(-1, 0, 0, -1, 0, 0)");
    await page.keyboard.press("ArrowDown");
    await expect(input).toHaveAttribute("aria-activedescendant", /option/);
    await page.keyboard.press("Escape");
    await expect(input).toHaveAttribute("aria-expanded", "false");
    await page.keyboard.press("ArrowUp");
    await expect(input).toHaveAttribute("aria-expanded", "true");
    await page.keyboard.press("ArrowDown");
    await inspect(page, info, "02-combobox");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("start-duel")).toBeEnabled();
    await tabTo(page, page.getByTestId("start-duel"));
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(new RegExp(`/g/${GAME}$`));
    if (fixed)
      await expect(page.getByTestId("fixed-replay-label")).toContainText(
        /same five/i,
      );
    await expect(page.locator(".choice-title").first()).toContainText(
      pairs[0][0].entity.name,
    );
    await inspect(page, info, "03-unanswered-long-title");
    for (let n = 0; n < 5; n++) {
      await expect(page.getByTestId("live-question")).toBeFocused();
      await expect(page.getByTestId("curation-disclosure")).toHaveCount(0);
      await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
      for (const p of pairs.slice(n + 1).flat())
        expect(await page.content()).not.toContain(p.entity.name);
      await tabTo(page, page.getByTestId("choice-card").first());
      await page.keyboard.press("Enter");
      await expect(page.getByTestId("reveal-panel")).toBeVisible();
      await expect(
        page.getByTestId("reveal-panel").getByRole("heading"),
      ).toBeFocused();
      expect(
        await page
          .getByTestId("reveal-panel")
          .evaluate((el) => Boolean(el.closest("[aria-live]"))),
      ).toBe(false);
      const disclosure = page.getByTestId("why-this-duel");
      await tabTo(page, disclosure.locator("summary"));
      await page.keyboard.press("Enter");
      await expect(disclosure).toHaveAttribute("open", "");
      await expect(disclosure).toContainText(/synthetic fixture evidence/i);
      await expect(disclosure).toContainText(/No Qloo or model was called/i);
      expect(await disclosure.ariaSnapshot()).not.toMatch(
        /affinity|chain.of.thought|psycholog/i,
      );
      if (n === 0) {
        await inspect(page, info, "04-reveal-evidence");
        await page.reload();
        await expect(
          page.getByTestId("reveal-panel").getByRole("heading"),
        ).toBeFocused();
        expect(h.answers).toHaveLength(1);
      }
      await tabTo(page, page.getByTestId("next-action"));
      await page.keyboard.press("Enter");
    }
    await expect(page).toHaveURL(new RegExp(`/results/${GAME}$`));
    await expect(page.getByTestId("result-ticket")).toContainText(/2\s*\/\s*5/);
    const curation = page.getByTestId("curation-disclosure");
    await tabTo(page, curation.locator("summary"));
    await page.keyboard.press("Enter");
    await expect(curation).toContainText(/synthetic fixture.*no live qloo/i);
    await expect(curation).toContainText(
      "Counts show primary validation exclusions.",
    );
    await expect(curation).not.toContainText("may overlap");
    expect(await curation.ariaSnapshot()).not.toMatch(
      /SYNTHETIC discovery|affinity|winning_choice_id|chain.of.thought|prompt/i,
    );
    await inspect(page, info, "05-result-curation");
    expect(h.keys.answer).toHaveLength(5);
    expect(h.keys.advance).toHaveLength(5);
    if (!fixed) {
      await page.goto("/how-it-works");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await inspect(page, info, "05b-how-it-works");
    }
    h.check();
  });
}

test("image failure preserves long titles, keyboard choice, layout and identical reduced-motion facts", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin);
  await context.route("**/art/*.svg", (route) => route.abort("failed"));
  await page.goto(`/g/${GAME}`);
  await expect(page.locator(".artwork-fallback")).toHaveCount(2);
  await expect(page.locator(".choice-title").first()).toHaveText(
    pairs[0][0].entity.name,
  );
  await inspect(page, info, "06-failed-imagery");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await tabTo(page, page.getByTestId("choice-card").first());
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("reveal-panel")).toBeVisible();
  const normal = await page.getByTestId("reveal-panel").innerText();
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(await page.getByTestId("reveal-panel").innerText()).toBe(normal);
  h.check();
});

test("200 percent CSS zoom emulation reflows keyboard arena and disclosures", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin);
  await page.goto(`/g/${GAME}`);
  // Explicitly CSS zoom; this does not claim manual browser UI zoom or screen-reader user testing.
  await page.evaluate(() => (document.documentElement.style.zoom = "2"));
  await expect(page.getByTestId("choice-card").first()).toBeEnabled();
  await inspect(page, info, "07-css-zoom-200-unanswered");
  await tabTo(page, page.getByTestId("choice-card").first());
  await page.keyboard.press("Enter");
  await expect(
    page.getByTestId("reveal-panel").getByRole("heading"),
  ).toBeFocused();
  await tabTo(page, page.getByTestId("why-this-duel").locator("summary"));
  await page.keyboard.press("Enter");
  await inspect(page, info, "08-css-zoom-200-reveal");
  h.check();
});

test("interrupted preparation and expired historic game are intentional focusable routes", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin, {
    interrupted: true,
  });
  await page.goto(`/g/${GAME}`);
  await expect(
    page.getByRole("heading", { name: "Generation was interrupted." }),
  ).toBeVisible();
  await expect(page.locator('.state-panel[aria-live="polite"]')).toContainText(
    "Generation was interrupted.",
  );
  await inspect(page, info, "09-interrupted");
  h.check();
});

test("expired game has no choices, score mutation or hidden evidence", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin, { expired: true });
  await page.goto(`/g/${GAME}`);
  await expect(
    page.getByRole("heading", { name: "This game has expired." }),
  ).toBeVisible();
  await expect(page.getByTestId("choice-card")).toHaveCount(0);
  await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
  await expect(page.locator('.state-panel[aria-live="polite"]')).toContainText(
    "This game has expired.",
  );
  await inspect(page, info, "10-expired");
  h.check();
});

test("fixed invitation and expiry expose no future contestants and remain keyboard accessible", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin, { fixed: true });
  await page.goto(`/c/${SLUG}`);
  await expect(page.getByTestId("challenge-invitation")).toContainText(
    /3 out of 5/i,
  );
  for (const p of pairs.flat())
    expect(await page.content()).not.toContain(p.entity.name);
  await inspect(page, info, "11-fixed-invitation");
  const play = page.getByRole("button", { name: /play these five/i });
  await tabTo(page, play);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/g/${GAME}$`));
  h.check();
  const expired = await context.newPage();
  await expired.route(`**/api/v1/challenges/${SLUG}`, (route) =>
    route.fulfill({
      status: 410,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "CHALLENGE_EXPIRED",
          message: "Synthetic challenge expired",
          retryable: false,
          request_id: identifier(999),
          field_errors: [],
          retry_after_seconds: null,
        },
      }),
    }),
  );
  await expired.goto(`/c/${SLUG}`);
  await expect(
    expired.getByRole("heading", { name: /THIS FIVE HAS EXPIRED/i }),
  ).toBeVisible();
  await expect(
    expired.locator('.state-panel[aria-live="polite"]'),
  ).toContainText("THIS FIVE HAS EXPIRED.");
  await inspect(expired, info, "12-fixed-expired");
  await expired.close();
  h.check();
});

for (const [source, mode, label, copy] of [
  [
    "fixture",
    "genuine_agent",
    /About this synthetic fixture/,
    /Prewritten test evidence/,
  ],
  ["qloo", "genuine_agent", /Curated with Qloo/, /A bounded agent selected/],
  [
    "qloo",
    "deterministic_qloo",
    /Curated with Qloo/,
    /A deterministic curator/,
  ],
] as const) {
  test(`synthetic wire rendering: ${source}/${mode} label never claims private reasoning`, async ({
    page,
    context,
    baseURL,
  }, info) => {
    const h = await harness(context, new URL(baseURL!).origin, {
      summarySource: source,
      sourceMode: mode,
    });
    await page.goto(`/g/${GAME}`);
    for (let n = 0; n < 5; n++) {
      await page.getByTestId("choice-card").first().click();
      await expect(page.getByTestId("reveal-panel")).toBeVisible();
      await page.getByTestId("next-action").click();
    }
    await expect(page).toHaveURL(new RegExp(`/results/${GAME}$`));
    const summary = page.getByTestId("curation-disclosure");
    await expect(summary.locator("summary")).toHaveText(label);
    await tabTo(page, summary.locator("summary"));
    await page.keyboard.press("Enter");
    await expect(summary).toContainText(copy);
    expect(await summary.ariaSnapshot()).not.toMatch(
      /SYNTHETIC discovery|affinity|winning_choice_id|chain.of.thought|prompt/i,
    );
    await inspect(page, info, `13-synthetic-wire-label-${source}-${mode}`);
    h.check();
  });
}

test("guest session clear restores wordmark focus without a trapped or stale private screen", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin);
  await page.goto(`/g/${GAME}`);
  await expect(page.getByTestId("choice-card").first()).toBeEnabled();
  const summary = page.locator(".guest-session-controls summary");
  await tabTo(page, summary);
  await page.keyboard.press("Enter");
  await page.keyboard.press("Escape");
  await expect(summary).toBeFocused();
  await expect(
    page.locator(".guest-session-controls details"),
  ).not.toHaveAttribute("open", "");
  await page.keyboard.press("Enter");
  const clear = page.getByRole("button", {
    name: "Clear guest session",
    exact: true,
  });
  await tabTo(page, clear);
  await page.keyboard.press("Enter");
  const confirm = page.getByRole("button", {
    name: "Clear this session",
    exact: true,
  });
  await tabTo(page, confirm);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("choice-card")).toHaveCount(0);
  await expect(page.locator(".wordmark")).toBeFocused();
  await expect(
    page.getByRole("status").filter({ hasText: /Guest session cleared/ }),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(summary).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  const how = page.locator('.header-nav a[href="/how-it-works"]');
  await expect(how).toBeFocused();
  await expect(
    page.locator(".guest-session-controls details"),
  ).not.toHaveAttribute("open", "");
  expect(
    await how.evaluate((el) => {
      const r = el.getBoundingClientRect();
      const hit = document.elementFromPoint(
        r.x + r.width / 2,
        r.y + r.height / 2,
      );
      return Boolean(hit && el.contains(hit));
    }),
  ).toBe(true);
  await inspect(page, info, "14-cleared-guest-session");
  h.check();
});

test("expired saved result announces its unavailable state without inventing score", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin, { expired: true });
  await page.goto(`/results/${GAME}`);
  await expect(page.locator('.state-panel[aria-live="polite"]')).toContainText(
    "No result to show yet.",
  );
  await expect(page.getByTestId("result-ticket")).toHaveCount(0);
  await inspect(page, info, "15-unavailable-result-polite");
  h.check();
});
