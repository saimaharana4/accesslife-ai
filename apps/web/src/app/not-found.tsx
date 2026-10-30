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
        This link does not match a Taste Duel page. Check the address, or start
        a new duel.
      </p>
      <Link href="/" className="button button-primary">
        Start a new duel <span aria-hidden="true">↗</span>
      </Link>
    </section>
  );
}
