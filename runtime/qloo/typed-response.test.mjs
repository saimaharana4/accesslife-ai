import assert from "node:assert/strict";
import test from "node:test";
import { preserveTypedEntityEvidence } from "./typed-response.mjs";

const encode = (row) => Buffer.from(JSON.stringify({ results: [row] }));
const entity = {
  entity_id: "synthetic",
  type: "urn:entity",
  types: ["urn:entity:artist"],
};

test("preserves genuine specific type before official harness compaction", () => {
  for (const path of ["/search", "/entities"]) {
    const result = JSON.parse(
      preserveTypedEntityEvidence(encode(entity), path, 200),
    );
    assert.equal(result.results[0].subtype, "urn:entity:artist");
    assert.deepEqual(result.results[0].types, entity.types);
  }
});

test("supports nested results without injecting any entity from the request", () => {
  const body = Buffer.from(
    JSON.stringify({
      results: { entities: [{ ...entity, types: ["urn:entity:movie"] }] },
    }),
  );
  const result = JSON.parse(
    preserveTypedEntityEvidence(body, "/entities", 200),
  );
  assert.equal(result.results.entities[0].subtype, "urn:entity:movie");
});

test("unknown, conflicting, malformed and existing types stay byte-identical", () => {
  for (const row of [
    null,
    [],
    {},
    { ...entity, types: [] },
    { ...entity, types: ["urn:entity:artist", "urn:entity:movie"] },
    { ...entity, types: ["urn:entity:artist", false] },
    { ...entity, types: ["urn:entity:book"] },
    { ...entity, subtype: "urn:entity:movie" },
    { ...entity, subtype: null },
    { ...entity, type: "urn:entity:movie" },
  ]) {
    const body = encode(row);
    assert.strictEqual(preserveTypedEntityEvidence(body, "/search", 200), body);
  }
});

test("never changes Insights, failures or malformed JSON", () => {
  const body = encode(entity);
  assert.strictEqual(
    preserveTypedEntityEvidence(body, "/v2/insights", 200),
    body,
  );
  assert.strictEqual(preserveTypedEntityEvidence(body, "/search", 429), body);
  const invalid = Buffer.from("{broken");
  assert.strictEqual(
    preserveTypedEntityEvidence(invalid, "/search", 200),
    invalid,
  );
});
