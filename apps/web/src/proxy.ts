import { NextResponse, type NextRequest } from "next/server";
import { contentSecurityPolicy } from "./lib/security/csp";

export function proxy(request: NextRequest) {
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
