import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("five-city discovery, evidence, planning, replanning and collections", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Create my outing", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("heading", {
      name: "Your kind of day. Thoughtfully planned.",
    }),
  ).toBeVisible();
  for (const [id, name] of [
    ["new-york", "New York"],
    ["paris", "Paris"],
    ["berlin", "Berlin"],
    ["chicago", "Chicago"],
    ["london", "London"],
  ]) {
    await page.getByLabel("Where are we exploring?").selectOption(id);
    await expect(
      page.getByRole("heading", { name: `A little inspiration in ${name}` }),
    ).toBeVisible();
    await expect(page.locator(".place-card")).toHaveCount(3);
  }
  await page.getByRole("button", { name: "View evidence" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page
      .getByRole("dialog")
      .getByText("Main entrance lifts provide step-free entry."),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Gentle pace", exact: true }).click();
  await page.getByLabel("Per-leg limit (m)", { exact: true }).fill("5000");
  await page.getByLabel("Total limit (m)", { exact: true }).fill("10000");
  await page
    .getByRole("button", { name: "Create my outing", exact: true })
    .click();
  await expect(
    page.getByText("Version 1 · Provisional", { exact: true }),
  ).toBeVisible({ timeout: 60000 });
  await expect(
    page.getByRole("heading", { name: "This outline needs your checks." }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByLabel("Per-leg limit (m)", { exact: true }).fill("200");
  await page
    .getByRole("button", { name: "Replan with these details", exact: true })
    .click();
  await expect(
    page.getByText("Version 2 · Provisional", { exact: true }),
  ).toBeVisible({ timeout: 60000 });
  await expect(
    page.getByRole("heading", { name: "What changed from version 1?" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Start a city collection", exact: true })
    .click();
  await expect(page.getByLabel("Collection name")).toBeVisible();
  await page.getByRole("button", { name: "Add city", exact: true }).click();
  await expect(page.locator(".trip-segment")).toHaveCount(1);
  await page
    .locator(".trip-add")
    .getByRole("combobox", { name: "City", exact: true })
    .selectOption("paris");
  await page.getByRole("button", { name: "Add city", exact: true }).click();
  await expect(
    page.getByText(
      "Inter-city travel: user-arranged and unverified. Timing and accessibility are not checked.",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Attach current london outline", exact: true })
    .click();
  await expect(
    page.getByText("Provisional plan v2 attached", { exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("application.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("full-page accessibility, keyboard access, zoom and reduced motion", async ({
  page,
}, testInfo) => {
  test.setTimeout(120000);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Create my outing", exact: true }),
  ).toBeEnabled();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "View evidence" }).first().click();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Toggle high contrast" }).click();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "200%";
  });
  await expect(
    page.getByRole("button", { name: "Create my outing", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 320, height: 800 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: testInfo.outputPath("accessibility.png"),
    fullPage: true,
  });
});
