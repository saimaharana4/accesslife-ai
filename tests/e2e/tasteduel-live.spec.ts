/**
 * Synthetic public-contract integration tests. This file intercepts every API
 * request; it proves browser behavior, never a live Qloo/Vertex integration.
 * Secret/private pool fixtures are intentionally absent from these responses.
 */
import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type Page,
  type TestInfo,
  type Locator,
} from "@playwright/test";
import type { components } from "../../apps/web/src/lib/api/schema";

type S = components["schemas"];
const GAME = "92b6b75c-078d-4c0a-9d0e-938979b8c172";
const SEED = "1a7b31e9-d054-42df-80fc-4fcdaf2ef509";
const stamp = "2026-10-26T12:00:00Z";
const expiry = "2099-01-01T00:00:00Z";
const seed: S["EntityPublic"] = {
  id: SEED,
  name: "Synthetic public-contract seed",
  type: "artist",
  source: "qloo",
  disambiguation: "Invented test identity, no upstream call",
  artwork: null,
};
const names = [
  [
    "The Unexpectedly Long Journey Through the Museum of Forgotten Summer Evenings and Beautiful Unfinished Conversations",
    "The Blue Hour Archive",
  ],
  ["Synthetic Evening Atlas", "Synthetic Quiet Orchestra"],
  ["Synthetic Lunar Cinema", "Synthetic Sunday Hotel"],
  ["Synthetic Electric Orbit", "Synthetic Paper Lanterns"],
  ["Synthetic Glass Radio", "Synthetic Last Light"],
];
function id(n: number) {
  return `db523c98-713f-4b7c-a5d9-${n.toString(16).padStart(12, "0")}`;
}
const choices = names.map(
  (pair, index): S["PlayableRoundPublic"]["choices"] =>
    pair.map((name, side): S["ChoicePublic"] => ({
      id: id(100 + index * 2 + side),
      entity: {
        id: id(300 + index * 2 + side),
        name,
        type: "movie",
        source: "qloo",
        artwork: side
          ? {
              kind: "owned_fallback",
              asset_id: "velvet-static",
              attribution: "Original Taste Duel title art",
            }
          : null,
      },
    })) as S["PlayableRoundPublic"]["choices"],
);
const winners = [1, 0, 1, 1, 0];

