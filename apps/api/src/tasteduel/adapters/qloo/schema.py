"""Validation for the JSON-Schema subset present in the pinned discovered tool inputs."""


def valid_input(value, schema):
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict) or any(key not in value for key in schema.get("required", [])):
            return False
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            return False
        return all(key in properties and valid_input(item, properties[key]) for key, item in value.items())
    if kind == "array":
        if not isinstance(value, list) or not schema.get("minItems", 0) <= len(value) <= schema.get(
            "maxItems", 100
        ):
            return False
        if schema.get("uniqueItems") and len({repr(item) for item in value}) != len(value):
            return False
        return all(valid_input(item, schema["items"]) for item in value)
    if kind == "string":
        if not isinstance(value, str) or not schema.get("minLength", 0) <= len(value) <= 2048:
            return False
    elif kind == "boolean":
        if type(value) is not bool:
            return False
    elif kind == "integer":
        if type(value) is not int or not schema.get("minimum", -1_000_000) <= value <= schema.get(
            "maximum", 1_000_000
        ):
            return False
    else:
        return False  # Fail closed if a future package introduces an uninspected schema keyword/type.
    return "enum" not in schema or value in schema["enum"]
