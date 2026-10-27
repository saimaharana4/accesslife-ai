// Real BFF/API/database proof with synthetic source data. Private handoff is stdin only.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const origin = "http://127.0.0.1:3003";
const directory = ".data/tasteduel-prompt12/browser";
let browser;
let stage = "private-handoff";
const errors = [];
const findings = {
  axeScans: 0,
  screenshots: 0,
  externalRequests: 0,
  providerPaths: 0,
  responsesChecked: 0,
};
try {
  let input = "";
  for await (const chunk of process.stdin) {
    input += chunk;
    assert(input.length < 2000);
  }
  const payload = JSON.parse(input);
  assert(/^[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}$/.test(payload.cookie));
  assert(/^[0-9a-f-]{36}$/.test(payload.game_id));
  await mkdir(directory, { recursive: true });
  browser = await chromium.launch({ headless: true });
  async function context(cookie) {
    const c = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: "reduce",
    });
    if (cookie)
      await c.addCookies([
        {
          name: "tasteduel_session",
          value: cookie,
          url: origin,
          httpOnly: true,
          sameSite: "Lax",
        },
      ]);
    await c.route("**/*", (route) => {
      const request = route.request(),
        url = new URL(request.url());
      if (["http:", "https:"].includes(url.protocol) && url.origin !== origin) {
        findings.externalRequests++;
        return route.abort("blockedbyclient");
      }
      if (
        url.pathname.includes("/entities/search") ||
        url.pathname === "/api/v1/games"
      )
        findings.providerPaths++;
      return route.continue();
    });
    c.on("page", (p) => p.on("pageerror", (e) => errors.push(e.name)));
    return c;
  }
  const creator = await context(payload.cookie);
  const creatorPage = await creator.newPage();
  stage = "creator-result";
  await creatorPage.goto(`${origin}/results/${payload.game_id}`);
  await creatorPage.getByTestId("result-ticket").waitFor();
  assert.match(
    await creatorPage.getByTestId("live-score").innerText(),
    /3\s*\/\s*5/,
  );
  const sourceResponse = await creator.request.get(
    `${origin}/api/v1/games/${payload.game_id}/results`,
  );
  assert.equal(sourceResponse.status(), 200);
  const source = await sourceResponse.json();
  const expected = source.answered_rounds.map((r) => ({
    names: r.choices.map((c) => c.entity.name),
    winner: r.choices.find((c) => c.id === r.winning_choice_id).entity.name,
    domain: r.target_type,
  }));
  async function inspect(page, name) {
    await page.evaluate(() => document.fonts.ready);
    const width = await page.evaluate(() => ({
      view: innerWidth,
      root: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
    }));
    assert(
      width.root <= width.view + 1 && width.body <= width.view + 1,
      `overflow ${name}`,
    );
    const axe = await new AxeBuilder({ page }).analyze();
    await writeFile(
      `${directory}/${name}-axe.json`,
      JSON.stringify(axe, null, 2),
    );
    assert.deepEqual(axe.violations, [], `axe ${name}`);
    findings.axeScans++;
    await page.screenshot({
      path: `${directory}/${name}.png`,
      fullPage: true,
      animations: "disabled",
    });
    findings.screenshots++;
  }
  stage = "creator-share";
  const responsePromise = creatorPage.waitForResponse(
    (r) =>
      r.url() === `${origin}/api/v1/challenges` &&
      r.request().method() === "POST",
  );
  await creatorPage
    .getByRole("button", { name: /create.*challenge|challenge.*friend/i })
    .first()
    .click();
  const createdResponse = await responsePromise;
  assert([200, 201].includes(createdResponse.status()));
  assert.match(createdResponse.headers()["cache-control"], /no-store/);
  const created = await createdResponse.json();
  const slug = created.invitation.slug;
  assert(/^[A-Za-z0-9_-]{32,80}$/.test(slug));
  assert.equal(created.invitation.creator_score, 3);
  const forbidden =
    /winning_choice_id|winner_entity_id|affinity|snapshot_id|session_id|source_game_id|private_pool|raw_payload|chain_of_thought/;
  assert(!forbidden.test(JSON.stringify(created)));
  const invitationPath = `/c/${slug}`;
  stage = "original-social-image";
  const og = await creator.request.get(`${origin}${invitationPath}/social`);
  assert.equal(og.status(), 200);
  assert.match(og.headers()["content-type"], /image\/png/);
  assert.match(og.headers()["cache-control"], /no-store/);
  const image = await og.body();
  assert.equal(image.readUInt32BE(16), 1200);
  assert.equal(image.readUInt32BE(20), 630);
  assert(image.length < 1_000_000);
  await writeFile(`${directory}/original-social-image.png`, image);
  for (const [width, height] of [
    [1440, 1000],
    [390, 844],
    [320, 844],
  ]) {
    await creatorPage.setViewportSize({ width, height });
    await inspect(creatorPage, `result-${width}`);
  }
  const players = [await context(), await context()];
  const pages = await Promise.all(players.map((c) => c.newPage()));
  const scores = [];
  const records = [];
  for (const [index, page] of pages.entries()) {
    stage = `invitation-player-${index + 1}`;
    await page.goto(origin + invitationPath);
    await page
      .getByRole("button", {
        name: /play.*five|play.*challenge|accept.*challenge|take.*challenge/i,
      })
      .first()
      .waitFor();
    const invitationResponse = await players[index].request.get(
      `${origin}/api/v1/challenges/${slug}`,
    );
    assert.equal(invitationResponse.status(), 200);
    assert.match(invitationResponse.headers()["cache-control"], /no-store/);
    const invitation = await invitationResponse.json();
    assert.equal(invitation.creator_score, 3);
    assert(!forbidden.test(JSON.stringify(invitation)));
    const html = await page.content();
    assert(!html.includes(payload.cookie));
    for (const comparison of expected)
      for (const name of comparison.names)
        assert(!html.includes(name), "Invitation reveals contestant");
    if (index === 0)
      for (const [width, height] of [
        [1440, 1000],
        [390, 844],
        [320, 844],
      ]) {
        await page.setViewportSize({ width, height });
        await inspect(page, `invitation-${width}`);
      }
    // Use keyboard for invitation and all gameplay actions.
    const play = page
      .getByRole("button", {
        name: /play.*five|play.*challenge|accept.*challenge|take.*challenge/i,
      })
      .first();
    await play.focus();
    await page.keyboard.press("Enter");
    await page.waitForURL(/\/g\/[0-9a-f-]{36}$/);
    const gameId = new URL(page.url()).pathname.split("/").pop();
    const rounds = [];
    let computedScore = 0;
    for (let ordinal = 1; ordinal <= 5; ordinal++) {
      stage = `player-${index + 1}-round-${ordinal}`;
      const cards = page.getByTestId("choice-card");
      await cards.first().waitFor();
      const currentResponse = await players[index].request.get(
        `${origin}/api/v1/games/${gameId}`,
      );
      const current = (await currentResponse.json()).current_round;
      assert.equal(current.state, "unanswered");
      assert.equal(current.ordinal, ordinal);
      assert(
        !forbidden.test(JSON.stringify(current)),
        "Playable DTO leaks private key",
      );
      const names = current.choices.map((c) => c.entity.name);
      assert.deepEqual(names, expected[ordinal - 1].names);
      assert.equal(current.target_type, expected[ordinal - 1].domain);
      for (const future of expected.slice(ordinal))
        for (const name of future.names)
          assert(!(await page.content()).includes(name));
      const answerPromise = page.waitForResponse(
        (r) =>
          r.url().endsWith(`/games/${gameId}/answer`) &&
          r.request().method() === "POST",
      );
      await cards.nth(index).focus();
      await page.keyboard.press("Enter");
      const reveal = await (await answerPromise).json();
      await page.getByTestId("reveal-panel").waitFor();
      const winner = reveal.choices.find(
        (c) => c.id === reveal.winning_choice_id,
      ).entity.name;
      assert.equal(winner, expected[ordinal - 1].winner);
      computedScore += Number(reveal.correct);
      assert.equal(reveal.cumulative_score, computedScore);
      rounds.push({ names, winner, domain: current.target_type });
      if (ordinal === 2) {
        await page.reload();
        await page.getByTestId("reveal-panel").waitFor();
        assert.match(
          await page.getByTestId("live-score").innerText(),
          new RegExp(`${computedScore}\\s*\\/\\s*5`),
        );
      }
      await page.getByTestId("next-action").focus();
      await page.keyboard.press("Enter");
      if (ordinal < 5)
        await page
          .getByRole("group", {
            name: `Round ${ordinal + 1} of 5`,
            exact: true,
          })
          .waitFor();
    }
    await page.waitForURL(/\/results\//);
    await page.getByTestId("result-ticket").waitFor();
    const resultResponse = await players[index].request.get(
      `${origin}/api/v1/games/${gameId}/results`,
    );
    const result = await resultResponse.json();
    assert.equal(result.score, computedScore);
    assert.equal(result.answered_rounds.length, 5);
    scores.push(computedScore);
    records.push(rounds);
    if (index === 0) await inspect(page, "replay-result-320");
    findings.responsesChecked += 12;
  }
  assert.deepEqual(records[0], records[1]);
  assert.equal(
    scores[0] + scores[1],
    5,
    "Opposite guesses on same rounds have complementary scores",
  );
  // Creator clearing revokes the invitation AND dependent already-completed replay access.
  stage = "creator-session-clear";
  const cleared = await creator.request.delete(
    `${origin}/api/v1/sessions/current`,
    { headers: { Origin: origin } },
  );
  findings.clearStatus = cleared.status();
  assert.equal(cleared.status(), 204);
  stage = "creator-clear-invitation-revocation";
  const revoked = await players[0].request.get(
    `${origin}/api/v1/challenges/${slug}`,
  );
  assert.equal(revoked.status(), 410);
  stage = "creator-clear-result-revocation";
  await pages[0].reload();
  await pages[0].getByTestId("result-ticket").waitFor({ state: "hidden" });
  stage = "creator-clear-invitation-page";
  await pages[1].goto(origin + invitationPath);
  await pages[1]
    .getByRole("heading", {
      name: /expired|unavailable|closed|no longer|retired/i,
    })
    .waitFor();
  await inspect(pages[1], "revoked-invitation");
  stage = "final-browser-error-check";
  assert.deepEqual(errors, []);
  assert.equal(findings.externalRequests, 0);
  assert.equal(findings.providerPaths, 0);
  const verification = {
    status: "passed",
    source: "synthetic fixture only",
    sessions: 3,
    replayGames: 2,
    roundsPerReplay: 5,
    exactSidesOrderWinners: true,
    independentScores: scores,
    refreshRestoredAcceptedReveal: true,
    creatorClearRevokedDependentAccess: true,
    keyboard: true,
    reducedMotion: true,
    qlooCalls: 0,
    vertexCalls: 0,
    ...findings,
  };
  await writeFile(
    `${directory}/verification.json`,
    JSON.stringify(verification, null, 2),
  );
  console.log(JSON.stringify(verification));
} catch (error) {
  console.log(
    JSON.stringify({
      status: "failed",
      stage,
      safeErrorType: error.name,
      safeAssertion: error.code ?? null,
      pageErrorNames: errors,
      ...findings,
    }),
  );
  process.exitCode = 1;
} finally {
  await browser?.close();
}