async function publicHarness(
  page: Page,
  options: {
    loseCreate?: boolean;
    loseAnswer?: boolean;
    loseAdvance?: boolean;
    expired?: boolean;
    unavailable?: boolean;
    generationRecovery?: boolean;
    holdCreate?: boolean;
    generationFailure?: "temporary" | "coverage";
  } = {},
) {
  let ordinal = 1;
  let revision = 1;
  let complete = false;
  let created = false;
  let generationObservations = 0;
  let generationLease = "";
  let releaseCreate = () => {};
  const createReplyGate = new Promise<void>((resolve) => {
    releaseCreate = resolve;
  });
  let finishCreateReply = () => {};
  const createReplySettled = new Promise<void>((resolve) => {
    finishCreateReply = resolve;
  });
  const answers: S["RevealedRoundPublic"][] = [];
  const keys = {
    create: [] as string[],
    answer: [] as string[],
    advance: [] as string[],
  };
  const calls: string[] = [];
  const createBodies: S["CreateGameRequest"][] = [];
  const unexpected: string[] = [];
  const errors: string[] = [];
  const serializedResponses: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const origin = new URL(test.info().project.use.baseURL as string).origin;
  function current(): S["PlayableRoundPublic"] | S["RevealedRoundPublic"] {
    return (
      answers[ordinal - 1] || {
        state: "unanswered",
        game_id: GAME,
        round_id: id(900 + ordinal),
        revision,
        ordinal,
        total: 5,
        seed,
        source: "qloo",
        target_type: "movie",
        question: "Which film ranks higher for this seed?",
        choices: choices[ordinal - 1],
      }
    );
  }
  function game(): S["GamePublic"] {
    return {
      game_id: GAME,
      phase: complete ? "completed" : "playing",
      mode: "solo",
      seed,
      source: "qloo",
      curator_mode: "genuine_agent",
      current_ordinal: ordinal,
      answered_count: answers.length,
      revision,
      score: answers.filter((a) => a.correct).length,
      total: 5,
      expires_at: expiry,
      current_round: complete ? null : current(),
    };
  }
  function result(): S["GameResultPublic"] {
    return {
      game_id: GAME,
      phase: "completed",
      source: "qloo",
      curator_mode: "genuine_agent",
      score: answers.filter((a) => a.correct).length,
      total: 5,
      expires_at: expiry,
      discoveries: [],
      answered_rounds: answers as S["GameResultPublic"]["answered_rounds"],
    };
  }
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!["http:", "https:"].includes(url.protocol)) return route.continue();
    if (url.origin !== origin) {
      unexpected.push(`${url.origin}${url.pathname}`);
      return route.abort("blockedbyclient");
    }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();
    calls.push(`${method} ${path}`);
    const reply = async (data: unknown, status = 200) => {
      const body = JSON.stringify(data);
      serializedResponses.push(body);
      await route.fulfill({
        status,
        contentType: "application/json",
        body,
        headers: { "Cache-Control": "no-store" },
      });
    };
    const fail = (code: string, message: string, status: number) =>
      reply(
        {
          error: {
            code,
            message,
            retryable: status >= 500,
            retry_after_seconds: null,
            request_id: id(88),
            field_errors: [],
          },
        } satisfies S["ErrorEnvelope"],
        status,
      );
    if (path === "/sessions" || path === "/sessions/current")
      return reply(
        {
          active: true,
          expires_at: expiry,
          resumable_game_ids: created ? [GAME] : [],
        } satisfies S["SessionPublic"],
        method === "POST" ? 201 : 200,
      );
    if (path === "/entities/search") {
      const query =
        url.searchParams.get("q") || url.searchParams.get("query") || "";
      if (query.toLowerCase().includes("slow")) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        return reply({
          status: "ok",
          results: [
            {
              ...seed,
              id: id(77),
              name: "Stale result must never replace new search",
            },
          ],
        } satisfies S["EntitySearchPublic"]);
      }
      if (options.unavailable)
        return fail(
          "QLOO_UNAVAILABLE",
          "Search is temporarily unavailable. Please retry.",
          503,
        );
      return reply({
        status: "needs_input",
        results: [
          seed,
          {
            ...seed,
            id: id(78),
            name: "Synthetic second identity",
            disambiguation: "Choose the exact identity",
          },
        ],
      } satisfies S["EntitySearchPublic"]);
    }
    if (path === "/games" && method === "POST") {
      keys.create.push(request.headers()["idempotency-key"] || "");
      createBodies.push(request.postDataJSON() as S["CreateGameRequest"]);
      created = true;
      if (options.generationFailure && keys.create.length === 1)
        return options.generationFailure === "coverage"
          ? fail(
              "GENERATION_INSUFFICIENT_COVERAGE",
              "There are not enough verified comparisons for this favourite. Choose another artist or film.",
              422,
            )
          : fail(
              "GENERATION_PROVIDER_UNAVAILABLE",
              "The cultural ranking service is temporarily unavailable. Retry the same saved request.",
              503,
            );
      if (options.loseCreate && keys.create.length === 1)
        return route.abort("failed");
      if (options.generationRecovery && keys.create.length === 1) {
        generationLease = new Date(Date.now() + 700).toISOString();
        return reply(
          {
            game_id: GAME,
            status: "generation_in_progress",
            lease_expires_at: generationLease,
            retry_after_seconds: 1,
          } satisfies S["GameGenerationPendingPublic"],
          202,
        );
      }
      if (options.holdCreate && keys.create.length === 1) {
        await createReplyGate;
        try {
          return await reply(game(), 201);
        } finally {
          finishCreateReply();
        }
      }
      return reply(game(), keys.create.length > 1 ? 200 : 201);
    }
    if (path === `/games/${GAME}/generation`) {
      if (options.generationRecovery && keys.create.length < 2) {
        generationObservations++;
        return reply(
          generationObservations === 1
            ? ({
                game_id: GAME,
                status: "generation_in_progress",
                lease_expires_at: generationLease,
                retry_after_seconds: 1,
                recovery_action: "wait_then_retry",
              } satisfies S["GenerationStatusPublic"])
            : ({
                game_id: GAME,
                status: "retryable",
                lease_expires_at: generationLease,
                recovery_action: "retry_same_request",
              } satisfies S["GenerationStatusPublic"]),
        );
      }
      return reply({
        game_id: GAME,
        status: "succeeded",
        recovery_action: "read_game",
      } satisfies S["GenerationStatusPublic"]);
    }
    if (options.expired && path.startsWith(`/games/${GAME}`))
      return fail(
        "GAME_EXPIRED",
        "This game has expired. Start a new duel.",
        410,
      );
    if (path === `/games/${GAME}`) {
      if (options.generationRecovery && keys.create.length < 2)
        return fail(
          "GENERATION_IN_PROGRESS",
          "This request is still being observed.",
          409,
        );
      return reply(game());
    }
    if (path === `/games/${GAME}/round`) return reply(current());
    if (path === `/games/${GAME}/results`)
      return complete
        ? reply(result())
        : fail("GAME_NOT_COMPLETE", "Finish your five rounds first.", 409);
    if (path === `/games/${GAME}/answer` && method === "POST") {
      keys.answer.push(request.headers()["idempotency-key"] || "");
      const body = request.postDataJSON() as S["AnswerRequest"];
      if (!answers[ordinal - 1]) {
        expect(body.round_id).toBe(id(900 + ordinal));
        expect(choices[ordinal - 1].map((c) => c.id)).toContain(body.choice_id);
        revision++;
        const winning = choices[ordinal - 1][winners[ordinal - 1]].id;
        const correct = body.choice_id === winning;
        answers.push({
          state: "revealed",
          game_id: GAME,
          round_id: body.round_id,
          ordinal,
          total: 5,
          revision,
          source: "qloo",
          seed,
          target_type: "movie",
          choices: choices[ordinal - 1],
          selected_choice_id: body.choice_id,
          winning_choice_id: winning,
          correct,
          cumulative_score:
            answers.filter((a) => a.correct).length + Number(correct),
          accepted_at: stamp,
          evidence: {
            source: "qloo",
            context: { seed, target_type: "movie", retrieved_at: stamp },
            supported_explanation: null,
          },
          curation_summary:
            ordinal === 5
              ? {
                  source: "qloo",
                  curator_mode: "genuine_agent",
                  target_domains: ["movie"],
                  candidate_count_received: 20,
                  rejection_counts: { near_tie: 1 },
                  bounded_correction_count: 0,
                  five_round_path_verified: true,
                  status: "succeeded",
                }
              : null,
        });
      }
      if (options.loseAnswer && keys.answer.length === 1)
        return route.abort("failed");
      await new Promise((resolve) => setTimeout(resolve, 150));
      return reply(current());
    }
    if (path === `/games/${GAME}/advance` && method === "POST") {
      keys.advance.push(request.headers()["idempotency-key"] || "");
      const body = request.postDataJSON() as S["AdvanceRequest"];
      const answeredOrdinal =
        Number(BigInt(`0x${body.answered_round_id.split("-")[4]}`)) - 900;
      if (answeredOrdinal === ordinal) {
        revision++;
        if (ordinal < 5) ordinal++;
        else complete = true;
      }
      if (options.loseAdvance && keys.advance.length === 1)
        return route.abort("failed");
      return reply(game());
    }
    if (path === "/discoveries")
      return reply({ discoveries: [] } satisfies S["DiscoveriesPublic"]);
    unexpected.push(`${method} ${path}`);
    return fail(
      "UNEXPECTED_TEST_REQUEST",
      "Unsupported synthetic test route",
      404,
    );
  });
  return {
    keys,
    calls,
    answers,
    serializedResponses,
    createBodies,
    releaseCreate,
    createReplySettled,
    check: () => {
      expect(unexpected).toEqual([]);
      expect(errors).toEqual([]);
    },
  };
}

