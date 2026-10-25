import type { Metadata } from "next";
import Link from "next/link";
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
          ranking. Your personal taste is never wrong.
        </p>
        <h2>What exists in this prototype</h2>
        <p>
          This is a local visual study with invented entities, original artwork
          and one synthetic reveal. The 3/5 result and challenge invitation are
          labelled specimens. There are no Qloo calls, accounts, scores, saved
          discoveries or share links. Refreshing the arena resets its visual
          state.
        </p>
        <h2>Built to be played your way.</h2>
        <p>
          No time pressure, sound or animation is required. Use the keyboard to
          search and choose. Reduced-motion preferences are respected. Real
          gameplay, durable progress, exact friend replay and live ranking will
          be built in later iterations.
        </p>
        <h2>Artwork and type</h2>
        <p>
          All displayed cover compositions are original SVG design assets for
          fictional works. No film poster or artist photography was copied.
          Barlow Condensed and Manrope are served locally with their font
          licence notices.
        </p>
        <div className="state-actions">
          <Link href="/g/demo" className="button button-primary">
            Preview a duel <span aria-hidden="true">↗</span>
          </Link>
          <Link href="/" className="button button-secondary">
            Choose a fictional seed
          </Link>
        </div>
      </div>
    </section>
  );
}
