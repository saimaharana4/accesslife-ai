import { test } from "node:test";
import assert from "node:assert/strict";
import { forwardApi, type ForwardSettings } from "./forward.ts";
import { metadataIdentityToken } from "./identity-token.ts";
import { matchesSchema } from "./forward-contract.ts";

const ID = "12345678-1234-4234-8234-123456789012";
const KEY = "12345678-1234-4234-8234-123456789013";
const token = `${ID}.${"a".repeat(43)}`;
const origin = "https://taste.example";
const SLUG = "synthetic_capability_1234567890";
const session = {
  active: true,
  expires_at: "2026-10-27T00:00:00Z",
  resumable_game_ids: [],
};

test("a measured cold API start can finish without a premature forwarding abort", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let release: (value: Response) => void = () => {};
  let signal: AbortSignal | undefined;
  const pending = forwardApi(
    request("/health/ready"),
    settings(async (_input, init) => {
      signal = init?.signal ?? undefined;
      return new Promise<Response>((resolve) => {
        release = resolve;
      });
    }),
  );
  t.mock.timers.tick(18000);
  assert.equal(signal?.aborted, false);
  release(Response.json({ status: "ok", generation_available: true }));
  assert.equal((await pending).status, 200);
});

test("an unresponsive API still reaches a bounded sanitized retryable deadline", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const pending = forwardApi(
    request("/health/ready"),
    settings(
      async (_input, init) =>
        new Promise<Response>((_resolve, reject) =>
          init?.signal?.addEventListener(
            "abort",
            () => reject(new Error("SYNTHETIC_PRIVATE_TIMEOUT_DIAGNOSTIC")),
            { once: true },
          ),
        ),
    ),
  );
  t.mock.timers.tick(25000);
  const response = await pending;
  assert.equal(response.status, 504);
  const value = await response.json();
  assert.equal(value.error.code, "REQUEST_INTERRUPTED");
  assert.equal(value.error.retryable, true);
  assert.ok(!JSON.stringify(value).includes("PRIVATE_TIMEOUT"));
});
const error = (code = "QLOO_UNAVAILABLE") => ({
  error: {
    code,
    message: "PRIVATE_PROVIDER_DIAGNOSTIC",
    retryable: true,
    request_id: ID,
    field_errors: [],
    retry_after_seconds: 4,
  },
});

for (const [code, status, fragment] of [
  ["GENERATION_INSUFFICIENT_COVERAGE", 422, "not enough verified comparisons"],
  ["GENERATION_PROVIDER_UNAVAILABLE", 503, "temporarily unavailable"],
  ["GENERATION_CONFIGURATION_UNAVAILABLE", 503, "try again later"],
] as const) {
  test(`preparation failure ${code} preserves its safe action without upstream details`, async () => {
    const response = await forwardApi(
      request("/sessions/current"),
      settings(async () => Response.json(error(code), { status })),
    );
    const value = await response.json();
    assert.equal(value.error.code, code);
    assert.ok(value.error.message.includes(fragment));
    assert.ok(!JSON.stringify(value).includes("PRIVATE_PROVIDER_DIAGNOSTIC"));
  });
}

for (const [status, code] of [
  [429, "SESSION_RATE_LIMITED"],
  [408, "REQUEST_TIMEOUT"],
] as const) {
  test(`preserves typed ${code} without upstream diagnostic text`, async () => {
    const response = await forwardApi(
      request("/sessions/current"),
      settings(async () => Response.json(error(code), { status })),
    );
    assert.equal(response.status, status);
    const result = await response.json();
    assert.equal(result.error.code, code);
    assert.equal(result.error.retryable, true);
    assert.ok(!JSON.stringify(result).includes("PRIVATE_PROVIDER_DIAGNOSTIC"));
  });
}

