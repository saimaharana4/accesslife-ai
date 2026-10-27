import { forwardApi, type ForwardSettings } from "./forward.ts";
import type { ApiSchemas } from "./contracts";

export const challengeSlug = /^[A-Za-z0-9_-]{22,80}$/;

// Configuration only: never derive a public URL from Host, Referer or request input.
export function configuredCanonicalOrigin(
  value: string | undefined,
  allowedOrigins: string[],
  allowLocalHttp = false,
): string | null {
  if (!value || !allowedOrigins.includes(value)) return null;
  try {
    const url = new URL(value);
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    return url.origin === value &&
      !url.username &&
      !url.password &&
      (url.protocol === "https:" ||
        (allowLocalHttp && local && url.protocol === "http:"))
      ? value
      : null;
  } catch {
    return null;
  }
}

export async function readPublicChallenge(
  slug: string,
  settings: ForwardSettings,
): Promise<{
  invitation: ApiSchemas["ChallengeInvitationPublic"] | null;
  status: number;
}> {
  if (!challengeSlug.test(slug)) return { invitation: null, status: 404 };
  const publicOrigin = settings.allowedOrigins.find(
    (origin) =>
      configuredCanonicalOrigin(
        origin,
        settings.allowedOrigins,
        settings.allowLocalHttp,
      ) !== null,
  );
  if (!publicOrigin) return { invitation: null, status: 503 };
  // Reuse strict forwarding/response validation, deadlines and bounded reads.
  // This request is deliberately anonymous: no incoming cookie/headers are read.
  const response = await forwardApi(
    new Request(`${publicOrigin}/api/v1/challenges/${slug}`),
    settings,
  );
  if (response.status !== 200)
    return { invitation: null, status: response.status };
  const invitation =
    (await response.json()) as ApiSchemas["ChallengeInvitationPublic"];
  if (
    invitation.slug !== slug ||
    Date.parse(invitation.expires_at) <= Date.now()
  )
    return { invitation: null, status: 410 };
  return { invitation, status: 200 };
}
