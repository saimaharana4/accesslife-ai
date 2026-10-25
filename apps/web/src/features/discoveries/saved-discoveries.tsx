import { Button } from "@/components/ui/button";
import { Artwork } from "../duel/artwork";
import type { FixtureChoice } from "../fixtures/types.ts";

export function SavedDiscoveries({
  discoveries,
  onToggle,
}: {
  discoveries: readonly FixtureChoice[];
  onToggle(choice: FixtureChoice): void;
}) {
  return (
    <section className="ticket-discoveries" aria-labelledby="discoveries-title">
      <h2 id="discoveries-title">Your discoveries</h2>
      {discoveries.length ? (
        discoveries.map((choice) => (
          <div className="ticket-discovery" key={choice.id}>
            <Artwork
              src={choice.art}
              title={choice.title}
              className="ticket-art"
            />
            <div>
              <h3>{choice.title}</h3>
              <p>Fictional film · saved in memory only</p>
              <Button variant="quiet" onClick={() => onToggle(choice)}>
                Unsave {choice.title}
              </Button>
            </div>
          </div>
        ))
      ) : (
        <p>
          No saved discoveries yet. Saving is optional; the five accepted
          answers are still shown above.
        </p>
      )}
    </section>
  );
}
