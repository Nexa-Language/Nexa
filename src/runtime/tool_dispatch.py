"""One policy and argument-validation boundary for local and remote tools."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http.client import HTTPException, InvalidURL
from typing import Any, Literal
from urllib.error import HTTPError, URLError

from jsonschema import Draft202012Validator
from referencing import Registry
from requests import exceptions as requests_errors


class ToolOutcomeUnknown(RuntimeError):
    """Transport failed after dispatch; external effects require reconciliation."""


def raise_for_unknown_outcome(error: Exception) -> None:
    transport_errors = (TimeoutError, ConnectionError, subprocess.TimeoutExpired, ToolOutcomeUnknown)
    known_request_failures = (requests_errors.HTTPError, requests_errors.InvalidURL, requests_errors.InvalidSchema,
                              requests_errors.MissingSchema, requests_errors.InvalidHeader, requests_errors.URLRequired)
    unknown_request = isinstance(error, requests_errors.RequestException) and not isinstance(error, known_request_failures)
    unknown_http = isinstance(error, HTTPException) and not isinstance(error, InvalidURL)
    unknown_url = isinstance(error, URLError) and not isinstance(error, HTTPError)
    if isinstance(error, transport_errors) or unknown_request or unknown_http or unknown_url:
        raise ToolOutcomeUnknown("Tool transport failed; external outcome requires reconciliation") from error


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    requires_approval: bool = False
    sandbox: bool = False
    risk_level: str = "low"

    def function_schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


@dataclass(frozen=True)
class ToolOutcome:
    name: str
    status: Literal["completed", "failed", "waiting_approval", "unknown"]
    value: Any = None
    error: str | None = None
    duration: float = 0.0
    sandboxed: bool = False

    def text(self) -> str:
        if self.error:
            return json.dumps({"error": self.error}, ensure_ascii=False)
        return self.value if isinstance(self.value, str) else json.dumps(self.value, ensure_ascii=False, default=str)


def validate_arguments(arguments: str | Mapping[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    parsed = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
    if not isinstance(parsed, dict):
        raise TypeError("Tool arguments must be a JSON object")
    validation_schema = {"additionalProperties": False, **schema}
    Draft202012Validator.check_schema(validation_schema)
    # An empty explicit registry never retrieves external references over the network.
    validator = Draft202012Validator(validation_schema, registry=Registry())
    error = next(iter(validator.iter_errors(parsed)), None)
    if error is not None:
        raise ValueError(f"Invalid tool arguments at {error.json_path}: {error.validator} constraint failed")
    return parsed


class ToolDispatcher:
    def __init__(self, tools: list[ToolSpec]) -> None:
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools):
            raise ValueError("Duplicate tool names in exposed tool set")

    def dispatch(self, name: str, arguments: str | Mapping[str, Any], *, approved: bool | None = None) -> ToolOutcome:
        if approved is not None and type(approved) is not bool:
            return ToolOutcome(name, "failed", error="Approval decision must be a boolean")
        tool = self.tools.get(name)
        if tool is None:
            return ToolOutcome(name, "failed", error=f"Tool '{name}' is not exposed to this run")
        try:
            parsed = validate_arguments(arguments, tool.parameters)
        except Exception as error:  # noqa: BLE001 - Schema failures are returned as tool outcomes.
            return ToolOutcome(name, "failed", error=f"Argument validation failed ({type(error).__name__}): {error}")
        if tool.sandbox:
            return ToolOutcome(name, "failed", error="A sandbox was requested, but no isolated executor is configured")
        if tool.requires_approval or tool.risk_level in {"high", "critical"}:
            if approved is None:
                return ToolOutcome(name, "waiting_approval", error=f"Tool '{name}' requires approval")
            if not approved:
                return ToolOutcome(name, "failed", error=f"Tool '{name}' execution denied by approval policy")
        started = time.monotonic()
        try:
            value = tool.handler(**parsed)
            return ToolOutcome(name, "completed", value=value, duration=time.monotonic() - started)
        except Exception as error:  # noqa: BLE001 - User handlers may raise arbitrary application exceptions.
            try:
                raise_for_unknown_outcome(error)
            except ToolOutcomeUnknown:
                return ToolOutcome(name, "unknown", error=str(error), duration=time.monotonic() - started)
            return ToolOutcome(name, "failed", error=str(error), duration=time.monotonic() - started)

    @classmethod
    def from_definitions(cls, definitions: list[dict[str, Any]]) -> ToolDispatcher:
        from .stdlib import get_stdlib_tools
        from .tool_registry import get_tool_registry
        from .tools_registry import LOCAL_TOOLS

        registry = get_tool_registry()
        standard = get_stdlib_tools()
        specs = []
        for definition in definitions:
            definition = definition.get("function", definition)
            name = definition["name"]
            policy = registry.get_tool(name)
            handler = definition.get("_handler") or registry.get_tool_function(name) or LOCAL_TOOLS.get(name)
            if handler is None and name in standard:
                handler = standard[name].handler
            if handler is None:
                raise ValueError(f"Tool '{name}' has a schema but no executable implementation")
            specs.append(ToolSpec(
                name=name,
                description=definition.get("description", ""),
                parameters=definition.get("parameters", {"type": "object", "properties": {}}),
                handler=handler,
                requires_approval=definition.get("requires_approval", policy.requires_approval if policy else False),
                sandbox=definition.get("sandbox", policy.sandbox if policy else False),
                risk_level=definition.get("risk_level", policy.risk_level if policy else "low"),
            ))
        return cls(specs)
