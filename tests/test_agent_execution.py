"""Real agent and compiler paths with only the provider replaced."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel

from src import nexa_sdk
from src.runtime.agent import NexaAgent
from src.runtime.run_state import RunConfig, RunStatus
from src.runtime.tools_registry import LOCAL_TOOLS


def completion(text: str = "done", calls: list[dict[str, Any]] | None = None) -> ChatCompletion:
    return ChatCompletion.model_validate({
        "id": "fixture", "object": "chat.completion", "created": 1, "model": "fixture",
        "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "stop",
                     "message": {"role": "assistant", "content": text, "tool_calls": calls}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    })


def call(name: str, arguments: str = "{}", call_id: str = "call-1") -> dict[str, Any]:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


class FakeClient:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = iter(responses)
        self.requests: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs: Any) -> Any:
        import copy
        self.requests.append(copy.deepcopy(kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.parametrize(("expression", "inputs", "outputs"), [
    ('"evidence" >> Researcher', ["evidence"], ["facts"]),
    ('"evidence" >> Researcher >> Summarizer', ["evidence", "facts"], ["facts", "summary"]),
    ('Researcher.run("evidence") >> Summarizer', ["evidence", "facts"], ["facts", "summary"]),
    ('"evidence" >> Researcher >> Summarizer >> Editor', ["evidence", "facts", "summary"], ["facts", "summary", "edited"]),
])
def test_compiled_pipeline_executes_every_stage_in_order(
    monkeypatch: pytest.MonkeyPatch, expression: str, inputs: list[str], outputs: list[str],
) -> None:
    client = FakeClient([completion(output) for output in outputs])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    result = nexa_sdk.run('''
agent Researcher { prompt: "Extract the facts." }
agent Summarizer { prompt: "Summarize the facts." }
agent Editor { prompt: "Edit the summary." }
flow main { result = ''' + expression + '; }')
    assert result.success, result.stderr
    assert result.result == outputs[-1]
    assert [request["messages"][-1]["content"] for request in client.requests] == inputs


def test_compiled_pipeline_rejects_unsupported_stage() -> None:
    result = nexa_sdk.compile('flow main { result = "evidence" >> 42; }')
    assert not result.success
    assert result.error is not None and "pipeline stage" in result.error.lower()


@pytest.mark.parametrize("history_limit", ["2", '"2"'])
def test_compiled_history_limit_bounds_provider_input(monkeypatch: pytest.MonkeyPatch, history_limit: str) -> None:
    client = FakeClient([completion("a"), completion("b"), completion("c")])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    result = nexa_sdk.run('agent A { max_history_turns: ' + history_limit + ''' }
flow main { A.run("first"); A.run("second"); result = A.run("third"); }
''')
    assert result.success, result.stderr
    assert result.result == "c"
    assert [message["content"] for message in client.requests[-1]["messages"] if message["role"] == "user"] == ["second", "third"]


@pytest.mark.parametrize("declaration", [
    "agent A { max_tokens: 2000 }",
    "@limit(max_tokens=2000) agent A {}",
    "@limit(max_tokens=2000) agent A { max_tokens: 100 }",
])
def test_compiled_token_limit_reaches_provider(monkeypatch: pytest.MonkeyPatch, declaration: str) -> None:
    client = FakeClient([completion()])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    result = nexa_sdk.run(declaration + ' flow main { result = A.run("evidence"); }')
    assert result.success, result.stderr
    assert client.requests[0]["max_tokens"] == 2000


def test_compiled_timeout_and_retry_decorators_reach_run_config(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([completion()])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    result = nexa_sdk.run('''
@timeout(seconds=7)
@retry(max_attempts=0)
agent A { timeout: 60, retry: 5 }
flow main { result = A.execute("evidence"); }
''')
    assert result.success, result.stderr
    assert result.result.success, result.result.error
    assert result.result.config["timeout"] == 7
    assert result.result.config["retries"] == 0
    assert 0 < client.requests[0]["timeout"] <= 7


def test_unexposed_tool_is_never_executed(monkeypatch: pytest.MonkeyPatch) -> None:
    effects: list[int] = []
    monkeypatch.setitem(LOCAL_TOOLS, "hidden", lambda: effects.append(1))
    agent = NexaAgent("limited", prompt="hello")
    monkeypatch.setattr(agent, "client", FakeClient([completion(calls=[call("hidden")]), completion()]))
    with pytest.raises(Exception, match="not exposed"):
        agent.run("hi")
    assert not effects


def test_malformed_arguments_do_not_become_empty_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    effects: list[int] = []
    monkeypatch.setitem(LOCAL_TOOLS, "change", lambda: effects.append(1))
    agent = NexaAgent("limited", tools=[{"name": "change", "parameters": {"type": "object", "properties": {}}}])
    monkeypatch.setattr(agent, "client", FakeClient([completion(calls=[call("change", "{broken")]), completion()]))
    with pytest.raises(json.JSONDecodeError):
        agent.run("hi")
    assert not effects


def test_protocol_completion_always_creates_context(monkeypatch: pytest.MonkeyPatch) -> None:
    class Answer(BaseModel):
        value: int

    agent = NexaAgent("structured", protocol=Answer)
    client = FakeClient([completion('{"value": 42}')])
    monkeypatch.setattr(agent, "client", client)
    result = agent.run("hi")
    assert result.value == 42
    assert agent.last_context() is not None
    assert 0 < client.requests[0]["timeout"] <= agent.timeout


def test_stream_completion_always_creates_context(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = [ChatCompletionChunk.model_validate({
        "id": "fixture", "object": "chat.completion.chunk", "created": 1, "model": "fixture",
        "choices": [{"index": 0, "finish_reason": finish, "delta": delta}],
    }) for delta, finish in [({"role": "assistant", "content": "hello"}, None), ({}, "stop")]]
    agent = NexaAgent("stream", stream=True)
    monkeypatch.setattr(agent, "client", FakeClient([iter(chunks)]))
    assert agent.run("hi") == "hello"
    assert agent.last_context() is not None


def test_compiled_tool_is_executed_by_real_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([completion(calls=[call("add", json.dumps({"a": 2, "b": 3}))]), completion("5")])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    result = nexa_sdk.run('''
@tool("Add two integers")
fn add(a: int, b: int): int {
    python! """return a + b"""
}
agent Calculator uses add { prompt: "Calculate" }
flow main { result = Calculator.run("2+3"); }
''')
    assert result.success, result.stderr
    assert result.result == "5"
    assert client.requests[-1]["messages"][-1]["content"] == "5"
    assert "timeout" in client.requests[0]


def test_tool_budget_counts_individual_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    effects: list[int] = []
    monkeypatch.setitem(LOCAL_TOOLS, "change", lambda: effects.append(1))
    calls = [call("change", call_id=f"call-{index}") for index in range(3)]
    agent = NexaAgent("budget", tools=[{"name": "change", "parameters": {"type": "object", "properties": {}}}])
    monkeypatch.setattr(agent, "client", FakeClient([completion(calls=calls)]))
    state = agent.execute("hi", config=RunConfig(max_tool_calls=2))
    assert state.status == RunStatus.BUDGET_EXHAUSTED
    assert state.tool_calls == len(effects) == 2
    assert state.model_calls == 1


def test_approval_resumes_the_same_run_without_repeating_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    effects: list[int] = []
    monkeypatch.setitem(LOCAL_TOOLS, "change", lambda: effects.append(1))
    agent = NexaAgent("approval", tools=[{"name": "change", "requires_approval": True,
                                          "parameters": {"type": "object", "properties": {}}}])
    client = FakeClient([completion(calls=[call("change")]), completion()])
    monkeypatch.setattr(agent, "client", client)
    state = agent.execute("hi")
    assert state.status == RunStatus.WAITING_APPROVAL
    assert not effects
    state.approvals["call-1"] = True
    resumed = agent.execute(state=state)
    assert resumed.run_id == state.run_id
    assert resumed.status == RunStatus.COMPLETED
    assert len(effects) == 1
    assert len(client.requests) == 2
    assert client.requests[-1]["messages"][-1]["tool_call_id"] == "call-1"


def test_cancellation_prevents_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    cancelled = threading.Event()
    cancelled.set()
    agent = NexaAgent("cancel")
    client = FakeClient([])
    monkeypatch.setattr(agent, "client", client)
    state = agent.execute("hi", cancel=cancelled)
    assert state.status == RunStatus.CANCELLED
    assert not client.requests


def test_cache_uses_request_snapshot_and_revalidates_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.runtime.cache_manager import init_cache_manager

    class Answer(BaseModel):
        value: int

    init_cache_manager(enable_disk_cache=False)
    agent = NexaAgent("cache", protocol=Answer, cache=True)
    client = FakeClient([completion('{"value": 42}')])
    monkeypatch.setattr(agent, "client", client)
    first = agent.execute("hi")
    second = agent.execute("hi")
    assert first.success and second.success
    assert second.output == first.output
    assert len(client.requests) == 1
    assert any(event["event"] == "cache_hit" for event in second.events)


def test_concurrent_execute_calls_have_independent_state() -> None:
    from concurrent.futures import ThreadPoolExecutor

    from src.runtime.providers import ModelReply, ModelRequest

    class EchoProvider:
        name = "fixture"

        def complete(self, request: ModelRequest, on_text: Any = None) -> ModelReply:
            assert len(request.messages) == 2
            return ModelReply({"role": "assistant", "content": request.messages[-1]["content"]})

    agent = NexaAgent("independent", prompt="echo")
    with ThreadPoolExecutor(max_workers=4) as executor:
        states = list(executor.map(lambda index: agent.execute(str(index), provider=EchoProvider()), range(8)))
    assert [state.output for state in states] == [str(index) for index in range(8)]
    assert len({state.run_id for state in states}) == 8
    assert len(agent.messages) == 1


@pytest.mark.parametrize("budget, status", [(4, RunStatus.BUDGET_EXHAUSTED), (5, RunStatus.COMPLETED)])
def test_usage_enforces_token_budget(monkeypatch: pytest.MonkeyPatch, budget: int, status: RunStatus) -> None:
    agent = NexaAgent("tokens")
    monkeypatch.setattr(agent, "client", FakeClient([completion()]))
    state = agent.execute("hi", config=RunConfig(max_tokens=budget))
    assert state.status == status
    assert state.input_tokens + state.output_tokens == 5
