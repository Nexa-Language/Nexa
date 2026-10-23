"""Native provider tool round trips preserve protocol-owned opaque state."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from anthropic.types import Message
from openai.types.responses import Response

from src import nexa_sdk
from src.runtime.agent import NexaAgent
from src.runtime.native_providers import AnthropicProvider, ResponsesProvider
from src.runtime.run_state import RunConfig


class NativeFixture:
    def __init__(self, replies: list[Any]) -> None:
        self.replies = iter(replies)
        self.requests: list[dict[str, Any]] = []
        self.responses = self.messages = self

    def create(self, **kwargs: Any) -> Any:
        self.requests.append(copy.deepcopy(kwargs))
        return next(self.replies)


def response(output: list[dict[str, Any]]) -> Response:
    return Response.model_validate({"id": "resp_fixture", "object": "response", "created_at": 1, "model": "fixture",
                                    "status": "completed", "output": output, "parallel_tool_calls": False,
                                    "tool_choice": "auto", "tools": [], "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5,
                                    "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                                    "output_tokens_details": {"reasoning_tokens": 0}}})


def test_responses_preserves_encrypted_reasoning_across_tool_result() -> None:
    reasoning = {"type": "reasoning", "id": "rs_fixture", "summary": [], "encrypted_content": "opaque-fixture"}
    client = NativeFixture([
        response([reasoning, {"type": "function_call", "id": "fc_fixture", "call_id": "c1", "name": "number", "arguments": "{}"}]),
        response([{"type": "message", "id": "msg_fixture", "role": "assistant", "status": "completed",
                   "content": [{"type": "output_text", "text": "42", "annotations": []}]}]),
    ])
    agent = NexaAgent("native", tools=[{"name": "number", "parameters": {"type": "object"}, "_handler": lambda: 42}])
    result = agent.execute("calculate", provider=ResponsesProvider(lambda: client))
    assert result.success, result.error
    assert result.output == "42"
    assert reasoning in client.requests[1]["input"]
    assert client.requests[1]["input"][-1] == {"type": "function_call_output", "call_id": "c1", "output": "42"}
    assert sum(item.get("type") == "function_call" for item in client.requests[1]["input"]) == 1
    assert result.input_tokens == 6 and result.output_tokens == 4
    assert client.requests[0]["store"] is False


def test_anthropic_preserves_signed_thinking_across_tool_result() -> None:
    thinking = {"type": "thinking", "thinking": "fixture reasoning", "signature": "fixture-signature"}
    def reply(blocks: list[dict[str, Any]], reason: str) -> Message:
        return Message.model_validate({"id": "msg_fixture", "type": "message", "role": "assistant", "model": "fixture",
                                       "content": blocks, "stop_reason": reason, "usage": {"input_tokens": 3, "output_tokens": 2}})
    client = NativeFixture([
        reply([thinking, {"type": "tool_use", "id": "c1", "name": "number", "input": {}}], "tool_use"),
        reply([{"type": "text", "text": "42"}], "end_turn"),
    ])
    agent = NexaAgent("native", tools=[{"name": "number", "parameters": {"type": "object"}, "_handler": lambda: 42}])
    result = agent.execute("calculate", provider=AnthropicProvider(lambda: client))
    assert result.success, result.error
    assert thinking in client.requests[1]["messages"][-2]["content"]
    assert client.requests[1]["messages"][-1] == {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "42"}]}
    assert result.output == "42"


def test_provider_api_is_lowered_from_nexa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(NexaAgent, "run", lambda self, *args: self.provider_api)
    result = nexa_sdk.run('agent A { provider_api: "responses" } flow main { result = A.run("hi"); }')
    assert result.success, result.stderr
    assert result.result == "responses"


@pytest.mark.parametrize("interrupted", [False, True])
def test_responses_continuation_preserves_opaque_items(interrupted: bool) -> None:
    reasoning = {"type": "reasoning", "id": "rs_fixture", "summary": [], "encrypted_content": "opaque-fixture"}
    message = {"type": "message", "id": "msg_fixture", "role": "assistant", "status": "completed",
               "content": [{"type": "output_text", "text": "answer", "annotations": []}]}
    pending = {"type": "function_call", "id": "fc_fixture", "call_id": "c1", "name": "number", "arguments": "{}"}
    client = NativeFixture([response([reasoning, pending if interrupted else message]), response([message])])
    provider = ResponsesProvider(lambda: client)
    effects: list[int] = []
    agent = NexaAgent("native", tools=[{"name": "number", "parameters": {"type": "object"}, "_handler": lambda: effects.append(1)}])
    previous = agent.execute("first", provider=provider, config=RunConfig(max_tool_calls=0))
    original = previous.to_dict()
    current = agent.continue_run(previous, "next", provider=provider)
    assert current.success, current.error
    assert previous.to_dict() == original and effects == []
    items = client.requests[-1]["input"]
    assert reasoning in items and items[-1] == {"role": "user", "content": "next"}
    assert sum(item.get("type") == "reasoning" for item in items) == 1
    if interrupted:
        assert items[-2]["type"] == "function_call_output" and items[-2]["call_id"] == "c1"
        assert '"cancelled": true' in items[-2]["output"]


@pytest.mark.parametrize("interrupted", [False, True])
def test_anthropic_continuation_preserves_signed_thinking(interrupted: bool) -> None:
    thinking = {"type": "thinking", "thinking": "fixture reasoning", "signature": "fixture-signature"}
    pending = {"type": "tool_use", "id": "c1", "name": "number", "input": {}}
    message = {"type": "text", "text": "answer"}

    def reply(blocks: list[dict[str, Any]], reason: str = "end_turn") -> Message:
        return Message.model_validate({"id": "msg_fixture", "type": "message", "role": "assistant", "model": "fixture",
                                       "content": blocks, "stop_reason": reason, "usage": {"input_tokens": 3, "output_tokens": 2}})

    client = NativeFixture([reply([thinking, pending if interrupted else message], "tool_use" if interrupted else "end_turn"), reply([message])])
    provider = AnthropicProvider(lambda: client)
    effects: list[int] = []
    agent = NexaAgent("native", tools=[{"name": "number", "parameters": {"type": "object"}, "_handler": lambda: effects.append(1)}])
    previous = agent.execute("first", provider=provider, config=RunConfig(max_tool_calls=0))
    original = previous.to_dict()
    current = agent.continue_run(previous, "next", provider=provider)
    assert current.success, current.error
    assert previous.to_dict() == original and effects == []
    messages = client.requests[-1]["messages"]
    assert thinking in messages[1]["content"]
    assert messages[-1] == {"role": "user", "content": [{"type": "text", "text": "next"}]}
    if interrupted:
        result = messages[-2]["content"][0]
        assert result["type"] == "tool_result" and result["tool_use_id"] == "c1"
        assert '"cancelled": true' in result["content"]
