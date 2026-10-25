import Link from "next/link";
export default function NotFound() {
  return (
    <section className="state-panel" aria-labelledby="not-found-title">
      <p className="eyebrow">THAT CONNECTION DOES NOT EXIST</p>
      <h1 id="not-found-title">
        BACK TO
        <br />
        <span className="text-accent">THE GOOD STUFF.</span>
      </h1>
      <p>
        This route is outside the visual prototype. No real game or challenge
        can be opened yet.
      </p>
      <Link href="/" className="button button-primary">
        Find a fictional favourite <span aria-hidden="true">↗</span>
      </Link>
    </section>
  );
}
