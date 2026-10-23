"""Create independent runs from settled conversation history."""

from __future__ import annotations

import copy
import json
import threading
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .agent_context import AgentContext
from .providers import ModelProvider
from .run_state import RunConfig, RunState, RunStatus

if TYPE_CHECKING:
    from .agent import NexaAgent


def continue_agent(agent: NexaAgent, previous: RunState, args: tuple[Any, ...], *, config: RunConfig | None = None,
                   cancel: threading.Event | None = None, save: Callable[[RunState], None] | None = None,
                   on_event: Callable[[dict[str, Any]], None] | None = None,
                   on_text: Callable[[str], None] | None = None, provider: ModelProvider | None = None) -> RunState:
    from .agent_execution import execute_agent

    if previous.status in {RunStatus.RUNNING, RunStatus.WAITING_APPROVAL}:
        raise ValueError("Resume or cancel the active run before starting a new turn")
    if any(isinstance(arg, AgentContext) for arg in args) or not " ".join(map(str, args)).strip():
        raise ValueError("Continuation requires new input; use execute for an independent AgentContext")
    if any(entry.get("status") != "completed" for entry in previous.tool_journal.values()):
        raise ValueError("A tool has an unknown outcome; resolve it before continuing")
    messages = _settled_history(previous)
    if not 0 <= previous.provider_cursor <= len(previous.messages):
        raise ValueError("Invalid provider history cursor")
    if previous.provider_cursor and not previous.provider_items:
        raise ValueError("Missing native provider history")
    metadata = copy.deepcopy(previous.metadata)
    metadata.update(parent_run_id=previous.run_id, session_id=metadata.get("session_id") or previous.run_id)
    if config is not None:
        config = replace(config, artifact_directory=str(Path(config.artifact_directory).resolve()))
        previous_directory = previous.config.get("artifact_directory")
        if previous_directory and Path(previous_directory).resolve() != Path(config.artifact_directory):
            raise ValueError("Continuation must retain the original artifact directory so history remains readable")
    state = RunState(agent_name=previous.agent_name, model=previous.model, provider=previous.provider,
                     config=asdict(config) if config else copy.deepcopy(previous.config),
                     definition_hash=previous.definition_hash, metadata=metadata, messages=messages,
                     provider_items=copy.deepcopy(previous.provider_items), provider_cursor=previous.provider_cursor)
    # execute_agent owns identity validation, contracts, provider calls and persistence.
    return execute_agent(agent, args, state=state, continuation=True, cancel=cancel, save=save,
                         on_event=on_event, on_text=on_text, provider=provider).state


def _settled_history(previous: RunState) -> list[dict[str, Any]]:
    messages = copy.deepcopy(previous.messages)
    outstanding: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for message in messages:
        if message.get("role") == "tool":
            call_id = message.get("tool_call_id")
            if call_id not in outstanding:
                raise ValueError("Tool history contains an orphan or duplicate result")
            del outstanding[call_id]
            continue
        if outstanding:
            raise ValueError("Tool history has an incomplete call before a later message")
        for call in message.get("tool_calls") or []:
            call_id = call.get("id")
            if message.get("role") != "assistant" or not isinstance(call_id, str) or not call_id or call_id in seen:
                raise ValueError("Tool history contains an invalid or duplicate call")
            seen.add(call_id)
            outstanding[call_id] = call
    pending = {call.get("id"): call for call in previous.pending_calls}
    if len(pending) != len(previous.pending_calls) or pending != outstanding:
        raise ValueError("Pending calls disagree with tool history")
    for call_id in outstanding:
        journal = previous.tool_journal.get(call_id)
        if journal is not None:
            if not isinstance(journal.get("content"), str):
                raise ValueError("Completed tool history is missing its result")
            content = journal["content"]
        else:
            # No started journal means dispatch never crossed the side-effect boundary.
            content = json.dumps({"cancelled": True, "error": "Tool call cancelled before execution"})
        messages.append({"role": "tool", "tool_call_id": call_id, "content": content})
    return messages
