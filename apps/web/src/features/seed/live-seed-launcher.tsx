"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button as ActionButton } from "@/components/ui/button";
import { LiveEntityCombobox } from "./live-entity-combobox";
import { api, ApiError, ensureSession } from "@/lib/api/client";
import type {
  ApiSchemas,
  EntityPublic,
  EntitySearchPublic,
  GamePublic,
  GameGenerationPendingPublic,
} from "@/lib/api/contracts";
import {
  associateGenerationGame,
  clearGenerationIntent,
  intentFor,
  readGenerationIntent,
  type GenerationIntent,
} from "./generation-intent";

type SearchState = {
  kind: "idle" | "loading" | "ready" | "error";
  data?: EntitySearchPublic;
  message?: string;
};

export function LiveSeedLauncher() {
  const router = useRouter();
  const [type, setType] = useState<"artist" | "movie">("artist");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<EntityPublic | null>(null);
  const [search, setSearch] = useState<SearchState>({ kind: "idle" });
  const [retry, setRetry] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [recovery, setRecovery] = useState<GenerationIntent>();
  const [hydrated, setHydrated] = useState(false);
  const revision = useRef(0);
  const searchAbort = useRef<AbortController | undefined>(undefined);
  const submitAbort = useRef<AbortController | undefined>(undefined);
  const lock = useRef(false);
  const activeIntent = useRef<GenerationIntent | undefined>(undefined);
  useEffect(() => {
    setRecovery(readGenerationIntent());
    setHydrated(true);
    if (!submitAbort.current || submitAbort.current.signal.aborted) {
      submitAbort.current = undefined;
      lock.current = false;
      setPending(false);
    }
    return () => {
      submitAbort.current?.abort();
    };
  }, []);

  function invalidateSearch() {
    revision.current += 1;
    searchAbort.current?.abort();
    setSearch({ kind: "idle" });
  }
  useEffect(() => {
    const term = query.trim();
    if (selected?.name === query || term.length < 2) return;
    const current = ++revision.current;
    const controller = new AbortController();
    searchAbort.current = controller;
    setSearch({ kind: "loading" });
    const timer = setTimeout(async () => {
      try {
        await ensureSession(controller.signal);
        const params = new URLSearchParams({ q: term, type, limit: "10" });
        const data = await api.get<EntitySearchPublic>(
          `/entities/search?${params}`,
          controller.signal,
        );
        if (!controller.signal.aborted && current === revision.current)
          setSearch({ kind: "ready", data });
      } catch (failure) {
        if (!controller.signal.aborted && current === revision.current)
          setSearch({
            kind: "error",
            message:
              failure instanceof ApiError
                ? failure.message
                : "Search is unavailable. Try again.",
          });
      }
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, selected, type, retry]);

  async function start(saved?: GenerationIntent) {
    if (lock.current || (!selected && !saved)) return;
    lock.current = true;
    const controller = new AbortController();
    submitAbort.current = controller;
    setPending(true);
    setError("");
    invalidateSearch();
    const body: ApiSchemas["CreateGameRequest"] = saved?.body ?? {
      seed_entity_id: selected!.id,
      seed_type: selected!.type,
      mode: "solo",
    };
    const intent =
      saved ??
      (activeIntent.current?.body.seed_entity_id === body.seed_entity_id &&
      activeIntent.current.body.seed_type === body.seed_type
        ? activeIntent.current
        : intentFor(body));
    activeIntent.current = intent;
    setRecovery(intent);
    try {
      await ensureSession(controller.signal);
      if (controller.signal.aborted) return;
      const result = await api.post<GamePublic | GameGenerationPendingPublic>(
        "/games",
        intent.body,
        intent.key,
        controller.signal,
      );
      if (controller.signal.aborted || submitAbort.current !== controller)
        return;
      if ("phase" in result) {
        clearGenerationIntent();
        activeIntent.current = undefined;
        setRecovery(undefined);
      } else associateGenerationGame(result.game_id);
      router.push(`/g/${result.game_id}`);
    } catch (failure) {
      if (controller.signal.aborted || submitAbort.current !== controller)
        return;
      setError(
        failure instanceof ApiError
          ? failure.message
          : "The response was interrupted. Retry this same duel safely.",
      );
    } finally {
      if (submitAbort.current === controller) {
        submitAbort.current = undefined;
        lock.current = false;
        if (!controller.signal.aborted) setPending(false);
      }
    }
  }

  // Retain a committed identity in the controlled collection until input changes.
  const results = selected ? [selected] : (search.data?.results ?? []);
  return (
    <div className="seed-launcher" aria-busy={pending || !hydrated}>
      <fieldset className="live-seed-types" disabled={pending || !hydrated}>
        <legend className="seed-label">Favourite type</legend>
        {(
          [
            ["artist", "Music artist"],
            ["movie", "Film"],
          ] as const
        ).map(([value, label]) => (
          <label key={value}>
            <input
              type="radio"
              name="seed-type"
              value={value}
              checked={type === value}
              onChange={() => {
                invalidateSearch();
                setType(value);
                setSelected(null);
                setQuery("");
                setError("");
              }}
            />
            {label}
          </label>
        ))}
      </fieldset>
      <LiveEntityCombobox
        query={query}
        type={type}
        selected={selected}
        choices={results}
        disabled={pending || !hydrated}
        unavailable={
          search.kind === "error" ||
          search.data?.status === "unavailable" ||
          search.data?.status === "empty"
        }
        onQuery={(value) => {
          if (value === query) return;
          invalidateSearch();
          setQuery(value);
          setError("");
          if (value !== selected?.name) setSelected(null);
        }}
        onSelect={(entity) => {
          invalidateSearch();
          setSelected(entity);
          setQuery(entity.name);
          setError("");
        }}
      />
      <p id="live-seed-help" className="seed-help">
        Choose the exact Qloo entity. Search coverage varies; a matching name
        does not guarantee five valid rounds.
      </p>
      <div className="selection-note" role="status" aria-live="polite">
        {!hydrated && "Preparing search…"}
        {search.kind === "loading" && "Searching Qloo…"}
        {search.data?.status === "needs_input" &&
          "Several matches. Choose the intended entity."}
        {search.data?.status === "partial" &&
          "Partial search results. Choose a verified match or retry."}
        {search.data?.status === "unavailable" &&
          "Qloo search is unavailable. Try again shortly."}
        {search.kind === "ready" &&
          search.data?.status === "empty" &&
          "No verified match. Try another name."}
      </div>
      {(search.kind === "error" || search.data?.status === "unavailable") && (
        <div className="fixture-notice">
          <p role="alert">
            {search.message ?? "Search is temporarily unavailable."}
          </p>
          <ActionButton
            variant="secondary"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry search
          </ActionButton>
        </div>
      )}
      {selected && (
        <section
          className="fixture-confirmation"
          aria-labelledby="live-confirm-seed"
        >
          <h2 id="live-confirm-seed">Confirm your seed</h2>
          <p>
            <strong>{selected.name}</strong> ·{" "}
            {selected.type === "artist" ? "Music artist" : "Film"} · Qloo
          </p>
          {selected.disambiguation && <p>{selected.disambiguation}</p>}
        </section>
      )}
      <div className="launch-actions">
        <ActionButton
          data-testid="start-duel"
          disabled={!selected || pending}
          onClick={() => void start()}
        >
          {pending ? "Preparing verified duels…" : "Start Qloo duel"}
          <span aria-hidden="true">↗</span>
        </ActionButton>
        <span className="launch-note">
          Five Qloo-backed predictions.
          <br />
          No account. Your taste is never graded.
        </span>
      </div>
      {pending && (
        <p className="selection-note" role="status">
          Preparing a Qloo-grounded pool. You will receive a game only after its
          five-round path is validated and saved.
        </p>
      )}
      {error && (
        <p className="fixture-notice" role="alert">
          {error}
        </p>
      )}
      {recovery && !pending && (
        <div className="live-recovery">
          <p className="seed-help">
            An unfinished request is saved in this tab. Retry to recover its
            authoritative result.
          </p>
          <ActionButton
            variant="secondary"
            onClick={() => void start(recovery)}
          >
            Recover unfinished request
          </ActionButton>
        </div>
      )}
    </div>
  );
}
