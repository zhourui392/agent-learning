"""
Contract validator based on JSON Schema subset.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping


class ContractValidationError(ValueError):
    """
    Raised when payload violates contract schema.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def __init__(self, errors: List[str]) -> None:
        """
        Build validation error.

        @param errors: Validation error list.
        @return: None.
        """
        super().__init__("; ".join(errors))
        self.errors = errors


class ContractValidator:
    """
    Validates JSON payloads against local schema files.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def __init__(self, contracts_root: Path) -> None:
        """
        Initialize validator.

        @param contracts_root: Root path for schema files.
        @return: None.
        """
        self._contracts_root = contracts_root
        self._schema_cache: Dict[str, Dict[str, Any]] = {}

    def validate(self, schema_path: str, payload: Mapping[str, Any]) -> None:
        """
        Validate payload with schema.

        @param schema_path: Path relative to contracts root.
        @param payload: JSON-like object.
        @return: None.
        """
        schema = self._load_schema(schema_path)
        errors: List[str] = []
        self._validate_node(schema=schema, value=payload, path="$", errors=errors)
        if errors:
            raise ContractValidationError(errors)

    def validate_request(self, payload: Mapping[str, Any]) -> None:
        """
        Validate agent request payload.

        @param payload: Agent request payload.
        @return: None.
        """
        self.validate("agent-request.schema.json", payload)

    def validate_response(self, payload: Mapping[str, Any]) -> None:
        """
        Validate agent response payload.

        @param payload: Agent response payload.
        @return: None.
        """
        self.validate("agent-response.schema.json", payload)

    def _load_schema(self, schema_path: str) -> Dict[str, Any]:
        """
        Load schema from disk with cache.

        @param schema_path: Relative schema path.
        @return: Parsed schema dictionary.
        """
        if schema_path in self._schema_cache:
            return self._schema_cache[schema_path]

        absolute_path = self._contracts_root / schema_path
        with absolute_path.open("r", encoding="utf-8") as file_handle:
            schema = json.load(file_handle)
        self._schema_cache[schema_path] = schema
        return schema

    def _validate_node(self, schema: Mapping[str, Any], value: Any, path: str, errors: List[str]) -> None:
        """
        Validate one schema node.

        @param schema: Current schema node.
        @param value: Current value.
        @param path: JSON path for error messages.
        @param errors: Mutable error collection.
        @return: None.
        """
        schema_types = schema.get("type")
        if schema_types is not None:
            if isinstance(schema_types, str):
                schema_types = [schema_types]
            if not any(self._is_type(value, item) for item in schema_types):
                errors.append(f"{path}: expected type {schema_types}, got {type(value).__name__}")
                return

        enum_values = schema.get("enum")
        if enum_values is not None and value not in enum_values:
            errors.append(f"{path}: value {value!r} not in enum {enum_values}")

        if self._is_type(value, "object"):
            self._validate_object(schema=schema, value=value, path=path, errors=errors)
            return

        if self._is_type(value, "array"):
            self._validate_array(schema=schema, value=value, path=path, errors=errors)
            return

        if self._is_type(value, "string"):
            self._validate_string(schema=schema, value=value, path=path, errors=errors)
            return

        if self._is_type(value, "integer") or self._is_type(value, "number"):
            self._validate_number(schema=schema, value=value, path=path, errors=errors)

    def _validate_object(self, schema: Mapping[str, Any], value: Mapping[str, Any], path: str, errors: List[str]) -> None:
        """
        Validate object constraints.

        @param schema: Object schema node.
        @param value: Object value.
        @param path: JSON path.
        @param errors: Mutable error collection.
        @return: None.
        """
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        for required_field in required_fields:
            if required_field not in value:
                errors.append(f"{path}: missing required field {required_field}")

        if schema.get("additionalProperties") is False:
            for field_name in value.keys():
                if field_name not in properties:
                    errors.append(f"{path}: unexpected field {field_name}")

        for field_name, property_schema in properties.items():
            if field_name not in value:
                continue
            self._validate_node(
                schema=property_schema,
                value=value[field_name],
                path=f"{path}.{field_name}",
                errors=errors,
            )

    def _validate_array(self, schema: Mapping[str, Any], value: List[Any], path: str, errors: List[str]) -> None:
        """
        Validate array constraints.

        @param schema: Array schema node.
        @param value: Array value.
        @param path: JSON path.
        @param errors: Mutable error collection.
        @return: None.
        """
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            errors.append(f"{path}: length {len(value)} < minItems {min_items}")

        max_items = schema.get("maxItems")
        if max_items is not None and len(value) > max_items:
            errors.append(f"{path}: length {len(value)} > maxItems {max_items}")

        item_schema = schema.get("items")
        if item_schema is None:
            return

        for item_index, item in enumerate(value):
            self._validate_node(schema=item_schema, value=item, path=f"{path}[{item_index}]", errors=errors)

    def _validate_string(self, schema: Mapping[str, Any], value: str, path: str, errors: List[str]) -> None:
        """
        Validate string constraints.

        @param schema: String schema node.
        @param value: String value.
        @param path: JSON path.
        @param errors: Mutable error collection.
        @return: None.
        """
        min_length = schema.get("minLength")
        if min_length is not None and len(value) < min_length:
            errors.append(f"{path}: length {len(value)} < minLength {min_length}")

        max_length = schema.get("maxLength")
        if max_length is not None and len(value) > max_length:
            errors.append(f"{path}: length {len(value)} > maxLength {max_length}")

    def _validate_number(self, schema: Mapping[str, Any], value: Any, path: str, errors: List[str]) -> None:
        """
        Validate number constraints.

        @param schema: Number schema node.
        @param value: Numeric value.
        @param path: JSON path.
        @param errors: Mutable error collection.
        @return: None.
        """
        minimum = schema.get("minimum")
        if minimum is not None and value < minimum:
            errors.append(f"{path}: value {value} < minimum {minimum}")

        maximum = schema.get("maximum")
        if maximum is not None and value > maximum:
            errors.append(f"{path}: value {value} > maximum {maximum}")

    def _is_type(self, value: Any, json_type: str) -> bool:
        """
        Check value against JSON Schema primitive types.

        @param value: Runtime value.
        @param json_type: JSON Schema type name.
        @return: True when value matches requested JSON type.
        """
        if json_type == "null":
            return value is None
        if json_type == "object":
            return isinstance(value, dict)
        if json_type == "array":
            return isinstance(value, list)
        if json_type == "string":
            return isinstance(value, str)
        if json_type == "boolean":
            return isinstance(value, bool)
        if json_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if json_type == "number":
            return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
        return False
