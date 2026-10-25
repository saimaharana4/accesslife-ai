// Local-only preview of Next's standalone production output. No cloud or API setup.
import { cpSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const workspace = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const web = join(workspace, "apps", "web");
const output = join(web, ".next", "standalone", "apps", "web");
const server = join(output, "server.js");

if (!existsSync(server)) {
  console.error("Build the local prototype first: corepack pnpm build");
  process.exit(1);
}

// Next standalone output intentionally omits public/static files; include only
// these reviewed local assets. Never copy the workspace, environment or ADC.
cpSync(join(web, "public"), join(output, "public"), { recursive: true });
cpSync(join(web, ".next", "static"), join(output, ".next", "static"), {
  recursive: true,
});
process.env.PORT = "3001";
process.env.HOSTNAME = "127.0.0.1";
process.env.NEXT_TELEMETRY_DISABLED = "1";
await import(pathToFileURL(server).href);
