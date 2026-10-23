"""Scoped execution semantics for generated Harness statements."""

from __future__ import annotations

import copy
import functools
import json
import threading
import time
from collections.abc import Callable, Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowRuntime:
    actors: Any = None
    hooks: dict[str, list[Callable[..., None]]] = field(default_factory=dict)
    reflections: list[str] = field(default_factory=list)
    shared: dict[str, Any] = field(default_factory=dict)
    lock: Any = field(default_factory=threading.RLock)


_flow: ContextVar[FlowRuntime | None] = ContextVar("nexa_flow", default=None)
_context_policy: ContextVar[tuple[int, str] | None] = ContextVar("nexa_context_policy", default=None)


def flow_scope(function: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        runtime = FlowRuntime()
        token = _flow.set(runtime)
        failed = True
        policy_token = _context_policy.set(_context_policy.get())
        try:
            result = function(*args, **kwargs)
            failed = False
            return result
        finally:
            try:
                if runtime.actors is not None:
                    runtime.actors.shutdown(failed)
            finally:
                _context_policy.reset(policy_token)
                _flow.reset(token)
    return wrapped


def spawn_actor(agent: Any, *args: Any) -> Any:
    from .flow_actors import FlowActors
    runtime = _flow.get()
    if runtime is None:
        raise RuntimeError('Actors require a flow scope')
    if runtime.actors is None:
        runtime.actors = FlowActors()
    return runtime.actors.spawn(agent, args)


def register_hook(event: str, function: Callable[..., None]) -> None:
    runtime = _flow.get()
    if runtime is None:
        raise RuntimeError("Lifecycle hooks require a flow scope")
    if event not in {"before_step", "after_step", "before_tool", "after_tool", "on_error"}:
        raise ValueError(f"Unknown lifecycle hook: {event}")
    runtime.hooks.setdefault(event, []).append(function)


def emit_hook(event: dict[str, Any]) -> None:
    runtime = _flow.get()
    name = {"model_started": "before_step", "model_completed": "after_step", "tool_started": "before_tool",
            "tool_completed": "after_tool", "run_stopped": "on_error"}.get(event["event"])
    if runtime is not None and name is not None:
        for hook in runtime.hooks.get(name, []):
            hook(**event)


def reflect(text: str) -> None:
    runtime = _flow.get()
    if runtime is None:
        raise RuntimeError("Reflection requires a flow scope")
    runtime.reflections.append(text)


def reflections() -> str:
    runtime = _flow.get()
    return "\n".join(runtime.reflections) if runtime is not None else ""


def shared_context(name: str, value: Any = None) -> Any:
    runtime = _flow.get()
    if runtime is None:
        raise RuntimeError("Shared context requires a flow scope")
    with runtime.lock:
        if value is not None:
            runtime.shared[name] = copy.deepcopy(value)
        if name not in runtime.shared:
            raise ValueError(f"Shared context {name!r} has not been produced")
        return copy.deepcopy(runtime.shared[name])


def set_context_policy(max_tokens: int, strategy: str = "sliding_window") -> None:
    if max_tokens < 1 or strategy not in {"sliding_window", "strict"}:
        raise ValueError("Context policy requires a positive budget and sliding_window or strict strategy")
    parent = _context_policy.get()
    _context_policy.set((min(max_tokens, parent[0]) if parent else max_tokens, strategy))


@contextmanager
def context_scope(max_tokens: int, strategy: str = "sliding_window") -> Generator[None, None, None]:
    if max_tokens < 1 or strategy not in {"sliding_window", "strict"}:
        raise ValueError("Context scope requires a positive budget and sliding_window or strict strategy")
    parent = _context_policy.get()
    token = _context_policy.set((min(max_tokens, parent[0]) if parent else max_tokens, strategy))
    try:
        yield
    finally:
        _context_policy.reset(token)


def select_context(messages: list[dict[str, Any]], max_turns: int | None = None, *, native: bool = False, provider_items: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Keep complete user turns; byte size is a conservative tokenizer-independent bound."""
    policy = _context_policy.get()
    selected = copy.deepcopy(messages)
    while True:
        starts = [i for i, message in enumerate(selected) if message["role"] == "user"]
        fits = policy is None or len(json.dumps(selected + (provider_items or []), ensure_ascii=False).encode()) <= policy[0]
        turns_fit = max_turns is None or len(starts) <= max_turns
        if fits and turns_fit:
            return selected
        if native or len(starts) < 2 or policy is not None and policy[1] == "strict":
            raise ValueError("Context budget exceeded; shorten input or increase the context budget")
        selected = [message for message in selected[:starts[0]] if message["role"] == "system"] + selected[starts[1]:]


def loop_steps(max_steps: int, timeout: float | None = None) -> Iterator[int]:
    if max_steps < 1 or timeout is not None and timeout <= 0:
        raise ValueError("Autoloop limits must be positive")
    started = time.monotonic()
    for step in range(max_steps):
        if timeout is not None and time.monotonic() - started >= timeout:
            raise TimeoutError("Autoloop deadline exceeded")
        yield step + 1
        if timeout is not None and time.monotonic() - started >= timeout:
            raise TimeoutError("Autoloop deadline exceeded")


def exit_condition(condition: str, observation: Any) -> bool:
    if isinstance(observation, dict):
        observation = observation.get("status")
    return isinstance(observation, str) and observation.strip().casefold() == condition.strip().casefold()


@dataclass
class FlowSnapshot:
    values: dict[str, Any]
    agents: list[tuple[Any, dict[str, Any]]]


def snapshot_scope(values: dict[str, Any], agents: list[Any]) -> FlowSnapshot:
    keys = ("messages", "_provider_items", "_provider_cursor", "_artifacts", "_tool_results", "_last_context", "last_run")
    return FlowSnapshot(copy.deepcopy(values), [(agent, {key: copy.deepcopy(getattr(agent, key, None)) for key in keys}) for agent in agents])


def restore_scope(snapshot: FlowSnapshot) -> dict[str, Any]:
    for agent, state in snapshot.agents:
        for key, value in state.items():
            setattr(agent, key, copy.deepcopy(value))
    return copy.deepcopy(snapshot.values)


def isolated_call(agent: Any, *args: Any) -> Any:
    from .agent_execution import execute_agent
    execution = execute_agent(agent, args)
    if not execution.state.success:
        raise execution.exception or RuntimeError(execution.state.error or execution.state.status.value)
    return execution.value


def fork_calls(branches: list[Callable[[], Any]], strategy: str) -> Any:
    if not branches:
        raise ValueError("Fork requires at least one branch")
    with ThreadPoolExecutor(max_workers=min(8, len(branches))) as executor:
        futures = [executor.submit(copy_context().run, branch) for branch in branches]
        results = [future.result() for future in futures]
    if strategy == "all":
        return results
    if strategy == "first":
        return results[0]
    if strategy == "vote":
        serialized = [json.dumps(result, sort_keys=True) for result in results]
        return results[max(range(len(results)), key=lambda index: serialized.count(serialized[index]))]
    if strategy in {"best", "best_of"} and all(isinstance(result, dict) and type(result.get("score")) in {float, int} for result in results):
        return max(results, key=lambda result: result["score"])
    raise ValueError(f"Merge strategy {strategy!r} requires scored results; use all, first, or vote for unscored output")
