"""Admission must use current observations and respect explicit author intent."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.open_programs.compiler import OpenCompiler
from src.open_programs.controller import RuntimeController, validate_artifact
from src.open_programs.model import (
    Candidate,
    CheckCase,
    CommandReport,
    CompilerEnvironment,
    EventHandler,
    ExecutionReport,
    ExecutionSpec,
    GoalSpec,
    Implementation,
    OutputCheck,
    Parameter,
    PatchValue,
    ProgramError,
    ProgramIR,
    ProgramRevision,
    RepositoryCase,
    WorkspaceSnapshot,
)
from src.open_programs.operations import ProgramSession
from src.open_programs.reuse import CapsuleOrigin, export_capsule, match_capsule
from src.open_programs.store import ProgramStore
from src.runtime.providers import ModelReply, ModelRequest

IMAGE = "python@sha256:" + "a" * 64


class ValueExecutor:
    def execute_candidate(self, candidate: Candidate, spec: ExecutionSpec) -> ExecutionReport:
        return ExecutionReport(succeeded=True, output_json=candidate.implementation.body, exit_code=0)

    def execute_repository(self, base: WorkspaceSnapshot, patch: PatchValue, case: RepositoryCase, spec: ExecutionSpec) -> CommandReport:
        raise AssertionError("Repository execution is outside this fixture")


def compiler_fixture(tmp_path: Path) -> tuple[OpenCompiler, ProgramIR]:
    environment = CompilerEnvironment(image=IMAGE, checks=(OutputCheck(name="answer", cases=(CheckCase(expected_json="42"),)),))
    compiler = OpenCompiler(environment, ProgramStore(tmp_path / "state.db"), executor=ValueExecutor())
    goal = GoalSpec(name="answer", return_type="Int", intent="Answer", checks=("answer",), implementation=Implementation(kind="value", body="42"))
    return compiler, ProgramIR(name="Test", goals=(goal,))


def test_new_failure_invalidates_old_lock_and_runtime_admission(tmp_path: Path) -> None:
    compiler, program = compiler_fixture(tmp_path)
    lock = tmp_path / "program.lock"
    artifact = compiler.build(program, lock_path=lock)
    result = artifact.results[0]
    assert result.context is not None
    failed = result.evidence[-1].model_copy(update={"passed": False, "issued_at": time.time()})
    compiler.store.put(failed)
    compiler.store = ProgramStore(compiler.store.path)
    with pytest.raises(ProgramError, match="evidence_stale"):
        compiler.build(program, lock_path=lock, locked=True)
    revision = ProgramRevision(program_id="test", program=program, environment_digest=compiler.environment.digest)
    with pytest.raises(ProgramError, match="evidence_stale"):
        validate_artifact(compiler, revision, artifact)
    rechecked = compiler.resolve_goal(program.goals[0], candidate=result.candidate, reusable_evidence=result.evidence,
                                      input_json='{"dependencies":{}}', task_id=result.context.task_id)
    assert rechecked.status == "accepted"
    assert rechecked.evidence[-1].issued_at > failed.issued_at


@pytest.mark.parametrize(("environment_caps", "goal_caps"), [((), ()), ((), ("repo.read",)), (("repo.read",), ())])
def test_maintenance_checks_read_capability_before_snapshot_or_model(tmp_path: Path, monkeypatch, environment_caps, goal_caps) -> None:
    from src.open_programs import operations

    calls = []

    class Provider:
        name = "fixture"

        def complete(self, request: ModelRequest, on_text=None) -> ModelReply:
            calls.append("model")
            return ModelReply({"role": "assistant", "content": '{"clarification":"Which change?"}'}, usage_reported=True)

    snapshot = operations.snapshot_workspace

    def observed_snapshot(root: Path, paths: list[str]):
        calls.append("snapshot")
        return snapshot(root, paths)

    monkeypatch.setattr(operations, "snapshot_workspace", observed_snapshot)
    environment = CompilerEnvironment(image=IMAGE, allow_model=True, model="fixture", capabilities=environment_caps)
    compiler = OpenCompiler(environment, ProgramStore(tmp_path / "state.db"), executor=ValueExecutor(), provider=Provider())
    goal = GoalSpec(name="repair", parameters=(Parameter(name="change", type="ChangeRequest"),), stage="runtime", return_type="Patch",
                    intent="Repair", capabilities=goal_caps)
    program = ProgramIR(name="Maintenance", goals=(goal,), handlers=(EventHandler(event="change_request", parameter="request", goal="repair", result="patch", repository="repo"),))
    revision = ProgramRevision(program_id="test", program=program, environment_digest=environment.digest)
    compiler.store.commit_revision(None, revision, [])
    runtime = RuntimeController(compiler)
    runtime.activate_revision(runtime.propose_revision(None, revision, compiler.build(program, lock_path=tmp_path / "lock")), None)
    (tmp_path / "private.txt").write_text("fixture-private-content")
    with pytest.raises(ProgramError, match="capability_denied"):
        ProgramSession(compiler).maintain("test", tmp_path, ["private.txt"], "Repair")
    assert calls == []


def test_explicit_implementation_is_never_overridden_by_capsule(tmp_path: Path) -> None:
    compiler, program = compiler_fixture(tmp_path)
    goal = program.goals[0]
    result = compiler.resolve_goal(goal)
    assert result.context is not None and result.policy is not None
    capsule = export_capsule(goal, result, CapsuleOrigin(source="fixture", creator="operator", license="MIT"))
    changed = goal.model_copy(update={"implementation": Implementation(kind="value", body="43")})
    decision = match_capsule(capsule, changed, result.context, result.policy)
    assert decision.status == "rejected" and "explicit_implementation_mismatch" in decision.reasons


def test_direct_candidate_cannot_override_explicit_implementation(tmp_path: Path) -> None:
    compiler, program = compiler_fixture(tmp_path)
    goal = program.goals[0]
    supplied = Candidate(goal_digest=goal.digest, implementation=Implementation(kind="value", body="43"))
    with pytest.raises(ProgramError, match="candidate_mismatch"):
        compiler.resolve_goal(goal, candidate=supplied)


def test_other_inputs_do_not_revoke_a_lock_and_old_databases_are_indexed(tmp_path: Path) -> None:
    import sqlite3

    from src.open_programs.model import Dependency

    compiler, program = compiler_fixture(tmp_path)
    lock = tmp_path / "program.lock"
    artifact = compiler.build(program, lock_path=lock)
    result = artifact.results[0]
    record = result.evidence[-1]
    changed = tuple(Dependency(name=item.name, digest="other" if item.name == "input" else item.digest) for item in record.dependencies)
    compiler.store.put(record.model_copy(update={"passed": False, "issued_at": time.time(), "dependencies": changed}))
    assert compiler.build(program, lock_path=lock, locked=True) == artifact
    compiler.store.put(record.model_copy(update={"passed": False, "issued_at": time.time()}))
    with sqlite3.connect(compiler.store.path) as connection:
        connection.execute("DROP TABLE evidence_index")
    compiler.store = ProgramStore(compiler.store.path)
    with pytest.raises(ProgramError, match="evidence_stale"):
        compiler.build(program, lock_path=lock, locked=True)


def test_cli_export_checks_latest_observations(tmp_path: Path) -> None:
    import argparse

    from src.open_programs.commands import _capsule
    from src.open_programs.model import RuntimeActivity

    compiler, program = compiler_fixture(tmp_path)
    result = compiler.resolve_goal(program.goals[0])
    revision = ProgramRevision(program_id="test", program=program, environment_digest=compiler.environment.digest)
    compiler.store.put(revision)
    activity = RuntimeActivity(activity_id="activity", program_id="test", revision=revision.digest, artifact_digest="fixture", goal="answer", state="completed", result=result)
    compiler.store.set_reference("runtime.activity:activity", None, activity)
    compiler.store.put(result.evidence[-1].model_copy(update={"passed": False, "issued_at": time.time()}))
    path = tmp_path / "stale-capsule.json"
    args = argparse.Namespace(capsule_command="export", activity="activity", source="fixture", creator="operator", license="MIT", path=str(path))
    with pytest.raises(ProgramError, match="evidence_stale"):
        _capsule(args, compiler.store)
    assert not path.exists()
