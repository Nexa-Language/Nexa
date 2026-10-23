"""Reuse preserves provenance and recomputes validity in the receiving task."""
from __future__ import annotations

import time
from pathlib import Path

import pytest


def capsule():
    from src.open_programs.model import (
        AcceptancePolicy,
        Candidate,
        ContextSnapshot,
        Dependency,
        EvidenceRecord,
        GoalSpec,
        Implementation,
        Requirement,
        ResolutionResult,
    )
    from src.open_programs.reuse import CapsuleOrigin, export_capsule

    goal = GoalSpec(name="answer", return_type="Int", intent="Return 42")
    candidate = Candidate(goal_digest=goal.digest, implementation=Implementation(kind="value", body="42"), dependencies=(Dependency(name="library", digest="v1"),))
    policy = AcceptancePolicy(name="fixture", requirements=(Requirement(name="check", kind="deterministic", checker_digest="checker"),
                                                          Requirement(name="review", kind="model_review", checker_digest="rule")))
    context = ContextSnapshot(subject_digest=candidate.digest, policy_digest=policy.digest, task_id="first", now=time.time(), dependencies=(Dependency(name="input", digest="one"), Dependency(name="library", digest="v1")))
    evidence = tuple(EvidenceRecord(requirement=r.name, kind=r.kind, checker_digest=r.checker_digest, subject_digest=candidate.digest, policy_digest=policy.digest,
                                   dependencies=context.dependencies, task_id="first", issued_at=context.now, passed=True, model_pinned=False) for r in policy.requirements)
    result = ResolutionResult(goal_name=goal.name, status="accepted", candidate=candidate, policy=policy, context=context, evidence=evidence, output_json="42")
    return export_capsule(goal, result, CapsuleOrigin(source="fixture-repository", creator="operator", license="MIT")), goal, context, policy


def test_matching_capsule_reuses_only_current_transferable_evidence() -> None:
    from src.open_programs.reuse import match_capsule

    value, goal, context, policy = capsule()
    decision = match_capsule(value, goal, context.model_copy(update={"task_id": "second"}), policy)
    assert decision.status == "needs_verification"
    assert decision.candidate == value.candidate
    assert [record.kind for record in decision.reusable_evidence] == ["deterministic"]
    assert decision.obligations == ("model_review:review",)
    assert value.origin.source == "fixture-repository"


def test_changed_inputs_require_revalidation_and_dependency_drift_rejects() -> None:
    from src.open_programs.model import Dependency
    from src.open_programs.reuse import match_capsule

    value, goal, context, policy = capsule()
    changed = context.model_copy(update={"dependencies": (Dependency(name="input", digest="two"), Dependency(name="library", digest="v1"))})
    decision = match_capsule(value, goal, changed, policy)
    assert decision.status == "needs_verification" and not decision.reusable_evidence
    changed = context.model_copy(update={"dependencies": (Dependency(name="input", digest="one"), Dependency(name="library", digest="v2"))})
    assert match_capsule(value, goal, changed, policy).reasons == ("dependency_changed:library",)


def test_unknown_conditions_type_and_capability_mismatches_are_explicit() -> None:
    from src.open_programs.model import Dependency
    from src.open_programs.reuse import match_capsule

    value, goal, context, policy = capsule()
    assert match_capsule(value, goal.model_copy(update={"return_type": "String"}), context, policy).status == "rejected"
    candidate = value.candidate.model_copy(update={"capabilities": ("sandbox.exec",)})
    assert "capability_denied" in match_capsule(value.model_copy(update={"candidate": candidate}), goal, context, policy).reasons
    unknown = value.model_copy(update={"conditions": (*value.conditions, Dependency(name="platform", digest="linux"))})
    decision = match_capsule(unknown, goal, context, policy)
    assert decision.status == "rejected" and decision.reasons == ("condition_unknown:platform",)


def test_local_capsules_validate_digest_and_provenance(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError
    from src.open_programs.reuse import read_capsule, write_capsule

    value, _, _, _ = capsule()
    path = tmp_path / "answer.capsule.json"
    write_capsule(value, path)
    assert read_capsule(path) == value
    path.write_text(path.read_text().replace('"MIT"', '"Modified"'))
    with pytest.raises(ProgramError, match="capsule_corrupt"):
        read_capsule(path)
