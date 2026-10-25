import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import { FixtureProvider } from "tasteduel-fixture-entry";
import { fixturesEnabled } from "@/features/mode/config";
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
    "A cultural prediction game in development. Live games are not connected.",
  robots: { index: false, follow: false },
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
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
                  : "Development status"
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
                    <strong>In development</strong> — live games are not
                    connected.
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
                <Link href="/how-it-works">About this prototype</Link>
              </span>
            </footer>
          </div>
        </FixtureProvider>
      </body>
    </html>
  );
}
