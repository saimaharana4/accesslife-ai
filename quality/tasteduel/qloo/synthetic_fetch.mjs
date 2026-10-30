// Offline test preload. The original fetch is intentionally never retained or called.
// All names, UUIDs, scores, URLs and failures in this file are invented.
import fs from "node:fs";

export function installSyntheticFetch(tracePath, mode = "ok") {
  const seed = {
    entity_id: "10000000-0000-4000-8000-000000000001",
    name: "Invented Artist",
    types: ["urn:entity:artist"],
    type: "urn:entity",
    subtype: "urn:entity:artist",
  };
  const films = [0.8, 0.3].map((affinity, index) => ({
    entity_id: `20000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    name: `Invented Film ${index + 1}`,
    type: "urn:entity",
    subtype: "urn:entity:movie",
    query: { affinity },
    properties: { image: { url: "https://example.invalid/invented.jpg" } },
  }));
  let dispatched = 0;
  globalThis.fetch = async (input, options = {}) => {
    dispatched += 1;
    const url = new URL(input instanceof Request ? input.url : String(input));
    const headers = new Headers(options.headers);
    const observation = {
      path: url.pathname,
      origin: url.origin,
      method: options.method,
      redirect: options.redirect,
      query: Object.fromEntries(url.searchParams),
      hasSyntheticKey: headers.get("X-Api-Key") === "synthetic-offline-key",
      hasAbortSignal: options.signal instanceof AbortSignal,
    };
    fs.appendFileSync(tracePath, JSON.stringify(observation) + "\n");
    if (url.origin !== "https://hackathon.api.qloo.com")
      throw Error("SYNTHETIC_HOST_REJECTED");
    if (mode === "timeout") {
      return await new Promise((_, reject) => {
        const abort = () =>
          reject(new DOMException("Synthetic timeout", "AbortError"));
        if (options.signal?.aborted) abort();
        else options.signal?.addEventListener("abort", abort, { once: true });
      });
    }
    if (mode === "auth" || (mode === "auth_once" && dispatched === 1))
      return new Response('{"message":"Synthetic unauthorized"}', {
        status: 401,
      });
    if (mode === "rate_limit") {
      return new Response('{"message":"Synthetic rate limit"}', {
        status: 429,
        headers: { "retry-after": "1" },
      });
    }
    if (mode === "malformed")
      return new Response("synthetic-not-json", { status: 200 });
    let entities;
    if (url.pathname === "/search" && mode === "ambiguous") {
      entities = [
        seed,
        { ...seed, entity_id: "10000000-0000-4000-8000-000000000002" },
      ];
    } else if (url.pathname === "/search" || url.pathname === "/entities")
      entities = [seed];
    else if (url.pathname === "/v2/insights") entities = films;
    else throw Error("SYNTHETIC_ENDPOINT_REJECTED");
    return new Response(
      JSON.stringify({ success: true, results: { entities } }),
      {
        status: 200,
        headers: { "content-type": "application/json" },
      },
    );
  };
}
