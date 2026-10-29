import {
  getOperation,
  validRequest,
  validResponse,
} from "./forward-contract.ts";

export type ForwardSettings = {
  apiUrl: string;
  // Cloud Run ID-token audience stays the canonical service origin even when
  // apiUrl targets a reviewed revision tag. Server configuration only.
  apiAudience?: string;
  allowedOrigins: string[];
  allowLocalHttp?: boolean;
  // Server-only IAM factory. Never accept an inbound Authorization value.
  identityToken?: (audience: string) => Promise<string>;
  fetch?: typeof fetch;
};
const COOKIE = "tasteduel_session";
const tokenPattern = /^[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}$/i;
const keyPattern = /^[A-Za-z0-9_-]{16,128}$/;
const safeHeaders = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
};
const allowed = [
  ["POST", /^\/v1\/sessions$/],
  ["GET", /^\/v1\/sessions\/current$/],
  ["DELETE", /^\/v1\/sessions\/current$/],
  ["GET", /^\/v1\/entities\/search$/],
  ["POST", /^\/v1\/games$/],
  ["GET", /^\/v1\/games\/[0-9a-f-]{36}(?:\/(?:round|generation|results))?$/i],
  ["POST", /^\/v1\/games\/[0-9a-f-]{36}\/(?:answer|advance)$/i],
  ["GET", /^\/v1\/health\/(?:live|ready)$/],
  ["GET", /^\/v1\/discoveries$/],
  ["POST", /^\/v1\/discoveries$/],
  ["DELETE", /^\/v1\/discoveries\/[0-9a-f-]{36}$/i],
  ["POST", /^\/v1\/challenges$/],
  ["GET", /^\/v1\/challenges\/[A-Za-z0-9_-]{22,80}$/],
  ["DELETE", /^\/v1\/challenges\/[A-Za-z0-9_-]{22,80}$/],
  ["POST", /^\/v1\/challenges\/[A-Za-z0-9_-]{22,80}\/plays$/],
] as const;

