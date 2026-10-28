import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import { connection } from "next/server";
import { FixtureProvider } from "tasteduel-fixture-entry";
import { fixturesEnabled } from "@/features/mode/config";
import { GuestSessionControls } from "@/features/seed/guest-session-controls";
import "./globals.css";

const displayFont = localFont({
  src: "../../public/fonts/BarlowCondensed-Bold.ttf",
  weight: "700",
  variable: "--font-display",
  display: "swap",
});
const bodyFont = localFont({
  src: "../../public/fonts/Manrope-variable.ttf",
  weight: "400 600",
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Taste Duel — One favourite. Five duels.",
    template: "%s · Taste Duel",
  },
  description:
    "One favourite. Five Qloo-ranked cultural duels. Predict connections and discover something new.",
  robots: { index: false, follow: false },
};
export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Per-response CSP nonces require request-time rendering, including landing.
  await connection();
  return (
    <html lang="en">
      <body className={`${displayFont.variable} ${bodyFont.variable}`}>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <FixtureProvider>
          <div className="site-shell" data-testid="prototype-frame">
            <div
              className="prototype-banner"
              role="region"
              aria-label={
                fixturesEnabled
                  ? "Development fixture mode"
                  : "Ranking source information"
              }
              data-testid={
                fixturesEnabled ? "fixture-mode-banner" : "development-status"
              }
            >
              <span className="status-indicator" aria-hidden="true" />
              <span>
                {fixturesEnabled ? (
                  <>
                    <strong>Development fixtures</strong> — fictional data and
                    outcomes. No live Qloo.
                  </>
                ) : (
                  <>
                    <strong>Qloo ranks. You predict.</strong> Ranking and
                    curator mode are identified in each game.
                  </>
                )}
              </span>
            </div>
            <header className="site-header">
              <Link className="wordmark" href="/" aria-label="Taste Duel home">
                TASTE <span>DUEL</span>
                <span className="wordmark-star" aria-hidden="true">
                  ✳
                </span>
              </Link>
              <nav className="header-nav" aria-label="Main navigation">
                {!fixturesEnabled && <GuestSessionControls />}
                <Link href="/how-it-works">
                  How it works <span aria-hidden="true">↗</span>
                </Link>
              </nav>
            </header>
            <main id="main" className="main-shell" tabIndex={-1}>
              {children}
            </main>
            <footer className="site-footer">
              <span>FOLLOW YOUR CURIOSITY.</span>
              <span>
                {fixturesEnabled ? "Local fixture play" : "Taste Duel"}{" "}
                <span aria-hidden="true">/</span>{" "}
                <Link href="/how-it-works">About the game</Link>
              </span>
            </footer>
          </div>
        </FixtureProvider>
      </body>
    </html>
  );
}
