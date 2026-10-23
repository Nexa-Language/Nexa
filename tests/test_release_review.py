"""Execute regressions reported during the 2.4 release review."""

from __future__ import annotations

from typing import Any

import pytest
from anthropic.types import Message
from pydantic import BaseModel
from test_agent_execution import FakeClient, call, completion
from test_native_providers import NativeFixture, response

from src.compiler import compile_source
from src.runtime.agent import NexaAgent
from src.runtime.agent_execution import execute_agent
from src.runtime.contracts import ContractClause, ContractSpec
from src.runtime.flow_runtime import emit_hook
from src.runtime.native_providers import AnthropicProvider, ResponsesProvider
from src.runtime.run_state import RunConfig, RunState, RunStatus


@pytest.mark.parametrize("budget", [0, 1])
def test_tool_budget_leaves_a_final_answer_request(monkeypatch: pytest.MonkeyPatch, budget: int) -> None:
    effects: list[int] = []
    replies = ([completion(calls=[call("work")])] if budget else []) + [completion("finished")]
    client = FakeClient(replies)
    agent = NexaAgent("bounded", tool_call_strategy="required", tools=[{
        "name": "work", "parameters": {"type": "object"}, "_handler": lambda: effects.append(1),
    }])
    monkeypatch.setattr(agent, "client", client)
    state = agent.execute("work", config=RunConfig(max_tool_calls=budget))
    assert state.success and state.output == "finished"
    assert effects == [1] * budget
    assert "tools" not in client.requests[-1] and "tool_choice" not in client.requests[-1]
    if budget:
        assert client.requests[0]["tool_choice"] == "required"
        assert client.requests[-1]["messages"][-1]["role"] == "tool"


class Answer(BaseModel):
    value: int