export function publicFailure(
  status: number,
  code: string,
  message: string,
  retryable = false,
  retryAfter?: number,
) {
  return Response.json(
    {
      error: {
        code,
        message,
        retryable,
        request_id: crypto.randomUUID(),
        field_errors: [],
        retry_after_seconds: retryAfter ?? null,
      },
    },
    { status, headers: safeHeaders },
  );
}
function loopback(host: string) {
  return ["localhost", "127.0.0.1", "[::1]"].includes(host);
}
function originAllowed(url: URL, settings: ForwardSettings) {
  return (
    settings.allowedOrigins.includes(url.origin) &&
    (url.protocol === "https:" ||
      (settings.allowLocalHttp === true &&
        url.protocol === "http:" &&
        loopback(url.hostname)))
  );
}
function publicRequestUrl(
  request: Request,
  settings: ForwardSettings,
): URL | undefined {
  const internal = new URL(request.url);
  const host = request.headers.get("host");
  // Next standalone/Cloud Run may reconstruct an internal HTTP URL. A raw Host
  // can only select an already configured public origin, never invent one.
  // Deliberately ignore Forwarded and every X-Forwarded-* header.
  if (host === null)
    return originAllowed(internal, settings) ? internal : undefined;
  if (!/^[A-Za-z0-9.\-\[\]:]+$/.test(host)) return undefined;
  const matches = settings.allowedOrigins.flatMap((configured) => {
    try {
      const candidate = new URL(configured);
      return configured === candidate.origin &&
        originAllowed(candidate, settings) &&
        candidate.host === host.toLowerCase()
        ? [candidate]
        : [];
    } catch {
      return [];
    }
  });
  // Ambiguous HTTP/HTTPS entries for the same host are configuration errors.
  if (matches.length !== 1) return undefined;
  return new URL(`${matches[0].origin}${internal.pathname}${internal.search}`);
}
async function readBounded(
  stream: ReadableStream<Uint8Array> | null,
  limit: number,
  signal?: AbortSignal,
) {
  if (!stream) return "";
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let size = 0,
    result = "";
  const abort = () => {
    void reader.cancel().catch(() => undefined);
  };
  signal?.addEventListener("abort", abort, { once: true });
  try {
    while (true) {
      if (signal?.aborted) throw new Error("READ_INTERRUPTED");
      const { value, done } = await reader.read();
      if (signal?.aborted) throw new Error("READ_INTERRUPTED");
      if (done) break;
      size += value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new Error("SIZE_LIMIT");
      }
      result += decoder.decode(value, { stream: true });
    }
    return result + decoder.decode();
  } finally {
    signal?.removeEventListener("abort", abort);
    reader.releaseLock();
  }
}
function cookieForUpstream(request: Request) {
  const entries = (request.headers.get("cookie") ?? "")
    .split(";")
    .map((part) => part.trim())
    .filter((part) => part.startsWith(`${COOKIE}=`));
  if (entries.length !== 1) return undefined;
  const token = entries[0].slice(COOKIE.length + 1);
  return tokenPattern.test(token) ? `${COOKIE}=${token}` : undefined;
}
function safeSetCookie(
  upstream: Response,
  local: boolean,
  method: string,
  path: string,
) {
  if (
    !(method === "POST" && path === "/v1/sessions") &&
    !(method === "DELETE" && path === "/v1/sessions/current")
  )
    return undefined;
  const values = upstream.headers.getSetCookie();
  const cookie = values.find((value) => value.startsWith(`${COOKIE}=`));
  if (!cookie) return undefined;
  const rawToken = cookie.split(";", 1)[0].slice(COOKIE.length + 1);
  // Starlette's delete_cookie emits a quoted empty value. Normalize only this
  // tombstone; quoted authentication tokens remain invalid.
  const token = method === "DELETE" && rawToken === '""' ? "" : rawToken;
  const deleting = method === "DELETE" && token === "";
  if (!deleting && !tokenPattern.test(token)) throw new Error("INVALID_COOKIE");
  const rawAge = /(?:^|;)\s*max-age=(\d+)/i.exec(cookie)?.[1];
  const age = deleting ? 0 : Math.min(Number(rawAge ?? 86400), 31 * 86400);
  return `${COOKIE}=${token}; Path=/; Max-Age=${age}; HttpOnly; SameSite=Lax${local ? "" : "; Secure"}`;
}
const messages: Record<string, string> = {
  SESSION_RATE_LIMITED:
    "This guest session has made too many requests. Pause, then retry the same saved action.",
  REQUEST_TIMEOUT:
    "The request body took too long. Retry the same saved action.",
  CHALLENGE_EXPIRED: "This challenge has expired. Start a new solo game.",
  CHALLENGE_REVOKED:
    "This challenge is no longer available. Start a new solo game.",
  CHALLENGE_UNAVAILABLE:
    "This challenge is unavailable. Start a new solo game.",
  CHALLENGE_NOT_FOUND:
    "This challenge could not be found. Check the link or start a new solo game.",
  CHALLENGE_INCOMPLETE: "Finish all five rounds before creating a challenge.",
  CHALLENGE_RESHARE_UNAVAILABLE:
    "A friend replay cannot create a detached challenge. Start a new solo game to share.",
  CHALLENGE_METADATA_CONFLICT:
    "This session retains different metadata. Open the fixed challenge in a fresh guest session.",
  DISCOVERY_EXPIRED:
    "This discovery's supporting evidence has expired. Play a fresh duel to explore it again.",
  DISCOVERY_REMOVED:
    "This save was removed. Check your discoveries before making a new explicit save.",
  DISCOVERY_LIMIT:
    "This guest session has reached its discovery limit. Remove an item before saving another.",
  SESSION_REQUIRED: "Start a guest session to continue.",
  NOT_FOUND: "This game or round is unavailable in your guest session.",
  EXPIRED: "This game has expired. Start a new duel.",
  GAME_EXPIRED: "This game has expired. Start a new duel.",
  GAME_CANCELLED: "This game is no longer active. Start a new duel.",
  GAME_INCOMPLETE: "Complete all five rounds before opening results.",
  NO_CURRENT_ROUND:
    "This game has no unanswered current round. Reload its saved state.",
  ROUND_AWAITING_ADVANCE: "Read the accepted reveal and select Next.",
  IDEMPOTENCY_CONFLICT:
    "This request key belongs to different input. Start a confirmed new request.",
  REVISION_CONFLICT:
    "The game changed in another request. Reload its saved state.",
  ANSWER_CONFLICT:
    "A different answer was already accepted. Reload the saved reveal.",
  GENERATION_UNAVAILABLE:
    "This duel could not be prepared. Retry the same saved request.",
  GENERATION_INSUFFICIENT_COVERAGE:
    "There are not enough verified comparisons for this favourite. Choose another artist or film.",
  GENERATION_CONFIGURATION_UNAVAILABLE:
    "Game preparation is unavailable. Please try again later.",
  GENERATION_PROVIDER_UNAVAILABLE:
    "The cultural ranking service is temporarily unavailable. Retry the same saved request.",
  GENERATION_IN_PROGRESS:
    "This generation is still running. Inspect its saved status and retry when its execution claim permits recovery.",
  QLOO_UNAVAILABLE: "Qloo search is temporarily unavailable. Retry shortly.",
  INVALID_REQUEST: "Check your selection and try again.",
  VALIDATION_ERROR: "Check your selection and try again.",
  INVALID_INPUT: "Check your selection and try again.",
  ANSWER_REQUIRED: "Accept the current answer before advancing.",
  STATE_CONFLICT: "The saved game state changed. Reload to continue.",
  SEED_EXPIRED:
    "This saved seed has expired. Search again in a new guest session.",
  GENERATION_ATTEMPTS_EXHAUSTED:
    "This generation could not be completed. Choose another seed.",
  GENERATION_CANCELLED:
    "This generation was cancelled. Start a new guest session.",
  GENERATION_CLAIM_EXPIRED:
    "The execution claim expired. Retry the same generation request.",
  GENERATION_CONTEXT_CONFLICT:
    "This generation no longer matches its saved context. Start a new duel.",
  GENERATION_DEADLINE_EXCEEDED:
    "Generation exceeded its deadline. Retry the same request safely.",
  GENERATION_FAILED:
    "Generation could not complete. Retry the same request safely.",
  REQUEST_TOO_LARGE: "The request is too large.",
  ORIGIN_NOT_ALLOWED: "Open this page directly before changing a game.",
  STORED_STATE_UNAVAILABLE:
    "The saved game is temporarily unavailable. Reload to recover it.",
  SERVICE_UNAVAILABLE: "The game service is temporarily unavailable.",
  DATABASE_UNAVAILABLE: "The saved game is temporarily unavailable.",
  QLOO_DATABASE_UNAVAILABLE: "Qloo search is temporarily unavailable.",
  SCHEMA_NOT_READY: "The game service is not ready yet.",
  FOUNDATION_NOT_IMPLEMENTED: "This operation is not available yet.",
  REQUEST_FAILED: "The request could not be completed. Retry safely.",
};

