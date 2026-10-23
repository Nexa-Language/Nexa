"""Tools obey declared policy before any handler runs."""

from __future__ import annotations

from src.runtime.tool_registry import ToolRegistry


def test_missing_approval_does_not_execute_handler() -> None:
    calls: list[str] = []
    registry = ToolRegistry()

    def change(value: str) -> str:
        calls.append(value)
        return value

    registry.register_from_annotation(change, requires_approval=True)
    result = registry.execute("change", {"value": "hello"})
    assert not result.success
    assert not result.approved
    assert not calls


def test_sandbox_declaration_requires_an_actual_backend() -> None:
    calls: list[int] = []
    registry = ToolRegistry()

    def change() -> str:
        calls.append(1)
        return "changed"

    registry.register_from_annotation(change, sandbox=True)
    result = registry.execute("change", {})
    assert not result.success
    assert not result.sandboxed
    assert not calls


def test_invalid_argument_types_are_rejected_before_execution() -> None:
    calls: list[int] = []
    registry = ToolRegistry()

    def change(count: int) -> str:
        calls.append(count)
        return "changed"

    registry.register_from_annotation(change)
    result = registry.execute("change", {"count": "not an integer"})
    assert not result.success
    assert not calls
