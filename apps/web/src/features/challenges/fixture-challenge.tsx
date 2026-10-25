"use client";

import { ActionLink } from "@/components/ui/button";
import { StatusPanel } from "@/components/ui/status-panel";
import { useFixture } from "../fixtures/provider";
import { fixtureScore } from "../fixtures/state.ts";
import { createFixtureRounds } from "../fixtures/fixture-data.ts";

export function FixtureChallenge() {
  const { state } = useFixture();
  if (state.kind !== "complete")
    return (
      <StatusPanel
        eyebrow="LOCAL INVITATION PREVIEW"
        title="Your five rounds come first"
        headingLevel={1}
        actions={<ActionLink href="/">Start a fixture</ActionLink>}
      >
        <p>
          This invitation requires a completed five-round fixture in the same
          browser memory. No sample score or invented friend result is
          substituted.
        </p>
      </StatusPanel>
    );
  const rounds = createFixtureRounds(state.game.story === "long-title");
  const played = state.answers.map(
    (answer) => rounds.find((round) => round.id === answer.roundId)!,
  );
  const score = fixtureScore(state.answers);
  return (
    <section className="challenge-page" aria-labelledby="challenge-title">
      <div className="challenge-ticket" data-testid="challenge-invitation">
        <p className="eyebrow">YOUR FIVE. A FRIEND'S INSTINCT.</p>
        <div className="challenge-mark" aria-hidden="true">
          ✳
        </div>
        <h1 id="challenge-title" className="challenge-title">
          SAME FIVE.
          <br />
          <span className="text-accent">YOUR INSTINCT.</span>
        </h1>
        <p className="challenge-summary">
          You picked <strong>{state.game.seed.name}.</strong>
          <br />
          Your fixture score: <strong>{score} out of 5.</strong>
        </p>
        <div className="challenge-rules">
          <span>FIVE PLAYED ROUNDS</span>
          <span aria-hidden="true">/</span>
          <span>FIXED ORDER</span>
          <span aria-hidden="true">/</span>
          <span>NO TIMER</span>
        </div>
        <ol
          className="result-round-list"
          aria-label="Five played rounds for the local invitation preview"
        >
          {played.map((round) => (
            <li className="result-round-row" key={round.id}>
              <span>Round {round.ordinal}</span>
              <strong>{round.choices[0].title}</strong>
              <span>vs {round.choices[1].title}</span>
            </li>
          ))}
        </ol>
        <p className="prototype-detail">
          Local invitation preview only: these are your actual five played
          fixture comparisons in their original order and sides. No public
          challenge, share URL or friend replay exists yet. Refresh clears this
          memory.
        </p>
        <div className="state-actions">
          <ActionLink href="/results/demo">
            Back to your fixture result
          </ActionLink>
          <ActionLink href="/" variant="secondary">
            Choose another seed
          </ActionLink>
        </div>
      </div>
      <aside className="challenge-aside">
        <p className="mono-label">A LITTLE FRIENDLY CULTURE CLASH.</p>
        <p>
          The future server-backed challenge will freeze the creator's five
          rounds and scoring rules. This iteration demonstrates the invitation
          using your completed local fixture.
        </p>
        <ActionLink href="/how-it-works" variant="quiet">
          What are we predicting? <span aria-hidden="true">↗</span>
        </ActionLink>
      </aside>
    </section>
  );
}
