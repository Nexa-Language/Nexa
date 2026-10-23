"""Contextual evidence validity and deterministic admission decisions."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from .model import AcceptancePolicy, AdmissionDecision, ContextSnapshot, EvidenceRecord, EvidenceStatus, EvidenceValidity, Requirement

if TYPE_CHECKING:
    from .store import ProgramStore


def current_evidence(store: ProgramStore, records: list[EvidenceRecord], context: ContextSnapshot) -> list[EvidenceRecord]:
    # Immutable artifacts keep history; current admission also sees later observations.
    return list({record.digest: record for record in [*records, *store.evidence_for(context)]}.values())


def validate_evidence(record: EvidenceRecord, context: ContextSnapshot) -> EvidenceStatus:
    if record.digest in context.revoked:
        return EvidenceStatus(validity=EvidenceValidity.REVOKED, reasons=("revoked",))
    reasons: list[str] = []
    if record.subject_digest != context.subject_digest:
        reasons.append("subject_changed")
    if record.policy_digest != context.policy_digest:
        reasons.append("policy_changed")
    dependencies = {item.name: item.digest for item in context.dependencies}
    for item in record.dependencies:
        if dependencies.get(item.name) != item.digest:
            reasons.append(f"dependency_changed:{item.name}")
    if record.expires_at is not None and context.now >= record.expires_at:
        reasons.append("expired")
    if record.issued_at > context.now:
        reasons.append("future_evidence")
    if record.task_id != context.task_id and (record.kind == "human_decision" or (record.kind == "model_review" and not record.model_pinned)):
        reasons.append("task_changed")
    return EvidenceStatus(validity=EvidenceValidity.STALE if reasons else EvidenceValidity.VALID, reasons=tuple(reasons))


def evaluate_policy(policy: AcceptancePolicy, records: list[EvidenceRecord], context: ContextSnapshot) -> AdmissionDecision:
    if policy.digest != context.policy_digest:
        return AdmissionDecision(accepted=False, reasons=("policy_changed",))
    reasons: list[str] = []
    used: list[str] = []
    for requirement in policy.requirements:
        decision = evaluate_requirement(requirement, records, context)
        reasons.extend(decision.reasons)
        used.extend(decision.evidence_digests)
    return AdmissionDecision(accepted=not reasons, reasons=tuple(reasons), evidence_digests=tuple(sorted(set(used))))


def evaluate_requirement(requirement: Requirement, records: list[EvidenceRecord], context: ContextSnapshot) -> AdmissionDecision:
    matching = [record for record in records if (record.requirement, record.kind) == (requirement.name, requirement.kind)]
    if not matching:
        return AdmissionDecision(accepted=False, reasons=(f"missing:{requirement.name}:{requirement.kind}",))
    latest_time = max(record.issued_at for record in matching)
    latest = [record for record in matching if record.issued_at == latest_time]
    reasons, used = [], []
    for record in latest:
        prefix = requirement.name
        status = validate_evidence(record, context)
        reasons.extend(f"{prefix}:{reason}" for reason in status.reasons)
        if record.checker_digest != requirement.checker_digest:
            reasons.append(f"{prefix}:checker_changed")
        available = {item.name for item in record.dependencies}
        for name in set(requirement.dependencies) - available:
            reasons.append(f"{prefix}:missing_dependency:{name}")
        if not record.passed:
            reasons.append(f"{prefix}:failed")
        used.append(record.digest)
    return AdmissionDecision(accepted=not reasons, reasons=tuple(reasons), evidence_digests=tuple(sorted(set(used))))


def invalidation_paths(graph: dict[str, tuple[str, ...]], changed: set[str]) -> dict[str, tuple[str, ...]]:
    reverse: dict[str, list[str]] = {}
    for dependent, inputs in graph.items():
        for item in inputs:
            reverse.setdefault(item, []).append(dependent)
    paths: dict[str, tuple[str, ...]] = {}
    queue: deque[tuple[str, tuple[str, ...]]] = deque((name, (name,)) for name in sorted(changed))
    visited = set(changed)
    while queue:
        name, path = queue.popleft()
        for dependent in sorted(reverse.get(name, [])):
            if dependent in visited:
                continue
            visited.add(dependent)
            paths[dependent] = (*path, dependent)
            queue.append((dependent, paths[dependent]))
    return paths
