import { Artwork } from "./artwork";
import type { FixtureRound } from "../fixtures/types.ts";

type ChoicePairProps = {
  round: FixtureRound;
  selectedId?: string;
  winnerId?: string;
  disabled: boolean;
  missingFirst?: boolean;
  onChoose(choiceId: string): void;
};

/** Choices and styling only; this component does not choose a winner. */
export function ChoicePair({
  round,
  selectedId,
  winnerId,
  disabled,
  missingFirst = false,
  onChoose,
}: ChoicePairProps) {
  return (
    <div className="choice-pair" aria-label="Two fictional films">
      {round.choices.map((choice, index) => (
        <div className="choice-slot" key={choice.id}>
          {index === 1 && (
            <span className="duel-seam" aria-hidden="true">
              DUEL
            </span>
          )}
          <button
            type="button"
            className={`choice-card${selectedId === choice.id ? " is-selected" : ""}${winnerId === choice.id ? " is-winner" : ""}${winnerId && winnerId !== choice.id ? " is-muted" : ""}`}
            data-testid="choice-card"
            disabled={disabled}
            aria-pressed={selectedId === choice.id}
            onClick={() => onChoose(choice.id)}
          >
            <Artwork
              src={choice.art}
              title={choice.title}
              missing={missingFirst && index === 0}
            />
            <span className="choice-info">
              <span className="choice-kind">
                FICTIONAL FILM{" "}
                <span aria-hidden="true">{index === 0 ? "A" : "B"}</span>
              </span>
              <strong className="choice-title">{choice.title}</strong>
              <span className="choice-year">
                Invented work · original cover art
              </span>
              <span className="choice-selection">
                {!disabled ? (
                  <>
                    Make your prediction <span aria-hidden="true">↗</span>
                  </>
                ) : selectedId === choice.id ? (
                  "Your selection"
                ) : (
                  "Other choice"
                )}
              </span>
            </span>
          </button>
        </div>
      ))}
    </div>
  );
}
