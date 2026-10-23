"""Serializable run state and explicit resource accounting."""

from __future__ import annotations

import math
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True)
class RunConfig:
    timeout: float = 30.0
    max_model_calls: int = 20
    max_tool_calls: int = 10
    max_tokens: int | None = None
    retries: int = 2
    max_tool_output_chars: int = 16000
    artifact_directory: str = ".nexa/artifacts"

    def __post_init__(self) -> None:
        integers = (self.max_model_calls, self.max_tool_calls, self.retries, self.max_tool_output_chars)
        if any(type(value) is not int for value in integers) or self.max_tokens is not None and type(self.max_tokens) is not int:
            raise ValueError("Run budgets must be integers")
        if isinstance(self.timeout, bool) or not math.isfinite(self.timeout):
            raise ValueError("Run timeout must be finite")
        if self.timeout <= 0 or self.max_model_calls < 1 or self.max_tool_calls < 0 or self.retries < 0:
            raise ValueError("Run limits must be positive; tool calls and retries may be zero")
        if self.max_tokens is not None and self.max_tokens < 1:
            raise ValueError("Token budget must be positive")
        if self.max_tool_output_chars < 256:
            raise ValueError("Tool output budget must be at least 256 characters")


@dataclass
class RunState:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    schema_version: int = 1
    revision: int = 0
    config: dict[str, Any] = field(default_factory=dict)
    definition_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    agent_name: str = ""
    model: str = ""
    provider: str = "chat"
    status: RunStatus = RunStatus.RUNNING
    messages: list[dict[str, Any]] = field(default_factory=list)
    provider_items: list[dict[str, Any]] = field(default_factory=list)
    provider_cursor: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usage_reported: bool = False
    output: str = ""
    error: str | None = None
    pending_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_journal: dict[str, dict[str, Any]] = field(default_factory=dict)
    approvals: dict[str, bool] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    elapsed: float = 0.0

    @property
    def success(self) -> bool:
        return self.status == RunStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunState:
        if data.get("schema_version") != 1:
            raise ValueError("Unsupported run-state schema version")
        values: dict[str, Any] = {**data, "status": RunStatus(data["status"])}
        state = cls(**values)
        if any(type(value) is not int or value < 0 for value in (state.revision, state.model_calls, state.tool_calls,
                                                               state.input_tokens, state.output_tokens, state.provider_cursor)):
            raise ValueError("Run counters must be nonnegative integers")
        if any(type(value) is not bool for value in state.approvals.values()):
            raise ValueError("Approval decisions must be booleans")
        if state.config:
            RunConfig(**state.config)
        if state.provider_cursor > len(state.messages):
            raise ValueError("Invalid provider history cursor")
        return state


class RunStopped(RuntimeError):
    def __init__(self, status: RunStatus, message: str) -> None:
        super().__init__(message)
        self.status = status


class RunContext:
    def __init__(self, state: RunState, config: RunConfig, *, cancel: threading.Event | None = None,
                 save: Callable[[RunState], None] | None = None, on_event: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.state = state
        self.config = config
        self.cancel = cancel if cancel is not None else threading.Event()
        self.save = save
        self.on_event = on_event
        self._started = time.monotonic()
        self._previous_elapsed = max(state.elapsed, time.time() - state.created_at)

    def remaining(self) -> float:
        self.state.elapsed = self._previous_elapsed + time.monotonic() - self._started
        return self.config.timeout - self.state.elapsed

    def check(self) -> None:
        if self.cancel.is_set():
            raise RunStopped(RunStatus.CANCELLED, "Run cancelled")
        if self.remaining() <= 0:
            raise RunStopped(RunStatus.TIMED_OUT, "Run deadline exceeded")
        if self.config.max_tokens is not None and self.state.input_tokens + self.state.output_tokens > self.config.max_tokens:
            raise RunStopped(RunStatus.BUDGET_EXHAUSTED, "Token budget exhausted")

    def record(self, event: str, **metadata: Any) -> None:
        from .flow_runtime import emit_hook

        self.remaining()
        item = {"sequence": len(self.state.events), "event": event, "run_id": self.state.run_id, "timestamp": time.time(), **metadata}
        self.state.events.append(item)
        if self.save is not None:
            self.save(self.state)
        if self.on_event is not None:
            self.on_event(dict(item))
        emit_hook(item)
