import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const workspace = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const web = join(workspace, "apps", "web");
const require = createRequire(join(web, "package.json"));
const cli = require.resolve("next/dist/bin/next");
process.chdir(web);
process.env.TASTEDUEL_FIXTURES = "1";
process.env.NEXT_TELEMETRY_DISABLED = "1";
process.argv = [
  process.execPath,
  cli,
  "dev",
  "--hostname",
  "127.0.0.1",
  "--port",
  "3001",
];
await import(pathToFileURL(cli).href);
