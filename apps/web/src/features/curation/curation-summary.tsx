import { summarizeCuration, type CurationSummaryFacts } from "./summary";

/** Compact execution facts, not reasoning, answer data or an agent console. */
export function CurationSummary({ facts }: { facts: CurationSummaryFacts }) {
  const summary = summarizeCuration(facts);
  if (!summary) return null;
  return (
    <section
      className="curation-summary"
      aria-label={summary.mode}
      data-testid="curation-summary"
    >
      <p>
        <strong>{summary.mode}</strong> · {summary.domain} rounds
      </p>
      <p>
        {summary.checked} candidates checked · {summary.rejected} rejected (
        {summary.rejectionSentence}) · {summary.correctionCount} corrections.{" "}
        {summary.path}.
      </p>
      {facts.mode === "fixture" && (
        <p>Prewritten local data; no live agent execution.</p>
      )}
    </section>
  );
}
