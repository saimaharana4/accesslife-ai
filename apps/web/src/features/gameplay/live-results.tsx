"use client";

import { useEffect, useState } from "react";
import { ActionLink, Button } from "@/components/ui/button";
import { StatusPanel } from "@/components/ui/status-panel";
import { api, ApiError } from "@/lib/api/client";
import type { ApiSchemas } from "@/lib/api/contracts";
import { CurationDisclosure } from "./curation-disclosure";
import { sourceLabel } from "./presentation";

export function LiveResults({ gameId }: { gameId: string }) {
  const [result, setResult] = useState<ApiSchemas["GameResultPublic"] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    setResult(null);
    void api
      .get<ApiSchemas["GameResultPublic"]>(
        `/games/${gameId}/results`,
        controller.signal,
      )
      .then((saved) => {
        if (!controller.signal.aborted) setResult(saved);
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
        <div className="ticket-actions">
          <ActionLink href="/">
            Play another duel <span aria-hidden="true">↗</span>
          </ActionLink>
          <ActionLink href={`/g/${gameId}`} variant="secondary">
            Revisit the final reveal
          </ActionLink>
        </div>
        <p className="ticket-fine-print">
          Saved within this guest session until its evidence expires. Discovery
          saves and friend challenges are coming in later iterations.
        </p>
      </div>
    </section>
  );
}
