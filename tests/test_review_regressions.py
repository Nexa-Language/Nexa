"""Behavior regressions found by the independent modernization review."""
from __future__ import annotations

import subprocess
from http.client import IncompleteRead
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest
from requests.exceptions import ChunkedEncodingError, ContentDecodingError
from requests.exceptions import Timeout as RequestsTimeout
from test_agent_execution import FakeClient, call, completion
from test_native_providers import NativeFixture, response

from src.runtime.agent import NexaAgent
from src.runtime.agent_context import ContextSpec
from src.runtime.agent_execution import execute_agent
from src.runtime.cache_manager import init_cache_manager
from src.runtime.flow_runtime import context_scope
from src.runtime.inspector import inspect_nexa_file
from src.runtime.native_providers import ResponsesProvider
from src.runtime.run_state import RunStatus
from src.runtime.tool_registry import ToolRegistry
from src.runtime.validator import validate_nexa_file


@pytest.mark.parametrize('interface', ['request_approval', 'wait_for_human'])
def test_approval_requires_a_boolean(interface: str) -> None:
    effects: list[int] = []
    manager = type('Manager', (), {interface: lambda *args, **kwargs: 'false'})()
    registry = ToolRegistry()
    registry._hitl_manager = manager

    def write() -> None:
        effects.append(1)

    registry.register_from_annotation(write, requires_approval=True)
    result = registry.execute('write', {})
    assert not result.success and not result.approved
    assert not effects


