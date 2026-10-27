"use client";

import { useEffect, useRef, useState } from "react";
import { ActionLink, Button } from "@/components/ui/button";
import { StatusPanel } from "@/components/ui/status-panel";
import { api, ApiError } from "@/lib/api/client";
import type { ApiSchemas } from "@/lib/api/contracts";
import { CurationDisclosure } from "./curation-disclosure";
import { sourceLabel } from "./presentation";
import { LiveDiscoveries } from "@/features/discoveries/live-discoveries";
import { subscribeSessionChanges } from "@/lib/api/session-events";
import { ChallengeShare } from "@/features/challenges/challenge-share";

export function LiveResults({
  gameId,
  canonicalOrigin = null,
}: {
  gameId: string;
  canonicalOrigin?: string | null;
}) {
  const [result, setResult] = useState<ApiSchemas["GameResultPublic"] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const epoch = useRef(0);
  useEffect(() => {
    const refresh = () => {
      if (!document.hidden) setAttempt((value) => value + 1);
    };
    const unsubscribe = subscribeSessionChanges((kind) => {
      if (kind === "session-cleared") {
        epoch.current += 1;
        setResult(null);
        setError("Your guest session has been cleared. Start a fresh duel.");
      } else if (kind === "game-changed" || kind === "discoveries-changed")
        refresh();
    });
    window.addEventListener("online", refresh);
    window.addEventListener("focus", refresh);
    window.addEventListener("pageshow", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      unsubscribe();
      window.removeEventListener("online", refresh);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("pageshow", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const version = epoch.current;
    setError(null);
    setResult(null);
    void api
      .get<ApiSchemas["GameResultPublic"]>(
        `/games/${gameId}/results`,
        controller.signal,
      )
      .then((saved) => {
        if (!controller.signal.aborted && version === epoch.current)
          setResult(saved);
      })
      .catch((failure) => {
        if (!controller.signal.aborted)
          setError(
            failure instanceof ApiError && failure.status === 409
              ? "Complete your five predictions to open the result ticket."
              : "This saved result is unavailable in this session. It may have expired; no score has been invented.",
          );
      });
    return () => controller.abort();
  }, [gameId, attempt]);
  if (!result)
    return (
      <StatusPanel
        title={error ? "No result to show yet." : "Opening your result."}
        eyebrow="TASTE DUEL · SAVED SCORE"
        headingLevel={1}
        tone={error ? "warning" : "pending"}
        actions={
          <>
            <ActionLink href={`/g/${gameId}`}>Return to duel</ActionLink>
            {error && (
              <Button
                variant="secondary"
                onClick={() => setAttempt((value) => value + 1)}
              >
                Check saved result
              </Button>
            )}
          </>
        }
      >
        <p>{error ?? "Reading your accepted answers from the server."}</p>
      </StatusPanel>
    );
  const seed = result.answered_rounds[0].seed;
  const summary = result.answered_rounds.find(
    (round) => round.curation_summary,
  )?.curation_summary;
  return (
    <section className="results-page" aria-labelledby="result-title">
      <div className="page-intro">
        <p className="eyebrow">FIVE CONNECTIONS. SOMETHING UNEXPECTED.</p>
        <h1 id="result-title">
          TASTE THE
          <br />
          <span className="text-accent">UNEXPECTED.</span>
        </h1>
        <p>
          {result.source === "qloo"
            ? "Qloo supplied the cultural answers. You made the predictions."
            : "Five synthetic rounds. This is a development test, not a live Qloo result."}
        </p>
      </div>
      <div className="result-ticket" data-testid="result-ticket">
        <div className="ticket-top">
          <span>TASTE DUEL</span>
          <span className="mono-label">
            {sourceLabel(result.source, result.curator_mode)}
          </span>
        </div>
        <p className="ticket-label">YOUR PREDICTION SCORE · {seed.name}</p>
        <div
          className="ticket-score"
          data-testid="live-score"
          aria-label={`Score ${result.score} out of 5`}
        >
          <strong>{result.score}</strong>
          <span>/ 5</span>
          <span className="ticket-star" aria-hidden="true">
            ✳
          </span>
        </div>
        <h2 className="ticket-title">CURIOUS BY NATURE.</h2>
        <p className="ticket-description">
          One point per matching prediction. No speed bonus.
          <br />
          Your preferences are yours; this score is game performance.
        </p>
        <div className="ticket-divider" aria-hidden="true" />
        <ol
          className="result-round-list"
          aria-label="Your five accepted predictions"
        >
          {result.answered_rounds.map((round) => (
            <li className="result-round-row" key={round.round_id}>
              <span>Round {round.ordinal}</span>
              <strong>
                {round.choices.find(
                  (choice) => choice.id === round.selected_choice_id,
                )?.entity.name ?? "Recorded prediction"}
              </strong>
              <span>
                {round.correct ? "✓ Matched" : "Different prediction"}
              </span>
            </li>
          ))}
        </ol>
        {summary && <CurationDisclosure summary={summary} />}
        <LiveDiscoveries
          choices={result.answered_rounds.flatMap((round) => [
            ...round.choices,
          ])}
        />
        <div className="ticket-actions">
          <ActionLink href="/">
            Play another duel <span aria-hidden="true">↗</span>
          </ActionLink>
          <ActionLink href={`/g/${gameId}`} variant="secondary">
            Revisit the final reveal
          </ActionLink>
        </div>
        {result.mode === "fixed" ? (
          <p className="ticket-fine-print" data-testid="fixed-replay-result">
            Fixed replay complete. Your score uses the creator's frozen
            comparisons. Start a new solo duel to create your own friend
            challenge; a replay cannot detach from its original link's
            revocation.
          </p>
        ) : (
          <ChallengeShare
            gameId={gameId}
            canonicalOrigin={canonicalOrigin}
            source={result.source}
          />
        )}
        <p className="ticket-fine-print">
          Saved within this guest session until its evidence expires. Share
          links expire with their supporting evidence and can be revoked.
        </p>
      </div>
    </section>
  );
}
