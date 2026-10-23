"""The model may propose code; only frozen checks admit it into a build."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.runtime.providers import ModelReply, ModelRequest

IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


class ScriptedProvider:
    name = "scripted"

    def __init__(self, replies: list[dict[str, object]]) -> None:
        self.replies = list(replies)
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest, on_text=None) -> ModelReply:
        self.requests.append(request)
        return ModelReply({"role": "assistant", "content": json.dumps(self.replies.pop(0))}, input_tokens=10, output_tokens=20, usage_reported=True)


def setup(tmp_path: Path, replies: list[dict[str, object]]):
    from src.open_programs.compiler import OpenCompiler
    from src.open_programs.executor import OCIExecutor
    from src.open_programs.model import CheckCase, CompilerEnvironment, GoalSpec, OutputCheck, ProgramIR
    from src.open_programs.store import ProgramStore

    environment = CompilerEnvironment(image=IMAGE, model="test-model", allow_model=True, model_pinned=True,
                                      checks=(OutputCheck(name="checks.answer", cases=(CheckCase(expected_json="42"),)),))
    provider = ScriptedProvider(replies)
    compiler = OpenCompiler(environment, ProgramStore(tmp_path / "program.sqlite3"), executor=OCIExecutor(), provider=provider)
    program = ProgramIR(name="Answer", goals=(GoalSpec(name="answer", return_type="Int", intent="Return 42", checks=("checks.answer",)),))
    return compiler, provider, program


def test_build_solves_checks_and_replays_without_model(tmp_path: Path) -> None:
    compiler, provider, program = setup(tmp_path, [{"implementation": {"kind": "value", "body": "41"}}, {"implementation": {"kind": "value", "body": "42"}}])
    lock = tmp_path / "nexa.lock"
    artifact = compiler.build(program, lock_path=lock)
    assert artifact.results[0].output_json == "42"
    assert len(provider.requests) == 2
    provider.replies.clear()
    replay = compiler.build(program, lock_path=lock, locked=True)
    assert replay.digest == artifact.digest
    assert len(provider.requests) == 2
    assert len(artifact.results[0].evidence) == 2


def test_changed_inputs_or_lock_tampering_fail_locked_build(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError

    compiler, _, program = setup(tmp_path, [{"implementation": {"kind": "value", "body": "42"}}])
    lock = tmp_path / "nexa.lock"
    compiler.build(program, lock_path=lock)
    changed = program.model_copy(update={"name": "Changed"})
    with pytest.raises(ProgramError, match="lock_mismatch"):
        compiler.build(changed, lock_path=lock, locked=True)
    data = json.loads(lock.read_text())
    data["artifact_digest"] = "bad"
    lock.write_text(json.dumps(data))
    with pytest.raises(ProgramError, match="object_missing"):
        compiler.build(program, lock_path=lock, locked=True)


def test_model_clarification_and_call_budget_are_explicit(tmp_path: Path) -> None:
    from src.open_programs.model import ResolutionBudget

    compiler, provider, program = setup(tmp_path, [{"clarification": "Which integer?"}])
    result = compiler.resolve_goal(program.goals[0], budget=ResolutionBudget(max_model_calls=1))
    assert result.status == "blocked" and result.reason == "clarification_required"
    assert result.clarification == "Which integer?"
    compiler, provider, program = setup(tmp_path / "second", [{"implementation": {"kind": "value", "body": "41"}}])
    result = compiler.resolve_goal(program.goals[0], budget=ResolutionBudget(max_model_calls=1))
    assert result.status == "blocked" and result.reason == "model_call_budget"
    assert len(provider.requests) == 1


def test_missing_checker_fails_before_model_request(tmp_path: Path) -> None:
    from src.open_programs.model import GoalSpec, ProgramError

    compiler, provider, _ = setup(tmp_path, [])
    with pytest.raises(ProgramError, match="checker_missing"):
        compiler.resolve_goal(GoalSpec(name="missing", return_type="Int", intent="Test", checks=("checks.missing",)))
    assert not provider.requests


def test_model_review_is_separate_evidence(tmp_path: Path) -> None:
    compiler, _, program = setup(tmp_path, [{"implementation": {"kind": "value", "body": "42"}}, {"passed": True, "detail": "Compatible"}])
    goal = program.goals[0].model_copy(update={"reviews": ("compatibility",)})
    result = compiler.resolve_goal(goal)
    assert result.status == "accepted"
    assert [record.kind for record in result.evidence] == ["deterministic", "deterministic", "model_review"]


def test_build_dependencies_supply_values_and_share_model_budget(tmp_path: Path) -> None:
    from src.open_programs.model import GoalSpec, Implementation, ProgramError, ProgramIR, ResolutionBudget

    compiler, provider, program = setup(tmp_path, [{"implementation": {"kind": "value", "body": "42"}}])
    first = program.goals[0]
    second = GoalSpec(name="next", return_type="Int", intent="Use dependency", depends_on=("answer",), capabilities=("sandbox.exec",),
                      implementation=Implementation(kind="python", body='def solve(inputs):\n return inputs["dependencies"]["answer"] + 1'))
    artifact = compiler.build(ProgramIR(name="Chain", goals=(second, first)), lock_path=tmp_path / "chain.lock")
    assert artifact.results[1].output_json == "43"
    provider.replies = [{"implementation": {"kind": "value", "body": "42"}}]
    third = GoalSpec(name="third", return_type="Int", intent="Return 1")
    with pytest.raises(ProgramError, match="model_call_budget"):
        compiler.build(ProgramIR(name="Budget", goals=(first, third)), lock_path=tmp_path / "budget.lock", budget=ResolutionBudget(max_model_calls=1))


def test_review_requests_typed_boolean_schema(tmp_path: Path) -> None:
    compiler, provider, program = setup(tmp_path, [{"implementation": {"kind": "value", "body": "42"}}, {"passed": True, "detail": "Matches"}])
    result = compiler.resolve_goal(program.goals[0].model_copy(update={"reviews": ("compatibility",)}))
    assert result.status == "accepted"
    schema = provider.requests[-1].response_format
    assert schema["type"] == "json_schema"
    assert schema["json_schema"]["schema"]["properties"]["passed"]["type"] == "boolean"


def test_proposal_requests_implementation_or_clarification_schema(tmp_path: Path) -> None:
    compiler, provider, program = setup(tmp_path, [{"clarification": "Which integer?"}])
    assert compiler.resolve_goal(program.goals[0]).status == "blocked"
    schema = provider.requests[0].response_format
    assert schema["type"] == "json_schema"
    assert set(schema["json_schema"]["schema"]["required"]) == {"implementation", "clarification"}


def test_reused_candidate_skips_generation_but_rechecks_changed_inputs(tmp_path: Path) -> None:
    from src.open_programs.model import ResolutionBudget

    compiler, provider, program = setup(tmp_path, [{"implementation": {"kind": "value", "body": "42"}}])
    first = compiler.resolve_goal(program.goals[0], task_id="first")
    assert first.status == "accepted"
    provider.replies.clear()
    second = compiler.resolve_goal(program.goals[0], candidate=first.candidate, reusable_evidence=first.evidence,
                                   input_json='{"different":true}', task_id="second", budget=ResolutionBudget(max_model_calls=0))
    assert second.status == "accepted" and second.model_calls == 0
    assert all(record.task_id == "second" for record in second.evidence)
    assert len(provider.requests) == 1


def test_runtime_imported_capsule_uses_normal_acceptance_without_generation(tmp_path: Path) -> None:
    from src.open_programs.controller import RuntimeController
    from src.open_programs.model import ProgramIR, ProgramRevision, ResolutionBudget
    from src.open_programs.reuse import CapsuleOrigin, export_capsule

    compiler, provider, original = setup(tmp_path, [{"implementation": {"kind": "value", "body": "42"}}])
    goal = original.goals[0].model_copy(update={"stage": "runtime"})
    result = compiler.resolve_goal(goal)
    capsule = export_capsule(goal, result, CapsuleOrigin(source="local-fixture", creator="operator", license="MIT"))
    compiler.store.put(capsule)
    program = ProgramIR(name="Reuse", goals=(goal,))
    revision = ProgramRevision(program_id="reuse", program=program, environment_digest=compiler.environment.digest)
    compiler.store.commit_revision(None, revision, [])
    artifact = compiler.build(program, lock_path=tmp_path / "reuse.lock")
    controller = RuntimeController(compiler)
    controller.activate_revision(controller.propose_revision(None, revision, artifact), None)
    activity = controller.start_activity("reuse", goal.name, capsule_digest=capsule.digest)
    reused = controller.resolve_activity(activity.activity_id, budget=ResolutionBudget(max_model_calls=0))
    assert reused.status == "accepted" and reused.model_calls == 0
    assert len(provider.requests) == 1


def test_rejected_review_returns_actionable_feedback_and_keeps_failure_evidence(tmp_path: Path) -> None:
    compiler, provider, program = setup(tmp_path, [
        {"implementation": {"kind": "python", "body": "def solve(inputs):\n return 42"}}, {"passed": False, "detail": "Provide a reusable Python solve function instead of a constant."},
        {"implementation": {"kind": "python", "body": "def solve(inputs):\n return 42"}}, {"passed": True, "detail": "Fixed"}])
    goal = program.goals[0].model_copy(update={"capabilities": ("sandbox.exec",), "reviews": ("reusability",)})
    result = compiler.resolve_goal(goal)
    assert result.status == "accepted"
    feedback = provider.requests[2].messages[0]["content"]
    assert "reusable Python solve function" in feedback and "previous_implementation" in feedback
    from src.open_programs.model import ResolutionBudget
    provider.replies = [{"implementation": {"kind": "python", "body": "def solve(inputs):\n return 41"}}]
    failure = compiler.resolve_goal(goal, budget=ResolutionBudget(max_model_calls=1))
    assert failure.status == "blocked" and failure.candidate is not None
    assert failure.evidence and any(not record.passed for record in failure.evidence)


def test_generation_schema_selects_an_executable_implementation_when_authorized(tmp_path: Path) -> None:
    compiler, provider, program = setup(tmp_path, [{"clarification": "Need an input"}])
    goal = program.goals[0].model_copy(update={"capabilities": ("sandbox.exec",)})
    compiler.resolve_goal(goal)
    schema = provider.requests[0].response_format["json_schema"]["schema"]
    assert schema["properties"]["implementation"]["anyOf"][0]["properties"]["kind"]["enum"] == ["python"]


def test_review_receives_the_current_change_input(tmp_path: Path) -> None:
    compiler, provider, program = setup(tmp_path, [{"implementation": {"kind": "value", "body": "42"}}, {"passed": True, "detail": "Current request checked"}])
    goal = program.goals[0].model_copy(update={"reviews": ("Honor this request",)})
    result = compiler.resolve_goal(goal, input_json='{"change":{"description":"Revalidate the existing answer"}}')
    assert result.status == "accepted"
    prompt = json.loads(provider.requests[-1].messages[0]["content"].split("\n", 1)[1])
    assert prompt["inputs"]["change"]["description"] == "Revalidate the existing answer"
