import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
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
    template: "%s · Taste Duel prototype",
  },
  description:
    "A visual prototype of a cultural prediction game. Fictional entities and sample rankings; no live Qloo integration.",
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
        <div className="site-shell" data-testid="prototype-frame">
          <div
            className="prototype-banner"
            role="region"
            aria-label="Prototype status"
          >
            <span className="status-indicator" aria-hidden="true" />
            <span>
              <strong>Prototype</strong> — not live Qloo. All entities and
              rankings are fictional.
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
              Design study 01 <span aria-hidden="true">/</span>{" "}
              <Link href="/how-it-works">About this prototype</Link>
            </span>
          </footer>
        </div>
      </body>
    </html>
  );
}
