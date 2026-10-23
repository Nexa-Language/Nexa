"""Acceptance is contextual: stale, missing and superseded results fail closed."""

from __future__ import annotations

import pytest


def fixture():
    from src.open_programs.model import AcceptancePolicy, ContextSnapshot, Dependency, EvidenceRecord, Requirement

    policy = AcceptancePolicy(name="release", requirements=(Requirement(name="regression", kind="deterministic", checker_digest="checker-v1", dependencies=("source", "environment")),))
    dependencies = (Dependency(name="source", digest="tree-a"), Dependency(name="environment", digest="image-a"))
    context = ContextSnapshot(subject_digest="candidate-a", policy_digest=policy.digest, dependencies=dependencies, now=100, task_id="task-a")
    record = EvidenceRecord(requirement="regression", kind="deterministic", subject_digest="candidate-a", policy_digest=policy.digest,
                            checker_digest="checker-v1", dependencies=dependencies, passed=True, issued_at=90, task_id="task-a")
    return policy, context, record


def test_acceptance_requires_exact_subject_policy_and_all_dependencies() -> None:
    from src.open_programs.evidence import evaluate_policy

    policy, context, record = fixture()
    assert evaluate_policy(policy, [record], context).accepted
    for update in ({"subject_digest": "candidate-b"}, {"policy_digest": "changed"}, {"dependencies": ()}, {"checker_digest": "checker-v2"}):
        decision = evaluate_policy(policy, [record.model_copy(update=update)], context)
        assert not decision.accepted
        assert decision.reasons
    assert not evaluate_policy(policy, [], context).accepted


@pytest.mark.parametrize("field", ["source", "environment"])
def test_changed_dependencies_invalidate_prior_success(field: str) -> None:
    from src.open_programs.evidence import evaluate_policy, validate_evidence
    from src.open_programs.model import Dependency

    policy, context, record = fixture()
    changed = tuple(Dependency(name=item.name, digest="changed" if item.name == field else item.digest) for item in context.dependencies)
    context = context.model_copy(update={"dependencies": changed})
    assert validate_evidence(record, context).validity == "stale"
    assert not evaluate_policy(policy, [record], context).accepted


def test_unrelated_dependency_preserves_evidence_and_failure_supersedes_success() -> None:
    from src.open_programs.evidence import evaluate_policy
    from src.open_programs.model import Dependency

    policy, context, record = fixture()
    context = context.model_copy(update={"dependencies": (*context.dependencies, Dependency(name="unrelated", digest="new"))})
    assert evaluate_policy(policy, [record], context).accepted
    failed = record.model_copy(update={"passed": False, "issued_at": 95})
    assert not evaluate_policy(policy, [failed, record], context).accepted


def test_expiry_revocation_and_mutable_model_reviews() -> None:
    from src.open_programs.evidence import validate_evidence

    _, context, record = fixture()
    assert validate_evidence(record.model_copy(update={"expires_at": 100}), context).validity == "stale"
    assert validate_evidence(record, context.model_copy(update={"revoked": (record.digest,)})).validity == "revoked"
    review = record.model_copy(update={"kind": "model_review", "model_pinned": False, "task_id": "old-task"})
    assert validate_evidence(review, context).validity == "stale"


def test_invalidation_explains_transitive_dependency_path() -> None:
    from src.open_programs.evidence import invalidation_paths

    graph: dict[str, tuple[str, ...]] = {"environment": ("lockfile",), "regression": ("environment",), "repair": ("regression",), "unrelated": ()}
    assert invalidation_paths(graph, {"lockfile"}) == {
        "environment": ("lockfile", "environment"),
        "regression": ("lockfile", "environment", "regression"),
        "repair": ("lockfile", "environment", "regression", "repair"),
    }