test("challenge forwarding requires keyed strict mutations and never exposes invitation answer fields", async () => {
  const invitation = {
    slug: SLUG,
    seed: {
      id: ID,
      name: "Synthetic favourite",
      type: "artist",
      source: "fixture",
    },
    creator_score: 3,
    total: 5,
    source: "fixture",
    expires_at: "2099-10-26T12:00:00Z",
  };
  const result = { invitation, share_path: `/c/${SLUG}` };
  let calls = 0;
  const transport: typeof fetch = async (input, init) => {
    calls++;
    assert.equal(new Headers(init?.headers).get("idempotency-key"), KEY);
    assert.equal(String(input), "https://private-api.example/v1/challenges");
    return Response.json(result, { status: 201 });
  };
  assert.equal(
    (
      await forwardApi(
        request("/challenges", "POST", { game_id: ID }),
        settings(transport),
      )
    ).status,
    422,
  );
  assert.equal(
    (
      await forwardApi(
        request(
          "/challenges",
          "POST",
          { game_id: ID, private_key: "PRIVATE" },
          { "Idempotency-Key": KEY },
        ),
        settings(transport),
      )
    ).status,
    422,
  );
  const created = await forwardApi(
    request("/challenges", "POST", { game_id: ID }, { "Idempotency-Key": KEY }),
    settings(transport),
  );
  assert.equal(created.status, 201);
  assert.deepEqual(await created.json(), result);
  assert.equal(calls, 1);
  for (const payload of [
    { ...invitation, private_pool: ["PRIVATE"] },
    { ...invitation, seed: { ...invitation.seed, affinity: 0.99 } },
  ]) {
    const invalid = await forwardApi(
      request(`/challenges/${SLUG}`),
      settings(async () => Response.json(payload)),
    );
    assert.equal(invalid.status, 502);
    assert.ok(!(await invalid.text()).includes("PRIVATE"));
  }
  const revoked = await forwardApi(
    request(`/challenges/${SLUG}`, "DELETE"),
    settings(async (_, init) => {
      assert.equal(init?.method, "DELETE");
      return new Response(null, { status: 204 });
    }),
  );
  assert.equal(revoked.status, 204);
  assert.equal(revoked.headers.get("cache-control"), "no-store");
  let playCalls = 0;
  for (const [body, key] of [
    [{}, undefined],
    [{ winner: ID }, KEY],
    [undefined, KEY],
  ] as const) {
    const response = await forwardApi(
      request(
        `/challenges/${SLUG}/plays`,
        "POST",
        body,
        key ? { "Idempotency-Key": key } : undefined,
      ),
      settings(async () => {
        playCalls++;
        return Response.json({});
      }),
    );
    assert.equal(response.status, 422);
  }
  const play = await forwardApi(
    request(
      `/challenges/${SLUG}/plays`,
      "POST",
      {},
      { "Idempotency-Key": KEY },
    ),
    settings(async (_, init) => {
      playCalls++;
      assert.equal(new Headers(init?.headers).get("idempotency-key"), KEY);
      assert.equal(init?.body, "{}");
      return Response.json(error("CHALLENGE_EXPIRED"), { status: 410 });
    }),
  );
  assert.equal(playCalls, 1);
  assert.equal(play.status, 410);
  assert.equal((await play.json()).error.code, "CHALLENGE_EXPIRED");
});

