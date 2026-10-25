import type { Metadata } from "next";
import Link from "next/link";
import { fixturesEnabled } from "@/features/mode/config";
export const metadata: Metadata = { title: "How it works" };
export default function HowItWorksPage() {
  return (
    <section className="reading-page" aria-labelledby="how-title">
      <Link href="/" className="back-link">
        ← Back to the good stuff
      </Link>
      <p className="eyebrow">A GAME OF CONNECTIONS, NOT CORRECT TASTE</p>
      <h1 id="how-title">
        YOUR INSTINCT.
        <br />
        <span className="text-accent">A DIFFERENT LENS.</span>
      </h1>
      <div className="reading-panel">
        <h2>The idea is simple.</h2>
        <p>
          Choose something you love. Predict which of two films or music artists
          ranks higher for it in Qloo's taste graph. Make five predictions,
          discover something new and challenge a friend to the same five rounds.
        </p>
        <h2>What you are predicting</h2>
        <p>
          The future game will use aggregate, request-specific Qloo rankings.
          They are cultural connections, not a probability that you will enjoy
          something. A different favourite or query can produce a different
          ranking. Correct and incorrect guesses measure game performance: how
          well you predicted that ranking. They do not tell us which choice you
          personally like or dislike. Saving a discovery is your explicit choice
          to explore it, independent of your prediction.
        </p>
        <h2>What exists today</h2>
        <p>
          {fixturesEnabled
            ? "This development-only fixture game uses invented entities and rankings, original artwork and five local rounds. Your score counts accepted sample answers out of five. It makes no Qloo calls and creates no real share link. Progress lasts only in this tab's current app session; reloading resets it."
            : "Live games are not connected. The development-only fixture game is excluded from this production build. No live Qloo integration, accounts or shared game service is available yet."}
        </p>
        <h2>Built to be played your way.</h2>
        <p>
          No time pressure, sound or animation is required. Use the keyboard to
          search and choose. Reduced-motion preferences are respected. Real
          server authority, durable progress, exact friend replay and live
          ranking will be built in later iterations.
        </p>
        <h2>Artwork and type</h2>
        <p>
          All displayed cover compositions are original SVG design assets for
          fictional works. No film poster or artist photography was copied.
          Barlow Condensed and Manrope are served locally with their font
          licence notices.
        </p>
        <div className="state-actions">
          {fixturesEnabled && (
            <Link href="/" className="button button-primary">
              Start a fixture duel <span aria-hidden="true">↗</span>
            </Link>
          )}
          <Link href="/" className="button button-secondary">
            {fixturesEnabled ? "Choose a fictional seed" : "Back to Taste Duel"}
          </Link>
        </div>
      </div>
    </section>
  );
}