async function tabTo(page: Page, target: Locator) {
  for (let i = 0; i < 24; i++) {
    if (await target.evaluate((el) => document.activeElement === el)) return;
    await page.keyboard.press("Tab");
  }
  await expect(target).toBeFocused();
}

async function capture(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBe(true);
  const loadedFonts = await page.evaluate(() =>
    Array.from(document.fonts)
      .filter((font) => font.status === "loaded")
      .map((font) => font.family),
  );
  expect(loadedFonts).toContain("displayFont");
  expect(loadedFonts).toContain("bodyFont");
  const widths = await page.evaluate(() => ({
    body: document.body.scrollWidth,
    root: document.documentElement.scrollWidth,
    viewport: innerWidth,
  }));
  expect(widths.body, `${name}: body overflow`).toBeLessThanOrEqual(
    widths.viewport + 1,
  );
  expect(widths.root, `${name}: root overflow`).toBeLessThanOrEqual(
    widths.viewport + 1,
  );
  const targets = await page
    .locator(
      ".button,.choice-card,.seed-input,.seed-toggle,.why-this-duel > summary,[data-testid='curation-disclosure'] > summary,.live-seed-popover [role='option']",
    )
    .evaluateAll((elements) =>
      elements
        .map((el) => ({
          text: el.textContent,
          width: el.getBoundingClientRect().width,
          height: el.getBoundingClientRect().height,
        }))
        .filter((e) => e.width && e.height),
    );
  for (const target of targets) {
    expect
      .soft(target.width, `${name} ${target.text}: width`)
      .toBeGreaterThanOrEqual(48);
    expect
      .soft(target.height, `${name} ${target.text}: height`)
      .toBeGreaterThanOrEqual(48);
  }
  await page.screenshot({
    path: info.outputPath(`${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
  const axe = await new AxeBuilder({ page }).analyze();
  await info.attach(`${name}-axe.json`, {
    body: JSON.stringify(axe, null, 2),
    contentType: "application/json",
  });
  expect.soft(axe.violations, `${name}: full axe scan`).toEqual([]);
}

async function selectSeed(page: Page) {
  const input = page.getByRole("combobox", { name: "Choose your favourite" });
  await expect(input).toBeEnabled();
  await tabTo(page, input);
  await page.keyboard.type("Synthetic");
  await expect(
    page.getByRole("option").filter({ hasText: seed.name }),
  ).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(input).toHaveAttribute("aria-activedescendant", /\S+/);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("start-duel")).toBeEnabled();
}

test("synthetic public API: keyboard five rounds, reload accepted reveal, server score, map-free responsive artwork", async ({
  page,
}, info) => {
  const harness = await publicHarness(page);
  await page.goto("/");
  await selectSeed(page);
  await capture(page, info, "01-confirmed-seed-synthetic-contract");
  await tabTo(page, page.getByTestId("start-duel"));
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/g/${GAME}`));
  for (let index = 0; index < 5; index++) {
    await expect(page.getByTestId("choice-card").first()).toBeEnabled();
    if (index > 0)
      await expect(page.getByTestId("live-question")).toBeFocused();
    await expect(
      page.getByRole("group", { name: `Round ${index + 1} of 5`, exact: true }),
    ).toBeVisible();
    await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
    await expect(page.getByTestId("curation-summary")).toHaveCount(0);
    for (const title of names.slice(index + 1).flat())
      await expect(page.getByText(title, { exact: true })).toHaveCount(0);
    if (index === 0)
      await capture(
        page,
        info,
        "02-unanswered-long-title-fallback-synthetic-contract",
      );
    const first = page.getByTestId("choice-card").first();
    await tabTo(page, first);
    await page.keyboard.press("Enter");
    await expect(first).toBeDisabled();
    await expect(page.getByTestId("reveal-panel")).toBeVisible();
    await expect(
      page.getByTestId("reveal-panel").getByRole("heading"),
    ).toBeFocused();
    expect(
      await page
        .getByTestId("reveal-panel")
        .evaluate((element) =>
          Boolean(
            element.closest('[aria-live="polite"],[aria-live="assertive"]'),
          ),
        ),
    ).toBe(false);
    const disclosure = page.getByTestId("why-this-duel");
    await expect(disclosure).toBeVisible();
    const toggle = disclosure.locator("summary");
    await tabTo(page, toggle);
    await page.keyboard.press("Enter");
    await expect(disclosure).toContainText(/Qloo ranked/);
    expect(await disclosure.ariaSnapshot()).not.toMatch(
      /affinity|chain.of.thought|psycholog/i,
    );
    if (index === 0) {
      await capture(page, info, "03-reveal-evidence-synthetic-contract");
      const answerCalls = harness.keys.answer.length;
      await page.reload();
      await expect(page.getByTestId("reveal-panel")).toBeVisible();
      expect(harness.keys.answer).toHaveLength(answerCalls);
      await expect(page.getByTestId("why-this-duel")).toBeVisible();
    }
    if (index < 4)
      await expect(page.getByTestId("curation-summary")).toHaveCount(0);
    await tabTo(page, page.getByTestId("next-action"));
    await page.keyboard.press("Enter");
  }
  await expect(page).toHaveURL(new RegExp(`/results/${GAME}`));
  await expect(page.getByTestId("result-ticket")).toContainText(/2\s*\/\s*5/);
  await capture(page, info, "04-server-result-synthetic-contract");
  const curation = page.getByTestId("curation-disclosure");
  await tabTo(page, curation.locator("summary"));
  await page.keyboard.press("Enter");
  await expect(curation).toHaveAttribute("open", "");
  await expect(curation).toContainText("20 candidates evaluated");
  await expect(curation).toContainText(
    "five-round path without repeated contestants",
  );
  expect(await curation.ariaSnapshot()).not.toMatch(
    /affinity|chain.of.thought|private_pool|context_hash/,
  );
  await capture(page, info, "04b-expanded-curation-synthetic-contract");
  await page.goBack();
  await expect(page.getByTestId("choice-card")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /view result/i })).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("result-ticket")).toContainText(/2\s*\/\s*5/);
  expect(harness.keys.answer).toHaveLength(5);
  expect(harness.keys.advance).toHaveLength(5);
  for (const body of harness.serializedResponses)
    expect(body).not.toMatch(
      /api[_-]?key|raw_payload|private_pool|query\.affinity|thought_signature|answer_key/i,
    );
  expect(
    harness.serializedResponses.find((body) =>
      body.includes('"state":"unanswered"'),
    ),
  ).not.toMatch(
    /winning_choice_id|selected_choice_id|curation_summary|affinity/,
  );
  harness.check();
});

