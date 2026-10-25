import type { ReactNode } from "react";
import type { AcceptedDuelEvidence } from "./evidence";

/** No fetching or cultural inference. The caller owns accepted-answer gating. */
export function WhyThisDuel({
  evidence,
  discoveryAction,
  children,
}: {
  evidence: AcceptedDuelEvidence;
  discoveryAction?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <details className="why-this-duel" data-testid="why-this-duel">
      <summary data-testid="why-this-duel-toggle">Why this duel?</summary>
      <div className="duel-evidence" data-testid="duel-evidence">
        <p className="evidence-source">
          {evidence.source.kind === "fixture"
            ? "SYNTHETIC FIXTURE EVIDENCE"
            : "RANKING SOURCE"}{" "}
          · {evidence.source.label}
        </p>
        <p>{evidence.rankingContextSentence}</p>
        {evidence.supportedExplanation && (
          <blockquote>
            <p>{evidence.supportedExplanation.text}</p>
            <cite>{evidence.supportedExplanation.attribution}</cite>
          </blockquote>
        )}
        {evidence.source.kind === "fixture" && (
          <p>
            No Qloo or model was called. This demonstrates a reveal, not a
            cultural explanation.
          </p>
        )}
        {children}
        {discoveryAction}
      </div>
    </details>
  );
}
