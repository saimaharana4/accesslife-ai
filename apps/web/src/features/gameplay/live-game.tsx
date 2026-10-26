"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ActionLink, Button } from "@/components/ui/button";
import { RoundPips } from "@/components/ui/round-pips";
import { StatusPanel } from "@/components/ui/status-panel";
import { WhyThisDuel } from "@/features/reveal/why-this-duel";
import { api, ApiError, createKey } from "@/lib/api/client";
import type { ApiSchemas } from "@/lib/api/contracts";
import {
  clearGenerationIntent,
  readGenerationIntent,
} from "@/features/seed/generation-intent";
import { CurationDisclosure } from "./curation-disclosure";
import { LiveChoices } from "./live-choices";
import {
  mutationResolved,
  mutationStorageKey,
  readPendingMutation,
  type PendingMutation,
} from "./mutation";
import { revealEvidence, sourceLabel } from "./presentation";
import { LiveDiscoveries } from "@/features/discoveries/live-discoveries";
import {
  publishSessionChange,
  subscribeSessionChanges,
} from "@/lib/api/session-events";

function problem(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 410)
      return "This game's evidence has expired. Choose a seed for a new game.";
    if (error.status === 401 || error.status === 404)
      return "This game is unavailable in this guest session. It may have expired or belong to another session.";
    if (error.status === 409)
      return "The saved game changed. Check its current state before continuing.";
    return error.message;
  }
  return "The response could not be confirmed. Check the saved game before retrying.";
}