test("open typed disambiguation has keyboard choices and accessible page semantics", async ({
  page,
}, info) => {
  const harness = await publicHarness(page);
  await page.goto("/");
  const input = page.getByRole("combobox", { name: "Choose your favourite" });
  await input.fill("Synthetic");
  await expect(
    page.getByRole("option").filter({ hasText: seed.name }),
  ).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(input).toHaveAttribute("aria-activedescendant", /\S+/);
  const optionBounds = await page.getByRole("option").evaluateAll((options) =>
    options.flatMap((option) => {
      const bounds = option.getBoundingClientRect();
      return Array.from(
        option.querySelectorAll(".seed-option-name,.seed-option-type"),
        (text) => ({
          label: text.textContent,
          left: text.getBoundingClientRect().left,
          right: text.getBoundingClientRect().right,
          parentLeft: bounds.left,
          parentRight: bounds.right,
          scroll: text.scrollWidth,
          client: text.clientWidth,
        }),
      );
    }),
  );
  for (const bounds of optionBounds) {
    expect(
      bounds.left,
      `${bounds.label}: contained left`,
    ).toBeGreaterThanOrEqual(bounds.parentLeft);
    expect(
      bounds.right,
      `${bounds.label}: contained right`,
    ).toBeLessThanOrEqual(bounds.parentRight);
    expect(
      bounds.scroll,
      `${bounds.label}: readable without clipping`,
    ).toBeLessThanOrEqual(bounds.client + 1);
  }
  await capture(page, info, "00-open-disambiguation-synthetic-contract");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("option")).toHaveCount(0);
  await expect(input).toBeFocused();
  harness.check();
});

