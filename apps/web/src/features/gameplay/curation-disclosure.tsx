import type { ApiSchemas } from "@/lib/api/contracts";

const REASONS: Readonly<Record<string, string>> = {
  invalid_identity: "unverified identity",
  wrong_type: "different entity type",
  self_pair: "seed repeated",
  duplicate_entity: "duplicate entity",
  missing_score: "missing ranking evidence",
  nonfinite_score: "invalid ranking evidence",
  score_tie: "tied comparison",
  near_tie: "near-tied comparison",
  contradictory_order: "contradictory ordering",
  insufficient_metadata: "incomplete metadata",
  unsupported_rights: "unsupported usage rights",
};

/** Only a completed-game public projection is accepted, never a private receipt. */
export function CurationDisclosure({
  summary,
}: {
  summary: ApiSchemas["CurationSummaryPublic"];
}) {
  const fixture =
    summary.source === "fixture" || summary.curator_mode === "fixture";
  const reasons = Object.entries(summary.rejection_counts).filter(
    ([key, count]) =>
      Object.hasOwn(REASONS, key) && Number.isSafeInteger(count) && count > 0,
  );
  return (
    <details className="why-this-duel" data-testid="curation-disclosure">
      <summary>
        {fixture ? "About this synthetic fixture" : "Curated with Qloo"}
      </summary>
      <div className="duel-evidence">
        <p className="evidence-source">
          {fixture
            ? "SYNTHETIC FIXTURE · NO LIVE QLOO"
            : "QLOO · CULTURAL RANKING SOURCE"}
        </p>
        <p>
          {fixture
            ? "Prewritten test evidence, not real cultural ranking."
            : summary.curator_mode === "genuine_agent"
              ? "A bounded agent selected the curation strategy. Deterministic validators controlled eligibility and winners."
              : "A deterministic curator constructed this journey from Qloo evidence. No live agent is claimed."}
        </p>
        <p>
          {summary.candidate_count_received} candidates evaluated ·{" "}
          {summary.target_domains
            .map((domain) => (domain === "movie" ? "Film" : "Music artist"))
            .join(" / ")}{" "}
          rounds · {summary.bounded_correction_count} bounded corrections.
        </p>
        {reasons.length > 0 && (
          <p>
            Validation exclusions:{" "}
            {reasons
              .map(([key, count]) => `${count} ${REASONS[key]}`)
              .join("; ")}
            . Counts show primary validation exclusions.
          </p>
        )}
        <p>
          {summary.five_round_path_verified
            ? "A complete five-round path without repeated contestants was verified."
            : "A complete five-round path was not verified."}
        </p>
      </div>
    </details>
  );
}
