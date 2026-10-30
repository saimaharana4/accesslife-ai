import test from "node:test";
import assert from "node:assert/strict";
import { createResponseAudit } from "./cloud-response-audit.mjs";

test("an unavailable body never passes without its exact accepted response being inspected", () => {
  const audit = createResponseAudit("SYNTHETIC_OPERATOR_TOKEN");
  assert.equal(audit.unavailable("unconfirmed"), false);
  assert.deepEqual(audit.findings, ["unavailable API response body"]);
});
test("controlled response loss is permitted only after successful public-body inspection", () => {
  const audit = createResponseAudit("SYNTHETIC_OPERATOR_TOKEN");
  assert.equal(
    audit.confirmControlled(
      "synthetic-answer",
      JSON.stringify({ state: "revealed", winning_choice_id: "synthetic" }),
    ),
    true,
  );
  assert.equal(audit.unavailable("synthetic-answer"), true);
  assert.equal(audit.confirmedControlled, 1);
  assert.equal(audit.expectedUnavailable, 1);
  assert.deepEqual(audit.findings, []);
});
for (const [name, body] of [
  ["malformed", "<html>upstream error</html>"],
  [
    "pre-answer winner",
    JSON.stringify({
      current_round: { state: "unanswered", winning_choice_id: "synthetic" },
    }),
  ],
  ["hidden reasoning", JSON.stringify({ chain_of_thought: "synthetic" })],
  ["unused pool", JSON.stringify({ private_pool: [] })],
  ["credential echo", JSON.stringify({ token: "SYNTHETIC_OPERATOR_TOKEN" })],
])
  test(`${name} cannot become an accepted controlled-loss exception`, () => {
    const audit = createResponseAudit("SYNTHETIC_OPERATOR_TOKEN");
    assert.equal(audit.confirmControlled("synthetic", body), false);
    assert.equal(audit.unavailable("synthetic"), false);
    assert.ok(audit.findings.length >= 2);
  });
