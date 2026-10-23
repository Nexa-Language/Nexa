"""Explicit local implementation capsules with contextual evidence reuse."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from .evidence import evaluate_policy, evaluate_requirement
from .model import (
    AcceptancePolicy,
    Candidate,
    ContextSnapshot,
    Dependency,
    EvidenceRecord,
    FrozenModel,
    GoalSpec,
    ProgramError,
    ResolutionResult,
    canonical_json,
    content_digest,
)


class CapsuleOrigin(FrozenModel):
    source: str = Field(min_length=1)
    creator: str = Field(min_length=1)
    license: str = Field(min_length=1)


class ImplementationCapsule(FrozenModel):
    schema_version: Literal[1] = 1
    language_version: Literal["3.0"] = "3.0"
    goal: GoalSpec
    candidate: Candidate
    conditions: tuple[Dependency, ...]
    origin: CapsuleOrigin
    evidence: tuple[EvidenceRecord, ...]
    policy: AcceptancePolicy


class ReuseDecision(FrozenModel):
    status: Literal["matched", "needs_verification", "rejected"]
    capsule_digest: str
    candidate: Candidate | None = None
    reusable_evidence: tuple[EvidenceRecord, ...] = ()
    obligations: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


def _contract(goal: GoalSpec) -> str:
    return content_digest(goal.model_dump(mode="json", exclude={"name", "span", "implementation"}))


def export_capsule(goal: GoalSpec, result: ResolutionResult, origin: CapsuleOrigin) -> ImplementationCapsule:
    if result.status != "accepted" or result.candidate is None or result.context is None or result.policy is None:
        raise ProgramError("capsule_unaccepted", "Export requires an accepted candidate and its evidence")
    context = result.context.model_copy(update={"now": time.time()})
    if result.candidate.goal_digest != goal.digest or not evaluate_policy(result.policy, list(result.evidence), context).accepted:
        raise ProgramError("evidence_stale", "Refresh evidence before exporting")
    return ImplementationCapsule(goal=goal, candidate=result.candidate, conditions=result.candidate.dependencies,
                                 origin=origin, evidence=result.evidence, policy=result.policy)


def match_capsule(capsule: ImplementationCapsule, goal: GoalSpec, context: ContextSnapshot, policy: AcceptancePolicy) -> ReuseDecision:
    reasons = []
    if _contract(capsule.goal) != _contract(goal):
        reasons.append("goal_contract_mismatch")
    if goal.implementation is not None and capsule.candidate.implementation != goal.implementation:
        reasons.append("explicit_implementation_mismatch")
    if not set(capsule.candidate.capabilities) <= set(goal.capabilities):
        reasons.append("capability_denied")
    if capsule.candidate.goal_digest != capsule.goal.digest:
        reasons.append("candidate_provenance_mismatch")
    conditions = {dependency.name: dependency.digest for dependency in capsule.conditions}
    if len(conditions) != len(capsule.conditions) or any(conditions.get(item.name) != item.digest for item in capsule.candidate.dependencies):
        reasons.append("candidate_conditions_mismatch")
    available = {dependency.name: dependency.digest for dependency in context.dependencies}
    for dependency in capsule.conditions:
        if dependency.name not in available:
            reasons.append("condition_unknown:" + dependency.name)
        elif available[dependency.name] != dependency.digest:
            reasons.append("dependency_changed:" + dependency.name)
    if reasons:
        return ReuseDecision(status="rejected", capsule_digest=capsule.digest, reasons=tuple(reasons),
                             obligations=tuple(reason for reason in reasons if reason.startswith("condition_unknown:")))
    candidate = capsule.candidate.model_copy(update={"goal_digest": goal.digest})
    current = context.model_copy(update={"subject_digest": candidate.digest, "policy_digest": policy.digest})
    reusable, obligations = [], []
    for requirement in policy.requirements:
        decision = evaluate_requirement(requirement, list(capsule.evidence), current)
        if decision.accepted:
            reusable.extend(record for record in capsule.evidence if record.digest in decision.evidence_digests)
        else:
            obligations.append(requirement.kind + ":" + requirement.name)
    return ReuseDecision(status="needs_verification" if obligations else "matched", capsule_digest=capsule.digest, candidate=candidate,
                         reusable_evidence=tuple(reusable), obligations=tuple(obligations))


def write_capsule(capsule: ImplementationCapsule, path: Path) -> None:
    envelope = {"digest": capsule.digest, "capsule": capsule.model_dump(mode="json")}
    # Exclusive creation makes an export reviewable without replacing an existing capsule.
    with path.open("x", encoding="utf-8") as handle:
        handle.write(canonical_json(envelope) + "\n")


def read_capsule(path: Path) -> ImplementationCapsule:
    try:
        if path.stat().st_size > 10485760:
            raise ProgramError("capsule_limit", "Capsule exceeds 10 MiB")
        envelope = json.loads(path.read_text(encoding="utf-8"))
        capsule = ImplementationCapsule.model_validate(envelope["capsule"])
        if capsule.digest != envelope["digest"]:
            raise ProgramError("capsule_corrupt", "Capsule content does not match its digest")
        return capsule
    except (KeyError, TypeError, ValidationError) as error:
        raise ProgramError("capsule_invalid", "Invalid capsule envelope") from error
