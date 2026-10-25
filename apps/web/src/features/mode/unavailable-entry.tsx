import type { ReactNode } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";

// Production composition root: deliberately imports no fixture modules/data.
export function FixtureProvider({ children }: { children: ReactNode }) {
  return children;
}
export function FixtureLanding() {
  return (
    <section className="reading-page" aria-labelledby="unavailable-title">
      <p className="eyebrow">THE NEXT CONNECTION IS COMING</p>
      <h1 id="unavailable-title" className="hero-title">
        TASTE THE
        <br />
        <span className="text-accent">UNEXPECTED.</span>
      </h1>
      <p>The game is in development. Live games are not connected yet.</p>
      <Link href="/how-it-works" className="button button-secondary">
        How the game will work
      </Link>
    </section>
  );
}
export function FixtureGame(_props: { story?: string }) {
  notFound();
}
export function FixtureResults() {
  notFound();
}
export function FixtureChallenge() {
  notFound();
}
export function FixtureStories(_props: { story?: string }) {
  notFound();
}
