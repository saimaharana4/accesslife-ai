import test from "node:test";
import assert from "node:assert/strict";
import { fixtureReducer, fixtureScore } from "./state.ts";
import { InMemoryFixtureTransport, FixtureFailure } from "./transport.ts";
import { createFixtureRounds } from "./fixture-data.ts";
import type { FixtureSeed, FixtureState } from "./types.ts";

const seed: FixtureSeed = {
  id: "test-seed",
  name: "Invented Test Seed",
  type: "Music artist",
  detail: "Synthetic only",
};

test("ten unique invented contestants, same-type pairs and no copied provider identities", () => {
  const rounds = createFixtureRounds();
  assert.equal(rounds.length, 5);
  assert.equal(
    new Set(rounds.flatMap((round) => round.choices.map((choice) => choice.id)))
      .size,
    10,
  );
  assert.ok(
    rounds.every((round) =>
      round.choices.every((choice) => choice.kind === "Fictional film"),
    ),
  );
});

test("five accepted first-card answers compute three points, never a specimen score", async () => {
  const adapter = new InMemoryFixtureTransport(0);
  const first = await adapter.start(seed, "normal", "start");
  assert.equal(first.kind, "ready");
  if (first.kind !== "ready") return;
  let state: FixtureState = { kind: "idle" };
  state = fixtureReducer(state, {
    type: "START",
    operation: 1,
    seed,
    story: "normal",
    key: "start",
  });
  state = fixtureReducer(state, {
    type: "STARTED",
    operation: 1,
    result: first,
  });
  for (let ordinal = 1; ordinal <= 5; ordinal++) {
    assert.equal(state.kind, "unanswered");
    if (state.kind !== "unanswered") throw Error("Expected round");
    const { game, round } = state;
    const op = ordinal * 2;
    state = fixtureReducer(state, {
      type: "ANSWER",
      operation: op,
      choiceId: round.choices[0].id,
      key: `a${ordinal}`,
    });
    const pending = state;
    assert.equal(
      fixtureReducer(state, {
        type: "ANSWER",
        operation: 999,
        choiceId: round.choices[1].id,
        key: "double",
      }),
      pending,
    );
    const answer = await adapter.answer(
      game.id,
      round.id,
      round.choices[0].id,
      `a${ordinal}`,
    );
    state = fixtureReducer(state, { type: "ANSWERED", operation: op, answer });
    const accepted = state;
    assert.equal(
      fixtureReducer(state, { type: "ANSWERED", operation: op, answer }),
      accepted,
    );
    assert.equal(
      "answers" in state && fixtureScore(state.answers),
      [1, 1, 2, 2, 3][ordinal - 1],
    );
    state = fixtureReducer(state, {
      type: "ADVANCE",
      operation: op + 1,
      key: `n${ordinal}`,
    });
    const next = await adapter.advance(game.id, round.id, `n${ordinal}`);
    assert.deepEqual(
      await adapter.advance(game.id, round.id, `n${ordinal}`),
      next,
    );
    state = fixtureReducer(state, {
      type: "ADVANCED",
      operation: op + 1,
      result: next,
    });
  }
  assert.equal(state.kind, "complete");
  assert.equal("answers" in state && state.answers.length, 5);
});

test("accepted answer with lost response retries once without duplicate points", async () => {
  const adapter = new InMemoryFixtureTransport(0);
  const first = await adapter.start(seed, "retry", "s");
  if (first.kind !== "ready") throw Error("Expected fixture");
  const choice = first.round.choices[0].id;
  await assert.rejects(
    adapter.answer(first.game.id, first.round.id, choice, "answer"),
    (error) => error instanceof FixtureFailure && error.kind === "retry",
  );
  const saved = await adapter.answer(
    first.game.id,
    first.round.id,
    choice,
    "answer",
  );
  assert.deepEqual(
    await adapter.answer(first.game.id, first.round.id, choice, "answer"),
    saved,
  );
  await assert.rejects(
    adapter.answer(
      first.game.id,
      first.round.id,
      first.round.choices[1].id,
      "answer",
    ),
  );
  await assert.rejects(
    adapter.answer(
      first.game.id,
      first.round.id,
      first.round.choices[1].id,
      "different",
    ),
  );
});

test("stale completion after cancellation/reset cannot replace a new generation", () => {
  const result = {
    kind: "ready" as const,
    game: { id: "old", seed, total: 5 as const, story: "normal" as const },
    round: createFixtureRounds()[0],
  };
  let state: FixtureState = fixtureReducer(
    { kind: "idle" },
    { type: "START", operation: 1, seed, story: "normal", key: "old" },
  );
  state = fixtureReducer(state, { type: "INTERRUPT" });
  const interrupted = state;
  assert.equal(
    fixtureReducer(state, { type: "STARTED", operation: 1, result }),
    interrupted,
  );
  state = fixtureReducer(state, { type: "RESET" });
  state = fixtureReducer(state, {
    type: "START",
    operation: 2,
    seed,
    story: "normal",
    key: "new",
  });
  assert.equal(
    fixtureReducer(state, { type: "STARTED", operation: 1, result }),
    state,
  );
});

