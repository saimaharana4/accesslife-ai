import Link from "next/link";

export function SampleResult() {
  return (
    <section className="results-page" aria-labelledby="result-title">
      <div className="page-intro">
        <p className="eyebrow">THE REVEAL AFTER THE REVEALS</p>
        <h1 id="result-title">
          TASTE THE
          <br />
          <span className="text-accent">UNEXPECTED.</span>
        </h1>
        <p>A specimen of the final result. This is not a completed game.</p>
      </div>
      <div className="result-ticket" data-testid="result-ticket">
        <div className="ticket-top">
          <span>TASTE DUEL</span>
          <span className="mono-label">DESIGN SPECIMEN / 001</span>
        </div>
        <p className="ticket-label">SAMPLE SCORE · FICTIONAL GAME</p>
        <div
          className="ticket-score"
          aria-label="Illustrative score, 3 out of 5"
        >
          <strong>3</strong>
          <span>/ 5</span>
          <span className="ticket-star" aria-hidden="true">
            ✳
          </span>
        </div>
        <h2 className="ticket-title">CURIOUS BY NATURE.</h2>
        <p className="ticket-description">
          Five connections. A few surprises.
          <br />
          Something new to get lost in.
        </p>
        <div className="ticket-divider" aria-hidden="true" />
        <div className="ticket-discovery">
          <div className="ticket-art">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/art/slow-burn.svg" alt="" width="120" height="160" />
          </div>
          <div>
            <p className="mono-label">SAMPLE DISCOVERY</p>
            <h3>The Slow Burn Society</h3>
            <p>Fictional film · original title artwork</p>
          </div>
        </div>
        <div className="ticket-actions">
          <Link className="button button-primary" href="/c/demo">
            Preview a challenge <span aria-hidden="true">↗</span>
          </Link>
          <Link className="button button-secondary" href="/">
            Pick another favourite <span aria-hidden="true">↗</span>
          </Link>
        </div>
        <p className="ticket-fine-print">
          The 3/5 score is an illustrative design specimen. Nothing was scored,
          saved or shared.
        </p>
      </div>
    </section>
  );
}