test("generated curation rejection keys reject unknown diagnostic fields", () => {
  const summary = {
    status: "succeeded",
    curator_mode: "genuine_agent",
    source: "qloo",
    target_domains: ["movie"],
    candidate_count_received: 20,
    rejection_counts: {},
    bounded_correction_count: 0,
    five_round_path_verified: true,
  };
  const schema = { $ref: "#/components/schemas/CurationSummaryPublic" };
  assert.equal(matchesSchema(summary, schema), true);
  assert.equal(
    matchesSchema(
      { ...summary, rejection_counts: { PRIVATE_DIAGNOSTIC: 1 } },
      schema,
    ),
    false,
  );
});
function request(
  path: string,
  method = "GET",
  body?: unknown,
  headers?: Record<string, string>,
) {
  return new Request(`${origin}/api/v1${path}`, {
    method,
    headers: {
      ...(method !== "GET"
        ? { Origin: origin, "Content-Type": "application/json" }
        : {}),
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
function settings(
  transport: typeof fetch = async () => Response.json(session),
): ForwardSettings {
  return {
    apiUrl: "https://private-api.example",
    allowedOrigins: [origin],
    fetch: transport,
  };
}

test("revision-tag requests retain the configured canonical IAM audience", async () => {
  let calls = 0;
  const response = await forwardApi(request("/sessions/current"), {
    ...settings(async (input, init) => {
      calls++;
      assert.equal(
        String(input),
        "https://candidate---private-api.example/v1/sessions/current",
      );
      assert.equal(
        new Headers(init?.headers).get("authorization"),
        "Bearer SERVER_ONLY",
      );
      return Response.json(session);
    }),
    apiUrl: "https://candidate---private-api.example",
    apiAudience: "https://private-api.example",
    identityToken: async (audience) => {
      assert.equal(audience, "https://private-api.example");
      return "SERVER_ONLY";
    },
  });
  assert.equal(response.status, 200);
  assert.equal(calls, 1);
});

test("invalid configured IAM audiences fail closed before fetching metadata or API", async () => {
  for (const apiAudience of [
    "",
    "http://private-api.example",
    "https://user:pass@private-api.example",
    "https://private-api.example/",
    "https://private-api.example/path",
    "https://private-api.example?query=x",
    "https://private-api.example#fragment",
  ]) {
    let calls = 0;
    const response = await forwardApi(request("/sessions/current"), {
      ...settings(async () => {
        calls++;
        return Response.json(session);
      }),
      apiAudience,
      identityToken: async () => {
        calls++;
        return "UNEXPECTED";
      },
    });
    assert.equal(response.status, 503);
    assert.equal((await response.json()).error.code, "WEB_API_UNCONFIGURED");
    assert.equal(calls, 0);
  }
});

test("forwards only method/path/query, own cookie, idempotency and configured IAM", async () => {
  let calls = 0;
  const response = await forwardApi(
    request(
      "/games",
      "POST",
      { seed_entity_id: ID, seed_type: "artist", mode: "solo" },
      {
        Cookie: `other=private; tasteduel_session=${token}`,
        "Idempotency-Key": KEY,
        Authorization: "Bearer BROWSER_SECRET",
        "X-Api-Key": "BROWSER_KEY",
        "X-Forwarded-Host": "evil.example",
      },
    ),
    {
      ...settings(async (input, init) => {
        calls++;
        assert.equal(String(input), "https://private-api.example/v1/games");
        const headers = new Headers(init?.headers);
        assert.deepEqual([...headers.keys()].sort(), [
          "accept",
          "authorization",
          "content-type",
          "cookie",
          "idempotency-key",
          "origin",
        ]);
        assert.equal(headers.get("authorization"), "Bearer SERVER_TOKEN");
        assert.equal(headers.get("cookie"), `tasteduel_session=${token}`);
        assert.equal(init?.redirect, "manual");
        assert.equal(init?.cache, "no-store");
        return Response.json(
          {
            game_id: ID,
            status: "generation_in_progress",
            lease_expires_at: "2026-10-26T10:10:10Z",
            retry_after_seconds: 2,
          },
          {
            status: 202,
            headers: { "X-Private": "secret", "Retry-After": "2" },
          },
        );
      }),
      identityToken: async (audience) => {
        assert.equal(audience, "https://private-api.example");
        return "SERVER_TOKEN";
      },
    },
  );
  assert.equal(calls, 1);
  assert.equal(response.status, 202);
  assert.equal(response.headers.get("x-private"), null);
  assert.equal(response.headers.get("retry-after"), null);
  assert.equal(response.headers.get("cache-control"), "no-store");
});

for (const [path, method, headers] of [
  ["/games", "POST", { Origin: "https://evil.example" }],
  ["/games", "POST", { Origin: "" }],
  ["/sessions", "POST", { "Sec-Fetch-Site": "cross-site" }],
  ["/sessions/current", "GET", { "Sec-Fetch-Site": "cross-site" }],
] as const)
  test(`blocks mutation/read origin ${method} ${JSON.stringify(headers)}`, async () => {
    let calls = 0;
    const response = await forwardApi(
      request(path, method, method === "POST" ? {} : undefined, headers),
      settings(async () => {
        calls++;
        return Response.json(session);
      }),
    );
    assert.equal(response.status, 403);
    assert.equal(calls, 0);
  });

for (const path of [
  "/../secret",
  "/games/a/private-pool",
  `/games/${ID}/receipt`,
  "/challenges",
  "/entities/search?q=x&type=artist&debug=true",
  "/entities/search?q=a&q=b&type=artist",
  "/entities/search?q=x&type=book",
  "/entities/search?q=x&type=movie&limit=100",
])
  test(`rejects unsupported path/query ${path}`, async () => {
    let calls = 0;
    const response = await forwardApi(
      request(path),
      settings(async () => {
        calls++;
        return Response.json(session);
      }),
    );
    assert.ok(response.status >= 400);
    assert.equal(calls, 0);
  });

test("request schemas reject private fields and missing idempotency", async () => {
  let calls = 0;
  const config = settings(async () => {
    calls++;
    return Response.json(session);
  });
  for (const body of [
    { seed_entity_id: ID, seed_type: "artist", mode: "solo", winner: ID },
    { seed_entity_id: "../private", seed_type: "artist" },
  ]) {
    assert.equal(
      (
        await forwardApi(
          request("/games", "POST", body, { "Idempotency-Key": KEY }),
          config,
        )
      ).status,
      422,
    );
  }
  assert.equal(
    (
      await forwardApi(
        request("/games", "POST", { seed_entity_id: ID, seed_type: "artist" }),
        config,
      )
    ).status,
    422,
  );
  assert.equal(calls, 0);
});

test("secure host-only cookie is rewritten, never copying upstream Domain or other cookies", async () => {
  const response = await forwardApi(
    request("/sessions", "POST", {}),
    settings(async () =>
      Response.json(session, {
        status: 201,
        headers: {
          "Set-Cookie": `tasteduel_session=${token}; Domain=.example; Path=/v1; Max-Age=86400; SameSite=None`,
          "X-Provider": "SECRET",
        },
      }),
    ),
  );
  assert.equal(response.status, 201);
  assert.equal(
    response.headers.get("set-cookie"),
    `tasteduel_session=${token}; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax; Secure`,
  );
  assert.equal(response.headers.get("x-provider"), null);
});

for (const emptyValue of ["", '\"\"'])
  test(`clear emits host-only tombstone for ${JSON.stringify(emptyValue)}`, async () => {
    const response = await forwardApi(
      request("/sessions/current", "DELETE"),
      settings(
        async () =>
          new Response(null, {
            status: 204,
            headers: {
              "Set-Cookie": `tasteduel_session=${emptyValue}; Max-Age=0; Domain=.example; Path=/`,
            },
          }),
      ),
    );
    assert.equal(response.status, 204);
    assert.match(
      response.headers.get("set-cookie")!,
      /Max-Age=0; HttpOnly; SameSite=Lax; Secure$/,
    );
  });

test("internal standalone HTTP URL selects only the exact configured public Host", async () => {
  let calls = 0;
  const incoming = new Request("http://localhost:3001/api/v1/sessions", {
    method: "POST",
    headers: {
      Host: "taste.example",
      Origin: origin,
      "Content-Type": "application/json",
      "X-Forwarded-Host": "attacker.example",
      "X-Forwarded-Proto": "http",
    },
    body: "{}",
  });
  const response = await forwardApi(
    incoming,
    settings(async (_, init) => {
      calls++;
      assert.equal(new Headers(init?.headers).get("origin"), origin);
      return Response.json(session, {
        status: 201,
        headers: { "Set-Cookie": `tasteduel_session=${token}; Max-Age=86400` },
      });
    }),
  );
  assert.equal(response.status, 201);
  assert.equal(calls, 1);
  assert.match(response.headers.get("set-cookie")!, /; Secure$/);
});

for (const [host, forwarded] of [
  ["attacker.example", "taste.example"],
  ["taste.example:444", "taste.example"],
  ["taste.example,attacker.example", "taste.example"],
  ["taste.example@attacker.example", "taste.example"],
  ["", "taste.example"],
])
  test(`forwarded headers cannot bless unconfigured raw Host ${host}`, async () => {
    let calls = 0;
    const incoming = new Request(
      "http://localhost:3001/api/v1/sessions/current",
      {
        headers: {
          Host: host,
          "X-Forwarded-Host": forwarded,
          "X-Forwarded-Proto": "https",
          Forwarded: `host=${forwarded};proto=https`,
        },
      },
    );
    const response = await forwardApi(
      incoming,
      settings(async () => {
        calls++;
        return Response.json(session);
      }),
    );
    assert.equal(response.status, 403);
    assert.equal(calls, 0);
  });

test("normalized public Host never excuses a mismatching mutation Origin", async () => {
  const incoming = new Request("http://internal:8080/api/v1/sessions", {
    method: "POST",
    headers: {
      Host: "taste.example",
      Origin: "https://attacker.example",
      "Content-Type": "application/json",
    },
    body: "{}",
  });
  let calls = 0;
  assert.equal(
    (
      await forwardApi(
        incoming,
        settings(async () => {
          calls++;
          return Response.json(session);
        }),
      )
    ).status,
    403,
  );
  assert.equal(calls, 0);
});

test("intentional loopback Host works despite standalone localhost reconstruction", async () => {
  const incoming = new Request("http://localhost:3001/api/v1/sessions", {
    method: "POST",
    headers: {
      Host: "127.0.0.1:3001",
      Origin: "http://127.0.0.1:3001",
      "Content-Type": "application/json",
    },
    body: "{}",
  });
  const response = await forwardApi(incoming, {
    apiUrl: "http://127.0.0.1:8004",
    allowedOrigins: ["http://127.0.0.1:3001"],
    allowLocalHttp: true,
    fetch: async (_, init) => {
      assert.equal(
        new Headers(init?.headers).get("origin"),
        "http://127.0.0.1:3001",
      );
      return Response.json(session, {
        status: 201,
        headers: {
          "Set-Cookie": `tasteduel_session=${token}; Secure; Max-Age=86400`,
        },
      });
    },
  });
  assert.equal(response.status, 201);
  assert.ok(!response.headers.get("set-cookie")?.includes("Secure"));
});

test("ambiguous configured schemes for the same Host fail closed", async () => {
  const incoming = new Request("http://internal:8080/api/v1/sessions/current", {
    headers: { Host: "localhost:3001" },
  });
  const response = await forwardApi(incoming, {
    ...settings(),
    allowLocalHttp: true,
    allowedOrigins: ["http://localhost:3001", "https://localhost:3001"],
  });
  assert.equal(response.status, 403);
});

test("HTTP works only for explicit loopback development origins and API", async () => {
  const local = new Request("http://localhost:3000/api/v1/sessions", {
    method: "POST",
    headers: {
      Origin: "http://localhost:3000",
      "Content-Type": "application/json",
    },
    body: "{}",
  });
  const cfg = {
    apiUrl: "http://127.0.0.1:8002",
    allowedOrigins: ["http://localhost:3000"],
    fetch: async () =>
      Response.json(session, {
        status: 201,
        headers: {
          "Set-Cookie": `tasteduel_session=${token}; Secure; Max-Age=86400`,
        },
      }),
  };
  assert.equal((await forwardApi(local.clone(), cfg)).status, 503);
  const good = await forwardApi(local.clone(), {
    ...cfg,
    allowLocalHttp: true,
  });
  assert.equal(good.status, 201);
  assert.ok(!good.headers.get("set-cookie")?.includes("Secure"));
  assert.equal(
    (
      await forwardApi(local.clone(), {
        ...cfg,
        apiUrl: "http://evil.example",
        allowLocalHttp: true,
      })
    ).status,
    503,
  );
});

test("unknown upstream diagnostic code, error text and headers never escape", async () => {
  const response = await forwardApi(
    request("/entities/search?q=real&type=artist"),
    settings(async () =>
      Response.json(error("PRIVATE_SECRET_DIAGNOSTIC"), {
        status: 503,
        headers: { "X-Api-Key": "SECRET" },
      }),
    ),
  );
  const text = await response.text();
  assert.equal(response.status, 503);
  assert.ok(!text.includes("PRIVATE"));
  assert.ok(!text.includes("DIAGNOSTIC"));
  assert.ok(!text.includes("SECRET"));
  assert.equal(JSON.parse(text).error.code, "REQUEST_FAILED");
  assert.equal(response.headers.get("x-api-key"), null);
});

test("in-progress generation code survives sanitized forwarding for recovery", async () => {
  const response = await forwardApi(
    request(`/games/${ID}`),
    settings(async () =>
      Response.json(error("GENERATION_IN_PROGRESS"), { status: 409 }),
    ),
  );
  assert.equal(response.status, 409);
  const body = await response.json();
  assert.equal(body.error.code, "GENERATION_IN_PROGRESS");
  assert.ok(!JSON.stringify(body).includes("PRIVATE_PROVIDER"));
});

for (const [name, upstream] of [
  [
    "unexpected pool field",
    () => Response.json({ ...session, private_pool: ["winner"] }),
  ],
  [
    "redirect",
    () =>
      new Response(null, {
        status: 302,
        headers: { Location: "http://169.254.169.254/" },
      }),
  ],
  [
    "non-json",
    () => new Response("PRIVATE", { headers: { "Content-Type": "text/html" } }),
  ],
  [
    "oversized",
    () =>
      new Response(JSON.stringify({ private: "x".repeat(270000) }), {
        headers: { "Content-Type": "application/json" },
      }),
  ],
  [
    "malformed JSON",
    () =>
      new Response("{PRIVATE", {
        headers: { "Content-Type": "application/json" },
      }),
  ],
] as const)
  test(`blocks ${name}`, async () => {
    const response = await forwardApi(
      request("/sessions/current"),
      settings(async () => upstream()),
    );
    assert.equal(response.status, 502);
    assert.ok(!(await response.text()).includes("PRIVATE"));
  });

test("playable DTO rejects pre-answer winners or any nested extra evidence", async () => {
  const entity = {
    id: ID,
    name: "Synthetic artist",
    type: "artist",
    source: "qloo",
  };
  const playable = {
    game_id: ID,
    round_id: ID,
    state: "unanswered",
    ordinal: 1,
    total: 5,
    revision: 1,
    seed: entity,
    target_type: "artist",
    question: "Which ranks higher?",
    choices: [
      { id: ID, entity },
      { id: KEY, entity: { ...entity, id: KEY } },
    ],
    source: "qloo",
  };
  const baseline = await forwardApi(
    request(`/games/${ID}/round`),
    settings(async () => Response.json(playable)),
  );
  assert.equal(baseline.status, 200);
  assert.deepEqual(await baseline.json(), playable);
  for (const data of [
    { ...playable, winning_choice_id: ID },
    {
      ...playable,
      choices: [
        { id: ID, entity: { ...entity, affinity: 0.9 } },
        playable.choices[1],
      ],
    },
  ]) {
    const response = await forwardApi(
      request(`/games/${ID}/round`),
      settings(async () => Response.json(data)),
    );
    assert.equal(response.status, 502);
    assert.ok(!(await response.text()).includes("affinity"));
  }
});

test("metadata IAM only fixed host, fixed audience, bounded response and matching JWT claims", async () => {
  const audience = "https://iam-test-api.example";
  const encoded = Buffer.from(
    JSON.stringify({ aud: audience, exp: Math.floor(Date.now() / 1000) + 600 }),
  ).toString("base64url");
  const result = await metadataIdentityToken(audience, async (input, init) => {
    const url = new URL(String(input));
    assert.equal(url.hostname, "metadata.google.internal");
    assert.equal(
      url.pathname,
      "/computeMetadata/v1/instance/service-accounts/default/identity",
    );
    assert.equal(url.searchParams.get("audience"), audience);
    assert.equal(new Headers(init?.headers).get("Metadata-Flavor"), "Google");
    assert.equal(init?.redirect, "error");
    return new Response(`abc.${encoded}.xyz`, {
      headers: { "Metadata-Flavor": "Google" },
    });
  });
  assert.equal(result, `abc.${encoded}.xyz`);
  await assert.rejects(() => metadataIdentityToken("http://127.0.0.1:8002"));
  await assert.rejects(() =>
    metadataIdentityToken(
      "https://other-api.example",
      async () =>
        new Response("x".repeat(17000), {
          headers: { "Metadata-Flavor": "Google" },
        }),
    ),
  );
});

test("discoveries require an explicit keyed save and permit only the safe collection and idempotent removal", async () => {
  const entity = {
    id: ID,
    name: "Synthetic explicit discovery",
    type: "movie",
    source: "fixture",
  };
  const discovery = {
    entity,
    saved_at: "2026-10-26T10:00:00Z",
    expires_at: "2026-10-27T10:00:00Z",
  };
  assert.equal(
    (
      await forwardApi(
        request("/discoveries", "POST", { entity_id: ID }),
        settings(),
      )
    ).status,
    422,
  );
  const response = await forwardApi(
    request(
      "/discoveries",
      "POST",
      { entity_id: ID },
      { "Idempotency-Key": KEY },
    ),
    settings(async (_url, init) => {
      assert.equal(new Headers(init?.headers).get("idempotency-key"), KEY);
      return Response.json(discovery, { status: 201 });
    }),
  );
  assert.equal(response.status, 201);
  const collection = await forwardApi(
    request("/discoveries"),
    settings(async () =>
      Response.json({
        discoveries: [discovery],
        expired_count: 1,
        session_expires_at: "2026-10-27T10:00:00Z",
      }),
    ),
  );
  assert.equal(collection.status, 200);
  const removed = await forwardApi(
    request(`/discoveries/${ID}`, "DELETE"),
    settings(async () => new Response(null, { status: 204 })),
  );
  assert.equal(removed.status, 204);
  assert.equal(await removed.text(), "");
  const unsafe = await forwardApi(
    request("/discoveries"),
    settings(async () =>
      Response.json({ discoveries: [], personal_likes: [ID] }),
    ),
  );
  assert.equal(unsafe.status, 502);
});
