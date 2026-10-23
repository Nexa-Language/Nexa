"""New conversation turns preserve evidence without replaying tool effects."""

from __future__ import annotations

import copy
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from src import nexa_sdk
from src.runtime.agent import NexaAgent
from src.runtime.checkpoints import SQLiteCheckpointStore
from src.runtime.providers import ModelReply, ModelRequest
from src.runtime.run_state import RunConfig, RunState, RunStatus


class ConversationProvider:
    name = "chat"

    def __init__(self, replies: list[ModelReply]) -> None:
        self.replies = iter(replies)
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest, on_text: Callable[[str], None] | None = None) -> ModelReply:
        self.requests.append(copy.deepcopy(request))
        return next(self.replies)


def answer(text: str = "done") -> ModelReply:
    return ModelReply({"role": "assistant", "content": text}, 3, 2, True)


def test_continuation_accepts_null_tool_calls_in_history() -> None:
    provider = ConversationProvider([
        ModelReply({"role": "assistant", "content": "first", "tool_calls": None}),
        answer("second"),
    ])
    agent = NexaAgent("conversation")
    previous = agent.execute("first turn", provider=provider)
    assert previous.success, previous.error
    current = agent.continue_run(previous, "next turn", provider=provider)
    assert current.success, current.error
    assert current.output == "second"
    assert len(provider.requests) == 2
    assert provider.requests[1].messages == previous.messages + [{"role": "user", "content": "next turn"}]


