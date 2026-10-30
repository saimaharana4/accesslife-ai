import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type TestInfo } from "@playwright/test";

async function ready(page: Page) {
  await expect(page.getByTestId("prototype-frame")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await expect(page.getByText(/prototype/i).first()).toBeVisible();
}

async function noOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    body: document.body.scrollWidth,
    root: document.documentElement.scrollWidth,
  }));
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport + 1);
  expect(dimensions.root).toBeLessThanOrEqual(dimensions.viewport + 1);
}

async function captureAndAudit(page: Page, info: TestInfo, name: string) {
  await ready(page);
  await noOverflow(page);
  // A click can scroll mobile pages. Chromium's full-page capture can then
  // paint off-viewport fixed content (such as a hidden skip link) above the
  // viewport. Normalize scroll without changing focus or hiding any element.
  await page.evaluate(() =>
    window.scrollTo({ top: 0, left: 0, behavior: "instant" }),
  );
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }),
  );
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  const targets = await page
    .locator("a, button, input, [role='button']")
    .evaluateAll((elements) =>
      elements
        .map((element) => {
          const bounds = element.getBoundingClientRect();
          return {
            text:
              element.getAttribute("aria-label") ||
              element.textContent?.trim().slice(0, 100) ||
              element.getAttribute("placeholder"),
            width: Math.round(bounds.width * 10) / 10,
            height: Math.round(bounds.height * 10) / 10,
            primary: element.matches(
              ".button, .seed-input, .seed-toggle, .choice-card, .example-seed, .wordmark, .back-link, .inline-link, .header-nav a, .site-footer a",
            ),
          };
        })
        .filter((entry) => entry.width > 0 && entry.height > 0),
    );
  await info.attach(`${name}-targets.json`, {
    body: JSON.stringify(targets, null, 2),
    contentType: "application/json",
  });
  for (const target of targets.filter((entry) => entry.primary)) {
    expect
      .soft(target.width, `${name}: ${target.text} primary target width`)
      .toBeGreaterThanOrEqual(48);
    expect
      .soft(target.height, `${name}: ${target.text} primary target height`)
      .toBeGreaterThanOrEqual(48);
  }
  await page.screenshot({
    path: info.outputPath(`${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
  const audit = await new AxeBuilder({ page }).analyze();
  await info.attach(`${name}-axe.json`, {
    body: JSON.stringify(audit, null, 2),
    contentType: "application/json",
  });
  // Keep auditing/capturing the remaining states while preserving a failing test.
  expect
    .soft(audit.violations, `${name}: full-page axe violations`)
    .toEqual([]);
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
      (url.origin !== origin || url.pathname.startsWith("/api/"))
    ) {
      // A visual fixture must never invoke a backend, Qloo, cloud, or remote art.
      forbidden.push(`${url.origin}${url.pathname}`);
      await route.abort("blockedbyclient");
      return;
    }
    await route.continue();
  });
  (
    page as Page & { prototypeForbidden?: string[]; prototypeErrors?: string[] }
  ).prototypeForbidden = forbidden;
  (page as Page & { prototypeErrors?: string[] }).prototypeErrors = errors;
});

test.afterEach(async ({ page }) => {
  const checked = page as Page & {
    prototypeForbidden?: string[];
    prototypeErrors?: string[];
  };
  expect(
    checked.prototypeForbidden,
    "Prototype made an external/backend request",
  ).toEqual([]);
  expect(checked.prototypeErrors, "Uncaught browser errors").toEqual([]);
});

test("five designed states, complete axe scans and inspected screenshot artifacts", async ({
  page,
}, info) => {
  await page.goto("/");
  await captureAndAudit(page, info, "01-landing");
  await page.goto("/g/demo");
  await expect(page.getByTestId("choice-card")).toHaveCount(2);
  await expect(page.getByTestId("reveal-panel")).toHaveCount(0);
  await captureAndAudit(page, info, "02-unanswered");
  await page.getByTestId("choice-card").first().click();
  await expect(page.getByTestId("reveal-panel")).toBeVisible();
  await expect(page.getByTestId("next-action")).toBeVisible();
  await captureAndAudit(page, info, "03-reveal");
  await page.goto("/results/demo");
  await expect(page.getByTestId("result-ticket")).toBeVisible();
  await captureAndAudit(page, info, "04-result");
  await page.goto("/c/demo");
  await expect(page.getByTestId("challenge-invitation")).toBeVisible();
  await captureAndAudit(page, info, "05-challenge");
});

test("long titles, missing artwork and useful waiting/error states", async ({
  page,
}, info) => {
  await page.goto("/g/demo?variant=long-title-missing-image");
  await expect(page.getByTestId("choice-card")).toHaveCount(2);
  for (const choice of await page.getByTestId("choice-card").all()) {
    await expect(choice).toHaveAccessibleName(/\S/);
    const bounds = await choice.boundingBox();
    expect(bounds?.width).toBeGreaterThanOrEqual(48);
    expect(bounds?.height).toBeGreaterThanOrEqual(48);
  }
  await captureAndAudit(page, info, "06-long-title-missing-artwork");
  await page.goto("/prototype/loading");
  await captureAndAudit(page, info, "07-loading");
  await page.goto("/prototype/error");
  await captureAndAudit(page, info, "08-provider-error");
  await expect(
    page.getByRole("link", { name: /try|back|favourite|home/i }).first(),
  ).toBeVisible();
});

test("keyboard selection and reveal, local fonts, reduced motion and enlarged text", async ({
  page,
}, info) => {
  await page.goto("/");
  await ready(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: /skip/i })).toBeFocused();
  await page.keyboard.press("Enter");
  const search = page.getByRole("combobox", { name: "Choose your favourite" });
  await search.focus();
  await search.fill("Velvet");
  await expect(page.getByRole("option").first()).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("start-duel")).toBeEnabled();
  await page.getByTestId("start-duel").focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/g\/demo/);
  await ready(page);
  const fonts = await page.evaluate(() => ({
    loaded: Array.from(document.fonts)
      .filter((font) => font.status === "loaded")
      .map((font) => font.family),
    body: getComputedStyle(document.body).fontFamily,
    heading: getComputedStyle(document.querySelector("h1")!).fontFamily,
    reduced: matchMedia("(prefers-reduced-motion: reduce)").matches,
  }));
  expect(
    new Set(fonts.loaded).size,
    "Both licensed local type families should load",
  ).toBeGreaterThanOrEqual(2);
  expect(fonts.heading).not.toBe(fonts.body);
  expect(fonts.reduced).toBe(true);
  await info.attach("loaded-fonts.json", {
    body: JSON.stringify(fonts, null, 2),
    contentType: "application/json",
  });
  await page.getByTestId("choice-card").first().focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("reveal-panel")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "AFTERLIGHT TAKES THIS ONE." }),
  ).toBeFocused();
  await page.getByTestId("next-action").focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/results\/demo/);
  await page.goto("/g/demo?variant=long-title-missing-image");
  // Text scaling/reflow emulation, explicitly distinct from actual browser zoom.
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "200%";
  });
  await noOverflow(page);
  await page.screenshot({
    path: info.outputPath("09-enlarged-text.png"),
    fullPage: true,
    animations: "disabled",
  });
});

test("a real local artwork request failure preserves identity and keyboard play", async ({
  page,
}, info) => {
  await page.route("**/art/afterlight.svg", (route) => route.abort("failed"));
  await page.goto("/g/demo");
  const first = page.getByTestId("choice-card").first();
  await expect(
    first.getByText("Artwork unavailable.", { exact: true }),
  ).toBeVisible();
  await expect(first).toContainText("Afterlight Assembly");
  await expect(first).toBeEnabled();
  await captureAndAudit(page, info, "10-actual-artwork-network-failure");
  await first.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("reveal-panel")).toBeVisible();
  await expect(page.getByTestId("next-action")).toBeVisible();
});