export async function forwardApi(
  request: Request,
  settings: ForwardSettings,
): Promise<Response> {
  let api: URL, incoming: URL, audience: string;
  try {
    api = new URL(settings.apiUrl);
    audience = settings.apiAudience ?? api.origin;
    if (settings.apiAudience !== undefined) {
      const configuredAudience = new URL(settings.apiAudience);
      if (
        configuredAudience.protocol !== "https:" ||
        configuredAudience.origin !== settings.apiAudience ||
        configuredAudience.username ||
        configuredAudience.password
      )
        throw new Error();
    }
    const publicUrl = publicRequestUrl(request, settings);
    if (
      api.username ||
      api.password ||
      api.search ||
      api.hash ||
      !["", "/"].includes(api.pathname)
    )
      throw new Error();
    if (
      !(
        api.protocol === "https:" ||
        (settings.allowLocalHttp &&
          api.protocol === "http:" &&
          loopback(api.hostname))
      )
    )
      throw new Error();
    if (!publicUrl)
      return publicFailure(
        403,
        "ORIGIN_REJECTED",
        "This web origin is not allowed.",
      );
    incoming = publicUrl;
  } catch {
    return publicFailure(
      503,
      "WEB_API_UNCONFIGURED",
      "The game service is not configured.",
      true,
    );
  }
  const method = request.method;
  const rawPath = incoming.pathname;
  if (!rawPath.startsWith("/api/v1/") || /%|\\|\/\//.test(rawPath))
    return publicFailure(404, "NOT_FOUND", "This operation is unavailable.");
  const path = rawPath.replace(/^\/api\/v1/, "/v1");
  if (!allowed.some(([verb, pattern]) => method === verb && pattern.test(path)))
    return publicFailure(404, "NOT_FOUND", "This operation is unavailable.");
  if (method !== "GET") {
    const origin = request.headers.get("origin");
    if (
      origin !== incoming.origin ||
      !settings.allowedOrigins.includes(origin) ||
      request.headers.get("sec-fetch-site") === "cross-site"
    )
      return publicFailure(
        403,
        "ORIGIN_REJECTED",
        "Open this page directly before changing a game.",
      );
  } else if (request.headers.get("sec-fetch-site") === "cross-site")
    return publicFailure(
      403,
      "ORIGIN_REJECTED",
      "Cross-site requests are unavailable.",
    );
  const operation = getOperation(path, method);
  if (!operation)
    return publicFailure(404, "NOT_FOUND", "This operation is unavailable.");
  const headers = new Headers({ Accept: "application/json" });
  const cookie = cookieForUpstream(request);
  if (cookie) headers.set("Cookie", cookie);
  const key = request.headers.get("idempotency-key");
  const keyRequired =
    method === "POST" &&
    (/^\/v1\/games(?:\/|$)/.test(path) ||
      path === "/v1/discoveries" ||
      /^\/v1\/challenges(?:\/|$)/.test(path));
  if ((keyRequired && !key) || (key && !keyPattern.test(key)))
    return publicFailure(
      422,
      "INVALID_REQUEST",
      "A valid request key is required.",
    );
  if (key && keyRequired) headers.set("Idempotency-Key", key);
  // The private API independently checks the verified web origin.
  if (method !== "GET") headers.set("Origin", incoming.origin);
  let body: unknown;
  try {
    if (method === "POST") {
      if (
        !/^application\/json(?:;|$)/i.test(
          request.headers.get("content-type") ?? "",
        )
      )
        return publicFailure(415, "INVALID_REQUEST", "Use a JSON request.");
      const text = await readBounded(
        request.body,
        8192,
        AbortSignal.any([request.signal, AbortSignal.timeout(3000)]),
      );
      body = JSON.parse(text);
    }
    if (!validRequest(operation, incoming.searchParams, body))
      return publicFailure(
        422,
        "INVALID_REQUEST",
        "Check your selection and try again.",
      );
  } catch {
    return publicFailure(
      422,
      "INVALID_REQUEST",
      "The request body is invalid or too large.",
    );
  }
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    // Cloud Run cold API startup measured 15-18s. Keep the proxy deadline
    // outside that startup plus bounded provider work; API generation remains 20s.
    method === "POST" && path === "/v1/games"
      ? 45000
      : path === "/v1/entities/search"
        ? 35000
        : 25000,
  );
  const abort = () => controller.abort();
  request.signal.addEventListener("abort", abort, { once: true });
  try {
    if (request.signal.aborted) controller.abort();
    if (settings.identityToken)
      headers.set(
        "Authorization",
        `Bearer ${await settings.identityToken(audience)}`,
      );
    if (body !== undefined) headers.set("Content-Type", "application/json");
    const target = new URL(path, api);
    target.search = incoming.search;
    const upstream = await (settings.fetch ?? fetch)(target, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      redirect: "manual",
      cache: "no-store",
      signal: controller.signal,
    });
    if (upstream.status >= 300 && upstream.status < 400)
      return publicFailure(
        502,
        "INVALID_RESPONSE",
        "The game service returned an unavailable response.",
        true,
      );
    const responseHeaders = new Headers(safeHeaders);
    const setCookie = upstream.ok
      ? safeSetCookie(upstream, incoming.protocol === "http:", method, path)
      : undefined;
    if (setCookie) responseHeaders.set("Set-Cookie", setCookie);
    if (
      upstream.status === 204 &&
      method === "DELETE" &&
      (path === "/v1/sessions/current" ||
        /^\/v1\/discoveries\/[0-9a-f-]{36}$/i.test(path) ||
        /^\/v1\/challenges\/[A-Za-z0-9_-]{22,80}$/.test(path))
    )
      return new Response(null, { status: 204, headers: responseHeaders });
    if (
      !/^application\/json(?:;|$)/i.test(
        upstream.headers.get("content-type") ?? "",
      )
    )
      throw new Error("INVALID_CONTENT_TYPE");
    const data: unknown = JSON.parse(
      await readBounded(upstream.body, 262144, controller.signal),
    );
    if (!validResponse(operation, upstream.status, data))
      throw new Error("INVALID_RESPONSE");
    if (!upstream.ok) {
      const error = (
        data as {
          error: {
            code: string;
            retryable: boolean;
            retry_after_seconds?: number;
          };
        }
      ).error;
      const code = Object.hasOwn(messages, error.code)
        ? error.code
        : "REQUEST_FAILED";
      return publicFailure(
        upstream.status,
        code,
        messages[code],
        error.retryable,
        error.retry_after_seconds,
      );
    }
    return Response.json(data, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return publicFailure(
      controller.signal.aborted ? 504 : 502,
      controller.signal.aborted ? "REQUEST_INTERRUPTED" : "SERVICE_UNAVAILABLE",
      "The response was interrupted. Retry to recover the same saved request.",
      true,
    );
  } finally {
    clearTimeout(timeout);
    request.signal.removeEventListener("abort", abort);
  }
}
