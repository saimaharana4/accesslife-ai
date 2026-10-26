import assert from "node:assert/strict";
import test from "node:test";
import type { components } from "../../lib/api/schema.d.ts";
import {
  choiceArtwork,
  ownedArtwork,
  revealEvidence,
  sourceLabel,
} from "./presentation.ts";

type S = components["schemas"];
function reveal(source: "qloo" | "fixture"): S["RevealedRoundPublic"] {
  return {
    source,
    target_type: "movie",
    seed: { name: "Example seed" },
    winning_choice_id: "accepted-winner",
    choices: [
      { id: "accepted-winner", entity: { name: "Accepted entity" } },
      { id: "other", entity: { name: "Other entity" } },
    ],
    evidence: {
      supported_explanation: {
        text: "Unreviewed causal story must not appear",
      },
    },
  } as S["RevealedRoundPublic"];
}

test("artwork accepts only exact reviewed owned IDs, never URL or prototype properties", () => {
  assert.equal(
    ownedArtwork({ kind: "owned_fallback", asset_id: "afterlight" }),
    "/art/afterlight.svg",
  );
  for (const asset_id of [
    "https://attacker.invalid/secret",
    "../secret",
    "constructor",
    "__proto__",
    "toString",
    "missing",
  ])
    assert.equal(ownedArtwork({ kind: "owned_fallback", asset_id }), undefined);
  assert.equal(
    ownedArtwork({ kind: "licensed", asset_id: "afterlight" }),
    undefined,
  );
  assert.equal(ownedArtwork(null), undefined);
});

test("missing provider artwork retains varied original composition independent of answer data", () => {
  const observed = new Set<string>();
  for (let index = 0; index < 100; index++) {
    const id = `c4f0e3ae-901c-42c7-ae71-${String(index).padStart(12, "0")}`;
    const path = choiceArtwork(id, null);
    observed.add(path);
    assert.match(
      path,
      /^\/art\/(afterlight|velvet-static|blue-hour|slow-burn)\.svg$/,
    );
    assert.equal(choiceArtwork(id, undefined), path);
    assert.equal(
      choiceArtwork(id, {
        kind: "licensed",
        asset_id: "https://unreviewed.invalid/image",
      }),
      path,
    );
    assert.equal(
      choiceArtwork(id, { kind: "owned_fallback", asset_id: "__proto__" }),
      path,
    );
  }
  assert.equal(observed.size, 4);
  assert.equal(
    choiceArtwork("opaque-choice", {
      kind: "owned_fallback",
      asset_id: "afterlight",
    }),
    "/art/afterlight.svg",
  );
});

test("reveals attribute only the accepted frozen ranking and withhold unreviewed rich explanations", () => {
  const evidence = revealEvidence(reveal("qloo"));
  assert.equal(evidence?.source.kind, "qloo");
  assert.match(
    evidence!.rankingContextSentence,
    /Qloo ranked Accepted entity higher for Example seed in this frozen movie query/,
  );
  assert.doesNotMatch(
    JSON.stringify(evidence),
    /causal story|affinity|Unreviewed/,
  );
  assert.match(
    evidence!.rankingContextSentence,
    /not a judgment of your personal taste/,
  );
});

test("fixture provenance cannot masquerade as a live Qloo result", () => {
  assert.match(sourceLabel("fixture", "genuine_agent"), /DEVELOPMENT FIXTURE/);
  assert.match(sourceLabel("qloo", "fixture"), /NO LIVE QLOO/);
  assert.match(sourceLabel("qloo", "genuine_agent"), /AGENT CURATED/);
  assert.match(
    sourceLabel("qloo", "deterministic_qloo"),
    /DETERMINISTIC CURATOR/,
  );
  assert.match(
    revealEvidence(reveal("fixture"))!.rankingContextSentence,
    /No Qloo request established this result/,
  );
});

test("inconsistent accepted winner renders no invented explanation", () => {
  assert.equal(
    revealEvidence({ ...reveal("qloo"), winning_choice_id: "unknown" }),
    null,
  );
});
