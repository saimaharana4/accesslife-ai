"use client";

import { ActionLink } from "@/components/ui/button";
import { StatusPanel } from "@/components/ui/status-panel";
import { useFixture } from "../fixtures/provider";
import { fixtureScore } from "../fixtures/state.ts";
import { SavedDiscoveries } from "../discoveries/saved-discoveries";

export function FixtureResults() {
  const { state, actions } = useFixture();
  if (state.kind !== "complete")
    return (
      <StatusPanel
        eyebrow="DEVELOPMENT FIXTURE"
        title="No completed fixture yet"
        headingLevel={1}
        actions={<ActionLink href="/">Choose a seed</ActionLink>}
      >
        <p>
          Complete all five fictional rounds to see your computed result. A
          refresh clears this local memory; no historic or server score exists.
        </p>
      </StatusPanel>
    );
  const score = fixtureScore(state.answers);
  return (
    <section className="results-page" aria-labelledby="result-title">
      <div className="page-intro">
        <p className="eyebrow">FIVE CONNECTIONS. YOUR OWN INSTINCT.</p>
        <h1 id="result-title">
          TASTE THE
          <br />
          <span className="text-accent">UNEXPECTED.</span>
        </h1>
        <p>
          Five invented rounds completed. This score comes from your fixture
          answers, not Qloo.
        </p>
      </div>
      <div className="result-ticket" data-testid="result-ticket">
        <div className="ticket-top">
          <span>TASTE DUEL</span>
          <span className="mono-label">DEVELOPMENT FIXTURE</span>
        </div>
        <p className="ticket-label">
          YOUR FIXTURE SCORE · {state.game.seed.name}
        </p>
        <div
          className="ticket-score"
          data-testid="fixture-score"
          aria-label={`Fixture score ${score} out of 5`}
        >
          <strong>{score}</strong>
          <span>/ 5</span>
          <span className="ticket-star" aria-hidden="true">
            ✳
          </span>
        </div>
        <h2 className="ticket-title">CURIOUS BY NATURE.</h2>
        <p className="ticket-description">
          A game reward, not a taste diagnosis.
          <br />
          One point per matching prediction. No speed bonus.
        </p>
        <div className="ticket-divider" aria-hidden="true" />
        <ol
          className="result-round-list"
          aria-label="Your five accepted fixture answers"
        >
          {state.answers.map((answer) => (
            <li className="result-round-row" key={answer.roundId}>
              <span>Round {answer.ordinal}</span>
              <strong>{answer.selectedTitle}</strong>
              <span>
                {answer.correct ? "✓ Matched" : "Different prediction"}
              </span>
            </li>
          ))}
        </ol>
        <SavedDiscoveries
          discoveries={state.discoveries}
          onToggle={actions.save}
        />
        <div className="ticket-actions">
          <ActionLink href="/c/demo">
            Preview your challenge <span aria-hidden="true">↗</span>
          </ActionLink>
          <ActionLink href="/" variant="secondary" onClick={actions.reset}>
            Play another fixture
          </ActionLink>
        </div>
        <p className="ticket-fine-print">
          Browser-memory fixture only. Refresh clears progress and discoveries.
          No result has been published or shared.
        </p>
      </div>
    </section>
  );
}