@pytest.mark.parametrize("mode", ["protocol", "output_schema", "json"])
def test_structured_output_retries_with_correction(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    options: dict[str, Any] = {"output_format": "json"} if mode == "json" else {mode: Answer}
    invalid = ["broken"] if mode == "json" else ["broken", '{"value":"invalid"}']
    client = FakeClient([completion(text) for text in [*invalid, '{"value":42}']])
    agent = NexaAgent("structured", max_history_turns=1, **options)
    monkeypatch.setattr(agent, "client", client)
    result = execute_agent(agent, ("answer",), config=RunConfig(retries=2))
    assert result.state.success, result.state.error
    assert (result.value if mode == "json" else result.value.model_dump()) == {"value": 42}
    assert result.state.model_calls == len(invalid) + 1
    assert [event["event"] for event in result.state.events].count("output_retry") == len(invalid)
    for request in client.requests[1:]:
        assert request["messages"][-1]["role"] == "user"
        assert "JSON" in request["messages"][-1]["content"]
        assert any(message.get("content") == "answer" for message in request["messages"])
        assert any(message.get("content") == "broken" for message in request["messages"])


@pytest.mark.parametrize(("config", "expected", "calls"), [
    (RunConfig(retries=1), RunStatus.FAILED, 2),
    (RunConfig(retries=2, max_model_calls=1), RunStatus.BUDGET_EXHAUSTED, 1),
    (RunConfig(retries=2, max_tokens=5), RunStatus.BUDGET_EXHAUSTED, 1),
])
def test_output_correction_obeys_run_budgets(
    monkeypatch: pytest.MonkeyPatch, config: RunConfig, expected: RunStatus, calls: int,
) -> None:
    client = FakeClient([completion("broken")] * 3)
    agent = NexaAgent("structured", protocol=Answer)
    monkeypatch.setattr(agent, "client", client)
    state = agent.execute("answer", config=config)
    assert state.status == expected
    assert len(client.requests) == calls


@pytest.mark.parametrize("valid_after_resume", [False, True])
def test_output_retry_budget_survives_approval_checkpoint(monkeypatch: pytest.MonkeyPatch, valid_after_resume: bool) -> None:
    effects: list[int] = []
    contract = ContractSpec(ensures=[ContractClause(expression='input == "answer"')])
    agent = NexaAgent("structured", protocol=Answer, contracts=contract, tools=[{
        "name": "work", "parameters": {"type": "object"}, "requires_approval": True, "_handler": lambda: effects.append(1),
    }])
    final = '{"value":42}' if valid_after_resume else "still broken"
    client = FakeClient([completion("broken"), completion(calls=[call("work")]), completion(final), completion('{"value":42}')])
    monkeypatch.setattr(agent, "client", client)
    state = agent.execute("answer", config=RunConfig(retries=1))
    assert state.status == RunStatus.WAITING_APPROVAL
    restored = RunState.from_dict(state.to_dict())
    restored.approvals["call-1"] = True
    result = agent.execute(state=restored)
    assert result.status == (RunStatus.COMPLETED if valid_after_resume else RunStatus.FAILED)
    assert effects == [1] and len(client.requests) == 3
    assert result.tool_journal["call-1"]["status"] == "completed"


@pytest.mark.parametrize("valid_contract", [False, True])
def test_output_correction_preserves_contract_input(monkeypatch: pytest.MonkeyPatch, valid_contract: bool) -> None:
    replies = [completion("broken"), completion('{"value":42}')] if valid_contract else [completion('{"value":42}')]
    client = FakeClient(replies)
    contract = ContractSpec(ensures=[ContractClause(expression='input == "answer"' if valid_contract else "False")])
    agent = NexaAgent("structured", protocol=Answer, contracts=contract)
    monkeypatch.setattr(agent, "client", client)
    result = agent.execute("answer", config=RunConfig(retries=2))
    assert result.success == valid_contract
    assert len(client.requests) == len(replies)
    if not valid_contract:
        assert "ContractViolation" in (result.error or "")
        assert not any(event["event"] == "output_retry" for event in result.events)


@pytest.mark.parametrize("api", ["responses", "anthropic"])
def test_native_output_correction_preserves_protocol_history(api: str) -> None:
    replies: list[Any] = []
    for index, text in enumerate(("broken", '{"value":42}')):
        if api == "responses":
            replies.append(response([{"type": "message", "id": f"msg{index}", "role": "assistant", "status": "completed",
                                      "content": [{"type": "output_text", "text": text, "annotations": []}]}]))
        else:
            replies.append(Message.model_validate({"id": f"msg{index}", "type": "message", "role": "assistant", "model": "fixture",
                                                   "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
                                                   "usage": {"input_tokens": 3, "output_tokens": 2}}))
    client = NativeFixture(replies)
    provider = ResponsesProvider(lambda: client) if api == "responses" else AnthropicProvider(lambda: client)
    state = NexaAgent("native", protocol=Answer, max_history_turns=1).execute("answer", provider=provider)
    assert state.success and state.model_calls == 2
    request = client.requests[1]
    if api == "responses":
        assert {"role": "user", "content": "answer"} in request["input"]
        assert request["input"][-2]["content"][0]["text"] == "broken"
        assert request["input"][-1]["role"] == "user" and "JSON" in request["input"][-1]["content"]
    else:
        assert request["messages"][0] == {"role": "user", "content": [{"type": "text", "text": "answer"}]}
        assert request["messages"][-2]["content"][0]["text"] == "broken"
        assert request["messages"][-1]["role"] == "user"
        assert "JSON" in request["messages"][-1]["content"][0]["text"]


def test_compiled_error_hook_binds_declared_name(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient([ValueError("fixture failure")])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    compiled = compile_source('agent A {} flow main { on_error(problem: Exception) { print(problem); } result = A.run("go"); }')
    namespace: dict[str, Any] = {"__name__": "error_hook_fixture"}
    exec(compiled.python_code, namespace)  # noqa: S102 - Fixed compiler fixture.
    with pytest.raises(ValueError, match="fixture failure"):
        namespace["flow_main"]()
    assert capsys.readouterr().out.splitlines() == ["Run failed: ValueError"]
    assert len(client.requests) == 1


def test_compiled_tool_hooks_filter_the_named_tool(capsys: pytest.CaptureFixture[str]) -> None:
    compiled = compile_source('''flow main {
        before_tool(foo) { print("before foo"); }
        after_tool(foo) { print("after foo"); }
    }''')
    namespace: dict[str, Any] = {"__name__": "hook_fixture"}
    exec(compiled.python_code, namespace)  # noqa: S102 - Fixed compiler fixture.
    register = namespace["_nexa_register_hook"]

    def register_and_emit(event: str, function: Any) -> None:
        register(event, function)
        if event == "after_tool":
            for tool in ("bar", "foo"):
                for name in ("tool_started", "tool_completed"):
                    emit_hook({"event": name, "tool": tool})

    namespace["_nexa_register_hook"] = register_and_emit
    namespace["flow_main"]()
    assert capsys.readouterr().out.splitlines() == ["before foo", "after foo"]
