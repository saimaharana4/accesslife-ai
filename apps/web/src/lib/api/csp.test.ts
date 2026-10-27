import { test } from "node:test";
import assert from "node:assert/strict";
import { contentSecurityPolicy } from "../security/csp.ts";

test("production CSP requires an unpredictable server nonce and blocks inline executable attributes", () => {
  const policy = contentSecurityPolicy("a".repeat(43) + "=");
  const script = policy
    .split(";")
    .find((s) => s.trim().startsWith("script-src "))!;
  assert.match(script, /'nonce-[A-Za-z0-9+/]+=+'/);
  assert.match(script, /'strict-dynamic'/);
  assert.ok(
    !script.includes("unsafe-inline") && !script.includes("unsafe-eval"),
  );
  assert.match(policy, /script-src-attr 'none'/);
  assert.match(policy, /frame-ancestors 'none'/);
  assert.match(policy, /connect-src 'self';/);
  for (const invalid of [
    "",
    "'unsafe-inline'",
    "a".repeat(31),
    "a; report-uri https://attacker.example",
  ])
    assert.throws(() => contentSecurityPolicy(invalid));
  assert.match(
    contentSecurityPolicy("a".repeat(43) + "=", true),
    /unsafe-eval/,
  );
});
