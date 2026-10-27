import "server-only";
import {
  configuredCanonicalOrigin,
  readPublicChallenge,
  challengeSlug,
} from "./challenge-server-core";
import { metadataIdentityToken } from "./identity-token";

function settings() {
  return {
    apiUrl: process.env.TASTEDUEL_API_URL ?? "",
    allowedOrigins: (process.env.TASTEDUEL_WEB_ORIGINS ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    allowLocalHttp: process.env.TASTEDUEL_ALLOW_LOCAL_HTTP === "true",
    identityToken:
      process.env.TASTEDUEL_API_IAM === "true"
        ? metadataIdentityToken
        : undefined,
  };
}

export function canonicalOrigin(): string | null {
  const config = settings();
  return configuredCanonicalOrigin(
    process.env.TASTEDUEL_CANONICAL_ORIGIN,
    config.allowedOrigins,
    config.allowLocalHttp,
  );
}

export function canonicalChallengeUrl(slug: string): string | null {
  const origin = canonicalOrigin();
  return origin && challengeSlug.test(slug) ? `${origin}/c/${slug}` : null;
}

export function readChallengeInvitation(slug: string) {
  return readPublicChallenge(slug, settings());
}
