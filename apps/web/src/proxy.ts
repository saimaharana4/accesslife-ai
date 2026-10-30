import { NextResponse, type NextRequest } from "next/server";
import { contentSecurityPolicy } from "./lib/security/csp";

const LEGACY_WEB_HOST = "tasteduel-web-dfthmgvvaa-el.a.run.app";
const CANONICAL_WEB_ORIGIN =
  "https://tasteduel-web-902056825143.asia-south1.run.app";

export function proxy(request: NextRequest) {
  // Old links resolve to this same Cloud Run service. Send new visitors to the
  // canonical host while letting existing guest cookies finish their session.
  if (
    request.nextUrl.hostname === LEGACY_WEB_HOST &&
    request.headers.get("accept")?.includes("text/html") &&
    !request.cookies.has("tasteduel_session")
  ) {
    const destination = new URL(
      `${request.nextUrl.pathname}${request.nextUrl.search}`,
      CANONICAL_WEB_ORIGIN,
    );
    return NextResponse.redirect(destination, 308);
  }

  const nonce = Buffer.from(
    crypto.getRandomValues(new Uint8Array(32)),
  ).toString("base64");
  const csp = contentSecurityPolicy(
    nonce,
    process.env.NODE_ENV === "development",
  );
  const headers = new Headers(request.headers);
  // Overwrite caller-supplied values before Next extracts the rendering nonce.
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  return response;
}

export const config = {
  matcher: ["/((?!api/|_next/|art/|fonts/|favicon.ico).*)"],
};
