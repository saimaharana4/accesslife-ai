import Link from "next/link";
export default function LoadingSpecimenPage() {
  return (
    <section className="state-panel" aria-labelledby="loading-title">
      <p className="eyebrow">LOADING STATE / DESIGN SPECIMEN</p>
      <div className="loading-orbit" aria-hidden="true">
        ✳
      </div>
      <h1 id="loading-title">
        GOOD CONNECTIONS
        <br />
        <span className="text-accent">TAKE A MOMENT.</span>
      </h1>
      <p>
        This is a static waiting-state preview. No task is running and no live
        progress is being simulated.
      </p>
      <div className="state-actions">
        <Link href="/g/demo" className="button button-primary">
          View sample arena <span aria-hidden="true">↗</span>
        </Link>
        <Link href="/" className="button button-secondary">
          Back to seed selection
        </Link>
      </div>
    </section>
  );
}
