import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";
import path from "node:path";
export default function configuration(phase: string): NextConfig {
  const fixturesEnabled =
    phase === PHASE_DEVELOPMENT_SERVER &&
    process.env.TASTEDUEL_FIXTURES === "1";
  // Turbopack's alias target is project-relative: Windows absolute imports are
  // unsupported. Webpack receives its required absolute filesystem path below.
  const fixtureEntry = fixturesEnabled
    ? "./src/features/fixtures/entry.tsx"
    : "./src/features/mode/unavailable-entry.tsx";
  const config: NextConfig = {
    output: "standalone",
    devIndicators: false,
    allowedDevOrigins: ["127.0.0.1", "localhost"],
    poweredByHeader: false,
    images: {
      unoptimized: true,
      remotePatterns: [],
      localPatterns: [{ pathname: "/art/**" }],
    },
    outputFileTracingRoot: process.cwd() + "/../..",
    env: { NEXT_PUBLIC_TASTEDUEL_FIXTURES: fixturesEnabled ? "1" : "0" },
    turbopack: { resolveAlias: { "tasteduel-fixture-entry": fixtureEntry } },
    webpack(config) {
      config.resolve.alias["tasteduel-fixture-entry"] = path.resolve(
        process.cwd(),
        fixtureEntry,
      );
      return config;
    },
    async headers() {
      return [
        {
          source: "/:path*",
          headers: [
            { key: "X-Content-Type-Options", value: "nosniff" },
            {
              key: "Referrer-Policy",
              value: "strict-origin-when-cross-origin",
            },
            {
              key: "Permissions-Policy",
              value: "camera=(), microphone=(), geolocation=()",
            },
          ],
        },
        ...["/g/:path*", "/results/:path*", "/c/:path*"].map((source) => ({
          source,
          headers: [
            { key: "Cache-Control", value: "private, no-store, max-age=0" },
            { key: "Referrer-Policy", value: "no-referrer" },
            { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
          ],
        })),
      ];
    },
  };
  return config;
}
