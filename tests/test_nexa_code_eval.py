"""Nexa Code edits a temporary workspace through real tools and explicit approvals."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import pytest
from test_agent_execution import FakeClient, call, completion

from src.agent_cli import run_declared_agent
from src.runtime.agent import NexaAgent
from src.runtime.checkpoints import SQLiteCheckpointStore
from src.runtime.workspace_tools import read_file, write_file

ROOT = Path(__file__).resolve().parents[1]


def test_nexa_code_fix_and_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task = json.loads((ROOT / "evals/tasks/fix-addition-v1.json").read_text())
    for name, content in task["files"].items():
        (tmp_path / name).write_text(content)
    monkeypatch.chdir(tmp_path)
    client = FakeClient([
        completion(calls=[call("read_file", '{"path":"calculator.py"}', "read")]),
        completion(calls=[call("write_file", json.dumps({"path": "calculator.py", "content": task["expected_file"]}), "write")]),
        completion(calls=[call("shell_exec", json.dumps({"command": f"{sys.executable} check.py"}), "verify")]),
        completion("The implementation is fixed and check.py passed."),
    ])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    source = str(ROOT / "examples/Nexa-Code/main.nx")
    database = str(tmp_path / "runs.sqlite3")
    first = run_declared_agent(source, "CodeAssistant", task["instruction"], checkpoint=database)
    assert first.status.value == "waiting_approval", first.error
    assert (tmp_path / "calculator.py").read_text() == task["files"]["calculator.py"]
    second = run_declared_agent(source, "CodeAssistant", None, checkpoint=database, resume=first.run_id, approve="write")
    assert second.status.value == "waiting_approval", second.error
    assert (tmp_path / "calculator.py").read_text() == task["expected_file"]
    final = run_declared_agent(source, "CodeAssistant", None, checkpoint=database, resume=first.run_id, approve="verify")
    assert final.success, final.error
    assert task["expected_verification"] in final.tool_journal["verify"]["content"]
    assert (final.model_calls, final.tool_calls) == (4, 3)
    assert SQLiteCheckpointStore(database).load(final.run_id).success
    report = {"schema_version": 1, "task_id": task["task_id"], "provider_mode": "deterministic_fixture",
              "python": platform.python_version(), "status": final.status.value, "model": final.model,
              "model_calls": final.model_calls, "tool_calls": final.tool_calls,
              "usage": {"input_tokens": final.input_tokens, "output_tokens": final.output_tokens, "source": "fixture"},
              "elapsed_seconds": final.elapsed, "events": final.events}
    (tmp_path / "eval-report.json").write_text(json.dumps(report, indent=2))


def test_workspace_tools_reject_escape_and_symlinks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("untouched")
    (root / "link").symlink_to(outside)
    monkeypatch.chdir(root)
    with pytest.raises(ValueError, match="inside"):
        read_file("../outside.txt")
    with pytest.raises(ValueError, match="inside"):
        write_file("link", "changed")
    assert outside.read_text() == "untouched"