def test_legacy_run_accepts_null_tool_calls_in_history(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ConversationProvider([
        ModelReply({"role": "assistant", "content": "first", "tool_calls": None}),
        answer("second"),
    ])
    monkeypatch.setattr(NexaAgent, "_provider_adapter", lambda self: provider)
    agent = NexaAgent("conversation")
    assert agent.run("first turn") == "first"
    assert agent.run("next turn") == "second"
    assert len(provider.requests) == 2


def tool_call(call_id: str) -> dict[str, Any]:
    return {"id": call_id, "type": "function", "function": {"name": "change", "arguments": "{}"}}


def tool_reply(*call_ids: str) -> ModelReply:
    return ModelReply({"role": "assistant", "content": "", "tool_calls": [tool_call(key) for key in call_ids]}, 3, 2, True)


def changing_agent(effects: list[int], *, approval: bool = False) -> NexaAgent:
    def change() -> str:
        effects.append(1)
        return "written"

    return NexaAgent("conversation", tools=[{"name": "change", "parameters": {"type": "object", "properties": {}},
                                             "_handler": change, "requires_approval": approval}])


def test_new_turn_has_fresh_budget_and_checkpoint_but_retains_history(tmp_path: Path) -> None:
    provider = ConversationProvider([answer("first answer"), answer("second answer"), answer("third answer")])
    agent = NexaAgent("conversation")
    store = SQLiteCheckpointStore(tmp_path / "runs.db")
    previous = agent.execute("first", provider=provider, config=RunConfig(max_model_calls=1, max_tokens=5), save=store.save)
    original = previous.to_dict()
    events: list[dict[str, Any]] = []
    current = agent.continue_run(previous, "second", provider=provider, save=store.save, on_event=events.append)
    assert current.success, current.error
    assert current.run_id != previous.run_id
    assert current.metadata["parent_run_id"] == previous.run_id
    assert current.metadata["session_id"] == previous.run_id
    assert current.model_calls == 1 and current.input_tokens + current.output_tokens == 5
    assert provider.requests[1].messages == previous.messages + [{"role": "user", "content": "second"}]
    assert previous.to_dict() == original == store.load(previous.run_id).to_dict()
    assert store.load(current.run_id).output == "second answer"
    assert events[0]["event"] == "run_started" and all(event["run_id"] == current.run_id for event in events)
    third = agent.continue_run(current, "third", provider=provider)
    assert third.metadata["session_id"] == previous.run_id
    assert third.metadata["parent_run_id"] == current.run_id


def test_partial_tool_batch_is_closed_without_replaying_effects() -> None:
    effects: list[int] = []
    provider = ConversationProvider([tool_reply("done-call", "unstarted-call"), answer()])
    agent = changing_agent(effects)
    previous = agent.execute("change twice", provider=provider, config=RunConfig(max_tool_calls=1))
    assert previous.status == RunStatus.BUDGET_EXHAUSTED
    original = previous.to_dict()
    current = agent.continue_run(previous, "explain", provider=provider, config=RunConfig(max_tool_calls=0))
    assert current.success, current.error
    assert effects == [1]
    assert current.tool_calls == 0 and current.tool_journal == {} and current.pending_calls == []
    results = [message for message in provider.requests[-1].messages if message["role"] == "tool"]
    assert results[0]["tool_call_id"] == "done-call" and results[0]["content"] == "written"
    assert results[1]["tool_call_id"] == "unstarted-call"
    assert json.loads(results[1]["content"])["cancelled"] is True
    assert previous.to_dict() == original


def test_completed_journal_is_used_when_result_was_not_yet_attached() -> None:
    effects: list[int] = []
    provider = ConversationProvider([tool_reply("done-call"), answer()])
    agent = changing_agent(effects)
    cancelled = threading.Event()

    def interrupt(state: RunState) -> None:
        if state.events[-1]["event"] == "tool_completed":
            cancelled.set()

    previous = agent.execute("change", provider=provider, cancel=cancelled, save=interrupt)
    assert previous.status == RunStatus.CANCELLED
    # A durable snapshot can precede appending the known result to messages.
    previous.messages = [message for message in previous.messages if message["role"] != "tool"]
    previous.pending_calls = [tool_call("done-call")]
    current = agent.continue_run(previous, "explain", provider=provider)
    assert current.success and effects == [1]
    assert provider.requests[-1].messages[-2] == {"role": "tool", "tool_call_id": "done-call", "content": "written"}


def test_approvals_do_not_cross_turns() -> None:
    effects: list[int] = []
    provider = ConversationProvider([tool_reply("first-call"), answer(), tool_reply("second-call")])
    agent = changing_agent(effects, approval=True)
    previous = agent.execute("first", provider=provider)
    previous.approvals["first-call"] = True
    previous = agent.execute(state=previous, provider=provider)
    current = agent.continue_run(previous, "second", provider=provider)
    assert current.status == RunStatus.WAITING_APPROVAL
    assert effects == [1] and current.approvals == {} and current.tool_journal == {}
    assert current.pending_calls[0]["id"] == "second-call"


def test_reused_historical_tool_id_stops_before_a_second_effect() -> None:
    effects: list[int] = []
    provider = ConversationProvider([tool_reply("same-call"), answer(), tool_reply("same-call"), answer()])
    agent = changing_agent(effects)
    previous = agent.execute("first", provider=provider)
    current = agent.continue_run(previous, "next", provider=provider)
    assert current.status == RunStatus.FAILED
    assert effects == [1] and current.tool_calls == 0
    assert len(provider.requests) == 3


def test_continuation_retains_artifact_store(tmp_path: Path) -> None:
    agent = NexaAgent("conversation")
    provider = ConversationProvider([answer(), answer()])
    previous = agent.execute("first", provider=provider, config=RunConfig(artifact_directory=str(tmp_path / "artifacts")))
    with pytest.raises(ValueError, match="artifact directory"):
        agent.continue_run(previous, "next", provider=provider, config=RunConfig(artifact_directory=str(tmp_path / "other")))
    assert len(provider.requests) == 1


def test_next_turn_can_read_previous_large_tool_output(tmp_path: Path) -> None:
    provider = ConversationProvider([tool_reply("large-output"), answer()])
    agent = NexaAgent("conversation", tools=[{"name": "change", "parameters": {"type": "object"}, "_handler": lambda: "evidence" * 100}])
    previous = agent.execute("first", provider=provider,
                             config=RunConfig(artifact_directory=str(tmp_path / "artifacts"), max_tool_output_chars=256))
    artifact_id = json.loads(previous.tool_journal["large-output"]["content"])["artifact_id"]
    read = {"id": "read-previous", "type": "function", "function": {
        "name": "__nexa_read_artifact", "arguments": json.dumps({"artifact_id": artifact_id, "offset": 0, "limit": 32}),
    }}
    next_provider = ConversationProvider([ModelReply({"role": "assistant", "content": "", "tool_calls": [read]}), answer()])
    current = agent.continue_run(previous, "read the evidence", provider=next_provider)
    assert current.success, current.error
    assert current.tool_journal["read-previous"]["content"] == "evidence" * 4


@pytest.mark.parametrize("status", [RunStatus.RUNNING, RunStatus.WAITING_APPROVAL])
def test_active_run_must_be_resumed_or_cancelled_first(status: RunStatus) -> None:
    provider = ConversationProvider([])
    previous = RunState(status=status)
    with pytest.raises(ValueError, match="Resume or cancel"):
        NexaAgent("conversation").continue_run(previous, "next", provider=provider)
    assert not provider.requests


def test_unknown_tool_outcome_blocks_continuation() -> None:
    provider = ConversationProvider([answer()])
    agent = NexaAgent("conversation")
    previous = agent.execute("first", provider=provider)
    previous.status = RunStatus.FAILED
    previous.tool_journal["uncertain"] = {"status": "started", "name": "change"}
    with pytest.raises(ValueError, match="unknown outcome"):
        agent.continue_run(previous, "next", provider=provider)
    assert len(provider.requests) == 1


@pytest.mark.parametrize("status", [RunStatus.CANCELLED, RunStatus.TIMED_OUT, RunStatus.FAILED])
def test_settled_stops_receive_new_deadline(status: RunStatus) -> None:
    agent = NexaAgent("conversation")
    provider = ConversationProvider([answer(), answer()])
    previous = agent.execute("first", provider=provider)
    previous.status, previous.error = status, "old stop"
    previous.created_at -= 1000
    previous.elapsed = 1000
    current = agent.continue_run(previous, "next", provider=provider)
    assert current.success and current.error is None and current.elapsed < 10


@pytest.mark.parametrize("messages", [
    [{"role": "tool", "tool_call_id": "orphan", "content": "unknown"}],
    [{"role": "assistant", "content": "", "tool_calls": [tool_call("missing")]}, {"role": "user", "content": "later"}],
    [{"role": "assistant", "content": "", "tool_calls": [tool_call("missing")]}],
])
def test_incomplete_or_orphaned_history_is_rejected(messages: list[dict[str, Any]]) -> None:
    agent = NexaAgent("conversation")
    provider = ConversationProvider([answer()])
    previous = agent.execute("first", provider=provider)
    previous.messages.extend(messages)
    with pytest.raises(ValueError, match="history"):
        agent.continue_run(previous, "next", provider=provider)
    assert len(provider.requests) == 1


def test_blank_turn_and_changed_workspace_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    agent = NexaAgent("conversation")
    provider = ConversationProvider([answer()])
    previous = agent.execute("first", provider=provider)
    with pytest.raises(ValueError, match="input"):
        agent.continue_run(previous, "  ", provider=provider)
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    with pytest.raises(ValueError, match="working directory"):
        agent.continue_run(previous, "next", provider=provider)
    assert len(provider.requests) == 1


def test_definition_and_model_changes_cannot_silently_join_session() -> None:
    agent = NexaAgent("conversation")
    provider = ConversationProvider([answer()])
    previous = agent.execute("first", provider=provider)
    agent.system_prompt = "different"
    changed = agent.continue_run(previous, "next", provider=provider)
    assert changed.status == RunStatus.FAILED
    agent.model = "other"
    with pytest.raises(ValueError, match="different agent, model, or provider"):
        agent.continue_run(previous, "next", provider=provider)
    assert len(provider.requests) == 1


def test_compiled_nexa_can_continue_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ConversationProvider([answer("first answer"), answer("next answer")])
    monkeypatch.setattr(NexaAgent, "_provider_adapter", lambda self: provider)
    result = nexa_sdk.run('''
agent Echo { prompt: "Echo the supplied input." }
flow main {
    first = Echo.execute("first");
    result = Echo.continue_run(first, "next");
}
''')
    assert result.success, result.stderr
    assert result.result.success and result.result.output == "next answer"
    assert [message["content"] for message in provider.requests[-1].messages if message["role"] == "user"] == ["first", "next"]