test("stale typed search cannot replace newer disambiguation", async ({
  page,
}) => {
  const harness = await publicHarness(page);
  await page.goto("/");
  const input = page.getByRole("combobox", { name: "Choose your favourite" });
  await input.fill("slow old query");
  await expect
    .poll(
      () =>
        harness.calls.filter((call) => call.includes("entities/search")).length,
    )
    .toBeGreaterThan(0);
  await input.fill("Synthetic new query");
  await expect(page.getByRole("option").first()).toContainText(seed.name);
  await page.waitForTimeout(850);
  await expect(page.getByRole("option").first()).toContainText(seed.name);
  await expect(
    page.getByText("Stale result must never replace new search", {
      exact: true,
    }),
  ).toHaveCount(0);
  harness.check();
});

test("lost create response preserves submission identity", async ({ page }) => {
  const harness = await publicHarness(page, { loseCreate: true });
  await page.goto("/");
  await selectSeed(page);
  await page.getByTestId("start-duel").click();
  await expect(
    page.getByRole("button", { name: /retry|recover/i }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /retry|recover/i })
    .first()
    .click();
  await expect(page).toHaveURL(new RegExp(`/g/${GAME}`));
  expect(harness.keys.create.length).toBe(2);
  expect(harness.keys.create[0]).toBeTruthy();
  expect(new Set(harness.keys.create).size).toBe(1);
  harness.check();
});

