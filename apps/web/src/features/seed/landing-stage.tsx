import Link from "next/link";
import { SeedLauncher } from "./seed-launcher";

export function LandingStage() {
  return (
    <section className="landing-stage" aria-labelledby="landing-title">
      <div className="hero-copy">
        <p className="eyebrow">
          <span aria-hidden="true">✳</span> YOUR NEXT CULTURAL OBSESSION STARTS
          HERE
        </p>
        <h1 id="landing-title" className="hero-title">
          ONE FAVOURITE.
          <br />
          <span className="text-accent">FIVE DUELS.</span>
        </h1>
        <p className="hero-description">
          You know what you love.
          <br />
          Can you read the connections?
        </p>
        <SeedLauncher />
      </div>
      <div className="hero-arena-preview">
        <div className="preview-label">
          <span>THE ART OF THE UNEXPECTED</span>
          <span aria-hidden="true">001 / TD</span>
        </div>
        <div
          className="preview-pair"
          aria-label="Original artwork for fictional cultural discoveries"
        >
          <figure className="mini-cover mini-cover-one">
            {/* Local, original SVG artwork does not benefit from an image proxy. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/art/afterlight.svg" alt="" width="480" height="640" />
            <figcaption>
              <span>FICTIONAL FILM</span>
              <strong>
                Afterlight
                <br />
                Assembly
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
              <span>FICTIONAL ARTIST</span>
              <strong>
                Velvet
                <br />
                Static
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
          <Link className="inline-link" href="/g/demo">
            Explore fixture states <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </div>
    </section>
  );
}
