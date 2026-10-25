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
    poweredByHeader: false,
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
            {
              key: "Content-Security-Policy",
              value: `default-src 'self'; script-src 'self' 'unsafe-inline'${process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'"}; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`,
            },
          ],
        },
      ];
    },
  };
  return config;
}
