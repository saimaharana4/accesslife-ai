import assert from "node:assert/strict";
import test from "node:test";
import type { components } from "../../lib/api/schema.d.ts";
import {
  mutationResolved,
  mutationStorageKey,
  readPendingMutation,
} from "./mutation.ts";

type S = components["schemas"];
const id = (n: number) =>
  `a3d90634-1126-406d-b08c-${String(n).padStart(12, "0")}`;
const answer = {
  kind: "answer" as const,
  key: id(1),
  body: { round_id: id(2), choice_id: id(3), expected_revision: 4 },
};
const advance = {
  kind: "advance" as const,
  key: id(5),
  body: { answered_round_id: id(2), expected_revision: 5 },
};
function game(
  state: "unanswered" | "revealed",
  roundId = id(2),
  phase = "playing",
): S["GamePublic"] {
  // This test exercises only projection settlement; no answer key/pool is needed.
  return {
    game_id: id(10),
    phase,
    current_round: { round_id: roundId, state },
  } as S["GamePublic"];
}

test("uncertain mutation retains the same key/body without storing server answer data", () => {
  assert.deepEqual(readPendingMutation(JSON.stringify(answer)), answer);
  assert.deepEqual(readPendingMutation(JSON.stringify(advance)), advance);
  assert.equal(mutationStorageKey(id(10)), `tasteduel:mutation:v1:${id(10)}`);
});

test("storage is explicitly projected rather than trusting extra persisted properties", () => {
  const parsed = readPendingMutation(
    JSON.stringify({
      ...answer,
      winning_choice_id: "forbidden",
      body: { ...answer.body, affinity: 999 },
    }),
  );
  assert.deepEqual(parsed, answer);
  assert.doesNotMatch(JSON.stringify(parsed), /winning|affinity/);
});

test("invalid, oversized or older storage never creates a mutation", () => {
  for (const raw of [
    null,
    "null",
    "{}",
    "[1]",
    "not json",
    "x".repeat(1001),
    JSON.stringify({ ...answer, key: "malicious/path" }),
    JSON.stringify({ ...answer, key: [answer.key] }),
    JSON.stringify({ ...answer, key: `${answer.key}\n` }),
    JSON.stringify({
      ...answer,
      body: { ...answer.body, expected_revision: -1 },
    }),
    JSON.stringify({
      ...answer,
      body: { ...answer.body, expected_revision: 1.2 },
    }),
    JSON.stringify({
      ...answer,
      body: { ...answer.body, choice_id: "http://127.0.0.1" },
    }),
  ]) {
    assert.equal(readPendingMutation(raw), null);
  }
});

test("lost answer response is settled by accepted reveal or server advancement", () => {
  assert.equal(mutationResolved(answer, game("unanswered")), false);
  assert.equal(mutationResolved(answer, game("revealed")), true);
  assert.equal(mutationResolved(answer, game("unanswered", id(8))), true);
});

test("Next remains uncertain until a new round or completed state is observed", () => {
  assert.equal(mutationResolved(advance, game("revealed")), false);
  assert.equal(mutationResolved(advance, game("unanswered", id(8))), true);
  assert.equal(
    mutationResolved(advance, game("revealed", id(2), "completed")),
    true,
  );
});

test("absent current round does not infer an accepted answer", () => {
  const saved = { ...game("unanswered"), current_round: null };
  assert.equal(mutationResolved(answer, saved), false);
  assert.equal(mutationResolved(advance, saved), false);
});

test("a completed game settles final Next even without a current round DTO", () => {
  const saved = {
    ...game("revealed", id(2), "completed"),
    current_round: null,
  };
  assert.equal(mutationResolved(advance, saved), true);
  assert.equal(mutationResolved(answer, saved), true);
});
