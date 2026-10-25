import { Button } from "@/components/ui/button";
import type { FixtureChoice } from "../fixtures/types.ts";

export function DiscoveryActions({
  choices,
  savedIds,
  disabled = false,
  onToggle,
}: {
  choices: readonly FixtureChoice[];
  savedIds: readonly string[];
  disabled?: boolean;
  onToggle(choice: FixtureChoice): void;
}) {
  return (
    <div className="fixture-toolbar">
      {choices.map((choice) => (
        <Button
          key={choice.id}
          variant="quiet"
          className="discovery-toggle"
          disabled={disabled}
          aria-pressed={savedIds.includes(choice.id)}
          onClick={() => onToggle(choice)}
        >
          {savedIds.includes(choice.id) ? "Unsave" : "Save"} {choice.title}
        </Button>
      ))}
    </div>
  );
}
