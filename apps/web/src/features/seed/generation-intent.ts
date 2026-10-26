import type { ApiSchemas } from "../../lib/api/contracts";

export type GenerationIntent = {
  body: ApiSchemas["CreateGameRequest"];
  key: string;
  gameId?: string;
};
const storageKey = "tasteduel.generation-intent.v1";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function storage() {
  try {
    return typeof window === "undefined" ? undefined : window.sessionStorage;
  } catch {
    return undefined;
  }
}
export function readGenerationIntent(): GenerationIntent | undefined {
  try {
    const raw = storage()?.getItem(storageKey);
    if (!raw || raw.length > 600) return undefined;
    const value = JSON.parse(raw) as GenerationIntent;
    if (
      !value ||
      !["body,key", "body,gameId,key"].includes(
        Object.keys(value).sort().join(","),
      ) ||
      !uuid.test(value.key) ||
      (value.gameId !== undefined && !uuid.test(value.gameId))
    )
      return undefined;
    const body = value.body;
    if (
      !body ||
      Object.keys(body).sort().join(",") !== "mode,seed_entity_id,seed_type" ||
      !uuid.test(body.seed_entity_id) ||
      !["artist", "movie"].includes(body.seed_type) ||
      body.mode !== "solo"
    )
      return undefined;
    return value;
  } catch {
    return undefined;
  }
}
export function intentFor(
  body: ApiSchemas["CreateGameRequest"],
): GenerationIntent {
  const canonical: ApiSchemas["CreateGameRequest"] = {
    seed_entity_id: body.seed_entity_id,
    seed_type: body.seed_type,
    mode: "solo",
  };
  const previous = readGenerationIntent();
  if (
    previous &&
    previous.body.seed_entity_id === canonical.seed_entity_id &&
    previous.body.seed_type === canonical.seed_type
  )
    return previous;
  const value = { body: canonical, key: crypto.randomUUID() };
  try {
    storage()?.setItem(storageKey, JSON.stringify(value));
  } catch {
    /* Current-page retries still retain the caller's intent. */
  }
  return value;
}
export function clearGenerationIntent() {
  try {
    storage()?.removeItem(storageKey);
  } catch {
    /* Storage is optional. */
  }
}
export function associateGenerationGame(gameId: string) {
  const intent = readGenerationIntent();
  if (!intent || !uuid.test(gameId)) return;
  try {
    storage()?.setItem(storageKey, JSON.stringify({ ...intent, gameId }));
  } catch {
    /* Storage is optional. */
  }
}
