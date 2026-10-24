import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "AccessLife — More possibility. Less uncertainty.",
  description:
    "A thoughtful cultural outing planner with visible accessibility evidence.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
