import test from "node:test";
import assert from "node:assert/strict";
import { fixtureDisclosure, fixtureCurationSummary } from "./disclosure.ts";
import { summarizeCuration } from "../curation/summary.ts";
import { InMemoryFixtureTransport } from "./transport.ts";
import { fixtureReducer } from "./state.ts";
import type { FixtureSeed, FixtureState } from "./types.ts";

const seed: FixtureSeed = {
  id: "invented-seed",
  name: "Invented Seed",
  type: "Music artist",
  detail: "Synthetic",
};

test("evidence exists only for the current accepted answer, not preparation, pending or next round", async () => {
  const transport = new InMemoryFixtureTransport(0);
  let state: FixtureState = { kind: "idle" };
  assert.equal(fixtureDisclosure(state), undefined);
  state = fixtureReducer(state, {
    type: "START",
    operation: 1,
    seed,
    story: "normal",
    key: "s",
  });
  assert.equal(fixtureDisclosure(state), undefined);
  const first = await transport.start(seed, "normal", "s");
  if (first.kind !== "ready") throw Error("Expected fixture");
  state = fixtureReducer(state, {
    type: "STARTED",
    operation: 1,
    result: first,
  });
  assert.equal(fixtureDisclosure(state), undefined);
  state = fixtureReducer(state, {
    type: "ANSWER",
    operation: 2,
    choiceId: first.round.choices[0].id,
    key: "a",
  });
  assert.equal(fixtureDisclosure(state), undefined);
  const answer = await transport.answer(
    first.game.id,
    first.round.id,
    first.round.choices[0].id,
    "a",
  );
  state = fixtureReducer(state, { type: "ANSWERED", operation: 2, answer });
  const evidence = fixtureDisclosure(state);
  assert.equal(evidence?.status, "accepted");
  assert.equal(evidence?.source.kind, "fixture");
  assert.match(
    evidence!.rankingContextSentence,
    /synthetic answer key, not a Qloo ranking/,
  );
  assert.match(evidence!.rankingContextSentence, /Afterlight Assembly/);
  assert.equal(evidence?.supportedExplanation, undefined);
  const serialized = JSON.stringify(evidence);
  for (const hidden of [
    "The Slow Burn Society",
    "Lunar Paper Parade",
    "Atlas of Small Storms",
    "affinity",
    "winnerId",
    "rounds",
    "correct",
  ])
    assert.equal(serialized.includes(hidden), false);
  state = fixtureReducer(state, { type: "ADVANCE", operation: 3, key: "n" });
  const next = await transport.advance(first.game.id, first.round.id, "n");
  state = fixtureReducer(state, {
    type: "ADVANCED",
    operation: 3,
    result: next,
  });
  assert.equal(fixtureDisclosure(state), undefined);
});

test("curation summary projects safe aggregates and drops every extra private property", () => {
  const facts = fixtureCurationSummary();
  const view = summarizeCuration({
    ...facts,
    ...{
      winner: "PRIVATE",
      affinity: 0.88,
      futureContestants: ["PRIVATE"],
      chainOfThought: "PRIVATE",
      rawPayload: "PRIVATE",
    },
  });
  assert.deepEqual(view, {
    mode: "Synthetic fixture curation",
    domain: "Film",
    checked: 10,
    rejected: 0,
    correctionCount: 0,
    rejectionSentence: "0 duplicate, 0 ambiguous, 0 tied, 0 missing metadata",
    path: "Five-round path checked",
  });
  assert.equal(JSON.stringify(view).includes("PRIVATE"), false);
  assert.equal(summarizeCuration({ ...facts, candidatesEvaluated: NaN }), null);
  assert.equal(summarizeCuration({ ...facts, correctionCount: -1 }), null);
  assert.equal(
    summarizeCuration({
      ...facts,
      rejections: { ...facts.rejections, tied: 11 },
    }),
    null,
  );
});
