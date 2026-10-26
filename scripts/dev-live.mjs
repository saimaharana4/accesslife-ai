// Explicit loopback preview. Credentials stay in the private Python service.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
const cwd = fileURLToPath(new URL("../apps/web/", import.meta.url));
const port = process.env.TASTEDUEL_PREVIEW_PORT ?? "3001";
if (!["3001", "3003"].includes(port))
  throw new Error("Use reviewed loopback preview port");
const child = spawn(
  process.execPath,
  [
    "node_modules/next/dist/bin/next",
    "dev",
    "--hostname",
    "127.0.0.1",
    "--port",
    port,
  ],
  {
    cwd,
    stdio: "inherit",
    env: {
      ...process.env,
      NEXT_TELEMETRY_DISABLED: "1",
      TASTEDUEL_FIXTURES: "0",
      TASTEDUEL_API_URL: "http://127.0.0.1:8004",
      TASTEDUEL_WEB_ORIGINS: `http://127.0.0.1:${port}`,
      TASTEDUEL_ALLOW_LOCAL_HTTP: "true",
    },
  },
);
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => child.kill(signal));
child.on("exit", (code) => process.exit(code ?? 1));
