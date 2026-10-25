/** Safe, aggregate presentation facts only. Never pass a private receipt/pool. */
export type CurationSummaryFacts = {
  mode: "fixture" | "genuine-agent" | "deterministic-qloo";
  targetDomain: "movies" | "music-artists";
  candidatesEvaluated: number;
  // Mutually exclusive first-rejection reasons; their sum is unique rejected candidates.
  rejections: {
    duplicate: number;
    ambiguous: number;
    tied: number;
    missingMetadata: number;
  };
  correctionCount: number;
  fiveRoundPathVerified: boolean;
};

// Explicit projection: extra properties are not serialized or rendered.
export function summarizeCuration(facts: CurationSummaryFacts) {
  const counts = [
    facts.candidatesEvaluated,
    facts.correctionCount,
    facts.rejections.duplicate,
    facts.rejections.ambiguous,
    facts.rejections.tied,
    facts.rejections.missingMetadata,
  ];
  if (!counts.every((count) => Number.isSafeInteger(count) && count >= 0))
    return null;
  const rejected = counts.slice(2).reduce((sum, count) => sum + count, 0);
  if (rejected > facts.candidatesEvaluated) return null;
  const mode = {
    fixture: "Synthetic fixture curation",
    "genuine-agent": "Agent curation",
    "deterministic-qloo": "Deterministic Qloo curation",
  }[facts.mode];
  const domain = { movies: "Film", "music-artists": "Music artist" }[
    facts.targetDomain
  ];
  if (!mode || !domain || typeof facts.fiveRoundPathVerified !== "boolean")
    return null;
  return {
    mode,
    domain,
    checked: facts.candidatesEvaluated,
    rejected,
    correctionCount: facts.correctionCount,
    rejectionSentence: `${facts.rejections.duplicate} duplicate, ${facts.rejections.ambiguous} ambiguous, ${facts.rejections.tied} tied, ${facts.rejections.missingMetadata} missing metadata`,
    path: facts.fiveRoundPathVerified
      ? "Five-round path checked"
      : "Five-round path not verified",
  };
}
