import { test } from "node:test";
import assert from "node:assert/strict";
import {
  configuredCanonicalOrigin,
  readPublicChallenge,
} from "./challenge-server-core.ts";

const origin = "https://taste.example";
const slug = "synthetic_capability_1234567890";
const invitation = {
  slug,
  seed: {
    id: "12345678-1234-4234-8234-123456789012",
    name: "Synthetic favourite",
    type: "artist",
    source: "fixture",
  },
  creator_score: 3,
  total: 5,
  source: "fixture",
  expires_at: "2099-10-26T12:00:00Z",
};

test("canonical sharing uses exact configured origin only; intentional local HTTP is explicit", () => {
  for (const value of [
    undefined,
    "https://attacker.example",
    `${origin}/`,
    `${origin}/path`,
    "https://user:pass@taste.example",
    `${origin}?next=x`,
  ])
    assert.equal(configuredCanonicalOrigin(value, [origin]), null);
  assert.equal(configuredCanonicalOrigin(origin, [origin]), origin);
  const local = "http://127.0.0.1:3003";
  assert.equal(configuredCanonicalOrigin(local, [local]), null);
  assert.equal(configuredCanonicalOrigin(local, [local], true), local);
  assert.equal(
    configuredCanonicalOrigin(
      "http://169.254.169.254",
      ["http://169.254.169.254"],
      true,
    ),
    null,
  );
});

test("public server rendering carries no visitor credentials and uses bounded no-store forwarding", async () => {
  let calls = 0;
  const result = await readPublicChallenge(slug, {
    apiUrl: "https://private-api.example",
    allowedOrigins: [origin],
    identityToken: async (audience) => {
      assert.equal(audience, "https://private-api.example");
      return "server-iam";
    },
    fetch: async (input, init) => {
      calls++;
      assert.equal(
        String(input),
        `https://private-api.example/v1/challenges/${slug}`,
      );
      const headers = new Headers(init?.headers);
      assert.equal(headers.get("cookie"), null);
      assert.equal(headers.get("authorization"), "Bearer server-iam");
      assert.equal(init?.cache, "no-store");
      assert.equal(init?.redirect, "manual");
      return Response.json(invitation, {
        headers: { "Set-Cookie": "PRIVATE", "X-Private": "SECRET" },
      });
    },
  });
  assert.deepEqual(result, { status: 200, invitation });
  assert.equal(calls, 1);
});

test("invitation rendering rejects extra answer fields, mismatched slug, stale evidence and redirect/size attacks", async () => {
  const settings = {
    apiUrl: "https://private-api.example",
    allowedOrigins: [origin],
  };
  for (const payload of [
    { ...invitation, private_pool: ["PRIVATE"] },
    { ...invitation, slug: "other_capability_1234567890" },
    { ...invitation, expires_at: "2020-01-01T00:00:00Z" },
  ]) {
    const result = await readPublicChallenge(slug, {
      ...settings,
      fetch: async () => Response.json(payload),
    });
    assert.equal(result.invitation, null);
    assert.ok(result.status >= 400);
  }
  for (const response of [
    new Response(null, {
      status: 302,
      headers: { Location: "http://169.254.169.254" },
    }),
    new Response("x".repeat(270000), {
      headers: { "Content-Type": "application/json" },
    }),
  ]) {
    const result = await readPublicChallenge(slug, {
      ...settings,
      fetch: async () => response,
    });
    assert.equal(result.invitation, null);
    assert.equal(result.status, 502);
  }
  let calls = 0;
  for (const invalid of [
    "../secret",
    "a".repeat(81),
    "https://attacker.example",
    "x?secret",
  ]) {
    assert.equal(
      (
        await readPublicChallenge(invalid, {
          ...settings,
          fetch: async () => {
            calls++;
            return Response.json(invitation);
          },
        })
      ).status,
      404,
    );
  }
  assert.equal(calls, 0);
});
