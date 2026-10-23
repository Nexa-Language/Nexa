"""Crash recovery at the actual tool side-effect boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_agent_execution import FakeClient, call, completion

from src.runtime.agent import NexaAgent
from src.runtime.artifacts import ArtifactStore
from src.runtime.checkpoints import CheckpointConflict, SQLiteCheckpointStore
from src.runtime.run_state import RunConfig, RunState, RunStatus


def test_checkpoint_can_be_loaded_in_another_process(tmp_path: Path) -> None:
    store = SQLiteCheckpointStore(tmp_path / "runs.sqlite")
    state = RunState(messages=[{"role": "user", "content": "persist me"}])
    store.save(state)
    code = "from src.runtime.checkpoints import SQLiteCheckpointStore; import sys; print(SQLiteCheckpointStore(sys.argv[1]).load(sys.argv[2]).messages[0]['content'])"
    result = subprocess.run([sys.executable, "-c", code, str(store.path), state.run_id], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "persist me"


def test_stale_executor_cannot_overwrite_checkpoint(tmp_path: Path) -> None:
    store = SQLiteCheckpointStore(tmp_path / "runs.sqlite")
    state = RunState()
    store.save(state)
    stale = store.load(state.run_id)
    store.save(state)
    with pytest.raises(CheckpointConflict):
        store.save(stale)


@pytest.mark.parametrize('window', ['after_effect', 'after_result'])
def test_real_process_crash_and_resume(tmp_path: Path, window: str) -> None:
    script = Path(__file__).parent / 'fixtures/checkpoint_worker.py'
    crashed = subprocess.run([sys.executable, str(script), 'start', window], cwd=tmp_path, capture_output=True, text=True, timeout=20, check=False)
    assert crashed.returncode == 73, crashed.stderr
    assert (tmp_path / 'effects.txt').read_text() == 'written\n'
    resumed = subprocess.run([sys.executable, str(script), 'resume', window], cwd=tmp_path, capture_output=True, text=True, timeout=20, check=True)
    store = SQLiteCheckpointStore(tmp_path / 'runs.sqlite')
    run_id = (tmp_path / 'run-id.txt').read_text()
    state = store.load(run_id)
    if window == 'after_effect':
        assert resumed.stdout.strip() == 'failed'
        assert state.tool_journal['write-1']['status'] == 'started'
        assert state.model_calls == 1
        store.resolve_tool(run_id, 'write-1', 'written', success=True)
        resumed = subprocess.run([sys.executable, str(script), 'resume', window], cwd=tmp_path, capture_output=True, text=True, timeout=20, check=True)
    assert resumed.stdout.strip() == 'completed'
    assert (tmp_path / 'effects.txt').read_text() == 'written\n'
    assert store.load(run_id).model_calls == 2


@pytest.mark.parametrize("interrupt_at", ["tool_started", "tool_completed"])
def test_recovery_never_repeats_uncertain_or_completed_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupt_at: str) -> None:
    store = SQLiteCheckpointStore(tmp_path / "runs.sqlite")
    effects: list[int] = []
    agent = NexaAgent("recover", tools=[{"name": "write", "parameters": {"type": "object"}, "_handler": lambda: effects.append(1) or "written"}])
    monkeypatch.setattr(agent, "client", FakeClient([completion(calls=[call("write")]), completion()]))
    captured: list[str] = []

    def checkpoint(state: RunState) -> None:
        store.save(state)
        captured.append(state.run_id)
        if state.events[-1]["event"] == interrupt_at:
            raise SystemExit("simulated crash")

    with pytest.raises(SystemExit):
        agent.execute("write", save=checkpoint)
    state = store.load(captured[-1])
    result = agent.execute(state=state, save=store.save)
    if interrupt_at == "tool_started":
        assert result.status == RunStatus.FAILED
        assert "unknown outcome" in (result.error or "")
        assert effects == []
        resolved = store.resolve_tool(state.run_id, "call-1", "verified externally", success=True)
        result = agent.execute(state=resolved, save=store.save)
        assert result.success
        assert effects == []
    else:
        assert result.success, result.error
        assert effects == [1]
    assert sum(message.get("tool_call_id") == "call-1" for message in result.messages) == 1


def test_resume_keeps_budget_and_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SQLiteCheckpointStore(tmp_path / "runs.sqlite")
    agent = NexaAgent("approve", tools=[{"name": "write", "parameters": {"type": "object"}, "requires_approval": True, "_handler": lambda: "ok"}])
    monkeypatch.setattr(agent, "client", FakeClient([completion(calls=[call("write")]), completion()]))
    first = agent.execute("hi", config=RunConfig(max_model_calls=1), save=store.save)
    state = store.approve(first.run_id, "call-1", True)
    resumed = agent.execute(state=state, save=store.save)
    assert resumed.status == RunStatus.BUDGET_EXHAUSTED
    assert resumed.tool_calls == 1 and resumed.model_calls == 1


def test_large_tool_output_is_retrievable_without_filling_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content = "你好" * 10000
    agent = NexaAgent("large", tools=[{"name": "large", "parameters": {"type": "object"}, "_handler": lambda: content}])
    client = FakeClient([completion(calls=[call("large")]), completion()])
    monkeypatch.setattr(agent, "client", client)
    state = agent.execute("hi", config=RunConfig(max_tool_output_chars=1000, artifact_directory=str(tmp_path)))
    assert state.success, state.error
    attached = client.requests[-1]["messages"][-1]["content"]
    assert len(attached) <= 1000
    ref = json.loads(attached)
    store = ArtifactStore(tmp_path)
    assert store.read(ref["artifact_id"], 100, 300) == content[100:400]
    with pytest.raises(ValueError):
        store.read("../../secret")
