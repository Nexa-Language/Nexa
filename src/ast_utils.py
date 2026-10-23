"""Normalize legacy transformer nodes at the compiler boundary."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, is_dataclass
from typing import Any


def normalize_ast(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        _preserve_spans(value, result)
        return normalize_ast(result)
    if is_dataclass(value) and not isinstance(value, type):
        return normalize_ast(asdict(value))
    if isinstance(value, dict):
        return {key: normalize_ast(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_ast(item) for item in value]
    return value


def _preserve_spans(value: Any, serialized: Any) -> None:
    # Legacy to_dict methods serialize child dataclasses before normalization.
    if isinstance(serialized, dict):
        if hasattr(value, "_span"):
            serialized["_span"] = value._span
        for key, item in serialized.items():
            child = value.get(key) if isinstance(value, dict) else getattr(value, key, None)
            if child is not None:
                _preserve_spans(child, item)
    elif isinstance(serialized, list) and isinstance(value, (list, tuple)):
        for child, item in zip(value, serialized):
            _preserve_spans(child, item)


def walk_nodes(value: Any) -> Iterator[dict[str, Any]]:
    """Visit every nested node, including expressions and branch containers."""
    if isinstance(value, dict):
        if "type" in value:
            yield value
        for child in value.values():
            yield from walk_nodes(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from walk_nodes(child)
