/** Synthetic intercepted recovery/error tests. Real exact replay has a separate local DB proof. */
import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type BrowserContext,
  type Page,
  type TestInfo,
} from "@playwright/test";
import type { components } from "../../apps/web/src/lib/api/schema";
type S = components["schemas"];
const GAME = "76daf293-aa63-4f05-80e7-6b41c89bdf7c";
const SLUG = "SYNTHETIC_opaque_challenge_slug_not_a_real_link_12";
const stamp = "2026-10-26T15:00:00Z",
  expires = "2099-01-01T00:00:00Z";
const id = (n: number) =>
  `f341802a-e4ee-4960-8bb0-${n.toString(16).padStart(12, "0")}`;
const seed: S["EntityPublic"] = {
  id: id(1),
  name: "SYNTHETIC An Extremely Long Favourite Beyond the Last Cinema and the Quietest Cultural Fight Night",
  type: "artist",
  source: "fixture",
  artwork: null,
};
const invitation: S["ChallengeInvitationPublic"] = {
  creator_name: "Mira",
  slug: SLUG,
  seed,
  creator_score: 3,
  total: 5,
  source: "fixture",
  expires_at: expires,
};
const choices: S["ChoicePublic"][] = [0, 1].map((n) => ({
  id: id(20 + n),
  entity: {
    id: id(30 + n),
    name: `SYNTHETIC_PRIVATE_UNDELIVERED_${n}`,
    type: "movie",
    source: "fixture",
    artwork: null,
  },
}));
const result: S["GameResultPublic"] = {
  game_id: GAME,
  phase: "completed",
  source: "fixture",
  curator_mode: "fixture",
  score: 3,
  total: 5,
  expires_at: expires,
  discoveries: [],
  answered_rounds: Array.from({ length: 5 }, (_, n) => ({
    state: "revealed",
    game_id: GAME,
    round_id: id(100 + n),
    ordinal: n + 1,
    total: 5,
    revision: 2 + n * 2,
    source: "fixture",
    seed,
    target_type: "movie",
    choices: choices as S["RevealedRoundPublic"]["choices"],
    selected_choice_id: choices[0].id,
    winning_choice_id: choices[n < 3 ? 0 : 1].id,
    correct: n < 3,
    cumulative_score: Math.min(n + 1, 3),
    accepted_at: stamp,
    evidence: {
      source: "fixture",
      context: { seed, target_type: "movie", retrieved_at: stamp },
      supported_explanation: null,
    },
    curation_summary: null,
  })),
};
async function fixture(
  context: BrowserContext,
  origin: string,
  opts: { code?: string; lostCreate?: boolean; lostPlay?: boolean } = {},
) {
  const createKeys: string[] = [],
    playKeys: string[] = [],
    unexpected: string[] = [],
    errors: string[] = [];
  let saved: S["DiscoveryPublic"] | null = null;
  context.on("page", (page) =>
    page.on("pageerror", (error) => errors.push(error.name)),
  );
  await context.route("**/*", async (route) => {
    const req = route.request(),
      url = new URL(req.url());
    if (["http:", "https:"].includes(url.protocol) && url.origin !== origin) {
      unexpected.push(url.origin);
      return route.abort("blockedbyclient");
    }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace("/api/v1", "");
    const reply = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
        headers: { "Cache-Control": "no-store" },
      });
    if (path === "/sessions/current" || path === "/sessions")
      return reply(
        {
          active: true,
          display_name: "Synthetic player",
          expires_at: expires,
          resumable_game_ids: [GAME],
        },
        req.method() === "POST" ? 201 : 200,
      );
    if (path === `/games/${GAME}/results`) return reply(result);
    if (path === `/games/${GAME}/duels`)
      return reply({ status: "not_shared", outcomes: [] });
    if (path === "/discoveries" && req.method() === "POST") {
      const requested = req.postDataJSON().entity_id;
      const entity = result.answered_rounds
        .flatMap((round) => round.choices)
        .find((choice) => choice.entity.id === requested)?.entity;
      if (!entity) return reply({}, 400);
      saved = { entity, saved_at: stamp, expires_at: expires };
      return reply(saved, 201);
    }
    if (path === "/discoveries")
      return reply({
        discoveries: saved ? [saved] : [],
        expired_count: 0,
        session_expires_at: expires,
      });
    if (path === "/challenges" && req.method() === "POST") {
      createKeys.push(req.headers()["idempotency-key"] ?? "");
      if (opts.lostCreate && createKeys.length === 1)
        return route.abort("failed");
      return reply(
        { invitation, share_path: `/c/${SLUG}` },
        createKeys.length === 1 ? 201 : 200,
      );
    }
    if (path === `/challenges/${SLUG}`) {
      if (opts.code)
        return reply(
          {
            error: {
              code: opts.code,
              message: "Synthetic unavailable invitation",
              retryable: false,
              request_id: id(800),
              field_errors: [],
              retry_after_seconds: null,
            },
          },
          opts.code === "NOT_FOUND" ? 404 : 410,
        );
      return reply(invitation);
    }
    if (path === `/challenges/${SLUG}/plays`) {
      playKeys.push(req.headers()["idempotency-key"] ?? "");
      if (opts.lostPlay && playKeys.length === 1) return route.abort("failed");
      return reply(
        {
          game_id: GAME,
          phase: "playing",
          mode: "fixed",
          seed,
          source: "fixture",
          curator_mode: "fixture",
          current_ordinal: 1,
          answered_count: 0,
          revision: 1,
          score: 0,
          total: 5,
          expires_at: expires,
          current_round: null,
        },
        201,
      );
    }
    if (path === `/games/${GAME}`)
      return reply({
        game_id: GAME,
        phase: "playing",
        mode: "fixed",
        seed,
        source: "fixture",
        curator_mode: "fixture",
        current_ordinal: 1,
        answered_count: 0,
        revision: 1,
        score: 0,
        total: 5,
        expires_at: expires,
        current_round: {
          state: "unanswered",
          game_id: GAME,
          round_id: id(500),
          revision: 1,
          ordinal: 1,
          total: 5,
          seed,
          source: "fixture",
          target_type: "movie",
          question: "Which synthetic movie ranks higher?",
          choices,
        },
      });
    unexpected.push(`${req.method()} ${path}`);
    return reply({}, 404);
  });
  return {
    createKeys,
    playKeys,
    check() {
      expect(unexpected).toEqual([]);
      expect(errors).toEqual([]);
    },
  };
}
async function inspect(page: Page, info: TestInfo, label: string) {
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(
      () =>
        Math.max(
          document.documentElement.scrollWidth,
          document.body.scrollWidth,
        ) <=
        innerWidth + 1,
    ),
  ).toBe(true);
  const axe = await new AxeBuilder({ page }).analyze();
  await info.attach(`${label}-axe.json`, {
    body: JSON.stringify(axe, null, 2),
    contentType: "application/json",
  });
  expect(axe.violations).toEqual([]);
  await page.screenshot({
    path: info.outputPath(`${label}.png`),
    fullPage: true,
    animations: "disabled",
  });
}
for (const [code, title] of [
  ["CHALLENGE_EXPIRED", /THIS FIVE HAS EXPIRED/i],
  ["CHALLENGE_REVOKED", /THIS LINK IS RETIRED/i],
  ["NOT_FOUND", /INVITATION NOT FOUND/i],
] as const) {
  test(`${code} is intentional and never silently becomes a new challenge`, async ({
    page,
    context,
    baseURL,
  }, info) => {
    const h = await fixture(context, new URL(baseURL!).origin, { code });
    await page.goto(`/c/${SLUG}`);
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /play these five/i }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: /start a new solo duel/i }),
    ).toBeVisible();
    await inspect(page, info, code);
    expect(h.createKeys).toHaveLength(0);
    expect(h.playKeys).toHaveLength(0);
    h.check();
  });
}
test("synthetic result opens answered choices before an explicit keyboard save", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await fixture(context, new URL(baseURL!).origin, {});
  await page.goto(`/results/${GAME}`);
  await expect(page.getByTestId("result-ticket")).toContainText(/fixture/i);
  const insets = await page.getByTestId("result-ticket").evaluate((ticket) => {
    const bounds = ticket.getBoundingClientRect();
    const heading = ticket
      .querySelector(".challenge-share h2")!
      .getBoundingClientRect();
    const button = ticket
      .querySelector(".challenge-share button")!
      .getBoundingClientRect();
    return {
      heading: heading.left - bounds.left,
      button: button.left - bounds.left,
      headingRight: bounds.right - heading.right,
    };
  });
  expect(insets.heading).toBeCloseTo(29, 0);
  expect(insets.button).toBeCloseTo(29, 0);
  expect(insets.headingRight).toBeGreaterThanOrEqual(28);
  await expect(
    page.getByRole("button", { name: /^Save discovery:/ }),
  ).toHaveCount(0);
  const explore = page
    .locator("summary")
    .filter({ hasText: "Explore answered choices" });
  await explore.focus();
  await page.keyboard.press("Enter");
  const save = page.getByRole("button", { name: /^Save discovery:/ }).first();
  await expect(save).toBeEnabled();
  await save.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: /^Remove discovery:/ }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: /^Remove discovery:/ }),
  ).toBeVisible();
  await inspect(page, info, "explicit-save-from-answered-choices");
  h.check();
});

