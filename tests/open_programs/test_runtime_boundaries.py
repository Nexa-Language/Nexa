"""Public input contracts and command budgets remain in force across stages."""
from __future__ import annotations

import argparse
import json
from contextlib import nullcontext
from pathlib import Path

import pytest
from test_compilation import IMAGE, setup
from test_reuse import capsule

from src.open_programs.commands import add_run_arguments, run_file
from src.open_programs.model import Parameter, ProgramError


def test_typed_goal_rejects_missing_or_wrong_inputs_before_sampling(tmp_path: Path) -> None:
    compiler, provider, program = setup(tmp_path, [])
    goal = program.goals[0].model_copy(update={"parameters": (Parameter(name="count", type="Int"),)})
    for payload in ('{}', '{"count":true}', '{"count":"1"}'):
        with pytest.raises(ProgramError, match="input_type"):
            compiler.resolve_goal(goal, input_json=payload)
    assert provider.requests == []


def test_capsule_cannot_drop_its_implementation_dependencies() -> None:
    from src.open_programs.model import Dependency
    from src.open_programs.reuse import match_capsule

    value, goal, context, policy = capsule()
    stripped = value.model_copy(update={"conditions": ()})
    changed = context.model_copy(update={"dependencies": (Dependency(name="library", digest="v2"),)})
    assert match_capsule(stripped, goal, changed, policy).status == "rejected"


def test_run_command_shares_model_budget_across_build_and_runtime(tmp_path: Path, monkeypatch, capsys) -> None:
    from test_compilation import ScriptedProvider

    source = tmp_path / "budget.nx"
    source.write_text('language "3.0" program Budget { goal seed() -> Int { intent "Return 1" } goal later() -> Int { stage runtime intent "Return 2" } }')
    env = tmp_path / "environment.json"
    env.write_text(json.dumps({"image": IMAGE, "model": "fixture", "allow_model": True}))
    provider = ScriptedProvider([{"implementation": {"kind": "value", "body": "1"}}, {"implementation": {"kind": "value", "body": "2"}}])
    monkeypatch.setattr("src.open_programs.commands.model_provider", lambda _: nullcontext(provider))
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    add_run_arguments(parser)
    args = parser.parse_args([str(source), "--environment", str(env), "--state", str(tmp_path / "state.db"), "--goal", "later", "--max-model-calls", "1"])
    assert run_file(args) == 1
    assert len(provider.requests) == 1
    assert json.loads(capsys.readouterr().out)["result"]["reason"] == "model_call_budget"
