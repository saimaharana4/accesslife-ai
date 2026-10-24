import { NextRequest } from "next/server";
import { GoogleAuth } from "google-auth-library";
const allowed = new Set([
  "cities",
  "places",
  "sessions",
  "plans",
  "runs",
  "trips",
  "evidence",
  "intent",
  "health",
  "providers",
]);
async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (
    !allowed.has(path[0]) ||
    path.some((p) => p === "." || p === ".." || !/^[a-zA-Z0-9_:.\-]+$/.test(p))
  )
    return Response.json({ error: { message: "Not found" } }, { status: 404 });
  const origin = request.headers.get("origin");
  const publicOrigin =
    process.env.APP_PUBLIC_URL || new URL(request.url).origin;
  if (
    !["GET", "HEAD"].includes(request.method) &&
    origin &&
    origin !== publicOrigin
  )
    return Response.json(
      { error: { message: "Origin denied" } },
      { status: 403 },
    );
  const base = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
  const headers = new Headers();
  for (const key of [
    "cookie",
    "content-type",
    "last-event-id",
    "idempotency-key",
    "origin",
  ]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    if (process.env.API_AUDIENCE) {
      const client = await new GoogleAuth().getIdTokenClient(
        process.env.API_AUDIENCE,
      );
      const auth = await client.getRequestHeaders();
      headers.set("authorization", auth.get("authorization") || "");
    }
    const body = ["GET", "HEAD"].includes(request.method)
      ? undefined
      : await request.arrayBuffer();
    if (body && body.byteLength > 20000)
      return Response.json(
        { error: { message: "Request too large" } },
        { status: 413 },
      );
    const upstream = await fetch(
      `${base}/v1/${path.map(encodeURIComponent).join("/")}${new URL(request.url).search}`,
      {
        method: request.method,
        headers,
        body,
        cache: "no-store",
        signal: request.signal,
      },
    );
    const resultHeaders = new Headers({
      "Cache-Control": "no-store",
      "X-Accel-Buffering": "no",
    });
    for (const name of ["content-type", "set-cookie", "retry-after"]) {
      const value = upstream.headers.get(name);
      if (value) resultHeaders.set(name, value);
    }
    return new Response(upstream.body, {
      status: upstream.status,
      headers: resultHeaders,
    });
  } catch {
    return Response.json(
      {
        error: {
          message: "The planning service is unavailable. Please retry shortly.",
          retryable: true,
        },
      },
      { status: 503 },
    );
  }
}
export { forward as GET, forward as POST, forward as PATCH, forward as DELETE };
