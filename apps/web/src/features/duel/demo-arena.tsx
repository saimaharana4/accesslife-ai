"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Artwork } from "./artwork";

type DemoState =
  | { kind: "unanswered" }
  | { kind: "selected" | "revealed"; choice: "afterlight" | "blue-hour" };

export function DemoArena({
  longTitle = false,
  missingImage = false,
  seedName = "Velvet Static",
  seedType = "Music artist",
}: {
  longTitle?: boolean;
  missingImage?: boolean;
  seedName?: string;
  seedType?: string;
}) {
  const [state, setState] = useState<DemoState>({ kind: "unanswered" });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const feedbackHeading = useRef<HTMLHeadingElement | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  useEffect(() => {
    if (state.kind === "revealed")
      feedbackHeading.current?.focus({ preventScroll: true });
  }, [state.kind]);
  const choices = [
    {
      id: "afterlight" as const,
      title: longTitle
        ? "Afterlight Assembly and the Unexpectedly Long Journey to the Edge of a Fictional Tomorrow"
        : "Afterlight Assembly",
      year: "Design fiction · 2026",
      art: "/art/afterlight.svg",
    },
    {
      id: "blue-hour" as const,
      title: "The Blue Hour Archive",
      year: "Design fiction · 2026",
      art: "/art/blue-hour.svg",
    },
  ];

  function choose(choice: "afterlight" | "blue-hour") {
    if (state.kind !== "unanswered") return;
    setState({ kind: "selected", choice });
    const delay = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? 0
      : 160;
    timer.current = setTimeout(
      () => setState({ kind: "revealed", choice }),
      delay,
    );
  }

  return (
    <section className="arena-page" aria-labelledby="arena-title">
      <div className="arena-meta">
        <Link className="back-link" href="/">
          ← Change seed
        </Link>
        <span className="mono-label">SINGLE-ROUND PREVIEW</span>
      </div>
      <div className="arena-context">
        <span className="seed-pill">
          <span aria-hidden="true">✳</span> {seedName}{" "}
          <span>FICTIONAL {seedType.toUpperCase()}</span>
        </span>
        <div
          className="round-pips"
          aria-label="Sample round 1 of 5 planned rounds"
        >
          {[1, 2, 3, 4, 5].map((round) => (
            <span
              key={round}
              className={`round-pip${round === 1 ? " is-current" : ""}`}
              aria-hidden="true"
            />
          ))}
          <span>01 / 05</span>
        </div>
      </div>
      <div className="arena-heading">
        <p className="eyebrow">READ THE CONNECTION</p>
        <h1 id="arena-title">
          WHICH FILM
          <br />
          <span className="text-accent">RANKS HIGHER?</span>
        </h1>
        <p>For {seedName}, in this fictional example.</p>
      </div>
      <div
        className="choice-pair"
        aria-label="Choose between two fictional films"
      >
        {choices.map((choice, index) => {
          const selected =
            state.kind !== "unanswered" && state.choice === choice.id;
          const revealed = state.kind === "revealed";
          return (
            <div className="choice-slot" key={choice.id}>
              {index === 1 && (
                <span className="duel-seam" aria-hidden="true">
                  DUEL
                </span>
              )}
              <button
                type="button"
                className={`choice-card${selected ? " is-selected" : ""}${revealed && choice.id === "afterlight" ? " is-winner" : ""}${revealed && choice.id !== "afterlight" ? " is-muted" : ""}`}
                data-testid="choice-card"
                disabled={state.kind !== "unanswered"}
                onClick={() => choose(choice.id)}
                aria-pressed={selected}
              >
                <Artwork
                  src={choice.art}
                  title={choice.title}
                  missing={missingImage && index === 0}
                />
                <span className="choice-info">
                  <span className="choice-kind">
                    FICTIONAL FILM{" "}
                    <span aria-hidden="true">{index === 0 ? "A" : "B"}</span>
                  </span>
                  <strong className="choice-title">{choice.title}</strong>
                  <span className="choice-year">{choice.year}</span>
                  <span className="choice-selection">
                    {state.kind === "unanswered" ? (
                      <>
                        Make your prediction <span aria-hidden="true">↗</span>
                      </>
                    ) : selected ? (
                      "Your selection"
                    ) : (
                      "Other choice"
                    )}
                  </span>
                </span>
              </button>
            </div>
          );
        })}
      </div>
      <div className="arena-feedback-slot">
        {state.kind === "selected" && (
          <p className="pending-copy">Revealing the fictional result…</p>
        )}
        {state.kind === "revealed" && (
          <div className="round-feedback" data-testid="reveal-panel">
            <div>
              <p className="feedback-status" id="demo-outcome">
                {state.choice === "afterlight"
                  ? "✓ MATCHED THE SAMPLE"
                  : "↗ A SURPRISE CONNECTION"}
              </p>
              <h2
                className="feedback-title"
                ref={feedbackHeading}
                tabIndex={-1}
                aria-describedby="demo-outcome"
              >
                AFTERLIGHT TAKES THIS ONE.
              </h2>
              <p className="feedback-copy">
                This invented ranking places Afterlight Assembly above The Blue
                Hour Archive. It demonstrates the reveal design; it is not Qloo
                output.
              </p>
            </div>
            <Link
              className="button button-primary"
              data-testid="next-action"
              href="/results/demo"
            >
              View sample result <span aria-hidden="true">↗</span>
            </Link>
          </div>
        )}
      </div>
      {state.kind === "unanswered" && (
        <p className="arena-help">
          Pick a card to reveal. No timer. No wrong taste.
        </p>
      )}
      <p className="prototype-detail">
        Visual study only: one invented round, no saved answers or live ranking.
        A complete five-round game comes later.
      </p>
    </section>
  );
}
