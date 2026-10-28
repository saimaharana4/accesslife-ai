import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { writeFile } from "node:fs/promises";

const slug = process.env.TASTEDUEL_CLOUD_REPLAY_SLUG;
test.skip(
  !slug,
  "A reviewed existing challenge is required; no generation permitted.",
);

test("provider-free candidate postchecks: image failure or actual expiry", async ({
  browser,
  baseURL,
}, info) => {
  if (!slug || !/^[A-Za-z0-9_-]{22,80}$/.test(slug) || !baseURL)
    throw new Error("Reviewed challenge required");
  const expired = process.env.TASTEDUEL_CLOUD_EXPECT_EXPIRED === "true";
  const token = process.env.TASTEDUEL_CANDIDATE_ID_TOKEN!;
  const origin = new URL(baseURL).origin;
  const context = await browser.newContext({
    viewport: { width: 320, height: 844 },
    reducedMotion: "reduce",
  });
  let blockedGeneration = 0;
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) return route.continue();
    if (
      url.pathname.endsWith("/entities/search") ||
      (url.pathname === "/api/v1/games" && route.request().method() === "POST")
    ) {
      blockedGeneration++;
      return route.abort("blockedbyclient");
    }
    if (!expired && url.pathname.startsWith("/art/"))
      return route.fulfill({
        status: 404,
        body: "Controlled owned-artwork failure",
      });
    return route.continue({
      headers: {
        ...route.request().headers(),
        "X-Serverless-Authorization": `Bearer ${token}`,
      },
    });
  });
  const page = await context.newPage();
  try {
    await page.goto(`${baseURL}/c/${slug}`);
    if (expired) {
      await expect(
        page.getByRole("heading", { name: /THIS FIVE HAS EXPIRED/ }),
      ).toBeVisible();
      await expect(page.getByTestId("choice-card")).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: /Play these five/ }),
      ).toHaveCount(0);
      const response = await page.evaluate(async (slug) => {
        const result = await fetch(`/api/v1/challenges/${slug}`, {
          cache: "no-store",
        });
        return { status: result.status, body: await result.json() };
      }, slug);
      expect(response.status).toBe(410);
      expect(response.body.error.code).toBe("CHALLENGE_EXPIRED");
      expect(
        /winning_choice_id|private_pool|"choices"/.test(
          JSON.stringify(response.body),
        ),
      ).toBe(false);
    } else {
      const play = page.getByRole("button", { name: /Play these five/ });
      await expect(play).toBeEnabled();
      await play.focus();
      await page.keyboard.press("Enter");
      await expect(page.getByTestId("choice-card").first()).toBeEnabled();
      await expect(page.locator(".artwork-fallback")).toHaveCount(2);
      const titles = await page
        .getByTestId("choice-card")
        .locator("strong")
        .allTextContents();
      expect(titles.length).toBe(2);
      expect(titles.every((title) => title.length > 0)).toBe(true);
      await expect(page.getByTestId("why-this-duel")).toHaveCount(0);
    }
    await page.waitForLoadState("networkidle");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations).toEqual([]);
    const name = expired
      ? "actual-expired-challenge"
      : "controlled-owned-image-failure";
    await writeFile(
      info.outputPath(name + ".json"),
      JSON.stringify({
        violations: [],
        axe_passes: axe.passes.length,
        new_provider_calls: 0,
        blockedGeneration,
        expired,
      }),
    );
    await page.screenshot({
      path: info.outputPath(name + ".png"),
      fullPage: true,
      animations: "disabled",
    });
    expect(blockedGeneration).toBe(0);
  } finally {
    await context.close();
  }
});
