// Server-only Cloud Run IAM identity. Credentials never enter a public variable.
// The host/path are constant; only a reviewed configured API origin is the audience.
const metadata =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";
let cached: { audience: string; token: string; until: number } | undefined;
export async function metadataIdentityToken(
  audience: string,
  transport: typeof fetch = fetch,
) {
  const target = new URL(audience);
  if (
    target.protocol !== "https:" ||
    target.origin !== audience ||
    target.username ||
    target.password
  )
    throw new Error("INVALID_AUDIENCE");
  if (cached?.audience === audience && cached.until > Date.now())
    return cached.token;
  const endpoint = new URL(metadata);
  endpoint.searchParams.set("audience", audience);
  endpoint.searchParams.set("format", "full");
  const response = await transport(endpoint, {
    headers: { "Metadata-Flavor": "Google" },
    redirect: "error",
    cache: "no-store",
    signal: AbortSignal.timeout(1500),
  });
  if (
    !response.ok ||
    response.headers.get("Metadata-Flavor") !== "Google" ||
    !response.body
  )
    throw new Error("IAM_UNAVAILABLE");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let token = "",
    size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 16384) {
        await reader.cancel();
        throw new Error("IAM_UNAVAILABLE");
      }
      token += decoder.decode(value, { stream: true });
    }
    token = (token + decoder.decode()).trim();
  } finally {
    reader.releaseLock();
  }
  if (!/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token))
    throw new Error("IAM_UNAVAILABLE");
  // Cache briefly, never past the claimed expiration; this is not JWT verification.
  let expires: number;
  try {
    const payload = JSON.parse(
      Buffer.from(token.split(".")[1], "base64url").toString("utf8"),
    ) as { exp?: number; aud?: string };
    if (
      payload.aud !== audience ||
      typeof payload.exp !== "number" ||
      !Number.isFinite(payload.exp)
    )
      throw new Error();
    expires = payload.exp * 1000 - 60000;
    if (expires <= Date.now()) throw new Error();
  } catch {
    throw new Error("IAM_UNAVAILABLE");
  }
  cached = { audience, token, until: Math.min(expires, Date.now() + 240000) };
  return token;
}
