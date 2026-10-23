"""Build strict Pydantic models from the language's compact schema declaration."""
from __future__ import annotations

import json
from types import GenericAlias
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model


def build_schema(name: str, declaration: str | dict[str, Any]) -> type[BaseModel]:
    fields = json.loads(declaration) if isinstance(declaration, str) else declaration
    if not isinstance(fields, dict) or not fields:
        raise ValueError('output_schema must declare at least one field')
    definitions: dict[str, Any] = {key: (_field_type(name + key.title(), value), ...) for key, value in fields.items()}
    return create_model(name + 'Schema', __config__=ConfigDict(extra='forbid', strict=True), **definitions)


def _field_type(name: str, value: Any) -> Any:
    if isinstance(value, dict):
        return build_schema(name, value)
    if isinstance(value, list) and len(value) == 1:
        return GenericAlias(list, _field_type(name, value[0]))
    types = {'string': str, 'number': float, 'integer': int, 'boolean': bool}
    if not isinstance(value, str) or value not in types:
        raise ValueError(f'Unknown output_schema field type: {value!r}')
    return types[value]