test("lost answer and Next responses recover without a duplicate accepted round", async ({
  page,
}) => {
  const harness = await publicHarness(page, {
    loseAnswer: true,
    loseAdvance: true,
  });
  await page.goto(`/g/${GAME}`);
  await page.getByTestId("choice-card").first().click();
  await expect(
    page.getByRole("button", { name: /retry|recover/i }).first(),
  ).toBeVisible();
  await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
  await page
    .getByRole("button", { name: /retry|recover/i })
    .first()
    .click();
  await expect(page.getByTestId("reveal-panel")).toBeVisible();
  expect(harness.answers.length).toBe(1);
  if (harness.keys.answer.length > 1)
    expect(new Set(harness.keys.answer).size).toBe(1);
  await page.getByTestId("next-action").click();
  await expect(
    page.getByRole("button", { name: /retry|recover/i }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /retry|recover/i })
    .first()
    .click();
  await expect(
    page.getByRole("group", { name: "Round 2 of 5", exact: true }),
  ).toBeVisible();
  expect(harness.answers.length).toBe(1);
  if (harness.keys.advance.length > 1)
    expect(new Set(harness.keys.advance).size).toBe(1);
  harness.check();
});

test("typed expired and unavailable states preserve editorial layout", async ({
  page,
}, info) => {
  const harness = await publicHarness(page, {
    expired: true,
    unavailable: true,
  });
  await page.goto(`/g/${GAME}`);
  await expect(page.getByRole("heading", { name: /expired/i })).toBeVisible();
  await expect(page.getByTestId("choice-card")).toHaveCount(0);
  await capture(page, info, "05-expired-synthetic-contract");
  await page.goto("/");
  await page
    .getByRole("combobox", { name: "Choose your favourite" })
    .fill("Synthetic");
  await expect(
    page.getByText(/temporarily unavailable|search unavailable/i).first(),
  ).toBeVisible();
  await capture(page, info, "06-unavailable-synthetic-contract");
  harness.check();
});

test("actual owned SVG load failures preserve complete choice titles", async ({
  page,
}, info) => {
  const harness = await publicHarness(page);
  await page.route("**/art/*.svg", (route) => route.abort("failed"));
  await page.goto(`/g/${GAME}`);
  await expect(page.getByTestId("choice-card")).toHaveCount(2);
  await expect(page.locator(".choice-card .artwork-fallback")).toHaveCount(2);
  await expect(page.getByTestId("choice-card").first()).toContainText(
    names[0][0],
  );
  await expect(page.getByTestId("choice-card").nth(1)).toContainText(
    names[0][1],
  );
  await capture(page, info, "07-owned-svg-load-failure-synthetic-contract");
  harness.check();
});

test("pending generation observes an expiring claim and explicitly retries the same request", async ({
  page,
}, info) => {
  const harness = await publicHarness(page, { generationRecovery: true });
  await page.goto("/");
  await selectSeed(page);
  await page.getByTestId("start-duel").click();
  await expect(page).toHaveURL(new RegExp(`/g/${GAME}`));
  await expect(
    page.getByRole("heading", { name: "Your duel is preparing.", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("choice-card")).toHaveCount(0);
  await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
  await expect(page.getByTestId("curation-disclosure")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Retry same generation", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Generation was interrupted.",
      exact: true,
    }),
  ).toBeVisible();
  expect(harness.keys.create).toHaveLength(1);
  // Reload observes the lease recovery status. It must not schedule another POST.
  await page.reload();
  const retry = page.getByRole("button", {
    name: "Retry same generation",
    exact: true,
  });
  await expect(retry).toBeVisible();
  expect(harness.keys.create).toHaveLength(1);
  await capture(page, info, "08-expired-generation-claim-synthetic-contract");
  await tabTo(page, retry);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("choice-card").first()).toBeEnabled();
  await expect(
    page.getByRole("group", { name: "Round 1 of 5", exact: true }),
  ).toBeVisible();
  expect(harness.keys.create).toHaveLength(2);
  expect(harness.keys.create[0]).toBeTruthy();
  expect(new Set(harness.keys.create).size).toBe(1);
  expect(harness.createBodies[1]).toEqual(harness.createBodies[0]);
  expect(harness.answers).toHaveLength(0);
  await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
  await capture(page, info, "09-reclaimed-generation-ready-synthetic-contract");
  harness.check();
});

