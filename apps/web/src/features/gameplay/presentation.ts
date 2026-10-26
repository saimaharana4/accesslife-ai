import type { components } from "../../lib/api/schema.d.ts";

type Schemas = components["schemas"];

export function sourceLabel(
  source: Schemas["RankingSource"],
  mode: Schemas["CuratorMode"],
) {
  if (source === "fixture" || mode === "fixture")
    return "DEVELOPMENT FIXTURE · NO LIVE QLOO";
  return mode === "genuine_agent"
    ? "QLOO · AGENT CURATED"
    : "QLOO · DETERMINISTIC CURATOR";
}

// Image metadata is not permission. Only reviewed project-owned IDs are rendered.
const OWNED_ART: Readonly<Record<string, string>> = {
  afterlight: "/art/afterlight.svg",
  "velvet-static": "/art/velvet-static.svg",
  "blue-hour": "/art/blue-hour.svg",
  "slow-burn": "/art/slow-burn.svg",
};
const OWNED_COMPOSITIONS = [
  "/art/afterlight.svg",
  "/art/velvet-static.svg",
  "/art/blue-hour.svg",
  "/art/slow-burn.svg",
] as const;
export function ownedArtwork(
  artwork: Schemas["ArtworkPublic"] | null | undefined,
) {
  return artwork?.kind === "owned_fallback" &&
    Object.hasOwn(OWNED_ART, artwork.asset_id)
    ? OWNED_ART[artwork.asset_id]
    : undefined;
}

/** An opaque delivered choice ID selects decoration, independently of ranking. */
export function choiceArtwork(
  choiceId: string,
  artwork: Schemas["ArtworkPublic"] | null | undefined,
) {
  const reviewed = ownedArtwork(artwork);
  if (reviewed) return reviewed;
  let hash = 2166136261;
  for (let index = 0; index < choiceId.length; index++) {
    hash = Math.imul(hash ^ choiceId.charCodeAt(index), 16777619);
  }
  return OWNED_COMPOSITIONS[(hash >>> 0) % OWNED_COMPOSITIONS.length];
}

export function revealEvidence(round: Schemas["RevealedRoundPublic"]) {
  const winner = round.choices.find(
    (choice) => choice.id === round.winning_choice_id,
  );
  if (!winner) return null;
  const fixture = round.source === "fixture";
  return {
    status: "accepted" as const,
    source: {
      kind: fixture ? ("fixture" as const) : ("qloo" as const),
      label: fixture
        ? "Synthetic server fixture"
        : "Qloo · frozen request-specific ranking",
    },
    rankingContextSentence: fixture
      ? `In this synthetic fixture, ${winner.entity.name} ranked higher for ${round.seed.name}. No Qloo request established this result.`
      : `Qloo ranked ${winner.entity.name} higher for ${round.seed.name} in this frozen ${round.target_type === "movie" ? "movie" : "music-artist"} query. This is a ranking prediction, not a judgment of your personal taste.`,
    // Richer evidence stays withheld until its semantics and display rights pass review.
  };
}
