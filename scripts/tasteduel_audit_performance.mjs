// Lab only: private synthetic cookie arrives through stdin, never an artifact.
import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import os from "node:os";
import { chromium } from "@playwright/test";

let browser;
try {
  let input = "";
  for await (const chunk of process.stdin) {
    input += chunk;
    assert(input.length < 2000);
  }
  const payload = JSON.parse(input);
  const quick = payload.quick === true;
  assert(/^[0-9a-f-]{36}$/.test(payload.game_id));
  assert(/^[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}$/.test(payload.cookie));
  const origin = "http://127.0.0.1:3001";
  browser = await chromium.launch({ headless: true });
  const rows = [];
  let externalBrowserRequests = 0;
  const resources = { landing: new Map(), gameplay: new Map() };
  async function sample(route, cache, number) {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: "reduce",
    });
    await context.addCookies([
      {
        name: "tasteduel_session",
        value: payload.cookie,
        url: origin,
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
    const page = await context.newPage();
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (["http:", "https:"].includes(url.protocol) && url.origin !== origin)
        externalBrowserRequests++;
    });
    const cdp = await context.newCDPSession(page);
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: 150,
      downloadThroughput: 1_600_000 / 8,
      uploadThroughput: 750_000 / 8,
    });
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await page.addInitScript(() => {
      window.__lab = { lcp: 0, cls: 0, csp_violations: [] };
      addEventListener("securitypolicyviolation", (event) => {
        window.__lab.csp_violations.push(event.effectiveDirective);
      });
      let sessionStart = 0;
      let previousShift = 0;
      let sessionScore = 0;
      new PerformanceObserver((entries) => {
        for (const e of entries.getEntries()) window.__lab.lcp = e.startTime;
      }).observe({ type: "largest-contentful-paint", buffered: true });
      new PerformanceObserver((entries) => {
        for (const e of entries.getEntries()) {
          if (e.hadRecentInput) continue;
          if (
            e.startTime - previousShift > 1000 ||
            e.startTime - sessionStart > 5000
          ) {
            sessionStart = e.startTime;
            sessionScore = 0;
          }
          sessionScore += e.value;
          previousShift = e.startTime;
          window.__lab.cls = Math.max(window.__lab.cls, sessionScore);
        }
      }).observe({ type: "layout-shift", buffered: true });
    });
    const bodies = [];
    page.on("response", (response) => {
      if (new URL(response.url()).pathname.endsWith(".js"))
        bodies.push(
          (async () => {
            const body = await response.body();
            resources[route].set(new URL(response.url()).pathname, {
              bytes: body.length,
              gzip_bytes: gzipSync(body).length,
            });
          })().catch(() => {}),
        );
    });
    const path = route === "landing" ? "/" : `/g/${payload.game_id}`;
    if (cache === "warm") {
      await page.goto(origin + path);
      await page.waitForLoadState("networkidle");
    }
    await page.goto(origin + path);
    if (route === "gameplay")
      await page.getByTestId("choice-card").first().waitFor();
    else await page.getByRole("combobox").waitFor();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    await Promise.all(bodies);
    const value = await page.evaluate(() => ({
      ...window.__lab,
      fonts_loaded: document.fonts.status === "loaded",
    }));
    rows.push({
      route,
      cache,
      sample: number,
      lcp_ms: +value.lcp.toFixed(2),
      cls: +value.cls.toFixed(5),
      fonts_loaded: value.fonts_loaded,
      csp_violations: value.csp_violations,
    });
    await context.close();
  }
  for (const route of ["landing", "gameplay"]) {
    for (let n = 1; n <= (quick ? 1 : 5); n++)
      await sample(route, "cold-browser", n);
    for (let n = 1; n <= (quick ? 0 : 3); n++) await sample(route, "warm", n);
  }
  // Isolate client acknowledgement from correctness: hold answer transport.
  const feedbackSamples = [];
  for (let attempt = 0; attempt < (quick ? 1 : 5); attempt++) {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: "reduce",
    });
    await context.addCookies([
      {
        name: "tasteduel_session",
        value: payload.cookie,
        url: origin,
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
    const page = await context.newPage();
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (["http:", "https:"].includes(url.protocol) && url.origin !== origin)
        externalBrowserRequests++;
    });
    const feedbackCdp = await context.newCDPSession(page);
    await feedbackCdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await page.route("**/answer", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      try {
        await route.abort("internetdisconnected");
      } catch {
        // Closing the isolated measurement context cancels this held request.
      }
    });
    await page.goto(`${origin}/g/${payload.game_id}`);
    await page.getByTestId("choice-card").first().waitFor();
    const feedback = await page
      .getByTestId("choice-card")
      .first()
      .evaluate(async (button) => {
        const before = performance.now();
        return new Promise((resolve) => {
          const observer = new MutationObserver(() => {
            if (button.getAttribute("aria-pressed") === "true") {
              observer.disconnect();
              resolve(performance.now() - before);
            }
          });
          observer.observe(button, {
            attributes: true,
            attributeFilter: ["aria-pressed"],
          });
          button.click();
        });
      });
    await context.close();
    feedbackSamples.push(+feedback.toFixed(2));
  }
  const landing = [...resources.landing.values()].reduce(
    (n, v) => n + v.gzip_bytes,
    0,
  );
  const additional = [...resources.gameplay]
    .filter(([path]) => !resources.landing.has(path))
    .reduce((n, [, v]) => n + v.gzip_bytes, 0);
  const report = {
    chromium: browser.version(),
    platform: process.platform,
    cpu_model: os.cpus()[0]?.model,
    node_version: process.version,
    measurement_mode: quick ? "final-build-smoke" : "full-lab",
    external_browser_request_count: externalBrowserRequests,
    conditions:
      "Production next start; warm local server; 390x844 Chromium headless; CDP150msRTT,1.6Mbpsdown,750kbpsup,4xCPU. Cold means fresh browser context/cache, not cold server. Warm samples prime same route cache. No field claim.",
    samples: rows,
    immediate_pressed_feedback_ms: feedbackSamples,
    pressed_feedback_samples: feedbackSamples.length,
    pressed_feedback_conditions:
      "Programmatic button click to committed aria-pressed mutation at 4xCPU; answer transport held1000ms thenaborted; not pointer hardware latency or field INP",
    javascript: {
      initial_landing_gzip_bytes: landing,
      gameplay_addition_gzip_bytes: additional,
      basis:
        "Actual requested JS bodies individually gzipped; browser HTTPencoding may differ; routes measured directly, not navigation timing",
      routes: Object.fromEntries(
        Object.entries(resources).map(([key, values]) => [
          key,
          [...values].map(([path, v]) => ({ path, ...v })),
        ]),
      ),
    },
  };
  await browser.close();
  browser = undefined;
  console.log(JSON.stringify(report));
} catch (error) {
  await browser?.close();
  console.log(
    JSON.stringify({
      status: "failed",
      safe_error_type: error?.name ?? "Error",
    }),
  );
  process.exitCode = 1;
}
