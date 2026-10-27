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
          Live games use aggregate, request-specific Qloo rankings. They are
          cultural connections, not a probability that you will enjoy something.
          A different favourite or query can produce a different ranking.
          Correct and incorrect guesses measure game performance: how well you
          predicted that ranking. They do not tell us which choice you
          personally like or dislike. Saving a discovery is your explicit choice
          to explore it, independent of your prediction.
        </p>
        <h2>What exists today</h2>
        <p>
          {fixturesEnabled
            ? "This development-only fixture game uses invented entities and rankings, original artwork and five local rounds. Your score counts accepted sample answers out of five. It makes no Qloo calls and creates no real share link. Progress lasts only in this tab's current app session; reloading resets it."
            : "When the private game service is configured, search resolves real Qloo entities and a bounded curator prepares five evidence-backed rounds. Each game identifies its actual curator mode. The server stores accepted answers, your score and only the discoveries you explicitly save. A completed game can become a fixed friend challenge. The synthetic fixture game is excluded from production builds."}
        </p>
        <h2>A challenge that follows your game.</h2>
        <p>
          New solo games begin at a medium band. Two matching predictions can
          raise the requested challenge; a miss can ease it. Only unused valid
          pairs from the saved pool are eligible, and a nearby band may be used
          to preserve five rounds without repeated contestants. Bands are
          engineering heuristics, not human-calibrated difficulty or a
          probability of enjoyment.
        </p>
        <p>
          Correct and incorrect predictions measure game performance. They are
          never stored as personal likes or dislikes. Your chosen favourite
          starts the journey; Save Discovery is your separate, explicit choice
          to explore either answered contestant. Remove a save whenever you
          wish.
        </p>
        <p>
          Saves expire with their supporting evidence or guest session. Clearing
          the guest session revokes private access and dependent share links;
          backups follow their retention policy. Previous game answers and
          frozen rankings do not change when difficulty adapts.
        </p>
        <h2>Built to be played your way.</h2>
        <p>
          No time pressure, sound or animation is required. Use the keyboard to
          search and choose. Reduced-motion preferences are respected. Real
          games restore accepted progress when you reload in the same guest
          session. A friend replay preserves the creator's exact played
          comparisons, order, sides and scoring rules, without another Qloo
          query.
        </p>
        <h2>Same five. Your predictions.</h2>
        <p>
          A public invitation shows the chosen favourite and creator's actual
          score out of five, never the answer key or remaining choices. Friends
          play their own fixed replay with independent scores. A share link
          expires with its supporting evidence and is revoked when the creator
          clears their session. It never silently refreshes into a different
          game.
        </p>
        <p>
          Sharing is casual play, not a cheat-proof competition: prior
          knowledge, external research and repeated attempts exist. There is no
          global leaderboard or claimed percentile. Copying a link or opening a
          share sheet does not send it until you choose to do so. External
          services may retain previously fetched social previews after a link is
          revoked; this application cannot recall those copies or rewrite old
          backups.
        </p>
        <h2>Artwork and type</h2>
        <p>
          Cover compositions are original SVG title cards, used as clearly
          labelled fallback art for real entities in live games. No film poster
          or artist photography was copied. Provider image URLs are not fetched.
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
