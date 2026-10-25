import type { AcceptedDuelEvidence } from "../reveal/evidence.ts";
import type { CurationSummaryFacts } from "../curation/summary.ts";
import { createFixtureRounds } from "./fixture-data.ts";
import type { FixtureState } from "./types.ts";

/** Current accepted round only. Never accepts the unused round pool. */
export function fixtureDisclosure(
  state: FixtureState,
): AcceptedDuelEvidence | undefined {
  if (state.kind !== "revealed" && state.kind !== "advancing") return undefined;
  return {
    status: "accepted",
    source: { kind: "fixture", label: "Local invented ranking · no live Qloo" },
    rankingContextSentence: `For the fictional seed ${state.game.seed.name}, this round's prewritten film comparison places ${state.answer.winnerTitle} higher. It is a synthetic answer key, not a Qloo ranking.`,
  };
}

export function fixtureCurationSummary(): CurationSummaryFacts {
  const rounds = createFixtureRounds();
  const ids = new Set(
    rounds.flatMap((round) => round.choices.map((choice) => choice.id)),
  );
  return {
    mode: "fixture",
    targetDomain: "movies",
    candidatesEvaluated: ids.size,
    rejections: { duplicate: 0, ambiguous: 0, tied: 0, missingMetadata: 0 },
    correctionCount: 0,
    fiveRoundPathVerified: rounds.length === 5 && ids.size === 10,
  };
}