test("nickname entrance is accessible, atomic and remembered", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await fixture(context, new URL(baseURL!).origin);
  let nickname: string | null = null;
  const bootstraps: string[] = [];
  await page.route("**/api/v1/sessions**", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      nickname = request.postDataJSON().display_name ?? nickname;
      bootstraps.push(request.headers()["idempotency-key"] ?? "");
    }
    if (!nickname)
      return route.fulfill({
        status: 401,
        json: { error: { code: "SESSION_REQUIRED" } },
      });
    return route.fulfill({
      json: {
        active: true,
        display_name: nickname,
        expires_at: expires,
        resumable_game_ids: [],
      },
    });
  });
  await page.goto(`/c/${SLUG}`);
  await expect(page.getByTestId("name-entry")).toContainText(
    "Mira poked you. Your move.",
  );
  await expect(page.getByRole("button", { name: /let’s go/i })).toBeDisabled();
  await inspect(page, info, "nickname-entrance");
  await page.getByLabel("Your nickname", { exact: true }).fill("Rio");
  await page.getByRole("button", { name: /let’s go/i }).click();
  await expect(page.getByTestId("challenge-invitation")).toBeVisible();
  expect(bootstraps).toHaveLength(1);
  expect(bootstraps[0]).toMatch(/^[A-Za-z0-9_-]{43}$/);
  await page.reload();
  await expect(page.getByTestId("challenge-invitation")).toBeVisible();
  await expect(page.getByTestId("name-entry")).toHaveCount(0);
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...sessionStorage, ...localStorage }),
    ),
  ).not.toContain("Rio");
  h.check();
});

