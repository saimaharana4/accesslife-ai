import { test } from "node:test";
import assert from "node:assert/strict";
import { api, ApiError, ensureSession } from "./client.ts";
import {
  intentFor,
  readGenerationIntent,
  clearGenerationIntent,
  associateGenerationGame,
} from "../../features/seed/generation-intent.ts";

const ID = "12345678-1234-4234-8234-123456789012";
const OTHER = "12345678-1234-4234-8234-123456789013";
test("uncertain request retains caller key; client never retries a mutation itself", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async (input, init) => {
    calls++;
    assert.equal(input, "/api/v1/games");
    assert.equal(new Headers(init?.headers).get("Idempotency-Key"), ID);
    assert.equal(init?.credentials, "same-origin");
    throw new TypeError("simulated connection loss");
  };
  try {
    await assert.rejects(
      () => api.post("/games", { seed_entity_id: ID }, ID),
      (failure: unknown) =>
        failure instanceof ApiError &&
        failure.code === "NETWORK_UNCERTAIN" &&
        failure.retryable,
    );
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = original;
  }
});

test("same submission survives reload-like reread; changed seed gets a different key", () => {
  const values = new Map<string, string>();
  const prior = Object.getOwnPropertyDescriptor(globalThis, "window");
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      sessionStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    },
  });
  try {
    const first = intentFor({
      seed_entity_id: ID,
      seed_type: "artist",
      mode: "solo",
    });
    assert.deepEqual(readGenerationIntent(), first);
    assert.equal(
      intentFor({ seed_type: "artist", seed_entity_id: ID, mode: "solo" }).key,
      first.key,
    );
    associateGenerationGame(OTHER);
    assert.equal(readGenerationIntent()?.gameId, OTHER);
    const changed = intentFor({
      seed_entity_id: OTHER,
      seed_type: "artist",
      mode: "solo",
    });
    assert.notEqual(changed.key, first.key);
    assert.equal(readGenerationIntent()?.gameId, undefined);
    assert.ok(!JSON.stringify([...values.values()]).includes("answer"));
    values.set(
      "tasteduel.generation-intent.v1",
      JSON.stringify({ ...changed, private_pool: [] }),
    );
    assert.equal(readGenerationIntent(), undefined);
    clearGenerationIntent();
    assert.equal(readGenerationIntent(), undefined);
  } finally {
    if (prior) Object.defineProperty(globalThis, "window", prior);
    else Reflect.deleteProperty(globalThis, "window");
  }
});

test("session handshake shares only an active promise and aborting one caller does not cancel another", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  let release!: () => void;
  const wait = new Promise<void>((resolve) => {
    release = resolve;
  });
  globalThis.fetch = async () => {
    calls++;
    await wait;
    return Response.json({
      active: true,
      expires_at: "2026-10-27T00:00:00Z",
      resumable_game_ids: [],
    });
  };
  try {
    const controller = new AbortController();
    const cancelled = ensureSession(controller.signal);
    const active = ensureSession();
    controller.abort();
    await assert.rejects(cancelled);
    release();
    assert.equal((await active).active, true);
    assert.equal(calls, 1);
    await ensureSession();
    assert.equal(calls, 2);
  } finally {
    globalThis.fetch = original;
  }
});

test("structured errors remain typed and invalid local paths never fetch", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return Response.json(
      {
        error: {
          code: "REVISION_CONFLICT",
          message: "Reload saved state.",
          retryable: false,
        },
      },
      { status: 409 },
    );
  };
  try {
    await assert.rejects(
      () => api.get("/games/one"),
      (failure: unknown) =>
        failure instanceof ApiError &&
        failure.status === 409 &&
        !failure.retryable,
    );
    await assert.rejects(() => api.get("//evil.example"));
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = original;
  }
});
