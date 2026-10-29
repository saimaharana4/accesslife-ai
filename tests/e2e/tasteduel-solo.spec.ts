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
      mode: "solo",
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
          curation_summary: null,
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
      ".button,.live-discoveries button,.guest-session-controls summary,[data-testid='discovery-reveal'] > summary,.discovery-explore > summary",
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

test("keyboard five-round predictions stay distinct from explicit discovery saves", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin);
  await page.goto(`/g/${GAME}`);
  for (let n = 0; n < 5; n++) {
    const card = page.getByTestId("choice-card").first();
    await expect(card).toBeEnabled();
    await expect(
      page.getByRole("button", { name: /save discovery/i }),
    ).toHaveCount(0);
    await tabTo(page, card);
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("reveal-panel")).toBeVisible();
    await expect(page.getByTestId("reveal-panel")).toContainText(
      /prediction is game performance; only an explicit save adds a discovery/i,
    );
    expect(
      h.saved.size,
      "Predictions never automatically create preference signals",
    ).toBe(n ? 1 : 0);
    if (n === 0) {
      const disclosure = page.getByTestId("discovery-reveal");
      await expect(disclosure).not.toHaveAttribute("open", "");
      await inspect(page, info, "00-reveal-secondary-save-collapsed");
      await tabTo(page, disclosure.locator("summary"));
      await page.keyboard.press("Enter");
      const save = page
        .getByRole("button", { name: /save discovery/i })
        .first();
      await tabTo(page, save);
      await page.keyboard.press("Enter");
      await expect.poll(() => h.saved.size).toBe(1);
      await page.reload();
      await expect(page.getByTestId("reveal-panel")).toBeVisible();
      await page.getByTestId("discovery-reveal").locator("summary").click();
      await expect(
        page.getByRole("button", { name: /remove discovery|unsave/i }).first(),
      ).toBeVisible();
      await inspect(page, info, "01-reveal-explicit-saved-discovery");
    }
    await tabTo(page, page.getByTestId("next-action"));
    await page.keyboard.press("Enter");
  }
  await expect(page).toHaveURL(new RegExp(`/results/${GAME}`));
  await expect(page.getByTestId("result-ticket")).toContainText(/2\s*\/\s*5/);
  await expect(page.getByTestId("discoveries")).toContainText(
    pairs[0][0].entity.name,
  );
  await inspect(page, info, "02-result-saved-discovery");
  const unsave = page
    .getByRole("button", { name: /remove discovery|unsave/i })
    .first();
  await tabTo(page, unsave);
  await page.keyboard.press("Enter");
  await expect.poll(() => h.saved.size).toBe(0);
  await expect(page.getByTestId("discoveries")).toContainText(
    /no .*saved|nothing saved|save .*discovery/i,
  );
  expect(h.answers).toHaveLength(5);
  expect(h.keys.answer).toHaveLength(5);
  expect(h.keys.advance).toHaveLength(5);
  expect(h.keys.save).toHaveLength(1);
  h.check();
});

