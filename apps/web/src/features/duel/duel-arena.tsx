import type { ReactNode, Ref } from "react";
import { ActionLink } from "@/components/ui/button";
import { RoundPips } from "@/components/ui/round-pips";

type DuelArenaProps = {
  phase: string;
  seedName: string;
  seedType: string;
  ordinal: number;
  score: number;
  answered: number;
  questionRef: Ref<HTMLHeadingElement>;
  children: ReactNode;
};

/** Presentation only. The caller owns progression, answers and transport. */
export function DuelArena({
  phase,
  seedName,
  seedType,
  ordinal,
  score,
  answered,
  questionRef,
  children,
}: DuelArenaProps) {
  return (
    <section
      className="arena-page"
      data-testid="fixture-game"
      data-phase={phase}
      aria-labelledby="fixture-question"
    >
      <div className="arena-meta">
        <ActionLink href="/" variant="quiet">
          ← Change seed
        </ActionLink>
        <span className="fixture-badge">
          DEVELOPMENT FIXTURE · NO LIVE QLOO
        </span>
      </div>
      <div className="arena-context">
        <span className="seed-pill" id="fixture-seed-context">
          <span aria-hidden="true">✳</span>
          {seedName}
          <span>FICTIONAL {seedType.toUpperCase()}</span>
        </span>
        <RoundPips
          current={ordinal}
          completed={answered}
          total={5}
          label={`Round ${ordinal} of 5`}
        />
        <span
          className="arena-score"
          data-testid="fixture-score"
          aria-label={`Fixture score ${score} out of 5`}
        >
          {score} / 5
        </span>
      </div>
      <div className="arena-heading">
        <p className="eyebrow" id="fixture-round-context">
          ROUND {ordinal} OF 5 · READ THE CONNECTION
        </p>
        <h1
          id="fixture-question"
          data-testid="fixture-question"
          tabIndex={-1}
          ref={questionRef}
          aria-describedby="fixture-round-context fixture-seed-context"
        >
          WHICH FILM
          <br />
          <span className="text-accent">RANKS HIGHER?</span>
        </h1>
        <p>For {seedName}, in this invented ranking.</p>
      </div>
      {children}
    </section>
  );
}
