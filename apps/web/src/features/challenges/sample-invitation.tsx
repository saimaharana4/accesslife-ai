import Link from "next/link";

export function SampleInvitation() {
  return (
    <section className="challenge-page" aria-labelledby="challenge-title">
      <div className="challenge-ticket" data-testid="challenge-invitation">
        <p className="eyebrow">THE CONNECTION IS CALLING</p>
        <div className="challenge-mark" aria-hidden="true">
          ✳
        </div>
        <h1 id="challenge-title" className="challenge-title">
          SAME FIVE.
          <br />
          <span className="text-accent">YOUR INSTINCT.</span>
        </h1>
        <p className="challenge-summary">
          A sample challenger picked <strong>Velvet Static.</strong>
          <br />
          The specimen score? <strong>3 out of 5.</strong>
        </p>
        <div className="challenge-rules">
          <span>ONE FAVOURITE</span>
          <span aria-hidden="true">/</span>
          <span>FIVE FIXED ROUNDS</span>
          <span aria-hidden="true">/</span>
          <span>NO TIMER</span>
        </div>
        <Link href="/g/demo" className="button button-primary">
          Preview the arena <span aria-hidden="true">↗</span>
        </Link>
        <p className="prototype-detail">
          Invitation design only. No challenge exists or has been shared. This
          opens the same single-round visual preview; exact five-round replay
          comes later.
        </p>
      </div>
      <aside className="challenge-aside">
        <p className="mono-label">A LITTLE FRIENDLY CULTURE CLASH.</p>
        <p>
          The future game freezes the creator's actual five rounds. Your friend
          gets the same choices, order and scoring rules.
        </p>
        <Link href="/how-it-works" className="inline-link">
          What are we predicting? <span aria-hidden="true">↗</span>
        </Link>
      </aside>
    </section>
  );
}