/** The server owns progress, accepted answers and score. No future pool is loaded. */
export function LiveGame({ gameId }: { gameId: string }) {
  const router = useRouter();
  const [game, setGame] = useState<ApiSchemas["GamePublic"] | null>(null);
  const [generation, setGeneration] = useState<
    ApiSchemas["GenerationStatusPublic"] | null
  >(null);
  const [busy, setBusy] = useState<
    "load" | "answer" | "advance" | "generation" | null
  >("load");
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [pending, setPending] = useState<PendingMutation | null>(null);
  const pendingMemory = useRef<PendingMutation | null>(null);
  const locked = useRef(false);
  const request = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const question = useRef<HTMLHeadingElement>(null);
  const outcome = useRef<HTMLHeadingElement>(null);
  const focused = useRef("");
  const queuedRefresh = useRef(false);
  const reload = useRef<() => void>(() => {});

  const storePending = useCallback(
    (value: PendingMutation | null) => {
      pendingMemory.current = value;
      setPending(value);
      try {
        if (value)
          sessionStorage.setItem(
            mutationStorageKey(gameId),
            JSON.stringify(value),
          );
        else sessionStorage.removeItem(mutationStorageKey(gameId));
      } catch {
        /* In-memory retries still work when browser storage is disabled. */
      }
    },
    [gameId],
  );

  const acceptGame = useCallback(
    (saved: ApiSchemas["GamePublic"]) => {
      setGame(saved);
      setGeneration(null);
      if (readGenerationIntent()?.gameId === saved.game_id)
        clearGenerationIntent();
      let stored: PendingMutation | null = pendingMemory.current;
      try {
        stored =
          readPendingMutation(
            sessionStorage.getItem(mutationStorageKey(gameId)),
          ) ?? stored;
      } catch {
        /* optional storage */
      }
      if (stored && !mutationResolved(stored, saved)) {
        pendingMemory.current = stored;
        setPending(stored);
      } else storePending(null);
    },
    [gameId, storePending],
  );

  const load = useCallback(async () => {
    if (locked.current) return;
    locked.current = true;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy("load");
    setError(null);
    setExpired(false);
    try {
      const saved = await api.get<ApiSchemas["GamePublic"]>(
        `/games/${gameId}`,
        controller.signal,
      );
      if (!controller.signal.aborted && mounted.current) acceptGame(saved);
    } catch (failure) {
      if (controller.signal.aborted || !mounted.current) return;
      if (
        failure instanceof ApiError &&
        (failure.status === 404 ||
          (failure.status === 409 && failure.code === "GENERATION_IN_PROGRESS"))
      ) {
        setGame(null);
        try {
          const observed = await api.get<ApiSchemas["GenerationStatusPublic"]>(
            `/games/${gameId}/generation`,
            controller.signal,
          );
          if (!controller.signal.aborted && mounted.current)
            setGeneration(observed);
        } catch (observationFailure) {
          if (!controller.signal.aborted && mounted.current) {
            setError(problem(observationFailure));
            if (
              observationFailure instanceof ApiError &&
              observationFailure.status === 410
            )
              setExpired(true);
          }
        }
      } else {
        setError(problem(failure));
        if (
          failure instanceof ApiError &&
          [401, 410].includes(failure.status)
        ) {
          setGame(null);
          setExpired(failure.status === 410);
        }
      }
    } finally {
      if (request.current === controller) {
        if (!controller.signal.aborted && mounted.current) setBusy(null);
        locked.current = false;
        if (queuedRefresh.current && mounted.current) {
          queuedRefresh.current = false;
          setTimeout(() => reload.current(), 0);
        }
      }
    }
  }, [acceptGame, gameId]);
  reload.current = () => void load();

  useEffect(() => {
    mounted.current = true;
    setGame(null);
    setGeneration(null);
    setPending(null);
    pendingMemory.current = null;
    focused.current = "";
    void load();
    const resume = () => {
      if (!document.hidden) void load();
    };
    window.addEventListener("online", resume);
    window.addEventListener("pageshow", resume);
    document.addEventListener("visibilitychange", resume);
    window.addEventListener("focus", resume);
    const unsubscribe = subscribeSessionChanges((kind) => {
      if (kind === "session-cleared") {
        request.current?.abort();
        locked.current = false;
        queuedRefresh.current = false;
        storePending(null);
        setGame(null);
        setGeneration(null);
        setBusy(null);
        setError(
          "Your guest session has been cleared. Start a fresh duel to continue.",
        );
      } else if (kind === "game-changed") {
        if (locked.current) queuedRefresh.current = true;
        else void load();
      }
    });
    return () => {
      mounted.current = false;
      request.current?.abort();
      locked.current = false;
      window.removeEventListener("online", resume);
      window.removeEventListener("pageshow", resume);
      document.removeEventListener("visibilitychange", resume);
      window.removeEventListener("focus", resume);
      unsubscribe();
    };
  }, [load]);

  useEffect(() => {
    if (generation?.status !== "generation_in_progress") return;
    const delay = Math.max(1, Math.min(5, generation.retry_after_seconds ?? 2));
    const timer = setTimeout(() => void load(), delay * 1000);
    return () => clearTimeout(timer);
  }, [generation, load]);

  const round = game?.current_round;
  useEffect(() => {
    if (!round) return;
    const marker = `${round.round_id}:${round.state}`;
    if (focused.current === marker) return;
    focused.current = marker;
    (round.state === "revealed" ? outcome.current : question.current)?.focus();
  }, [round?.round_id, round?.state]);

  async function executeMutation(action: PendingMutation) {
    if (!game || locked.current) return;
    locked.current = true;
    storePending(action);
    setBusy(action.kind);
    setError(null);
    const controller = new AbortController();
    request.current = controller;
    try {
      if (action.kind === "answer") {
        const accepted = await api.post<ApiSchemas["RevealedRoundPublic"]>(
          `/games/${gameId}/answer`,
          action.body,
          action.key,
          controller.signal,
        );
        if (controller.signal.aborted || !mounted.current) return;
        setGame(
          (previous) =>
            previous && {
              ...previous,
              revision: accepted.revision,
              current_ordinal: accepted.ordinal,
              answered_count: accepted.ordinal,
              score: accepted.cumulative_score,
              current_round: accepted,
            },
        );
      } else {
        const saved = await api.post<ApiSchemas["GamePublic"]>(
          `/games/${gameId}/advance`,
          action.body,
          action.key,
          controller.signal,
        );
        if (controller.signal.aborted || !mounted.current) return;
        acceptGame(saved);
        if (saved.phase === "completed") router.push(`/results/${gameId}`);
      }
      storePending(null);
      publishSessionChange("game-changed", false);
    } catch (failure) {
      if (!controller.signal.aborted && mounted.current) {
        setError(problem(failure));
        if (failure instanceof ApiError && failure.status === 410) {
          setGame(null);
          setExpired(true);
        }
      }
      // Keep the same key and exact body until a server response or GET settles it.
    } finally {
      if (request.current === controller) {
        if (!controller.signal.aborted && mounted.current) setBusy(null);
        locked.current = false;
        if (queuedRefresh.current && mounted.current) {
          queuedRefresh.current = false;
          setTimeout(() => reload.current(), 0);
        }
      }
    }
  }

  async function retryGeneration() {
    if (locked.current) return;
    const intent = readGenerationIntent();
    if (!intent || intent.gameId !== gameId) {
      setError(
        "The original request is unavailable in this browser. Choose a seed to start a new game.",
      );
      return;
    }
    locked.current = true;
    setBusy("generation");
    setError(null);
    const controller = new AbortController();
    request.current = controller;
    try {
      const saved = await api.post<
        ApiSchemas["GamePublic"] | ApiSchemas["GameGenerationPendingPublic"]
      >("/games", intent.body, intent.key, controller.signal);
      if (controller.signal.aborted || !mounted.current) return;
      if ("current_ordinal" in saved) acceptGame(saved);
      else setGeneration({ ...saved, recovery_action: "wait_then_retry" });
    } catch (failure) {
      if (!controller.signal.aborted && mounted.current)
        setError(problem(failure));
    } finally {
      if (request.current === controller) {
        if (!controller.signal.aborted && mounted.current) setBusy(null);
        locked.current = false;
      }
    }
  }

  if (game?.phase === "completed" && !round)
    return (
      <StatusPanel
        eyebrow="FIVE ROUNDS · COMPLETE"
        title="Your duel is complete."
        headingLevel={1}
        actions={
          <>
            <ActionLink href={`/results/${gameId}`}>View result</ActionLink>
            <ActionLink href="/" variant="secondary">
              Choose another seed
            </ActionLink>
          </>
        }
      >
        <p>
          All five predictions have been accepted. Opening this page again does
          not replay or resubmit an answer.
        </p>
      </StatusPanel>
    );
  if (!game || !round)
    return (
      <StatusPanel
        eyebrow="TASTE DUEL · YOUR SAVED GAME"
        title={
          expired
            ? "This game has expired."
            : generation
              ? generation.status === "generation_in_progress"
                ? "Your duel is preparing."
                : "Generation was interrupted."
              : busy
                ? "Opening your saved duel."
                : "This duel is unavailable."
        }
        headingLevel={1}
        tone={error ? "error" : "pending"}
        actions={
          <>
            <Button pending={Boolean(busy)} onClick={() => void load()}>
              Check saved game
            </Button>
            {generation?.recovery_action === "retry_same_request" && (
              <Button
                variant="secondary"
                pending={Boolean(busy)}
                onClick={() => void retryGeneration()}
              >
                Retry same generation
              </Button>
            )}
            <ActionLink href="/" variant="quiet">
              Choose a seed
            </ActionLink>
          </>
        }
      >
        <p>
          {error ??
            (generation?.status === "generation_in_progress"
              ? "Your game is being prepared. Check again to recover its saved state. You can safely leave and return."
              : generation?.recovery_action === "retry_same_request"
                ? "Preparation was interrupted. Retry the same request to recover your game."
                : "Pick up where you left off, or choose a seed to start another duel.")}
        </p>
      </StatusPanel>
    );

  const revealed = round.state === "revealed" ? round : null;
  const uncertainAnswer = pending?.kind === "answer" && !revealed;
  const selected =
    revealed?.selected_choice_id ??
    (pending?.kind === "answer" ? pending.body.choice_id : undefined);
  const evidence = revealed ? revealEvidence(revealed) : null;
  const winner = revealed?.choices.find(
    (choice) => choice.id === revealed.winning_choice_id,
  );
  const unavailable = game.phase === "expired" || game.phase === "cancelled";
  return (
    <section
      className="arena-page"
      data-testid="live-game"
      data-phase={busy ?? round.state}
      aria-labelledby="live-question"
    >
      <div className="arena-meta">
        <ActionLink href="/" variant="quiet">
          ← Change seed
        </ActionLink>
        <span className="fixture-badge">
          {sourceLabel(game.source, game.curator_mode)}
        </span>
      </div>
      <div className="arena-context">
        <span className="seed-pill" id="live-seed-context">
          <span aria-hidden="true">✳</span>
          {game.seed.name}
          <span>{game.seed.type === "movie" ? "FILM" : "MUSIC ARTIST"}</span>
        </span>
        <RoundPips
          current={round.ordinal}
          completed={game.answered_count}
          label={`Round ${round.ordinal} of 5`}
        />
        <span
          className="arena-score"
          data-testid="live-score"
          aria-label={`Score ${game.score} out of 5`}
        >
          {game.score} / 5
        </span>
      </div>
      <div className="arena-heading">
        <p className="eyebrow" id="live-round-context">
          ROUND {round.ordinal} OF 5 · PREDICT THE CONNECTION
        </p>
        <h1
          id="live-question"
          data-testid="live-question"
          tabIndex={-1}
          ref={question}
          aria-describedby="live-round-context live-seed-context"
        >
          WHICH {round.target_type === "movie" ? "FILM" : "ARTIST"}
          <br />
          <span className="text-accent">RANKS HIGHER?</span>
        </h1>
        <p>
          For {game.seed.name}, in{" "}
          {game.source === "qloo"
            ? "Qloo’s request-specific cultural ranking"
            : "this clearly synthetic fixture"}
          .
        </p>
      </div>
      <LiveChoices
        round={round}
        selectedId={selected}
        disabled={Boolean(busy || revealed || uncertainAnswer || unavailable)}
        onChoose={(id) =>
          void executeMutation({
            kind: "answer",
            key: createKey(),
            body: {
              round_id: round.round_id,
              choice_id: id,
              expected_revision: game.revision,
            },
          })
        }
      />
      {busy === "answer" && (
        <p role="status" className="feedback-copy">
          Sending your prediction. Correctness is confirmed by the server.
        </p>
      )}
      {(error || (!busy && pending)) && (
        <StatusPanel
          title="Check before continuing."
          live="polite"
          tone="warning"
          actions={
            <>
              <Button pending={Boolean(busy)} onClick={() => void load()}>
                Check saved game
              </Button>
              {pending && (
                <Button
                  variant="secondary"
                  pending={Boolean(busy)}
                  onClick={() => void executeMutation(pending)}
                >
                  {pending.kind === "answer"
                    ? "Retry prediction"
                    : "Retry Next"}
                </Button>
              )}
            </>
          }
        >
          <p>
            {error ??
              "Your previous action is not yet confirmed. Its original request key is preserved; no new answer will be submitted automatically."}
          </p>
        </StatusPanel>
      )}
      {revealed && (
        <div className="round-feedback" data-testid="reveal-panel">
          <div>
            <p className="feedback-status" id="live-outcome">
              {revealed.correct
                ? "✓ MATCHED THE RANKING"
                : "↗ DIFFERENT PREDICTION"}
            </p>
            <h2
              className="feedback-title"
              tabIndex={-1}
              ref={outcome}
              aria-describedby="live-outcome"
            >
              {winner?.entity.name ?? "The recorded winner"} ranks higher.
            </h2>
            <p className="feedback-copy">
              {game.source === "qloo"
                ? "Qloo determines this cultural answer. Your score measures predictions, not your personal taste."
                : "Synthetic fixture result. No genuine Qloo ranking is claimed."}
            </p>
            {evidence && <WhyThisDuel evidence={evidence} />}
            <details
              className="discovery-reveal"
              data-testid="discovery-reveal"
              key={revealed.round_id}
            >
              <summary>Save a discovery</summary>
              <LiveDiscoveries choices={[...revealed.choices]} />
            </details>
            {revealed.curation_summary && (
              <CurationDisclosure summary={revealed.curation_summary} />
            )}
          </div>
          <Button
            data-testid="next-action"
            pending={busy === "advance"}
            disabled={Boolean(busy || pending || unavailable)}
            pendingLabel={
              round.ordinal === 5
                ? "Opening your result…"
                : "Opening next round…"
            }
            onClick={() =>
              void executeMutation({
                kind: "advance",
                key: createKey(),
                body: {
                  answered_round_id: round.round_id,
                  expected_revision: game.revision,
                },
              })
            }
          >
            {round.ordinal === 5 ? "View result" : "Next round"}{" "}
            <span aria-hidden="true">↗</span>
          </Button>
        </div>
      )}
    </section>
  );
}
