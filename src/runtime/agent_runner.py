"""Bounded agent loop shared by generated programs and the Python SDK."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from .artifacts import ArtifactStore
from .checkpoints import CheckpointConflict
from .flow_runtime import select_context
from .providers import ModelProvider, ModelReply, ModelRequest
from .run_state import RunContext, RunState, RunStatus, RunStopped
from .tool_dispatch import ToolDispatcher, ToolOutcome, validate_arguments


class AgentRunner:
    def __init__(self, context: RunContext, provider: ModelProvider, tools: ToolDispatcher, *,
                 validate_output: Callable[[str], Any], max_output_tokens: int | None = None,
                 response_format: dict[str, Any] | None = None, stream: bool = False, tool_choice: str = "auto",
                 on_text: Callable[[str], None] | None = None, artifacts: ArtifactStore | None = None, max_history_turns: int | None = None) -> None:
        self.context = context
        self.provider = provider
        self.tools = tools
        self.validate_output = validate_output
        self.max_output_tokens = max_output_tokens
        self.response_format = response_format
        self.stream = stream
        self.tool_choice = tool_choice
        self.on_text = on_text
        self.value: Any = None
        self.exception: Exception | None = None
        self.artifacts = artifacts
        self.max_history_turns = max_history_turns

    def run(self) -> RunState:
        state = self.context.state
        if state.status not in {RunStatus.RUNNING, RunStatus.WAITING_APPROVAL}:
            return state
        state.status = RunStatus.RUNNING
        state.error = None
        try:
            self.context.record("run_started" if not state.events else "run_resumed")
            while True:
                self.context.check()
                if state.pending_calls:
                    if not self._dispatch_pending():
                        return state
                    continue
                reply = self._request_model()
                self._accept_reply(reply)
                self.context.check()
                if state.pending_calls:
                    continue
                self.value = self.validate_output(reply.text)
                self.context.check()
                state.output = reply.text
                state.status = RunStatus.COMPLETED
                self.context.record("run_completed")
                return state
        except CheckpointConflict:
            raise
        except RunStopped as error:
            self.exception = error
            state.status, state.error = error.status, str(error)
        except Exception as error:  # noqa: BLE001 - The public result retains failed runs; legacy callers re-raise.
            self.exception = error
            state.status, state.error = RunStatus.FAILED, f"Run failed: {type(error).__name__}"
        self.context.record("run_stopped", status=state.status.value, error=state.error)
        return state

    def _request_model(self) -> ModelReply:
        state = self.context.state
        for attempt in range(self.context.config.retries + 1):
            self.context.check()
            if state.model_calls >= self.context.config.max_model_calls:
                raise RunStopped(RunStatus.BUDGET_EXHAUSTED, "Model-call budget exhausted")
            if self.context.config.max_tokens is not None and state.input_tokens + state.output_tokens >= self.context.config.max_tokens:
                raise RunStopped(RunStatus.BUDGET_EXHAUSTED, "Token budget exhausted")
            state.model_calls += 1
            self.context.record("model_started", attempt=attempt + 1, model_call=state.model_calls)
            exposed = [tool.function_schema() for tool in self.tools.tools.values()] if self.tool_choice != "none" else []
            request = ModelRequest(
                model=state.model, messages=select_context(state.messages, self.max_history_turns, native=self.provider.name != "chat", provider_items=state.provider_items),
                tools=exposed, timeout=self.context.remaining(),
                stream=self.stream, max_output_tokens=self.max_output_tokens, response_format=self.response_format,
                tool_choice=self.tool_choice if state.tool_calls == 0 else "auto", provider_items=copy.deepcopy(state.provider_items),
                provider_cursor=state.provider_cursor,
            )
            try:
                return self.provider.complete(request, self._stream_text)
            except Exception as error:
                if not _retryable_provider_error(error):
                    raise
                self.context.record("model_retry", error_type=type(error).__name__)
                if attempt == self.context.config.retries:
                    raise
                if self.context.cancel.wait(min(0.25 * 2**attempt, max(0.0, self.context.remaining()))):
                    self.context.check()
        raise RuntimeError("Model retries exhausted")

    def _stream_text(self, text: str) -> None:
        self.context.check()
        if self.on_text is not None:
            self.on_text(text)

    def _accept_reply(self, reply: ModelReply) -> None:
        state = self.context.state
        seen: set[str] = set()
        historical_ids = {call.get("id") for message in state.messages for call in message.get("tool_calls") or []}
        for call in reply.tool_calls:
            call_id = call.get("id")
            if not isinstance(call_id, str) or not call_id or call_id in seen or call_id in state.tool_journal or call_id in historical_ids:
                raise ValueError("Provider returned a missing or reused tool-call ID")
            if call.get("type", "function") != "function" or not isinstance(call.get("function"), dict):
                raise ValueError("Provider returned an unsupported tool-call shape")
            seen.add(call_id)
        state.messages.append(copy.deepcopy(reply.message))
        state.pending_calls = copy.deepcopy(reply.tool_calls)
        state.provider_items = copy.deepcopy(reply.provider_items)
        state.provider_cursor = reply.provider_cursor
        state.input_tokens += reply.input_tokens
        state.output_tokens += reply.output_tokens
        state.usage_reported = state.usage_reported or reply.usage_reported
        self.context.record("model_completed", tool_call_count=len(reply.tool_calls), input_tokens=reply.input_tokens,
                            output_tokens=reply.output_tokens, usage_reported=reply.usage_reported)
        if self.context.config.max_tokens is not None and not reply.usage_reported:
            raise RunStopped(RunStatus.FAILED, "Provider omitted usage required by the token budget")

    def _dispatch_pending(self) -> bool:
        state = self.context.state
        call = state.pending_calls[0]
        call_id, function = call["id"], call["function"]
        name, arguments = function["name"], function.get("arguments", "{}")
        journal = state.tool_journal.get(call_id)
        if journal is not None:
            if journal["status"] == "completed":
                self._append_result(call, journal["content"])
                return True
            raise RunStopped(RunStatus.FAILED, f"Tool call {call_id} has an unknown outcome; resolve it before retrying")
        tool = self.tools.tools.get(name)
        if tool is None or self.tool_choice == "none":
            raise RunStopped(RunStatus.FAILED, f"Tool '{name}' is not exposed to this run")
        validate_arguments(arguments, tool.parameters)
        if tool.sandbox:
            raise RunStopped(RunStatus.FAILED, "A sandbox was requested, but no isolated executor is configured")
        approval = state.approvals.get(call_id)
        if (tool.requires_approval or tool.risk_level in {"high", "critical"}) and approval is None:
            state.status = RunStatus.WAITING_APPROVAL
            self.context.record("approval_requested", call_id=call_id, tool=name)
            return False
        if approval is False:
            self._store_tool_result(call, ToolOutcome(name, "failed", error="Tool execution denied by approval policy"))
            return True
        if state.tool_calls >= self.context.config.max_tool_calls:
            raise RunStopped(RunStatus.BUDGET_EXHAUSTED, "Tool-call budget exhausted")
        self.context.check()
        state.tool_calls += 1
        state.tool_journal[call_id] = {"status": "started", "tool": name}
        self.context.record("tool_started", call_id=call_id, tool=name)
        outcome = self.tools.dispatch(name, arguments, approved=approval)
        if outcome.status == "unknown":
            raise RunStopped(RunStatus.FAILED, f"Tool call {call_id} has an unknown outcome; resolve it before retrying")
        self._store_tool_result(call, outcome)
        self.context.check()
        return True

    def _store_tool_result(self, call: dict[str, Any], outcome: ToolOutcome) -> None:
        state = self.context.state
        content = outcome.text()
        if self.artifacts is not None:
            content = self.artifacts.offload(content, self.context.config.max_tool_output_chars)
        state.tool_journal[call["id"]] = {"status": "completed", "tool": outcome.name, "content": content,
                                           "success": outcome.status == "completed", "sandboxed": outcome.sandboxed}
        self.context.record("tool_completed", call_id=call["id"], tool=outcome.name, success=outcome.status == "completed")
        self._append_result(call, content)

    def _append_result(self, call: dict[str, Any], content: str) -> None:
        state = self.context.state
        if not any(message.get("tool_call_id") == call["id"] for message in state.messages):
            state.messages.append({"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"], "content": content})
        state.pending_calls.pop(0)
        self.context.record("tool_result_attached", call_id=call["id"])


def _retryable_provider_error(error: Exception) -> bool:
    if isinstance(error, (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)):
        return True
    try:
        import anthropic
    except ImportError:
        return False
    return isinstance(error, (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.InternalServerError, anthropic.RateLimitError))
