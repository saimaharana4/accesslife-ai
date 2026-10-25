import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type Locator,
  type Page,
  type TestInfo,
} from "@playwright/test";

async function tabTo(page: Page, target: Locator) {
  for (let attempt = 0; attempt < 18; attempt++) {
    if (await target.evaluate((element) => element === document.activeElement))
      return;
    await page.keyboard.press("Tab");
  }
  await expect(
    target,
    "Control must be reachable by keyboard in a bounded tab sequence",
  ).toBeFocused();
}

async function fixtureMode(page: Page) {
  await expect(page.getByTestId("fixture-mode-banner")).toBeVisible();
  await expect(page.getByTestId("fixture-mode-banner")).toContainText(
    /fixture/i,
  );
  await page.evaluate(() => document.fonts.ready);
}

async function capture(page: Page, info: TestInfo, name: string, axe = true) {
  await fixtureMode(page);
  expect(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
    "The complete fixture flow is exercised with reduced motion enabled",
  ).toBe(true);
  const primaryTargets = await page
    .locator(
      ".button,.choice-card,.seed-input,.seed-toggle,.example-seed,.why-this-duel > summary",
    )
    .evaluateAll((elements) =>
      elements
        .map((element) => ({
          label:
            element.getAttribute("aria-label") ||
            element.textContent?.trim() ||
            element.tagName,
          width: element.getBoundingClientRect().width,
          height: element.getBoundingClientRect().height,
        }))
        .filter((target) => target.width > 0 && target.height > 0),
    );
  for (const target of primaryTargets) {
    expect
      .soft(target.width, `${name}: ${target.label} target width`)
      .toBeGreaterThanOrEqual(48);
    expect
      .soft(target.height, `${name}: ${target.label} target height`)
      .toBeGreaterThanOrEqual(48);
  }
  const widths = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    body: document.body.scrollWidth,
    root: document.documentElement.scrollWidth,
  }));
  expect(widths.body, `${name}: body overflow`).toBeLessThanOrEqual(
    widths.viewport + 1,
  );
  expect(widths.root, `${name}: root overflow`).toBeLessThanOrEqual(
    widths.viewport + 1,
  );
  await page.evaluate(() =>
    window.scrollTo({ top: 0, left: 0, behavior: "instant" }),
  );
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await page.screenshot({
    path: info.outputPath(`${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
  if (axe) {
    const result = await new AxeBuilder({ page }).analyze();
    await info.attach(`${name}-axe.json`, {
      body: JSON.stringify(result, null, 2),
      contentType: "application/json",
    });
    expect
      .soft(result.violations, `${name}: full axe scan, without exclusions`)
      .toEqual([]);
  }
}

test.beforeEach(async ({ page }) => {
  const origin = new URL(test.info().project.use.baseURL as string).origin;
  const forbidden: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      ["http:", "https:"].includes(url.protocol) &&
      (url.origin !== origin ||
        url.pathname === "/api" ||
        url.pathname.startsWith("/api/"))
    ) {
      forbidden.push(`${url.origin}${url.pathname}`);
      await route.abort("blockedbyclient");
    } else await route.continue();
  });
  (
    page as Page & { fixtureForbidden?: string[]; fixtureErrors?: string[] }
  ).fixtureForbidden = forbidden;
  (page as Page & { fixtureErrors?: string[] }).fixtureErrors = errors;
  await page.addInitScript(() => {
    const state = window as Window & { fixtureOutcomeFocusCount?: number };
    state.fixtureOutcomeFocusCount = 0;
    document.addEventListener("focusin", (event) => {
      const target = event.target as Element | null;
      if (
        target?.matches("h1,h2,h3") &&
        target.closest('[data-testid="reveal-panel"]')
      ) {
        state.fixtureOutcomeFocusCount =
          (state.fixtureOutcomeFocusCount || 0) + 1;
      }
    });
  });
});

test.afterEach(async ({ page }) => {
  const checked = page as Page & {
    fixtureForbidden?: string[];
    fixtureErrors?: string[];
  };
  expect(
    checked.fixtureForbidden,
    "Synthetic fixture mode must never call a backend/external provider",
  ).toEqual([]);
  expect(checked.fixtureErrors, "No uncaught browser error").toEqual([]);
});

test("five complete rounds by keyboard, computed score, explicit advance and challenge invitation", async ({
  page,
}, info) => {
  await page.goto("/");
  await fixtureMode(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: /skip/i })).toBeFocused();
  await page.keyboard.press("Enter");
  const input = page.getByRole("combobox", { name: "Choose your favourite" });
  await tabTo(page, input);
  await page.keyboard.type("Velvet");
  await expect(page.getByRole("option").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("option")).toHaveCount(0);
  await page.keyboard.press("ArrowDown");
  await expect(input).toHaveAttribute("aria-expanded", "true");
  await expect(input).toHaveAttribute("aria-activedescendant", /\S+/);
  await page.keyboard.press("Enter");
  await expect(
    page.getByText("Confirm your seed", { exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("start-duel")).toBeEnabled();
  await capture(page, info, "01-confirmed-seed");
  await tabTo(page, page.getByTestId("start-duel"));
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/g\/demo/);
  const game = page.getByTestId("fixture-game");
  await expect(game).toHaveAttribute("data-phase", "unanswered");

  // Independent, declared synthetic contract: first choice wins rounds 1/3/5.
  const expectedScores = [1, 1, 2, 2, 3];
  const firstTitles = [
    "Afterlight Assembly",
    "The Slow Burn Society",
    "Lunar Paper Parade",
    "The Quiet Orbit",
    "Atlas of Small Storms",
  ];
  const otherTitles = [
    "The Blue Hour Archive",
    "Neon Daydreams Club",
    "Sunday Static Hotel",
    "Electric Velvet Cinema",
    "Glass Midnight Radio",
  ];
  for (let round = 0; round < 5; round++) {
    await expect(
      page.getByRole("group", { name: `Round ${round + 1} of 5`, exact: true }),
    ).toBeVisible();
    const first = page.getByTestId("choice-card").first();
    await expect(first).toContainText(firstTitles[round]);
    await expect(first).toBeEnabled();
    await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
    await expect(page.getByTestId("curation-summary")).toHaveCount(0);
    for (const futureTitle of [
      ...firstTitles.slice(round + 1),
      ...otherTitles.slice(round + 1),
    ]) {
      await expect(page.getByText(futureTitle, { exact: true })).toHaveCount(0);
    }
    if (round === 0) await capture(page, info, "02-first-unanswered");
    if (round > 0)
      await expect(page.getByTestId("fixture-question")).toBeFocused();
    await tabTo(page, first);
    await page.keyboard.press("Enter");
    await expect(game).toHaveAttribute("data-phase", "submitting");
    await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
    await expect(page.getByTestId("choice-card").first()).toBeDisabled();
    await expect(page.getByTestId("choice-card").nth(1)).toBeDisabled();
    await expect(game).toHaveAttribute("data-phase", "revealed");
    const reveal = page.getByTestId("reveal-panel");
    await expect(reveal).toBeVisible();
    await expect(reveal.getByRole("heading")).toBeFocused();
    const disclosure = page.getByTestId("why-this-duel");
    await expect(disclosure).not.toHaveAttribute("open", "");
    const disclosureToggle = page.getByTestId("why-this-duel-toggle");
    await tabTo(page, disclosureToggle);
    await page.keyboard.press("Enter");
    await expect(disclosure).toHaveAttribute("open", "");
    await expect(
      disclosure.getByText(/SYNTHETIC FIXTURE EVIDENCE/),
    ).toBeVisible();
    await expect(
      disclosure.getByText(/No Qloo or model was called/),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Synthetic fixture curation" }),
    ).toBeVisible();
    const accessibleEvidence = await disclosure.ariaSnapshot();
    expect(accessibleEvidence).toContain(
      "synthetic answer key, not a Qloo ranking",
    );
    expect(accessibleEvidence).toContain("No Qloo or model was called");
    expect(accessibleEvidence).not.toMatch(/affinity|chain.of.thought/i);
    for (const futureTitle of [
      ...firstTitles.slice(round + 1),
      ...otherTitles.slice(round + 1),
    ])
      expect(accessibleEvidence).not.toContain(futureTitle);
    if (round === 0) {
      const save = disclosure.getByRole("button", {
        name: "Save Afterlight Assembly",
        exact: true,
      });
      await tabTo(page, save);
      await page.keyboard.press("Enter");
      await expect(
        disclosure.getByRole("button", {
          name: "Unsave Afterlight Assembly",
          exact: true,
        }),
      ).toHaveAttribute("aria-pressed", "true");
    }
    expect(
      await reveal.evaluate((element) =>
        Boolean(
          element.closest('[aria-live="polite"],[aria-live="assertive"]'),
        ),
      ),
    ).toBe(false);
    await expect(page.getByTestId("fixture-score")).toContainText(
      new RegExp(`${expectedScores[round]}\\s*/\\s*5`),
    );
    await expect(
      page.getByRole("group", { name: `Round ${round + 1} of 5`, exact: true }),
    ).toBeVisible();
    if (round === 0 || round === 4)
      await capture(page, info, `03-reveal-round-${round + 1}`);
    await tabTo(page, page.getByTestId("next-action"));
    await page.keyboard.press("Enter");
    if (round < 4) {
      await expect(game).toHaveAttribute("data-phase", "unanswered");
      await expect(reveal).toHaveCount(0);
      await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
    }
  }
  await expect(page).toHaveURL(/\/results\/demo/);
  await expect(page.getByTestId("result-ticket")).toContainText(/3\s*\/\s*5/);
  await expect(
    page.getByRole("region", { name: "Your discoveries" }),
  ).toContainText("Afterlight Assembly");
  expect(
    await page.evaluate(
      () =>
        (window as Window & { fixtureOutcomeFocusCount?: number })
          .fixtureOutcomeFocusCount,
    ),
  ).toBe(5);
  await capture(page, info, "04-computed-result");
  await page.goBack();
  await expect(page).toHaveURL(/\/g\/demo/);
  await expect(
    page.getByRole("link", { name: "View result", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("choice-card")).toHaveCount(0);
  await page.goForward();
  await expect(page).toHaveURL(/\/results\/demo/);
  await expect(page.getByTestId("result-ticket")).toContainText(/3\s*\/\s*5/);
  const challenge = page.getByRole("link", { name: /challenge/i }).first();
  await tabTo(page, challenge);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/c\/demo/);
  await expect(page.getByTestId("challenge-invitation")).toContainText(/3.*5/);
  await capture(page, info, "05-local-challenge-invitation");
  await expect(page.locator("audio[autoplay],video[autoplay]")).toHaveCount(0);
});

test("batched choices and advance, accepted-response retry, and honest refresh reset", async ({
  page,
}, info) => {
  await page.goto("/g/demo?story=retry");
  await fixtureMode(page);
  const game = page.getByTestId("fixture-game");
  await expect(game).toHaveAttribute("data-phase", "unanswered");
  await page.getByTestId("choice-card").evaluateAll((cards) => {
    (cards[0] as HTMLButtonElement).click();
    (cards[1] as HTMLButtonElement).click();
  });
  await expect(game).toHaveAttribute("data-phase", "retry");
  await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Your answer is not lost" }),
  ).toBeVisible();
  await expect(
    page.getByText(/accepted your answer.*lost response/i),
  ).toBeVisible();
  await capture(page, info, "06-accepted-response-lost");
  await page.getByRole("button", { name: "Retry answer", exact: true }).click();
  await expect(game).toHaveAttribute("data-phase", "revealed");
  await expect(page.getByTestId("why-this-duel")).toHaveCount(1);
  await expect(page.getByTestId("fixture-score")).toContainText(/1\s*\/\s*5/);
  await expect(
    page.getByTestId("reveal-panel").getByRole("heading"),
  ).toContainText("Afterlight Assembly");
  expect(
    await page.evaluate(
      () =>
        (window as Window & { fixtureOutcomeFocusCount?: number })
          .fixtureOutcomeFocusCount,
    ),
  ).toBe(1);
  await capture(page, info, "07-same-accepted-answer-recovered");
  await page.getByTestId("next-action").evaluate((button) => {
    (button as HTMLButtonElement).click();
    (button as HTMLButtonElement).click();
  });
  await expect(game).toHaveAttribute("data-phase", "unanswered");
  await expect(
    page.getByRole("group", { name: "Round 2 of 5", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("choice-card").first()).toContainText(
    "The Slow Burn Society",
  );
  await expect(page.getByTestId("fixture-score")).toContainText(/1\s*\/\s*5/);
  await page.reload();
  await fixtureMode(page);
  await expect(game).toHaveAttribute("data-phase", "unanswered");
  await expect(
    page.getByRole("group", { name: "Round 1 of 5", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("fixture-score")).toContainText(/0\s*\/\s*5/);
  await expect(page.getByTestId("reveal-panel")).toHaveCount(0);
  await expect(page.getByText(/refresh resets progress/i)).toBeVisible();
});

test("an actually cancelled preparation stays interrupted until explicit same-action resume", async ({
  page,
}, info) => {
  await page.goto("/g/demo");
  await fixtureMode(page);
  const game = page.getByTestId("fixture-game");
  await expect(game).toHaveAttribute("data-phase", "confirmation");
  await page.getByTestId("start-duel").click();
  await expect(game).toHaveAttribute("data-phase", "preparing");
  await page
    .getByRole("button", { name: "Cancel fixture preparation" })
    .click();
  await expect(game).toHaveAttribute("data-phase", "interrupted");
  await expect(
    page.getByRole("button", { name: "Resume fixture", exact: true }),
  ).toBeVisible();
  await capture(page, info, "08-actual-cancelled-preparation");
  // Capture/axe has allowed the abandoned response deadline to elapse.
  await expect(game).toHaveAttribute("data-phase", "interrupted");
  await page
    .getByRole("button", { name: "Resume fixture", exact: true })
    .click();
  await expect(game).toHaveAttribute("data-phase", "unanswered");
  await expect(
    page.getByRole("group", { name: "Round 1 of 5", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("fixture-score")).toContainText(/0\s*\/\s*5/);
});

test("honest empty, partial, expired, interrupted, preparing and selected stories", async ({
  page,
}, info) => {
  const stories = [
    ["empty", "No fixture rounds available"],
    ["partial", "Three rounds are not five"],
    ["expired", "This fixture has expired"],
    ["interrupted", "The fixture was interrupted"],
  ];
  for (const [story, title] of stories) {
    await page.goto(`/g/demo?story=${story}`);
    await fixtureMode(page);
    await expect(page.getByTestId("fixture-game")).toHaveAttribute(
      "data-phase",
      story,
    );
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await expect(page.getByTestId("choice-card")).toHaveCount(0);
    await capture(page, info, `09-story-${story}`);
  }
  await page
    .getByRole("button", { name: "Start a full fixture", exact: true })
    .click();
  await expect(page.getByTestId("fixture-game")).toHaveAttribute(
    "data-phase",
    "unanswered",
  );
  await expect(
    page.getByRole("group", { name: "Round 1 of 5", exact: true }),
  ).toBeVisible();
  await page.goto("/prototype/preparing");
  await expect(
    page.getByRole("heading", { name: "Preparing a connection", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/static pending-state.*no task is running/i),
  ).toBeVisible();
  await capture(page, info, "10-static-preparing");
  await page.goto("/prototype/selected");
  const disabled = page.locator("button.choice-card");
  await expect(disabled).toHaveCount(2);
  await expect(disabled.first()).toBeDisabled();
  await expect(disabled.nth(1)).toBeDisabled();
  await expect(page.getByText(/no answer has been accepted/i)).toBeVisible();
  await capture(page, info, "11-static-selected-disabled");
});

test("readable long titles and an actual missing-image failure preserve usable choices", async ({
  page,
}, info) => {
  await page.goto("/g/demo?story=long-title");
  await fixtureMode(page);
  const game = page.getByTestId("fixture-game");
  await expect(game).toHaveAttribute("data-phase", "unanswered");
  await expect(page.getByTestId("choice-card").first()).toContainText(
    "Unexpectedly Long Journey",
  );
  const title = page
    .getByTestId("choice-card")
    .first()
    .locator(".choice-title");
  expect(
    await title.evaluate(
      (element) =>
        element.scrollHeight <= element.clientHeight + 1 &&
        element.scrollWidth <= element.clientWidth + 1,
    ),
  ).toBe(true);
  await capture(page, info, "12-long-title");
  await page.getByTestId("choice-card").first().click();
  await expect(game).toHaveAttribute("data-phase", "revealed");
  await page.getByTestId("why-this-duel-toggle").click();
  await expect(page.getByTestId("duel-evidence")).toContainText(
    "Unexpectedly Long Journey",
  );
  await capture(page, info, "12b-long-title-evidence");
  await page.route("**/art/afterlight.svg", (route) => route.abort("failed"));
  await page.goto("/g/demo?story=missing-image");
  await expect(game).toHaveAttribute("data-phase", "unanswered");
  await expect(
    page
      .getByTestId("choice-card")
      .first()
      .getByText("Artwork unavailable.", { exact: true }),
  ).toBeVisible();
  await capture(page, info, "13-owned-artwork-fallback");
  // The flag checks the explicit story; a fresh normal game checks a real fetch failure.
  await page.goto("/g/demo?story=retry");
  await expect(game).toHaveAttribute("data-phase", "unanswered");
  await expect(
    page
      .getByTestId("choice-card")
      .first()
      .getByText("Artwork unavailable.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("choice-card").first()).toBeEnabled();
  await page.getByTestId("choice-card").first().click();
  await expect(game).toHaveAttribute("data-phase", "retry");
  await page.getByRole("button", { name: "Retry answer", exact: true }).click();
  await expect(game).toHaveAttribute("data-phase", "revealed");
  await expect(page.getByTestId("fixture-score")).toContainText(/1\s*\/\s*5/);
  await page.getByTestId("why-this-duel-toggle").click();
  await capture(page, info, "14-missing-artwork-evidence");
});

test("how it works separates ranking prediction, personal preference and explicit saves", async ({
  page,
}, info) => {
  await page.goto("/how-it-works");
  await fixtureMode(page);
  const main = page.getByRole("main");
  await expect(main).toContainText("aggregate, request-specific Qloo rankings");
  await expect(main).toContainText(
    "Correct and incorrect guesses measure game performance",
  );
  await expect(main).toContainText(
    "They do not tell us which choice you personally like or dislike",
  );
  await expect(main).toContainText(
    "Saving a discovery is your explicit choice",
  );
  await expect(main).toContainText("It makes no Qloo calls");
  await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
  await expect(page.getByTestId("curation-summary")).toHaveCount(0);
  await capture(page, info, "15-ranking-not-personal-preference");
});

test("motion preference changes no accepted evidence or game meaning", async ({
  page,
}) => {
  const evidence: string[] = [];
  for (const reducedMotion of ["no-preference", "reduce"] as const) {
    await page.emulateMedia({ reducedMotion });
    await page.goto("/g/demo");
    await fixtureMode(page);
    await page.getByTestId("start-duel").click();
    await expect(page.getByTestId("fixture-game")).toHaveAttribute(
      "data-phase",
      "unanswered",
    );
    await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
    await page.getByTestId("choice-card").first().click();
    await expect(page.getByTestId("fixture-game")).toHaveAttribute(
      "data-phase",
      "revealed",
    );
    await page.getByTestId("why-this-duel-toggle").click();
    evidence.push(await page.getByTestId("why-this-duel").ariaSnapshot());
    await expect(page.getByTestId("fixture-score")).toContainText(/1\s*\/\s*5/);
    await expect(page.getByTestId("next-action")).toBeEnabled();
  }
  expect(evidence[0]).toEqual(evidence[1]);
});