@pytest.mark.parametrize("error", [TimeoutError("Disconnected"), subprocess.TimeoutExpired("command", 30), RequestsTimeout("Disconnected"), URLError("Disconnected")])
def test_transport_failure_keeps_unknown_journal(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    effects: list[int] = []

    def write() -> None:
        effects.append(1)
        raise error

    client = FakeClient([completion(calls=[call('write')]), completion()])
    agent = NexaAgent('transport', tools=[{'name': 'write', 'parameters': {'type': 'object'}, '_handler': write}])
    monkeypatch.setattr(agent, 'client', client)
    result = agent.execute('write')
    assert result.status == RunStatus.FAILED
    assert 'unknown outcome' in (result.error or '')
    assert effects == [1] and len(client.requests) == 1
    assert result.tool_journal['call-1']['status'] == 'started'


def test_stdlib_shell_timeout_keeps_unknown_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.runtime.stdlib import get_stdlib_tools

    effects: list[int] = []

    def disconnect(*args: Any, **kwargs: Any) -> None:
        effects.append(1)
        raise subprocess.TimeoutExpired('fixture-command', 30)

    monkeypatch.setenv('NEXA_ENABLE_DANGEROUS_TOOLS', '1')
    monkeypatch.setattr(subprocess, 'run', disconnect)
    tool = get_stdlib_tools()['shell_exec']
    client = FakeClient([completion(calls=[call(tool.name, '{"command":"python fixture.py"}')]), completion()])
    agent = NexaAgent('stdlib', tools=[{**tool.to_dict(), '_handler': tool.handler}])
    monkeypatch.setattr(agent, 'client', client)
    result = agent.execute('execute')
    assert result.status == RunStatus.FAILED
    assert result.tool_journal['call-1']['status'] == 'started'
    assert effects == [1] and len(client.requests) == 1


def test_resume_rejects_a_changed_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    agent = NexaAgent('workspace', tools=[{'name': 'write', 'parameters': {'type': 'object'}, 'requires_approval': True, '_handler': lambda: None}])
    monkeypatch.setattr(agent, 'client', FakeClient([completion(calls=[call('write')])]))
    result = agent.execute('write')
    other = tmp_path / 'other'
    other.mkdir()
    monkeypatch.chdir(other)
    result.approvals['call-1'] = True
    with pytest.raises(ValueError, match='working directory'):
        agent.execute(state=result)


def test_inspect_and_validate_resolve_includes(tmp_path: Path) -> None:
    (tmp_path / 'hidden.nx').write_text('agent Hidden {}')
    main = tmp_path / 'main.nx'
    main.write_text('include "hidden.nx"; flow main {}')
    assert validate_nexa_file(str(main))['valid']
    assert any(agent['name'] == 'Hidden' for agent in inspect_nexa_file(str(main))['agents'])


def test_responses_refusal_fails() -> None:
    client = NativeFixture([response([{'type': 'message', 'id': 'msg', 'role': 'assistant', 'status': 'completed',
                                     'content': [{'type': 'refusal', 'refusal': 'declined'}]}])])
    result = NexaAgent('refusal').execute('hi', provider=ResponsesProvider(lambda: client))
    assert result.status == RunStatus.FAILED


def test_upstream_declaration_preserves_native_continuation(monkeypatch: pytest.MonkeyPatch) -> None:
    reasoning = {'type': 'reasoning', 'id': 'rs', 'summary': [], 'encrypted_content': 'opaque'}
    client = NativeFixture([response([reasoning]), response([])])
    agent = NexaAgent('continuation', provider_api='responses', context_spec=ContextSpec(source='upstream'))
    monkeypatch.setattr(agent, 'client', client)
    agent.run('one')
    agent.run('two')
    assert reasoning in client.requests[1]['input']


def test_native_context_budget_counts_opaque_items() -> None:
    client = NativeFixture([response([
        {'type': 'reasoning', 'id': 'rs', 'summary': [], 'encrypted_content': 'x' * 10000},
        {'type': 'function_call', 'id': 'fc', 'call_id': 'c1', 'name': 'number', 'arguments': '{}'},
    ]), response([])])
    agent = NexaAgent('budget', tools=[{'name': 'number', 'parameters': {'type': 'object'}, '_handler': lambda: 42}])
    with context_scope(2000, 'strict'):
        result = agent.execute('hi', provider=ResponsesProvider(lambda: client))
    assert result.status == RunStatus.FAILED
    assert len(client.requests) == 1


def test_cache_uses_effective_context_and_checks_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    init_cache_manager(enable_disk_cache=False)
    client = FakeClient([completion('short'), completion('full')])
    monkeypatch.setattr(NexaAgent, '_get_client', lambda self: client)
    history: list[dict[str, Any]] = [{'role': 'system', 'content': ''}, {'role': 'user', 'content': 'old fact'}, {'role': 'assistant', 'content': 'ok'}]
    short = NexaAgent('cache', cache=True, max_history_turns=1)
    full = NexaAgent('cache', cache=True, max_history_turns=2)
    assert execute_agent(short, ('question',), history=history).value == 'short'
    assert execute_agent(full, ('question',), history=history).value == 'full'
    assert len(client.requests) == 2
    with context_scope(1, 'strict'):
        rejected = execute_agent(short, ('question',), history=history)
    assert rejected.state.status == RunStatus.FAILED
    assert len(client.requests) == 2


@pytest.mark.parametrize('method', ['post', 'put', 'delete'])
@pytest.mark.parametrize('error', [RequestsTimeout('Response missing'), ChunkedEncodingError('Response interrupted'),
                                  ContentDecodingError('Response invalid'), IncompleteRead(b'partial')])
def test_stdlib_transport_failure_is_not_a_successful_result(method: str, error: Exception, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    import requests

    from src.runtime.stdlib import get_stdlib_tools

    effects: list[int] = []
    def disconnect(*args: Any, **kwargs: Any) -> None:
        effects.append(1)
        raise error

    monkeypatch.setattr(requests, method, disconnect)
    tool = get_stdlib_tools()['http_' + method]
    params = {'url': 'https://fixture.invalid'}
    if method != 'delete':
        params['data'] = '{}'
    client = FakeClient([completion(calls=[call(tool.name, json.dumps(params))]), completion()])
    agent = NexaAgent('stdlib', tools=[{**tool.to_dict(), '_handler': tool.handler}])
    monkeypatch.setattr(agent, 'client', client)
    result = agent.execute('send')
    assert result.status == RunStatus.FAILED
    assert result.tool_journal['call-1']['status'] == 'started'
    assert effects == [1] and len(client.requests) == 1
