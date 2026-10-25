/** Presentation contract, not a provider response or a future API schema.
 * Callers may supply only evidence authorized for this accepted round. */
export type AcceptedDuelEvidence = {
  status: "accepted";
  source: { kind: "fixture" | "qloo"; label: string };
  rankingContextSentence: string;
  supportedExplanation?: { text: string; attribution: string };
};