test("delayed accepted creation cannot redirect after navigation and retains recovery identity", async ({
  page,
}, info) => {
  const harness = await publicHarness(page, { holdCreate: true });
  await page.goto("/");
  await selectSeed(page);
  await page.getByTestId("start-duel").click();
  await expect.poll(() => harness.keys.create.length).toBe(1);
  // The synthetic server has accepted this identity, but its response is held.
  await page.getByRole("link", { name: /^How it works/ }).click();
  await expect(page).toHaveURL(/\/how-it-works$/);
  harness.releaseCreate();
  await harness.createReplySettled;
  await expect(page).toHaveURL(/\/how-it-works$/);
  await expect(page.getByTestId("live-game")).toHaveCount(0);
  await capture(
    page,
    info,
    "10-navigation-preserved-after-late-create-synthetic-contract",
  );
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  const recover = page.getByRole("button", {
    name: "Recover unfinished request",
    exact: true,
  });
  await expect(recover).toBeVisible();
  await recover.click();
  await expect(page).toHaveURL(new RegExp(`/g/${GAME}`));
  await expect(page.getByTestId("choice-card").first()).toBeEnabled();
  expect(harness.keys.create).toHaveLength(2);
  expect(harness.keys.create[0]).toBeTruthy();
  expect(new Set(harness.keys.create).size).toBe(1);
  expect(harness.createBodies[1]).toEqual(harness.createBodies[0]);
  expect(harness.answers).toHaveLength(0);
  harness.check();
});

test("temporary preparation failure has one safe retry with identical identity", async ({
  page,
}, info) => {
  const harness = await publicHarness(page, { generationFailure: "temporary" });
  await page.goto("/");
  await selectSeed(page);
  await page.getByTestId("start-duel").click();
  await expect(page.locator(".seed-launcher").getByRole("alert")).toContainText(
    "temporarily unavailable",
  );
  await expect(page.getByTestId("start-duel")).toHaveCount(0);
  const retry = page.getByRole("button", {
    name: "Retry same duel",
    exact: true,
  });
  await expect(retry).toHaveCount(1);
  await expect(retry).toBeFocused();
  await expect(
    page.getByText(/will not create a duplicate game/),
  ).toBeVisible();
  await capture(page, info, "11-retryable-preparation-failure");
  await tabTo(page, retry);
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("choice-card").first()).toBeEnabled();
  expect(harness.keys.create).toHaveLength(2);
  expect(new Set(harness.keys.create).size).toBe(1);
  expect(harness.createBodies[0]).toEqual(harness.createBodies[1]);
  harness.check();
});

test("insufficient coverage offers a different favourite without a retry loop", async ({
  page,
}, info) => {
  const harness = await publicHarness(page, { generationFailure: "coverage" });
  await page.goto("/");
  await selectSeed(page);
  await page.getByTestId("start-duel").click();
  await expect(page.locator(".seed-launcher").getByRole("alert")).toContainText(
    "not enough verified comparisons",
  );
  await expect(page.getByTestId("start-duel")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Retry same duel" }),
  ).toHaveCount(0);
  await capture(page, info, "12-insufficient-coverage-preparation");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Retry same duel" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Recover unfinished request" }),
  ).toHaveCount(0);
  expect(harness.keys.create).toHaveLength(1);
  await page
    .getByRole("button", { name: "Choose another favourite", exact: true })
    .click();
  await expect(
    page.getByRole("combobox", { name: "Choose your favourite" }),
  ).toHaveValue("");
  expect(harness.keys.create).toHaveLength(1);
  harness.check();
});