test("accepted lost answer and Next recover through reload, reconnect and another tab", async ({
  page,
  context,
  baseURL,
}) => {
  const h = await harness(context, new URL(baseURL!).origin, {
    loseAnswer: true,
    loseAdvance: true,
  });
  await page.goto(`/g/${GAME}`);
  await page.getByTestId("choice-card").first().click();
  await expect(
    page.getByRole("button", { name: "Check saved game", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("reveal-panel")).toBeVisible();
  expect(h.answers).toHaveLength(1);
  expect(h.keys.answer).toHaveLength(1);
  const other = await context.newPage();
  await other.goto(`/g/${GAME}`);
  await expect(other.getByTestId("reveal-panel")).toBeVisible();
  await page.getByTestId("next-action").click();
  await expect(
    page.getByRole("button", { name: "Check saved game", exact: true }),
  ).toBeVisible();
  h.setOffline(true);
  await page
    .getByRole("button", { name: "Check saved game", exact: true })
    .click();
  await expect(
    page
      .getByText(/connection|network|could not|not confirmed|interrupted/i)
      .first(),
  ).toBeVisible();
  h.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect(
    page.getByRole("group", { name: "Round 2 of 5", exact: true }),
  ).toBeVisible();
  await other.bringToFront();
  await other.evaluate(() => window.dispatchEvent(new Event("pageshow")));
  await expect(
    other.getByRole("group", { name: "Round 2 of 5", exact: true }),
  ).toBeVisible();
  expect(h.answers).toHaveLength(1);
  expect(h.keys.answer).toHaveLength(1);
  expect(h.keys.advance).toHaveLength(1);
  await page.goto("/how-it-works");
  await page.goBack();
  await expect(
    page.getByRole("group", { name: "Round 2 of 5", exact: true }),
  ).toBeVisible();
  expect(h.keys.answer).toHaveLength(1);
  await other.close();
  h.check();
});

test("session clear revokes private screens in another tab without rewriting history", async ({
  page,
  context,
  baseURL,
}) => {
  const h = await harness(context, new URL(baseURL!).origin);
  await page.goto(`/g/${GAME}`);
  await page.getByTestId("choice-card").first().click();
  await expect(page.getByTestId("reveal-panel")).toBeVisible();
  const other = await context.newPage();
  await other.goto(`/g/${GAME}`);
  await expect(other.getByTestId("reveal-panel")).toBeVisible();
  await page.locator(".guest-session-controls summary").click();
  await page
    .getByRole("button", { name: "Clear guest session", exact: true })
    .click();
  const confirm = page.getByRole("button", {
    name: "Clear this session",
    exact: true,
  });
  if (await confirm.count()) await confirm.click();
  await expect(page.getByTestId("choice-card")).toHaveCount(0);
  await other.bringToFront();
  await other.evaluate(() => window.dispatchEvent(new Event("pageshow")));
  await expect(other.getByTestId("choice-card")).toHaveCount(0);
  await expect(
    other.getByText(/session|choose.*seed|start.*fresh/i).first(),
  ).toBeVisible();
  expect(h.answers).toHaveLength(1);
  expect(h.keys.answer).toHaveLength(1);
  h.check();
});

test("expired historical game offers a fresh game and no mutable historic score", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin, { expired: true });
  await page.goto(`/g/${GAME}`);
  await expect(
    page.getByRole("heading", { name: /game has expired/i }),
  ).toBeVisible();
  await expect(page.getByTestId("choice-card")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: /seed|fresh|new/i }).first(),
  ).toBeVisible();
  await inspect(page, info, "03-expired-historic-game");
  expect(h.keys.answer).toHaveLength(0);
  expect(h.keys.advance).toHaveLength(0);
  h.check();
});

test("an accepted save with a lost response restores as an explicit save without changing score", async ({
  page,
  context,
  baseURL,
}) => {
  const h = await harness(context, new URL(baseURL!).origin, {
    loseSave: true,
  });
  await page.goto(`/g/${GAME}`);
  await page.getByTestId("choice-card").first().click();
  await expect(page.getByTestId("reveal-panel")).toBeVisible();
  await page.getByTestId("discovery-reveal").locator("summary").click();
  await page
    .getByRole("button", { name: /save discovery/i })
    .first()
    .click();
  await expect.poll(() => h.saved.size).toBe(1);
  await page.reload();
  await page.getByTestId("discovery-reveal").locator("summary").click();
  await expect(
    page.getByRole("button", { name: /remove discovery|unsave/i }).first(),
  ).toBeVisible();
  expect(h.keys.save).toHaveLength(1);
  expect(h.answers).toHaveLength(1);
  await expect(page.getByTestId("live-score")).toContainText(/0\s*\/\s*5/);
  h.check();
});

test("expired discoveries use an honest compact empty state rather than stale metadata", async ({
  page,
  context,
  baseURL,
}, info) => {
  const h = await harness(context, new URL(baseURL!).origin, {
    expiredSaved: true,
  });
  await page.goto(`/g/${GAME}`);
  for (let n = 0; n < 5; n++) {
    await page.getByTestId("choice-card").first().click();
    await expect(page.getByTestId("reveal-panel")).toBeVisible();
    await page.getByTestId("next-action").click();
  }
  await expect(page).toHaveURL(new RegExp(`/results/${GAME}`));
  await expect(page.getByTestId("discoveries")).toContainText(/expir/i);
  await expect(
    page.getByRole("button", { name: /remove discovery|unsave/i }),
  ).toHaveCount(0);
  await inspect(page, info, "04-result-expired-discovery-state");
  expect(h.saved.size).toBe(0);
  h.check();
});
