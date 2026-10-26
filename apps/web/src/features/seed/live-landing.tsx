import Link from "next/link";
import { LiveSeedLauncher } from "./live-seed-launcher";

export function LiveLanding() {
  return (
    <section className="landing-stage" aria-labelledby="landing-title">
      <div className="hero-copy">
        <p className="eyebrow">
          <span aria-hidden="true">✳</span> CULTURAL DISCOVERY. FIVE ROUNDS.
        </p>
        <h1 id="landing-title" className="hero-title">
          ONE FAVOURITE.
          <br />
          <span className="text-accent">FIVE DUELS.</span>
        </h1>
        <p className="hero-description">
          You know what you love.
          <br />
          Can you predict Qloo’s connections?
        </p>
        <LiveSeedLauncher />
      </div>
      <div className="hero-arena-preview">
        <div className="preview-label">
          <span>THE ART OF THE UNEXPECTED</span>
          <span aria-hidden="true">001 / TD</span>
        </div>
        <div
          className="preview-pair"
          aria-label="Project-owned title-card artwork. Your real contestants appear after generation."
        >
          <figure className="mini-cover mini-cover-one">
            {/* Owned local artwork; no provider image fetch. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/art/afterlight.svg" alt="" width="480" height="640" />
            <figcaption>
              <span>YOU PICK THE SEED</span>
              <strong>
                Follow
                <br />
                the feeling.
              </strong>
            </figcaption>
          </figure>
          <span className="preview-star" aria-hidden="true">
            ✳
          </span>
          <figure className="mini-cover mini-cover-two">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/art/velvet-static.svg" alt="" width="480" height="640" />
            <figcaption>
              <span>QLOO SETS THE RANKING</span>
              <strong>
                Find the
                <br />
                unexpected.
              </strong>
            </figcaption>
          </figure>
        </div>
        <div className="preview-caption">
          <p>
            GOOD TASTE.
            <br />
            <span>UNEXPECTED CONNECTIONS.</span>
          </p>
          <Link className="inline-link" href="/how-it-works">
            How the duel works <span aria-hidden="true">↗</span>
          </Link>
        </div>
        <p className="seed-help">
          Original title-card artwork. Not sample Qloo recommendations.
        </p>
      </div>
    </section>
  );
}
