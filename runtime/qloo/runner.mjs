/** Pinned official canonical MCP, with counted/guarded HTTP. Stdout is protocol only. */
import { dirname, join } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { createInterface } from "node:readline";
import { PassThrough } from "node:stream";
import { readFileSync } from "node:fs";

const packageRoot = dirname(
  fileURLToPath(import.meta.resolve("@qloo/qloo-harness")),
);
const packageVersion = JSON.parse(
  readFileSync(join(packageRoot, "../package.json"), "utf8"),
).version;
if (process.version !== "v24.18.1" || packageVersion !== "0.1.26")
  throw new Error("PIN_MISMATCH");
const ALLOWED = new Set([
  "qloo_capabilities",
  "qloo_describe",
  "qloo_recommend",
]);
const PATHS = new Set(["/search", "/entities", "/v2/insights"]);
const pending = new Map();
const canonicalInput = new PassThrough();
let sequence = 0;
let fetchTail = Promise.resolve();
const write = (value) => process.stdout.write(`${JSON.stringify(value)}\n`);

async function reserve(path) {
  const id = `reserve-${++sequence}`;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error("RESERVATION_TIMEOUT"));
    }, 2000);
    pending.set(id, { resolve, reject, timer });
    write({
      jsonrpc: "2.0",
      id,
      method: "tasteduel/reserve",
      params: { path },
    });
  });
}

const realFetch = globalThis.fetch;
async function guardedFetch(input, init = {}) {
  const previous = fetchTail;
  let release;
  fetchTail = new Promise((resolve) => {
    release = resolve;
  });
  await previous;
  try {
    const url = new URL(input instanceof Request ? input.url : String(input));
    const method =
      init.method ?? (input instanceof Request ? input.method : "GET");
    if (
      url.origin !== "https://hackathon.api.qloo.com" ||
      url.username ||
      url.password ||
      url.hash ||
      !PATHS.has(url.pathname) ||
      method !== "GET"
    )
      throw new Error("ENDPOINT_BLOCKED");
    if (!process.env.QLOO_API_KEY) throw new Error("CREDENTIAL_UNAVAILABLE");
    await reserve(url.pathname); // Includes hydration, retries and failures; parent persists before dispatch.
    const response = await realFetch(input, {
      ...init,
      redirect: "manual",
      signal: AbortSignal.any([
        ...(init.signal ? [init.signal] : []),
        AbortSignal.timeout(10000),
      ]),
    });
    const chunks = [];
    let length = 0;
    if (response.body) {
      for await (const chunk of response.body) {
        length += chunk.byteLength;
        if (length > 2000000) throw new Error("RESPONSE_TOO_LARGE");
        chunks.push(Buffer.from(chunk));
      }
    }
    // Numeric status only. No URL, query, credential, response body or arbitrary header logging.
    write({
      jsonrpc: "2.0",
      method: "tasteduel/http",
      params: { status: response.status },
    });
    return new Response(Buffer.concat(chunks), {
      status: response.status,
      headers: response.headers,
    });
  } finally {
    release();
  }
}
// Block auxiliary uncounted fetches too. No docs-MCP, update checks or credential files.
globalThis.fetch = guardedFetch;
const { QlooClient } = await import(
  pathToFileURL(join(packageRoot, "chunks/chunk-ESNY4EJL.js"))
);
const { createQlooTools } = await import(
  pathToFileURL(join(packageRoot, "qloo-tools.js"))
);
const { startCanonicalMcpServer } = await import(
  pathToFileURL(join(packageRoot, "mcp.js"))
);
const client = new QlooClient({
  apiKey: process.env.QLOO_API_KEY || "offline-no-credential",
  baseUrl: "https://hackathon.api.qloo.com",
  allowCustomBaseUrl: true,
  maxAttempts: 1,
  timeoutMs: 10000,
  maxResponseBytes: 2000000,
  fetch: guardedFetch,
});
startCanonicalMcpServer({
  input: canonicalInput,
  tools: createQlooTools({ client }),
  serverVersion: "0.1.26",
});
const input = createInterface({ input: process.stdin, terminal: false });
input.on("line", (line) => {
  let message;
  try {
    message = JSON.parse(line);
  } catch {
    process.exitCode = 1;
    input.close();
    return;
  }
  const reservation = pending.get(message.id);
  if (reservation && !message.method) {
    pending.delete(message.id);
    clearTimeout(reservation.timer);
    if (message.result?.allowed === true) reservation.resolve();
    else reservation.reject(new Error("REQUEST_BUDGET_DENIED"));
    return;
  }
  if (message.method === "tools/call" && !ALLOWED.has(message.params?.name)) {
    write({
      jsonrpc: "2.0",
      id: message.id,
      error: { code: -32602, message: "Workflow not allowed" },
    });
    return;
  }
  canonicalInput.write(`${line}\n`);
});
input.on("close", () => {
  canonicalInput.end();
});
process.on("uncaughtException", () => {
  process.stderr.write("QLOO_RUNNER_FAILURE\n");
  process.exit(1);
});
process.on("unhandledRejection", () => {
  process.stderr.write("QLOO_RUNNER_FAILURE\n");
  process.exit(1);
});
