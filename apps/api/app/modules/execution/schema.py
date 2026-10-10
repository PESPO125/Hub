"""Small, deliberately bounded JSON Schema subset for tool arguments."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit


class SchemaError(ValueError):
    pass


def validate_params(schema: dict[str, Any], value: Any) -> None:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise SchemaError("params_schema debe declarar un objeto raíz.")
    _validate(schema, value, "params")


def _validate(schema: dict[str, Any], value: Any, path: str) -> None:
    kind = schema.get("type")
    expected = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str),
        "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
        "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        "boolean": lambda x: isinstance(x, bool),
        "null": lambda x: x is None,
    }
    if kind not in expected:
        raise SchemaError(f"{path}: tipo de esquema no soportado.")
    if not expected[kind](value):
        raise SchemaError(f"{path}: se esperaba {kind}.")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: valor no permitido.")
    if kind == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise SchemaError(f"{path}: definición de objeto inválida.")
        missing = [key for key in required if key not in value]
        if missing:
            raise SchemaError(f"{path}: falta el campo '{missing[0]}'.")
        if schema.get("additionalProperties", True) is False:
            extra = value.keys() - properties.keys()
            if extra:
                raise SchemaError(f"{path}: campo desconocido '{sorted(extra)[0]}'.")
        for key, item in value.items():
            if key in properties:
                _validate(properties[key], item, f"{path}.{key}")
    elif kind == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise SchemaError(f"{path}: contiene muy pocos elementos.")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaError(f"{path}: contiene demasiados elementos.")
        if "items" in schema:
            for index, item in enumerate(value):
                _validate(schema["items"], item, f"{path}[{index}]")
    elif kind == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise SchemaError(f"{path}: es demasiado corto.")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaError(f"{path}: es demasiado largo.")
        if schema.get("format") == "uri":
            try:
                parsed = urlsplit(value)
            except ValueError:
                raise SchemaError(f"{path}: se esperaba una URI válida.") from None
            if not parsed.scheme or not parsed.netloc:
                raise SchemaError(f"{path}: se esperaba una URI válida.")
    elif kind in {"integer", "number"}:
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError(f"{path}: el valor es menor que el mínimo.")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaError(f"{path}: el valor supera el máximo.")


def validate_schema(schema: dict[str, Any]) -> None:
    """Validate schema structure during discovery, so unsupported rules fail early."""
    if not isinstance(schema, dict):
        raise SchemaError("params_schema debe ser un objeto.")
    kind = schema.get("type")
    supported = {"object", "array", "string", "integer", "number", "boolean", "null"}
    if kind not in supported:
        raise SchemaError("params_schema debe usar un tipo JSON Schema soportado.")
    common = {"type", "title", "description", "default", "enum"}
    specific = {
        "object": {"properties", "required", "additionalProperties"},
        "array": {"items", "minItems", "maxItems"},
        "string": {"minLength", "maxLength", "format"},
        "integer": {"minimum", "maximum"},
        "number": {"minimum", "maximum"},
        "boolean": set(),
        "null": set(),
    }
    unknown = schema.keys() - common - specific[kind]
    if unknown:
        raise SchemaError(f"params_schema usa una regla no soportada: {sorted(unknown)[0]}.")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise SchemaError("params_schema.enum debe ser una lista no vacía.")
    if schema.get("format") not in (None, "uri"):
        raise SchemaError("params_schema usa un formato de cadena no soportado.")
    if kind == "object":
        required = schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(key, str) for key in required):
            raise SchemaError("params_schema.required debe ser una lista de nombres.")
        if schema.get("additionalProperties", True) not in (True, False):
            raise SchemaError("params_schema solo admite additionalProperties booleano.")
    if kind == "object":
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise SchemaError("params_schema.properties debe ser un objeto.")
        for value in properties.values():
            validate_schema(value)
    if kind == "array" and "items" in schema:
        validate_schema(schema["items"])