test("a friend verdict arrives through polling with names, scores and attempt labels", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await fixture(context, new URL(baseURL!).origin);
  let finished = false;
  await page.route(`**/api/v1/games/${GAME}/duels*`, (route) =>
    route.fulfill({
      json: {
        status: "active",
        expires_at: expires,
        next_cursor: null,
        replay_slug: null,
        outcomes: !finished
          ? []
          : [
              {
                attempt_id: id(701),
                attempt_number: 2,
                completed_at: stamp,
                creator_name: "Mira",
                challenger_name: "Rio",
                creator_score: 3,
                challenger_score: 5,
                outcome: "challenger",
              },
            ],
      },
    }),
  );
  await page.goto(`/results/${GAME}`);
  await expect(page.getByTestId("duel-verdict")).toContainText(
    "BRAGGING RIGHTS: PENDING.",
  );
  finished = true;
  await expect(page.getByTestId("duel-verdict")).toContainText(
    "THE VERDICT IS IN.",
    { timeout: 20_000 },
  );
  await expect(page.getByTestId("duel-verdict")).toContainText("Mira: 3/5");
  await expect(page.getByTestId("duel-verdict")).toContainText("Rio: 5/5");
  await expect(page.getByTestId("duel-verdict")).toContainText("ATTEMPT 2");
  await inspect(page, info, "named-shared-verdict");
  h.check();
});

