/**
 * Preserve source type evidence before the pinned harness compacts away `types`.
 * This is an explicit compatibility shim, never an inference from the request.
 * Bounded input is supplied by runner.mjs. No output is persisted or logged.
 */
export function preserveTypedEntityEvidence(body, path, status) {
  if (status !== 200 || !["/search", "/entities"].includes(path)) return body;
  let payload;
  try {
    payload = JSON.parse(body.toString("utf8"));
  } catch {
    return body;
  }
  const rows = Array.isArray(payload?.results)
    ? payload.results
    : payload?.results?.entities;
  if (!Array.isArray(rows)) return body;
  let changed = false;
  for (const row of rows) {
    if (
      row === null ||
      typeof row !== "object" ||
      Array.isArray(row) ||
      row.type !== "urn:entity" ||
      Object.hasOwn(row, "subtype") ||
      !Array.isArray(row.types) ||
      row.types.some((value) => typeof value !== "string")
    )
      continue;
    const specific = new Set(
      row.types.filter((value) => value.startsWith("urn:entity:")),
    );
    if (specific.size !== 1) continue;
    const [actualType] = specific;
    if (!["urn:entity:artist", "urn:entity:movie"].includes(actualType))
      continue;
    row.subtype = actualType;
    changed = true;
  }
  return changed ? Buffer.from(JSON.stringify(payload), "utf8") : body;
}
