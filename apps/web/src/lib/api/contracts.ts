import type { components } from "./schema";

// Python/Pydantic owns every wire shape. These are aliases, not duplicate schemas.
export type ApiSchemas = components["schemas"];
export type EntityPublic = ApiSchemas["EntityPublic"];
export type EntitySearchPublic = ApiSchemas["EntitySearchPublic"];
export type GamePublic = ApiSchemas["GamePublic"];
export type GameResultPublic = ApiSchemas["GameResultPublic"];
export type PlayableRoundPublic = ApiSchemas["PlayableRoundPublic"];
export type RevealedRoundPublic = ApiSchemas["RevealedRoundPublic"];
export type GenerationStatusPublic = ApiSchemas["GenerationStatusPublic"];
export type GameGenerationPendingPublic =
  ApiSchemas["GameGenerationPendingPublic"];
export type CurationSummaryPublic = ApiSchemas["CurationSummaryPublic"];
