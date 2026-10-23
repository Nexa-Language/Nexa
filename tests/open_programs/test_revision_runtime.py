"""Runtime activation uses evidence and a checkpoint without rewriting old activities."""
from __future__ import annotations

from pathlib import Path

import pytest

IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


def runtime(tmp_path: Path):
    from src.open_programs.compiler import OpenCompiler
    from src.open_programs.controller import RuntimeController
    from src.open_programs.executor import OCIExecutor
    from src.open_programs.model import CompilerEnvironment
    from src.open_programs.store import ProgramStore

    compiler = OpenCompiler(CompilerEnvironment(image=IMAGE), ProgramStore(tmp_path / "state.db"), executor=OCIExecutor())
    return RuntimeController(compiler), compiler


def revision(compiler, value: int, parent: str | None = None):
    from src.open_programs.model import GoalSpec, Implementation, ProgramIR, ProgramRevision

    goal = GoalSpec(name="answer", stage="runtime", return_type="Int", intent=f"Return {value}", implementation=Implementation(kind="value", body=str(value)))
    program = ProgramIR(name="Demo", goals=(goal,))
    rev = ProgramRevision(program_id="demo", parent=parent, program=program, environment_digest=compiler.environment.digest)
    compiler.store.commit_revision(parent, rev, [])
    return rev, compiler.build(program, lock_path=compiler.store.path.with_suffix(".lock"))


def test_revision_switch_keeps_inflight_revision_and_detects_competing_writer(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError

    controller, compiler = runtime(tmp_path)
    first, artifact = revision(compiler, 1)
    controller.activate_revision(controller.propose_revision(None, first, artifact), None)
    activity = controller.start_activity("demo", "answer")
    checkpoint = controller.checkpoint("demo")
    second, artifact = revision(compiler, 2, first.digest)
    proposal = controller.propose_revision(first.digest, second, artifact)
    assert proposal.invalidated == (("answer",),)
    controller.activate_revision(proposal, checkpoint)
    assert controller.activity(activity.activity_id).revision == first.digest
    assert controller.start_activity("demo", "answer").revision == second.digest
    result = controller.resolve_activity(activity.activity_id)
    assert result.output_json == "1"
    assert controller.status("demo").revision == second.digest
    with pytest.raises(ProgramError, match="checkpoint_conflict"):
        controller.activate_revision(proposal, checkpoint)


def test_source_edits_do_not_activate_unvalidated_artifacts(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError

    controller, compiler = runtime(tmp_path)
    first, artifact = revision(compiler, 1)
    controller.activate_revision(controller.propose_revision(None, first, artifact), None)
    second, _ = revision(compiler, 2, first.digest)
    with pytest.raises(ProgramError, match="artifact_mismatch"):
        controller.propose_revision(first.digest, second, artifact)
    assert controller.status("demo").revision == first.digest


def test_state_migration_is_sandboxed_and_failed_migration_preserves_head(tmp_path: Path) -> None:
    from src.open_programs.model import Candidate, Implementation, ProgramError

    controller, compiler = runtime(tmp_path)
    first, artifact = revision(compiler, 1)
    controller.activate_revision(controller.propose_revision(None, first, artifact), None)
    checkpoint = controller.checkpoint("demo")
    second, artifact = revision(compiler, 2, first.digest)
    proposal = controller.propose_revision(first.digest, second, artifact)
    invalid = Candidate(goal_digest="migration", implementation=Implementation(kind="value", body='"bad"'))
    with pytest.raises(ProgramError, match="migration_invalid"):
        controller.activate_revision(proposal, checkpoint, migration=invalid, state_schema_json='{"type":"object"}')
    assert controller.status("demo").revision == first.digest
    migration = Candidate(goal_digest="migration", capabilities=("sandbox.exec",), implementation=Implementation(kind="python", body='def solve(inputs):\n return {"count": inputs["state"].get("count", 0) + 1}'))
    head = controller.activate_revision(proposal, checkpoint, migration=migration, state_schema_json='{"type":"object","required":["count"]}')
    assert head.state_json == '{"count":1}'


def test_runtime_goal_consumes_pinned_build_and_runtime_dependencies(tmp_path: Path) -> None:
    from src.open_programs.model import GoalSpec, Implementation, ProgramIR, ProgramRevision

    controller, compiler = runtime(tmp_path)
    first = GoalSpec(name="base", return_type="Int", intent="Seed", implementation=Implementation(kind="value", body="40"))
    second = GoalSpec(name="next", return_type="Int", stage="runtime", intent="Next", depends_on=("base",), capabilities=("sandbox.exec",),
                      implementation=Implementation(kind="python", body='def solve(inputs):\n return inputs["dependencies"]["base"] + 1'))
    third = second.model_copy(update={"name": "last", "depends_on": ("next",), "implementation": Implementation(kind="python", body='def solve(inputs):\n return inputs["dependencies"]["next"] + 1')})
    program = ProgramIR(name="Chain", goals=(first, second, third))
    rev = ProgramRevision(program_id="demo", program=program, environment_digest=compiler.environment.digest)
    compiler.store.commit_revision(None, rev, [])
    artifact = compiler.build(program, lock_path=tmp_path / "chain.lock")
    controller.activate_revision(controller.propose_revision(None, rev, artifact), None)
    activity = controller.start_activity("demo", "last")
    assert controller.resolve_activity(activity.activity_id).output_json == "42"
