import type { ApiSchemas } from "./contracts";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
  readonly retryAfterSeconds?: number;
  constructor(
    code: string,
    status: number,
    retryable: boolean,
    message: string,
    retryAfterSeconds?: number,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryable = retryable;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export const createKey = () => crypto.randomUUID();

async function request<T>(
  method: "GET" | "POST" | "DELETE",
  path: string,
  body?: unknown,
  key?: string,
  signal?: AbortSignal,
): Promise<T> {
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\")) {
    throw new ApiError(
      "INVALID_REQUEST",
      400,
      false,
      "The requested path is unavailable.",
    );
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (key) headers["Idempotency-Key"] = key;
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      signal,
    });
  } catch (error) {
    if (
      signal?.aborted ||
      (error instanceof DOMException && error.name === "AbortError")
    )
      throw error;
    throw new ApiError(
      "NETWORK_UNCERTAIN",
      0,
      true,
      "The response was interrupted. Retry to recover the same request.",
    );
  }
  if (response.status === 204) return undefined as T;
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw new ApiError(
      "INVALID_RESPONSE",
      502,
      true,
      "The service response was unavailable. Retry safely.",
    );
  }
  if (!response.ok) {
    const error = (value as ApiSchemas["ErrorEnvelope"])?.error;
    throw new ApiError(
      error?.code ?? "SERVICE_UNAVAILABLE",
      response.status,
      error?.retryable === true,
      error?.message ?? "The request could not be completed.",
      error?.retry_after_seconds ?? undefined,
    );
  }
  return value as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) =>
    request<T>("GET", path, undefined, undefined, signal),
  post: <T>(path: string, body: unknown, key?: string, signal?: AbortSignal) =>
    request<T>("POST", path, body, key, signal),
  delete: <T>(path: string, signal?: AbortSignal) =>
    request<T>("DELETE", path, undefined, undefined, signal),
};

let sessionRequest: Promise<ApiSchemas["SessionPublic"]> | undefined;
export function ensureSession(signal?: AbortSignal) {
  // A caller's cancellation must not cancel a shared session handshake.
  sessionRequest ??= api
    .post<ApiSchemas["SessionPublic"]>("/sessions", {})
    .finally(() => {
      sessionRequest = undefined;
    });
  if (!signal) return sessionRequest;
  return Promise.race([
    sessionRequest,
    new Promise<never>((_, reject) => {
      if (signal.aborted)
        reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
      else
        signal.addEventListener(
          "abort",
          () =>
            reject(signal.reason ?? new DOMException("Aborted", "AbortError")),
          { once: true },
        );
    }),
  ]);
}
