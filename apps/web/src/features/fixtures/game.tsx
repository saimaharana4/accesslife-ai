"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button, ActionLink } from "@/components/ui/button";
import { StatusPanel } from "@/components/ui/status-panel";
import { Artwork } from "../duel/artwork";
import { DuelArena } from "../duel/duel-arena";
import { ChoicePair } from "../duel/choice-pair";
import { RoundReveal } from "../reveal/round-reveal";
import { fictionalSeeds } from "../seed/fictional-seeds";
import { useFixture } from "./provider";
import { fixtureScore } from "./state.ts";
import { createFixtureRounds } from "./fixture-data.ts";
import type { FixtureStory } from "./types.ts";
import { fixtureDisclosure, fixtureCurationSummary } from "./disclosure.ts";

export function FixtureGame({ story = "normal" }: { story?: FixtureStory }) {
  const { state, actions } = useFixture();
  const router = useRouter();
  const question = useRef<HTMLHeadingElement>(null);
  const feedback = useRef<HTMLHeadingElement>(null);
  const initiatedStory = useRef<string | null>(null);
  const active = useRef(true);
  const requestedResult = useRef(false);
  const ordinal = "round" in state ? state.round.ordinal : 0;

  useEffect(() => {
    if (story === "normal" || initiatedStory.current === story) return;
    initiatedStory.current = story;
    actions.reset();
    if (story === "expired" || story === "interrupted")
      actions.showStory(story);
    else if (
      !["preparing", "pending", "selected", "submitting", "disabled"].includes(
        story,
      )
    )
      actions.start(fictionalSeeds[0], story);
  }, [story, actions]);
  useEffect(() => {
    if (state.kind === "revealed")
      feedback.current?.focus({ preventScroll: true });
    if (state.kind === "unanswered")
      question.current?.focus({ preventScroll: true });
    // Only the explicit final Next action may navigate. Cached/restored arenas
    // must not redirect Back navigation merely because context is complete.
    if (state.kind === "complete" && requestedResult.current) {
      requestedResult.current = false;
      router.push("/results/demo");
    }
  }, [state.kind, ordinal, router]);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      queueMicrotask(() => {
        if (!active.current) actions.interrupt();
      });
    };
  }, [actions]);

  if (
    ["preparing", "pending", "selected", "submitting", "disabled"].includes(
      story,
    )
  )
    return <FixtureStaticStory story={story} />;
  if (state.kind === "idle")
    return (
      <div data-testid="fixture-game" data-phase="confirmation">
        <StatusPanel
          eyebrow="DEVELOPMENT FIXTURE"
          title="Confirm your seed"
          headingLevel={1}
          actions={
            <>
              <Button
                data-testid="start-duel"
                onClick={() => actions.start(fictionalSeeds[0], story)}
              >
                Start fixture duel
              </Button>
              <ActionLink href="/" variant="secondary">
                Choose a different seed
              </ActionLink>
            </>
          }
        >
          <p>
            The direct arena preview uses{" "}
            <strong>{fictionalSeeds[0].name}</strong>, a fictional music artist.
            This is a five-round, in-memory fixture. Refreshing resets it.
          </p>
        </StatusPanel>
      </div>
    );
  if (state.kind === "preparing")
    return (
      <div data-testid="fixture-game" data-phase="preparing">
        <StatusPanel
          eyebrow="DEVELOPMENT FIXTURE"
          title="Preparing five fictional connections"
          headingLevel={1}
          live="polite"
          tone="pending"
          actions={
            <Button variant="secondary" onClick={actions.interrupt}>
              Cancel fixture preparation
            </Button>
          }
        >
          <p>
            A local adapter is preparing invented rounds. No Qloo, model or
            server request is running.
          </p>
        </StatusPanel>
      </div>
    );
  if (state.kind === "issue") {
    const titles = {
      empty: "No fixture rounds available",
      partial: "Three rounds are not five",
      retry: "Your answer is not lost",
      expired: "This fixture has expired",
      interrupted: "The fixture was interrupted",
    };
    return (
      <div data-testid="fixture-game" data-phase={state.issue}>
        <StatusPanel
          eyebrow="DEVELOPMENT FIXTURE STATE"
          title={titles[state.issue]}
          headingLevel={1}
          tone="warning"
          actions={
            <>
              {state.recovery &&
                !["empty", "partial"].includes(state.issue) && (
                  <Button onClick={actions.retry}>
                    {state.recovery.kind === "answer"
                      ? "Retry answer"
                      : state.recovery.kind === "advance"
                        ? "Retry next round"
                        : "Resume fixture"}
                  </Button>
                )}
              <Button
                variant="secondary"
                onClick={() => {
                  actions.reset();
                  actions.start(fictionalSeeds[0]);
                }}
              >
                Start a full fixture
              </Button>
              <ActionLink href="/" variant="quiet">
                Choose another seed
              </ActionLink>
            </>
          }
        >
          <p>{state.message}</p>
          <p>UI-only fixture. Nothing has been saved to a backend.</p>
        </StatusPanel>
      </div>
    );
  }
  if (state.kind === "complete")
    return (
      <div data-testid="fixture-game" data-phase="complete">
        <StatusPanel
          title="Five fictional rounds complete"
          actions={<ActionLink href="/results/demo">View result</ActionLink>}
        >
          <p>Opening your computed fixture result.</p>
        </StatusPanel>
      </div>
    );

  const revealed = state.kind === "revealed" || state.kind === "advancing";
  const answer = revealed ? state.answer : undefined;
  const evidence = fixtureDisclosure(state);
  const selected =
    state.kind === "submitting" ? state.choiceId : answer?.choiceId;
  return (
    <DuelArena
      phase={state.kind}
      seedName={state.game.seed.name}
      seedType={state.game.seed.type}
      ordinal={state.round.ordinal}
      score={fixtureScore(state.answers)}
      answered={state.answers.length}
      questionRef={question}
    >
      <ChoicePair
        round={state.round}
        selectedId={selected}
        winnerId={answer?.winnerId}
        disabled={state.kind !== "unanswered"}
        missingFirst={state.game.story === "missing-image"}
        onChoose={actions.answer}
      />
      {state.kind === "submitting" && (
        <p className="pending-copy" role="status">
          Checking the local fixture answer…
        </p>
      )}
      {revealed && answer && evidence && (
        <RoundReveal
          correct={answer.correct}
          winnerTitle={answer.winnerTitle}
          evidence={evidence}
          curation={fixtureCurationSummary()}
          ordinal={state.round.ordinal}
          pending={state.kind === "advancing"}
          headingRef={feedback}
          choices={state.round.choices}
          savedIds={state.discoveries.map((choice) => choice.id)}
          onSave={actions.save}
          onNext={() => {
            requestedResult.current = state.round.ordinal === 5;
            actions.advance();
          }}
        />
      )}
      {!revealed && (
        <p className="arena-help">
          No timer. No wrong taste. Your answer is accepted once.
        </p>
      )}
      <p className="prototype-detail">
        Development fixture: five invented rounds in browser memory. No backend
        or live provider. Refresh resets progress.
      </p>
      <FixtureStoryLinks />
    </DuelArena>
  );
}

