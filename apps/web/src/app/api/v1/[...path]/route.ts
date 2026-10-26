import { forwardApi } from "@/lib/api/forward";
import { metadataIdentityToken } from "@/lib/api/identity-token";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function handler(request: Request) {
  return forwardApi(request, {
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
  });
}

export {
  handler as GET,
  handler as POST,
  handler as DELETE,
  handler as PUT,
  handler as PATCH,
};
