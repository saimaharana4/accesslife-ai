"use client";
import { Button } from "@/components/ui/button";
import type { ApiSchemas } from "@/lib/api/contracts";
import { useDiscoveries } from "./use-discoveries";

export function LiveDiscoveries({
  choices = [],
}: {
  choices?: ApiSchemas["ChoicePublic"][];
}) {
  const state = useDiscoveries();
  const entries = state.data?.discoveries ?? [];
  const entities = new Map(
    choices.map((choice) => [choice.entity.id, choice.entity]),
  );
  if (choices.length !== 2)
    for (const item of entries) entities.set(item.entity.id, item.entity);
  const compact = choices.length !== 2;
  const list = (values: ApiSchemas["EntityPublic"][]) => (
    <ul className="discovery-list">
      {values.map((entity) => (
        <li key={entity.id}>
          <span>
            <strong>{entity.name}</strong>
            <span className="discovery-kind">
              {entity.type === "movie" ? "Film" : "Music artist"}
              {state.saved(entity.id)
                ? " · Explicitly saved"
                : " · From your answered rounds"}
            </span>
          </span>
          <Button
            variant="secondary"
            data-testid={`save-discovery-${entity.id}`}
            aria-label={`${state.saved(entity.id) ? "Remove" : "Save"} discovery: ${entity.name}`}
            pending={state.pending === entity.id}
            disabled={state.loading || Boolean(state.pending)}
            onClick={() => void state.toggle(entity.id)}
          >
            {state.saved(entity.id) ? "Remove discovery" : "Save discovery"}
          </Button>
        </li>
      ))}
    </ul>
  );
  return (
    <section
      className="live-discoveries"
      data-testid="discoveries"
      aria-label="Your discoveries"
    >
      <h2>KEEP THE CONNECTION.</h2>
      <p>
        Save something you want to explore. A prediction is game performance;
        only an explicit save adds a discovery.
      </p>
      {state.loading && <p role="status">Checking saved discoveries…</p>}
      {!state.loading && !entries.length && (
        <p>
          {state.data?.expired_count
            ? "Earlier discoveries expired. Nothing remains saved in this guest session."
            : "No discoveries saved yet. Choose one to explore; either contestant can be interesting."}
        </p>
      )}
      {state.error && (
        <p role="status">
          {state.error}{" "}
          <Button variant="quiet" onClick={() => void state.refresh()}>
            Check saved discoveries
          </Button>
        </p>
      )}
      {!compact && list([...entities.values()])}
      {compact && list(entries.map((entry) => entry.entity))}
      {compact && choices.some((choice) => !state.saved(choice.entity.id)) && (
        <details className="discovery-explore">
          <summary>Explore answered choices</summary>
          {list(
            [...entities.values()].filter((entity) => !state.saved(entity.id)),
          )}
        </details>
      )}
      {state.data?.session_expires_at && (
        <p className="discovery-expiry">
          Guest session ends{" "}
          {new Date(state.data.session_expires_at).toLocaleString()}. Each save
          also expires with its supporting evidence; clearing this session
          removes access.
        </p>
      )}
      {entries.length > 0 && (
        <p className="discovery-expiry">
          Next saved discovery expires{" "}
          {new Date(
            Math.min(...entries.map((entry) => Date.parse(entry.expires_at))),
          ).toLocaleString()}
          .
        </p>
      )}
    </section>
  );
}