test("empty/partial never silently become shortened games; changed idempotent input conflicts", async () => {
  const adapter = new InMemoryFixtureTransport(0);
  assert.deepEqual(await adapter.start(seed, "empty", "empty"), {
    kind: "empty",
    available: 0,
  });
  assert.deepEqual(await adapter.start(seed, "partial", "partial"), {
    kind: "partial",
    available: 3,
  });
  await assert.rejects(adapter.start(seed, "normal", "empty"));
});

test("aborted accepted answer can be recovered; advancing unanswered/future rounds is rejected", async () => {
  const adapter = new InMemoryFixtureTransport(0);
  const first = await adapter.start(seed, "normal", "s");
  if (first.kind !== "ready") throw Error("Expected fixture");
  await assert.rejects(adapter.advance(first.game.id, first.round.id, "early"));
  await assert.rejects(
    adapter.answer(
      first.game.id,
      "fixture-round-2",
      "fixture-entity-3",
      "future",
    ),
  );
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    adapter.answer(
      first.game.id,
      first.round.id,
      first.round.choices[0].id,
      "a",
      controller.signal,
    ),
  );
  const answer = await adapter.answer(
    first.game.id,
    first.round.id,
    first.round.choices[0].id,
    "a",
  );
  assert.equal(answer.ordinal, 1);
  assert.equal(answer.correct, true);
  const next = await adapter.advance(first.game.id, first.round.id, "next");
  assert.equal(next.kind, "round");
  await assert.rejects(
    adapter.advance(first.game.id, "fixture-round-2", "next"),
  );
});

test("response-loss recovery retains the same answer request and rejects a stale completion", async () => {
  const adapter = new InMemoryFixtureTransport(0);
  const first = await adapter.start(seed, "retry", "s");
  if (first.kind !== "ready") throw Error("Expected fixture");
  let state: FixtureState = fixtureReducer(
    { kind: "idle" },
    { type: "START", operation: 1, seed, story: "retry", key: "s" },
  );
  state = fixtureReducer(state, {
    type: "STARTED",
    operation: 1,
    result: first,
  });
  state = fixtureReducer(state, {
    type: "ANSWER",
    operation: 2,
    choiceId: first.round.choices[0].id,
    key: "same-answer",
  });
  await assert.rejects(
    adapter.answer(
      first.game.id,
      first.round.id,
      first.round.choices[0].id,
      "same-answer",
    ),
  );
  state = fixtureReducer(state, {
    type: "ISSUE",
    operation: 2,
    issue: "retry",
    message: "Lost fixture response",
  });
  assert.equal(state.kind, "issue");
  state = fixtureReducer(state, { type: "RETRY", operation: 3 });
  assert.equal(state.kind, "submitting");
  if (state.kind !== "submitting") throw Error("Expected retry");
  assert.equal(state.key, "same-answer");
  const answer = await adapter.answer(
    first.game.id,
    first.round.id,
    state.choiceId,
    state.key,
  );
  assert.equal(
    fixtureReducer(state, { type: "ANSWERED", operation: 2, answer }),
    state,
  );
  state = fixtureReducer(state, { type: "ANSWERED", operation: 3, answer });
  assert.equal(state.kind, "revealed");
  assert.equal("answers" in state && fixtureScore(state.answers), 1);
});

test("discovery save/unsave changes only local discoveries, never accepted score", () => {
  const round = createFixtureRounds()[0];
  const game = { id: "g", seed, total: 5 as const, story: "normal" as const };
  const answer = {
    roundId: round.id,
    ordinal: 1,
    choiceId: round.choices[0].id,
    winnerId: round.choices[0].id,
    correct: true,
    winnerTitle: round.choices[0].title,
    selectedTitle: round.choices[0].title,
  };
  let state: FixtureState = {
    kind: "revealed",
    game,
    round,
    answers: [answer],
    answer,
    discoveries: [],
  };
  state = fixtureReducer(state, { type: "SAVE", choice: round.choices[1] });
  assert.equal("discoveries" in state && state.discoveries.length, 1);
  state = fixtureReducer(state, { type: "SAVE", choice: round.choices[1] });
  assert.equal("discoveries" in state && state.discoveries.length, 0);
  assert.equal("answers" in state && fixtureScore(state.answers), 1);
});
