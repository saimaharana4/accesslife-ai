import openapi from "../../../../../packages/contracts/openapi.json" with { type: "json" };

type Schema = {
  $ref?: string;
  type?: string;
  const?: unknown;
  enum?: unknown[];
  anyOf?: Schema[];
  oneOf?: Schema[];
  allOf?: Schema[];
  properties?: Record<string, Schema>;
  required?: string[];
  additionalProperties?: boolean | Schema;
  propertyNames?: Schema;
  items?: Schema;
  prefixItems?: Schema[];
  minItems?: number;
  maxItems?: number;
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  pattern?: string;
  format?: string;
};
type Operation = {
  parameters?: {
    in: string;
    name: string;
    required?: boolean;
    schema: Schema;
  }[];
  requestBody?: { content: Record<string, { schema: Schema }> };
  responses: Record<string, { content?: Record<string, { schema: Schema }> }>;
};
const document = openapi as unknown as {
  components: { schemas: Record<string, Schema> };
  paths: Record<string, Record<string, Operation>>;
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function matchesSchema(
  value: unknown,
  schema: Schema,
  depth = 0,
): boolean {
  if (depth > 32) return false;
  if (schema.$ref) {
    const name = schema.$ref.replace(/^#\/components\/schemas\//, "");
    return (
      !!document.components.schemas[name] &&
      matchesSchema(value, document.components.schemas[name], depth + 1)
    );
  }
  if (schema.anyOf)
    return schema.anyOf.some((s) => matchesSchema(value, s, depth + 1));
  if (schema.oneOf)
    return (
      schema.oneOf.filter((s) => matchesSchema(value, s, depth + 1)).length ===
      1
    );
  if (
    schema.allOf &&
    !schema.allOf.every((s) => matchesSchema(value, s, depth + 1))
  )
    return false;
  if (Object.hasOwn(schema, "const") && value !== schema.const) return false;
  if (schema.enum && !schema.enum.includes(value)) return false;
  if (schema.type === "null") return value === null;
  if (schema.type === "boolean") return typeof value === "boolean";
  if (schema.type === "string")
    return (
      typeof value === "string" &&
      value.length >= (schema.minLength ?? 0) &&
      value.length <= (schema.maxLength ?? Infinity) &&
      (!schema.pattern || new RegExp(schema.pattern).test(value)) &&
      (schema.format !== "uuid" || uuid.test(value)) &&
      (schema.format !== "date-time" ||
        (/^\d{4}-\d{2}-\d{2}T/.test(value) &&
          Number.isFinite(Date.parse(value))))
    );
  if (schema.type === "integer" || schema.type === "number")
    return (
      typeof value === "number" &&
      Number.isFinite(value) &&
      (schema.type !== "integer" || Number.isInteger(value)) &&
      value >= (schema.minimum ?? -Infinity) &&
      value <= (schema.maximum ?? Infinity)
    );
  if (schema.type === "array")
    return (
      Array.isArray(value) &&
      value.length >= (schema.minItems ?? 0) &&
      value.length <= (schema.maxItems ?? Infinity) &&
      value.every((item, index) => {
        const rule = schema.prefixItems?.[index] ?? schema.items;
        return rule ? matchesSchema(item, rule, depth + 1) : false;
      })
    );
  if (schema.type === "object" || schema.properties) {
    if (!value || typeof value !== "object" || Array.isArray(value))
      return false;
    const record = value as Record<string, unknown>;
    if (schema.required?.some((key) => !Object.hasOwn(record, key)))
      return false;
    return Object.entries(record).every(([key, item]) => {
      if (
        schema.propertyNames &&
        !matchesSchema(key, schema.propertyNames, depth + 1)
      )
        return false;
      const rule = schema.properties?.[key];
      if (rule) return matchesSchema(item, rule, depth + 1);
      if (
        schema.additionalProperties &&
        typeof schema.additionalProperties === "object"
      )
        return matchesSchema(item, schema.additionalProperties, depth + 1);
      // Fail closed even if a later export forgets additionalProperties:false.
      return false;
    });
  }
  // A schema with only enum/const is fully checked above; unknown shapes fail closed.
  return !!schema.enum || Object.hasOwn(schema, "const");
}

export function getOperation(path: string, method: string) {
  for (const [template, methods] of Object.entries(document.paths)) {
    const pattern = template.replace(/\{[^}]+\}/g, "([0-9a-fA-F-]{36})");
    if (!new RegExp(`^${pattern}$`).test(path)) continue;
    return methods[method.toLowerCase()];
  }
}
export function validRequest(
  operation: Operation,
  params: URLSearchParams,
  body?: unknown,
) {
  const rules = (operation.parameters ?? []).filter((p) => p.in === "query");
  for (const key of params.keys())
    if (!rules.some((r) => r.name === key) || params.getAll(key).length !== 1)
      return false;
  for (const rule of rules) {
    const raw = params.get(rule.name);
    if (raw === null) {
      if (rule.required) return false;
      continue;
    }
    if (
      !matchesSchema(
        rule.schema.type === "integer" ? Number(raw) : raw,
        rule.schema,
      )
    )
      return false;
  }
  const schema = operation.requestBody?.content["application/json"]?.schema;
  return schema ? matchesSchema(body, schema) : body === undefined;
}
export function validResponse(
  operation: Operation,
  status: number,
  body: unknown,
) {
  const schema =
    operation.responses[String(status)]?.content?.["application/json"]?.schema;
  return !!schema && matchesSchema(body, schema);
}
