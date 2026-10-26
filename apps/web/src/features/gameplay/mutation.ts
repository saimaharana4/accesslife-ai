import type { components } from "../../lib/api/schema.d.ts";

type Schemas = components["schemas"];
export type PendingMutation =
  | { kind: "answer"; key: string; body: Schemas["AnswerRequest"] }
  | { kind: "advance"; key: string; body: Schemas["AdvanceRequest"] };

export function mutationStorageKey(gameId: string) {
  return `tasteduel:mutation:v1:${gameId}`;
}

/** Stores only the player's own intended action. No answers, contestants or pool. */
export function readPendingMutation(
  value: string | null,
): PendingMutation | null {
  if (!value || value.length > 1000) return null;
  try {
    const parsed = JSON.parse(value);
    const uuid =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const isUuid = (candidate: unknown): candidate is string =>
      typeof candidate === "string" &&
      candidate.length === 36 &&
      uuid.test(candidate);
    if (
      !isUuid(parsed.key) ||
      !Number.isSafeInteger(parsed.body?.expected_revision) ||
      parsed.body.expected_revision < 0
    )
      return null;
    if (
      parsed.kind === "answer" &&
      isUuid(parsed.body.round_id) &&
      isUuid(parsed.body.choice_id)
    ) {
      return {
        kind: "answer",
        key: parsed.key,
        body: {
          round_id: parsed.body.round_id,
          choice_id: parsed.body.choice_id,
          expected_revision: parsed.body.expected_revision,
        },
      };
    }
    if (parsed.kind === "advance" && isUuid(parsed.body.answered_round_id)) {
      return {
        kind: "advance",
        key: parsed.key,
        body: {
          answered_round_id: parsed.body.answered_round_id,
          expected_revision: parsed.body.expected_revision,
        },
      };
    }
  } catch {
    /* Storage may be absent, blocked or from an older build. */
  }
  return null;
}

/** A fresh GET can settle a lost response without sending the action again. */
export function mutationResolved(
  pending: PendingMutation,
  game: Schemas["GamePublic"],
) {
  if (game.phase === "completed") return true;
  const round = game.current_round;
  if (!round) return false;
  if (pending.kind === "answer") {
    return (
      round.round_id !== pending.body.round_id || round.state === "revealed"
    );
  }
  return round.round_id !== pending.body.answered_round_id;
}