export function FixtureStoryLinks() {
  return (
    <details className="fixture-story-links">
      <summary>Explore fixture states</summary>
      <p>
        Opening a story replaces the current local fixture. Refreshing clears
        its memory.
      </p>
      <nav aria-label="Fixture state stories">
        {[
          "empty",
          "partial",
          "retry",
          "expired",
          "interrupted",
          "long-title",
          "missing-image",
          "preparing",
          "selected",
        ].map((story) => (
          <ActionLink key={story} variant="quiet" href={`/prototype/${story}`}>
            {story.replaceAll("-", " ")}
          </ActionLink>
        ))}
      </nav>
    </details>
  );
}

export function FixtureStaticStory({ story }: { story: FixtureStory }) {
  if (story === "preparing" || story === "pending")
    return (
      <div data-testid="fixture-game" data-phase="preparing">
        <StatusPanel
          eyebrow="STATIC FIXTURE STORY"
          title="Preparing a connection"
          headingLevel={1}
          tone="pending"
          actions={
            <ActionLink href="/g/demo">Open playable fixture</ActionLink>
          }
        >
          <p>
            This is a static pending-state composition. No task is running, and
            no fake live progress is being generated.
          </p>
        </StatusPanel>
      </div>
    );
  const round = createFixtureRounds()[0];
  return (
    <section
      className="arena-page"
      data-testid="fixture-game"
      data-phase={story}
    >
      <div className="arena-heading">
        <p className="eyebrow">STATIC {story.toUpperCase()} FIXTURE STORY</p>
        <h1>
          YOUR CHOICE.
          <br />
          <span className="text-accent">A MOMENT TO REVEAL.</span>
        </h1>
        <p>
          Static selected/disabled composition. No answer has been accepted and
          no request is running.
        </p>
      </div>
      <div className="choice-pair">
        {round.choices.map((choice, index) => (
          <div className="choice-slot" key={choice.id}>
            {index === 1 && (
              <span className="duel-seam" aria-hidden="true">
                DUEL
              </span>
            )}
            <button
              type="button"
              className={`choice-card${index === 0 ? " is-selected" : ""}`}
              disabled
              aria-pressed={index === 0}
            >
              <Artwork src={choice.art} title={choice.title} />
              <span className="choice-info">
                <span className="choice-kind">FICTIONAL FILM</span>
                <strong className="choice-title">{choice.title}</strong>
                <span className="choice-selection">
                  {index === 0
                    ? "Selected · disabled specimen"
                    : "Other choice · disabled specimen"}
                </span>
              </span>
            </button>
          </div>
        ))}
      </div>
      <div className="state-actions">
        <ActionLink href="/g/demo">Open playable fixture</ActionLink>
      </div>
    </section>
  );
}
