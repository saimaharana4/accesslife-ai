import Link from "next/link";
export default function ErrorSpecimenPage() {
  return (
    <section className="state-panel" aria-labelledby="error-title">
      <p className="eyebrow">UNAVAILABLE STATE / DESIGN SPECIMEN</p>
      <div className="state-error-mark" aria-hidden="true">
        ↗
      </div>
      <h1 id="error-title">
        A CONNECTION
        <br />
        <span className="text-accent">MISSED. NOT LOST.</span>
      </h1>
      <p>
        The finished game will preserve accepted progress and offer a useful
        retry when its taste provider is unavailable. This is a static error
        design; no service was called.
      </p>
      <div className="state-actions">
        <Link href="/g/demo" className="button button-primary">
          Return to sample arena <span aria-hidden="true">↗</span>
        </Link>
        <Link href="/" className="button button-secondary">
          Choose another demo seed
        </Link>
      </div>
    </section>
  );
}
