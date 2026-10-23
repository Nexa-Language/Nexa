"""Execute generated Harness constructs, observing effects at runtime boundaries."""

from __future__ import annotations

from typing import Any

import pytest
from test_agent_execution import FakeClient, completion

from src import nexa_sdk
from src.compiler import compile_source
from src.runtime.agent import NexaAgent
from src.runtime.flow_runtime import context_scope, select_context


def test_autoloop_checks_exact_exit_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([completion("not done"), completion("done")])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    result = nexa_sdk.run('agent A {} flow main { autoloop max_steps: 5, exit_when: "done" { result = A.run("work"); } }')
    assert result.success, result.stderr
    assert len(client.requests) == 2


def test_failed_verify_stops_flow() -> None:
    result = nexa_sdk.run('flow main { result = 3; verify result satisfies string; result = "unexpected"; }')
    assert not result.success
    assert "string" in result.stderr


def test_context_scope_applies_budget_and_cleans_up(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([completion()])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    result = nexa_sdk.run('agent A {} flow main { with_context max_tokens: 1, strategy: sliding_window { result = A.run("hi"); } }')
    assert not result.success
    assert "Context budget exceeded" in result.stderr
    assert not client.requests
    assert NexaAgent("next").run("hi") == "done"


def test_context_trimming_keeps_tool_call_result_pairs() -> None:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "instructions"}, {"role": "user", "content": "old" * 1000},
        {"role": "assistant", "tool_calls": [{"id": "c1"}]}, {"role": "tool", "tool_call_id": "c1", "content": "result"},
        {"role": "assistant", "content": "done"}, {"role": "user", "content": "new"},
    ]
    with context_scope(1000):
        selected = select_context(messages)
    assert selected == [messages[0], messages[-1]]
    assert len(messages) == 6


def test_snapshot_restores_agent_and_flow_state(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([completion("first"), completion("second")])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    compiled = compile_source('agent A {} flow main { result = A.run("one"); snap = snapshot(); result = A.run("two"); restore(snap); }')
    namespace: dict[str, Any] = {"__name__": "snapshot_fixture"}
    exec(compiled.python_code, namespace)  # noqa: S102 - Executes compiler output from a fixed test program.
    assert namespace["flow_main"]() == "first"
    assert namespace["A"].messages[-1]["content"] == "first"


def test_reflection_reaches_next_agent_request(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([completion()])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    result = nexa_sdk.run('agent A {} flow main { reflect "Check the evidence"; result = A.run("hi"); }')
    assert result.success, result.stderr
    assert "Check the evidence" in client.requests[0]["messages"][-1]["content"]


def test_shorthand_schema_validates_actual_generated_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([completion('{"steps":[{"title":"run"}],"count":1}')])
    monkeypatch.setattr(NexaAgent, '_get_client', lambda self: client)
    result = nexa_sdk.run('agent A { output_schema: {"steps":[{"title":"string"}],"count":"integer"} } flow main { result = A.run("plan"); }')
    assert result.success, result.stderr
    assert result.result.count == 1 and result.result.steps[0].title == 'run'


def test_correction_body_runs_and_bare_print_is_real() -> None:
    result = nexa_sdk.run('flow main { result = "before"; try_agent { assert false; } catch_correction(e: Exception) { result = "corrected"; print result; } }')
    assert result.success, result.stderr
    assert 'corrected' in result.stdout


def test_string_literals_preserve_quotes_and_newlines() -> None:
    result = nexa_sdk.run('flow main { result = "{\\"key\\": 1}"; }')
    assert result.success, result.stderr
    assert result.result == '{"key": 1}'


def test_actor_mailbox_runs_in_order_and_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([completion('first'), completion('second')])
    monkeypatch.setattr(NexaAgent, '_get_client', lambda self: client)
    result = nexa_sdk.run('agent A {} flow main { worker = spawn A("one"); pass "two" to worker; result = await worker; }')
    assert result.success, result.stderr
    assert result.result == 'second'
    assert [message['content'] for message in client.requests[-1]['messages'] if message['role'] == 'user'] == ['one', 'two']


def test_unjoined_actor_stops_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(NexaAgent, '_get_client', lambda self: FakeClient([completion()]))
    result = nexa_sdk.run('agent A {} flow main { worker = spawn A("one"); }')
    assert not result.success
    assert 'must be awaited' in result.stderr


def test_actor_limit_applies_to_concurrency_not_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.runtime.flow_runtime import flow_scope, spawn_actor
    client = FakeClient([completion(str(index)) for index in range(10)])
    monkeypatch.setattr(NexaAgent, '_get_client', lambda self: client)

    @flow_scope
    def run() -> list[str]:
        return [spawn_actor(NexaAgent('A'), 'work').join() for _ in range(10)]

    assert run() == [str(index) for index in range(10)]
