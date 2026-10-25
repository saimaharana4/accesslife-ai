import { readdirSync, readFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const workspace = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = join(workspace, "apps", "web", ".next");
if (!existsSync(join(output, "BUILD_ID"))) {
  throw new Error(
    "Run the normal production build before checking fixture exclusion.",
  );
}
const markers = [
  "Velvet Static",
  "Afterlight Assembly",
  "fictional-seeds",
  "fixture-story-controls",
  "FIXTURE_ROUND_POOL_V1",
];
let checked = 0;
function inspect(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const file = join(directory, entry.name);
    if (entry.isDirectory()) inspect(file);
    else if (/\.(?:js|json|html|txt|map)$/.test(entry.name)) {
      checked++;
      const text = readFileSync(file, "utf8");
      for (const marker of markers) {
        if (text.includes(marker))
          throw new Error(
            `Development fixture marker found in production output: ${marker}`,
          );
      }
    }
  }
}
inspect(join(output, "server"));
inspect(join(output, "static"));
console.log(
  `Production fixture exclusion passed across ${checked} emitted files.`,
);