test("native share cancellation stays neutral and shares the embedded URL", async ({
  page,
  context,
  baseURL,
}) => {
  const h = await fixture(context, new URL(baseURL!).origin);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "share", {
      configurable: true,
      value: async (data: ShareData) => {
        (window as Window & { shared?: ShareData }).shared = data;
        throw new DOMException("Cancelled", "AbortError");
      },
    });
  });
  await page.goto(`/results/${GAME}`);
  await page.getByRole("button", { name: /poke a friend/i }).click();
  await page.getByRole("button", { name: /share the poke/i }).click();
  expect(
    await page.evaluate(
      () => (window as Window & { shared?: ShareData }).shared?.url,
    ),
  ).toBe(`${new URL(baseURL!).origin}/c/${SLUG}`);
  await expect(
    page.getByRole("textbox", { name: "Challenge link", exact: true }),
  ).toBeHidden();
  h.check();
});
test("create response loss retains its key and accessible manual copy does not claim success", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await fixture(context, new URL(baseURL!).origin, {
    lostCreate: true,
  });
  await page.addInitScript(() =>
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async () => {
          throw new DOMException("Synthetic denied", "NotAllowedError");
        },
      },
    }),
  );
  await page.goto(`/results/${GAME}`);
  const create = page.getByRole("button", { name: /poke a friend/i });
  await create.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("status").filter({ hasText: /interrupted|retry/i }),
  ).toBeVisible();
  await page.reload();
  await create.focus();
  await page.keyboard.press("Enter");
  const copy = page.getByRole("button", {
    name: "Copy challenge link",
    exact: true,
  });
  await expect(copy).toBeVisible();
  await copy.focus();
  await page.keyboard.press("Enter");
  const field = page.getByRole("textbox", {
    name: "Challenge link",
    exact: true,
  });
  await expect(field).toBeVisible();
  await expect(field).toHaveValue(`${new URL(baseURL!).origin}/c/${SLUG}`);
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: /copy is unavailable|select and copy/i }),
  ).toBeVisible();
  expect(h.createKeys).toHaveLength(2);
  expect(h.createKeys[0]).toBe(h.createKeys[1]);
  expect(h.createKeys[0].length).toBeGreaterThanOrEqual(16);
  await inspect(page, info, "manual-copy-recovery");
  h.check();
});
test("invitation has no choices and lost replay response retries the same explicit play", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await fixture(context, new URL(baseURL!).origin, {
    lostPlay: true,
  });
  await page.goto(`/c/${SLUG}`);
  const play = page.getByRole("button", { name: /play these five/i });
  await expect(play).toBeVisible();
  await expect(page.getByTestId("challenge-invitation")).toContainText(
    /synthetic fixture/i,
  );
  await expect(page.getByTestId("challenge-invitation")).toContainText(
    /3 out of 5/i,
  );
  expect(await page.content()).not.toContain("SYNTHETIC_PRIVATE_UNDELIVERED");
  await inspect(page, info, "invitation-no-answer-leak");
  await play.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("status").filter({ hasText: /interrupted|retry/i }),
  ).toBeVisible();
  await page.reload();
  await play.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/g/${GAME}$`));
  expect(h.playKeys).toHaveLength(2);
  expect(h.playKeys[0]).toBe(h.playKeys[1]);
  h.check();
});
