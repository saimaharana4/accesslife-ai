/** Test-only observer: accepted controlled losses still have their body audited. */
export function createResponseAudit(token) {
  const findings = [];
  const confirmed = new Set();
  let expectedUnavailable = 0;
  function inspect(text) {
    let body;
    try {
      body = JSON.parse(text);
    } catch {
      findings.push("non-JSON API response");
      return false;
    }
    const before = findings.length;
    if (
      /raw_payload|private_pool|answer_key|thought_signature|chain_of_thought|hidden_reasoning|future_contestants|unused_pairs|query_context_hash|"affinity"|hack_[a-z0-9]{20}|sk-proj-/i.test(
        text,
      ) ||
      (token && text.includes(token))
    )
      findings.push("private API response field");
    if (
      body.current_round?.state === "unanswered" &&
      /winning_choice_id|selected_choice_id|curation_summary/.test(
        JSON.stringify(body.current_round),
      )
    )
      findings.push("pre-answer reveal metadata");
    return findings.length === before;
  }
  return {
    findings,
    inspect,
    confirmControlled(key, text) {
      if (typeof key !== "string" || !key || !inspect(text)) return false;
      confirmed.add(key);
      return true;
    },
    unavailable(key) {
      if (key && confirmed.has(key)) {
        expectedUnavailable++;
        return true;
      }
      findings.push("unavailable API response body");
      return false;
    },
    get confirmedControlled() {
      return confirmed.size;
    },
    get expectedUnavailable() {
      return expectedUnavailable;
    },
  };
}
