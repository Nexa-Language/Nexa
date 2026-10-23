"""Adapt legacy Agent definitions to isolated runs without duplicating the loop."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .agent_context import AgentContext
from .agent_runner import AgentRunner
from .artifacts import ArtifactStore
from .cache_manager import get_cache_manager
from .checkpoints import CheckpointConflict
from .contracts import capture_old_values, check_requires
from .flow_runtime import reflections, select_context, shared_context
from .memory import global_memory
from .providers import ModelProvider
from .run_state import RunConfig, RunContext, RunState, RunStatus, RunStopped
from .tool_dispatch import ToolDispatcher

if TYPE_CHECKING:
    from .agent import NexaAgent


@dataclass
class AgentExecution:
    state: RunState
    value: Any = None
    context: AgentContext | None = None
    exception: Exception | None = None


def execute_agent(agent: NexaAgent, args: tuple[Any, ...], *, config: RunConfig | None = None,
                  state: RunState | None = None, history: list[dict[str, Any]] | None = None,
                  cancel: threading.Event | None = None, save: Callable[[RunState], None] | None = None,
                  on_event: Callable[[dict[str, Any]], None] | None = None,
                  on_text: Callable[[str], None] | None = None, provider: ModelProvider | None = None,
                  continuation: bool = False) -> AgentExecution:
    resuming = state is not None
    workspace = str(Path.cwd().resolve())
    if state is not None and state.metadata.get("workspace", workspace) != workspace:
        raise ValueError("Resume must use the original working directory")
    if state is not None and any(type(value) is not bool for value in state.approvals.values()):
        raise ValueError("Approval decisions must be booleans")
    if config is not None:
        config = replace(config, artifact_directory=str(Path(config.artifact_directory).resolve()))
    stored_config = RunConfig(**state.config) if state is not None and state.config else None
    if stored_config is not None and config is not None and config != stored_config:
        raise ValueError("Resume must retain the original run limits")
    config = config or stored_config or RunConfig(timeout=agent.timeout, max_tool_calls=agent.max_tool_calls, retries=max(0, agent.retry - 1))
    config = replace(config, artifact_directory=str(Path(config.artifact_directory).resolve()))
    provider = provider or agent._provider_adapter()
    session = copy.copy(agent)
    session.messages = copy.deepcopy(history if history is not None else [{"role": "system", "content": agent.system_prompt}])
    session._artifacts, session._tool_results = {}, []
    if state is None:
        state = RunState(agent_name=agent.name, model=agent.model, provider=provider.name, messages=session.messages, config=asdict(config))
    elif args and not continuation:
        raise ValueError("Resume accepts a RunState without new input arguments")
    elif (state.agent_name, state.model, state.provider) != (agent.name, agent.model, provider.name):
        raise ValueError("RunState belongs to a different agent, model, or provider")
    state.metadata["workspace"] = workspace
    session.messages = state.messages
    context = RunContext(state, config, cancel=cancel, save=save, on_event=on_event)
    try:
        if not resuming:
            inherited = _prepare_input(session, args)
            state.messages = session.messages
            if history is not None and not inherited:
                state.provider_items = copy.deepcopy(agent._provider_items)
                state.provider_cursor = agent._provider_cursor
        elif continuation:
            _append_input(session, args)
        tools = ToolDispatcher.from_definitions(agent.tools)
        validate = _output_validator(session, args)
        response_format = _response_format(agent)
        identity = {"system": agent.system_prompt, "provider": _cache_identity(agent, provider.name, response_format),
                    "tools": [{**tool.function_schema(), "approval": tool.requires_approval, "risk": tool.risk_level, "sandbox": tool.sandbox}
                              for tool in tools.tools.values()], "tool_choice": agent.tool_call_strategy}
        definition_hash = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        if state.definition_hash and state.definition_hash != definition_hash:
            raise ValueError("Agent definition changed since checkpoint; resume with the original definition")
        state.definition_hash = definition_hash
        if state.status not in {RunStatus.RUNNING, RunStatus.WAITING_APPROVAL}:
            value = validate(state.output) if state.success else None
            return AgentExecution(state, value, _result_context(session, state, value) if state.success else None)
        artifacts = ArtifactStore(config.artifact_directory, max_read_chars=min(8000, config.max_tool_output_chars))
        if tools.tools:
            artifact_tool = artifacts.tool()
            if artifact_tool.name in tools.tools:
                raise ValueError("Reserved artifact tool name")
            tools.tools[artifact_tool.name] = artifact_tool
        runner = AgentRunner(context, provider, tools, validate_output=validate, max_output_tokens=agent.max_tokens,
                             response_format=response_format, stream=agent.stream, tool_choice=agent.tool_call_strategy,
                             on_text=on_text, artifacts=artifacts, max_history_turns=(agent.context_spec.max_history_turns if agent.context_spec and agent.context_spec.max_history_turns is not None else agent.max_history_turns))
        cache_messages = select_context(state.messages, runner.max_history_turns, native=provider.name != "chat", provider_items=state.provider_items)
        cache_key = _cache_identity(agent, provider.name, response_format)
        cached = get_cache_manager().get(cache_messages, cache_key, use_semantic=False) if agent.cache and provider.name == "chat" and not agent.tools and not resuming else None
        if cached is not None:
            context.check()
            value = validate(cached)
            state.messages.append({"role": "assistant", "content": cached})
            state.output, state.status = cached, RunStatus.COMPLETED
            context.record("cache_hit")
            context.record("run_completed")
        else:
            runner.run()
            value = runner.value
        if not state.success:
            return AgentExecution(state, exception=runner.exception)
        output_context = _result_context(session, state, value)
        if agent.cache and provider.name == "chat" and not agent.tools and cached is None:
            get_cache_manager().set(cache_messages, cache_key, state.output)
        return AgentExecution(state, value, output_context)
    except CheckpointConflict:
        raise
    except Exception as error:  # noqa: BLE001 - Preserve typed failure for synchronous compatibility callers.
        state.status = error.status if isinstance(error, RunStopped) else RunStatus.FAILED
        state.error = str(error) if isinstance(error, RunStopped) else f"Run setup or output validation failed: {type(error).__name__}"
        context.record("run_stopped", status=state.status.value, error=state.error)
        return AgentExecution(state, exception=error)


def _result_context(session: NexaAgent, state: RunState, value: Any) -> AgentContext | None:
    session._tool_results = [{"call_id": key, **entry} for key, entry in state.tool_journal.items()]
    session._snapshot_context(value)
    output_context = session.last_context()
    if session.context_spec:
        sink = session.context_spec.sink
        if sink.startswith("shared:"):
            shared_context(sink.removeprefix("shared:"), output_context)
        elif sink == "discard":
            return None
        elif sink != "downstream":
            raise ValueError(f"Unknown context sink: {sink}")
    return output_context


def _prepare_input(session: NexaAgent, args: tuple[Any, ...]) -> bool:
    upstream = next((arg for arg in args if isinstance(arg, AgentContext)), None)
    if session.context_spec and session.context_spec.source.startswith("shared:"):
        upstream = shared_context(session.context_spec.source.removeprefix("shared:"))
    if session.context_spec and session.context_spec.source == "fresh":
        session.messages = [{"role": "system", "content": session.system_prompt}]
    if upstream is not None and session.context_spec and session.context_spec.source != "fresh":
        if session.context_spec.input_schema and upstream.output_schema != session.context_spec.input_schema:
            raise ValueError("Upstream context does not satisfy the declared input schema")
        upstream.apply_to(session, session.context_spec.inherit)
    if session.context_spec and session.context_spec.source not in {"fresh", "upstream"} and not session.context_spec.source.startswith("shared:"):
        raise ValueError(f"Unknown context source: {session.context_spec.source}")
    _append_input(session, args)
    return bool(session.context_spec and (session.context_spec.source == "fresh" or upstream is not None))


def _append_input(session: NexaAgent, args: tuple[Any, ...]) -> None:
    text = " ".join(str(arg) for arg in args if not isinstance(arg, AgentContext))
    reflection = reflections()
    if reflection:
        text += f"\n[Reflection]: {reflection}"
    memory = global_memory.get_context(session.memory_scope)
    if memory:
        text += f"\n[Context]: {memory}"
    session.messages.append({"role": "user", "content": text})


def _output_validator(session: NexaAgent, args: tuple[Any, ...]) -> Callable[[str], Any]:
    input_text = next((str(message.get("content", "")) for message in reversed(session.messages) if message.get("role") == "user"), "")
    context = {"input": input_text, "args": args}
    old_values = None
    if session.contracts:
        violation = check_requires(session.contracts, context)
        if violation is not None:
            raise violation
        old_values = capture_old_values(session.contracts, context)

    def validate(text: str) -> Any:
        value: Any = text
        schema = session.protocol or session.output_schema
        if schema:
            value = schema.model_validate_json(text)
        elif session.output_format == "json":
            value = json.loads(text)
        return session._check_ensures_contract(value, old_values)

    return validate


def _response_format(agent: NexaAgent) -> dict[str, Any] | None:
    schema = agent.protocol or agent.output_schema
    if schema:
        return {"type": "json_schema", "json_schema": {"name": f"{agent.name}_schema", "schema": schema.model_json_schema()}}
    return {"type": "json_object"} if agent.output_format == "json" else None


def _cache_identity(agent: NexaAgent, provider: str, response_format: dict[str, Any] | None) -> str:
    _, endpoint = agent._resolve_provider_config()
    if provider == "anthropic":
        endpoint = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    return json.dumps({"provider": provider, "model": agent.model, "endpoint": endpoint,
                       "response_format": response_format, "max_tokens": agent.max_tokens}, sort_keys=True)
