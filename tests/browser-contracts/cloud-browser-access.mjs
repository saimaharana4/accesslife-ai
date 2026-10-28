const canonicalWeb = "https://tasteduel-web-902056825143.asia-south1.run.app";
const serviceWeb = "https://tasteduel-web-dfthmgvvaa-el.a.run.app";
const apiOrigins = new Set([
  "https://tasteduel-api-dfthmgvvaa-el.a.run.app",
  "https://tasteduel-api-902056825143.asia-south1.run.app",
]);

/** Test-only access configuration; public verification must carry no operator identity. */
export function cloudBrowserAccess(env) {
  const mode = env.TASTEDUEL_CLOUD_ACCESS_MODE ?? "private";
  if (!["private", "public"].includes(mode))
    throw new Error("Cloud access mode must be private or public");
  const origin = env.TASTEDUEL_CANDIDATE_ORIGIN;
  let target;
  try {
    target = new URL(origin);
  } catch {
    throw new Error("An exact reviewed Cloud Run web origin is required");
  }
  const reviewedTag =
    /^https:\/\/[a-z][a-z0-9-]{0,62}---tasteduel-web-dfthmgvvaa-el\.a\.run\.app$/.test(
      origin,
    ) && env.TASTEDUEL_CLOUD_REVIEWED_TAG_ORIGIN === origin;
  if (
    target.protocol !== "https:" ||
    target.origin !== origin ||
    (![canonicalWeb, serviceWeb].includes(origin) && !reviewedTag)
  )
    throw new Error("An exact reviewed Taste Duel web origin is required");
  const identityToken = env.TASTEDUEL_CANDIDATE_ID_TOKEN;
  const privateApiOrigin = env.TASTEDUEL_CLOUD_PRIVATE_API_ORIGIN;
  if (mode === "public") {
    if (origin !== canonicalWeb || identityToken)
      throw new Error(
        "Public verification requires the canonical origin and no operator token",
      );
    if (!apiOrigins.has(privateApiOrigin))
      throw new Error(
        "Public verification requires the reviewed private API origin",
      );
  } else if (!identityToken) {
    throw new Error(
      "Private candidate verification requires an in-memory identity token",
    );
  }
  return {
    mode,
    origin,
    identityToken: identityToken ?? null,
    privateApiOrigin: privateApiOrigin ?? null,
  };
}
