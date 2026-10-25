import type { Ref } from "react";
import { Button } from "@/components/ui/button";
import { DiscoveryActions } from "../discoveries/discovery-actions";
import type { FixtureChoice } from "../fixtures/types.ts";
import { WhyThisDuel } from "./why-this-duel";
import type { AcceptedDuelEvidence } from "./evidence";
import { CurationSummary } from "../curation/curation-summary";
import type { CurationSummaryFacts } from "../curation/summary";

type RoundRevealProps = {
  correct: boolean;
  winnerTitle: string;
  ordinal: number;
  pending: boolean;
  headingRef: Ref<HTMLHeadingElement>;
  choices: readonly FixtureChoice[];
  savedIds: readonly string[];
  evidence: AcceptedDuelEvidence;
  curation?: CurationSummaryFacts;
  onSave(choice: FixtureChoice): void;
  onNext(): void;
};

/** The parent focuses the heading once. There is intentionally no live region. */
export function RoundReveal({
  correct,
  winnerTitle,
  ordinal,
  pending,
  headingRef,
  choices,
  savedIds,
  evidence,
  curation,
  onSave,
  onNext,
}: RoundRevealProps) {
  return (
    <div className="round-feedback" data-testid="reveal-panel">
      <div>
        <p className="feedback-status" id="fixture-outcome">
          {correct ? "✓ MATCHED THE FIXTURE" : "↗ DIFFERENT PREDICTION"}
        </p>
        <h2
          className="feedback-title"
          tabIndex={-1}
          ref={headingRef}
          aria-describedby="fixture-outcome"
        >
          {winnerTitle} ranks higher.
        </h2>
        <p className="feedback-copy">
          An invented result for this fixture. It is not Qloo output or a
          judgment of your taste.
        </p>
        <WhyThisDuel
          evidence={evidence}
          discoveryAction={
            <DiscoveryActions
              choices={choices}
              savedIds={savedIds}
              disabled={pending}
              onToggle={onSave}
            />
          }
        >
          {curation && <CurationSummary facts={curation} />}
        </WhyThisDuel>
      </div>
      <Button
        data-testid="next-action"
        pending={pending}
        pendingLabel={
          ordinal === 5 ? "Opening your result…" : "Opening next round…"
        }
        onClick={onNext}
      >
        {ordinal === 5 ? "View result" : "Next round"}{" "}
        <span aria-hidden="true">↗</span>
      </Button>
    </div>
  );
}
