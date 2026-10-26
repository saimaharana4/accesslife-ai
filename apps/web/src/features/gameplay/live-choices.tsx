import type { ApiSchemas } from "@/lib/api/contracts";
import { Artwork } from "@/features/duel/artwork";
import { choiceArtwork } from "./presentation";

export function LiveChoices({
  round,
  selectedId,
  disabled,
  onChoose,
}: {
  round: ApiSchemas["PlayableRoundPublic"] | ApiSchemas["RevealedRoundPublic"];
  selectedId?: string;
  disabled: boolean;
  onChoose(id: string): void;
}) {
  const winner =
    round.state === "revealed" ? round.winning_choice_id : undefined;
  return (
    <div
      className="choice-pair"
      aria-label={`Two ${round.target_type === "movie" ? "films" : "music artists"}`}
    >
      {round.choices.map((choice, index) => {
        const artwork = choiceArtwork(choice.id, choice.entity.artwork);
        return (
          <div className="choice-slot" key={choice.id}>
            {index === 1 && (
              <span className="duel-seam" aria-hidden="true">
                DUEL
              </span>
            )}
            <button
              type="button"
              className={`choice-card${selectedId === choice.id ? " is-selected" : ""}${winner === choice.id ? " is-winner" : ""}${winner && winner !== choice.id ? " is-muted" : ""}`}
              data-testid="choice-card"
              disabled={disabled}
              aria-pressed={selectedId === choice.id}
              onClick={() => onChoose(choice.id)}
            >
              <Artwork src={artwork} title={choice.entity.name} />
              <span className="choice-info">
                <span className="choice-kind">
                  {choice.entity.type === "movie" ? "FILM" : "MUSIC ARTIST"}{" "}
                  <span aria-hidden="true">{index === 0 ? "A" : "B"}</span>
                </span>
                <strong className="choice-title">{choice.entity.name}</strong>
                <span className="choice-year">
                  Original title card ·{" "}
                  {round.source === "fixture"
                    ? "synthetic fixture"
                    : "Qloo entity"}
                </span>
                <span className="choice-selection">
                  {selectedId === choice.id ? (
                    "Your prediction"
                  ) : disabled ? (
                    "Other choice"
                  ) : (
                    <>
                      Make your prediction <span aria-hidden="true">↗</span>
                    </>
                  )}
                </span>
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
