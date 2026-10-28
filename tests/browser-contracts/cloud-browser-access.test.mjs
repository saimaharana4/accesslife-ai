import test from "node:test";
import assert from "node:assert/strict";
import { cloudBrowserAccess } from "./cloud-browser-access.mjs";

const canonical = "https://tasteduel-web-902056825143.asia-south1.run.app";
const api = "https://tasteduel-api-dfthmgvvaa-el.a.run.app";
const privateEnv = {
  TASTEDUEL_CANDIDATE_ORIGIN: canonical,
  TASTEDUEL_CANDIDATE_ID_TOKEN: "SYNTHETIC_OPERATOR_IDENTITY",
};
const publicEnv = {
  TASTEDUEL_CANDIDATE_ORIGIN: canonical,
  TASTEDUEL_CLOUD_ACCESS_MODE: "public",
  TASTEDUEL_CLOUD_PRIVATE_API_ORIGIN: api,
};
test("default candidate mode still requires operator identity", () => {
  assert.equal(cloudBrowserAccess(privateEnv).mode, "private");
  assert.throws(() =>
    cloudBrowserAccess({ TASTEDUEL_CANDIDATE_ORIGIN: canonical }),
  );
});
test("explicit public verification has no operator token", () => {
  const access = cloudBrowserAccess(publicEnv);
  assert.equal(access.identityToken, null);
  assert.equal(access.mode, "public");
  assert.equal(access.privateApiOrigin, api);
  assert.throws(() =>
    cloudBrowserAccess({
      ...publicEnv,
      TASTEDUEL_CANDIDATE_ID_TOKEN: "SYNTHETIC",
    }),
  );
});
test("public verification rejects missing or unreviewed private API destinations", () => {
  assert.throws(() =>
    cloudBrowserAccess({
      ...publicEnv,
      TASTEDUEL_CLOUD_PRIVATE_API_ORIGIN: undefined,
    }),
  );
  assert.throws(() =>
    cloudBrowserAccess({
      ...publicEnv,
      TASTEDUEL_CLOUD_PRIVATE_API_ORIGIN: "https://unrelated.run.app",
    }),
  );
});
for (const origin of [
  "http://localhost:3000",
  canonical + "/",
  canonical + "?test=1",
  "https://unrelated.run.app",
  "https://tasteduel-web-902056825143.asia-south1.run.app.evil.example",
]) {
  test(`unreviewed web origin is rejected: ${origin}`, () => {
    assert.throws(() =>
      cloudBrowserAccess({ ...privateEnv, TASTEDUEL_CANDIDATE_ORIGIN: origin }),
    );
  });
}
test("known private service tag requires exact separate review; public mode rejects it", () => {
  const tag = "https://reviewed---tasteduel-web-dfthmgvvaa-el.a.run.app";
  const env = { ...privateEnv, TASTEDUEL_CANDIDATE_ORIGIN: tag };
  assert.throws(() => cloudBrowserAccess(env));
  assert.equal(
    cloudBrowserAccess({ ...env, TASTEDUEL_CLOUD_REVIEWED_TAG_ORIGIN: tag })
      .origin,
    tag,
  );
  assert.throws(() =>
    cloudBrowserAccess({
      ...publicEnv,
      TASTEDUEL_CANDIDATE_ORIGIN: tag,
      TASTEDUEL_CLOUD_REVIEWED_TAG_ORIGIN: tag,
    }),
  );
});
test("invalid access mode cannot silently choose private or public", () => {
  assert.throws(() =>
    cloudBrowserAccess({ ...privateEnv, TASTEDUEL_CLOUD_ACCESS_MODE: "other" }),
  );
});
