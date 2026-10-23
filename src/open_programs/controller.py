"""Checkpoint activation, pinned activities and conservative effect recovery."""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable

from jsonschema import Draft202012Validator, SchemaError, ValidationError

from .cancellation import ActivityCancellation
from .compiler import OpenCompiler
from .evidence import current_evidence, evaluate_policy, invalidation_paths
from .model import (
    BuildArtifact,
    Candidate,
    EffectIntent,
    ExecutionSpec,
    GoalSpec,
    ProgramError,
    ProgramEvent,
    ProgramRevision,
    ResolutionBudget,
    ResolutionResult,
    RevisionProposal,
    RuntimeActivity,
    RuntimeCheckpoint,
    RuntimeHead,
    canonical_json,
    content_digest,
)
from .reuse import ImplementationCapsule, match_capsule
from .store import ProgramStore


def validate_artifact(compiler: OpenCompiler, revision: ProgramRevision, artifact: BuildArtifact) -> None:
    environment = compiler.environment
    if (artifact.program_digest != revision.program.digest or artifact.environment_digest != environment.digest
            or revision.environment_digest != environment.digest):
        raise ProgramError("artifact_mismatch", "Rebuild the revision in the current environment")
    goals = {goal.name: goal for goal in revision.program.goals if goal.stage == "build"}
    if set(goals) != {result.goal_name for result in artifact.results} or len(goals) != len(artifact.results):
        raise ProgramError("artifact_incomplete", "Build goals are missing or duplicated")
    if set(artifact.runtime_goals) != {goal.name for goal in revision.program.goals if goal.stage == "runtime"}:
        raise ProgramError("artifact_incomplete", "Runtime obligations differ from the revision")
    for result in artifact.results:
        if result.status != "accepted" or result.context is None or result.policy is None or result.candidate is None:
            raise ProgramError("artifact_incomplete", result.goal_name)
        goal = goals[result.goal_name]
        if result.candidate.goal_digest != goal.digest or result.policy != compiler.policy_for(goal):
            raise ProgramError("artifact_mismatch", result.goal_name)
        context = result.context.model_copy(update={"now": time.time()})
        dependencies = {dependency.name: dependency.digest for dependency in context.dependencies}
        if (dependencies.get("environment") != environment.digest or dependencies.get("goal") != goal.digest
                or context.subject_digest != result.candidate.digest
                or not evaluate_policy(result.policy, current_evidence(compiler.store, list(result.evidence), context), context).accepted):
            raise ProgramError("evidence_stale", result.goal_name)


class RuntimeController:
    def __init__(self, compiler: OpenCompiler) -> None:
        self.compiler = compiler
        self.store = compiler.store
        self.effects = EffectJournal(self.store)
        self._cancellations: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def _head_ref(self, program_id: str) -> str:
        return "runtime:" + content_digest(program_id)

    def status(self, program_id: str) -> RuntimeHead:
        head = self.store.reference(self._head_ref(program_id), RuntimeHead)
        if head is None:
            raise ProgramError("program_inactive", program_id)
        return head

    def checkpoint(self, program_id: str) -> RuntimeCheckpoint:
        with self.store.lease(self._head_ref(program_id)):
            return self._checkpoint(program_id)

    def _checkpoint(self, program_id: str) -> RuntimeCheckpoint:
        head = self.status(program_id)
        if self.effects.pending(program_id):
            raise ProgramError("pending_effect", "Reconcile or finish external operations before a checkpoint")
        checkpoint = RuntimeCheckpoint(program_id=program_id, head_digest=head.digest, revision=head.revision)
        self.store.put(checkpoint)
        return checkpoint

    def propose_revision(self, base: str | None, revision: ProgramRevision, artifact: BuildArtifact) -> RevisionProposal:
        validate_artifact(self.compiler, revision, artifact)
        changed = {goal.name for goal in revision.program.goals}
        if base:
            previous = self.store.get(base, ProgramRevision)
            old = {goal.name: goal.digest for goal in previous.program.goals}
            changed = {goal.name for goal in revision.program.goals if old.get(goal.name) != goal.digest}
            if previous.environment_digest != revision.environment_digest:
                changed.update(old)
        paths: dict[str, tuple[str, ...]] = {name: (name,) for name in changed}
        paths.update(invalidation_paths({goal.name: goal.depends_on for goal in revision.program.goals}, changed))
        proposal = RevisionProposal(program_id=revision.program_id, base=base, revision=revision.digest, artifact_digest=artifact.digest,
                                    invalidated=tuple(paths[name] for name in sorted(paths)))
        self.store.put(revision)
        self.store.put(artifact)
        self.store.put(proposal)
        return proposal

    def activate_revision(self, proposal: RevisionProposal, checkpoint: RuntimeCheckpoint | None, *,
                          migration: Candidate | None = None, state_schema_json: str | None = None) -> RuntimeHead:
        with self.store.lease(self._head_ref(proposal.program_id)):
            return self._activate(proposal, checkpoint, migration=migration, state_schema_json=state_schema_json)

    def _activate(self, proposal: RevisionProposal, checkpoint: RuntimeCheckpoint | None, *,
                  migration: Candidate | None, state_schema_json: str | None) -> RuntimeHead:
        current = self.store.reference(self._head_ref(proposal.program_id), RuntimeHead)
        if current is None:
            if proposal.base is not None or checkpoint is not None:
                raise ProgramError("checkpoint_conflict", "Initial activation has no checkpoint")
        elif (checkpoint is None or checkpoint.program_id != proposal.program_id or checkpoint.head_digest != current.digest
              or current.revision != proposal.base or checkpoint.revision != current.revision):
            raise ProgramError("checkpoint_conflict", "Checkpoint no longer describes the active revision")
        if self.effects.pending(proposal.program_id):
            raise ProgramError("pending_effect", "Resolve external operations before activation")
        revision = self.store.get(proposal.revision, ProgramRevision)
        if revision.program_id != proposal.program_id:
            raise ProgramError("revision_conflict", "Proposal belongs to another program")
        artifact = self.store.get(proposal.artifact_digest, BuildArtifact)
        validate_artifact(self.compiler, revision, artifact)
        state, schema = self._migrate(current, migration, state_schema_json)
        head = RuntimeHead(program_id=proposal.program_id, revision=proposal.revision, generation=current.generation + 1 if current else 1,
                           artifact_digest=artifact.digest, state_json=state, state_schema_json=schema)
        event = ProgramEvent(kind="revision_activated", object_id=head.digest, detail=proposal.digest)
        self.store.set_reference(self._head_ref(proposal.program_id), current.digest if current else None, head, events=[(proposal.program_id, event)])
        return head

    def _migrate(self, current: RuntimeHead | None, migration: Candidate | None, schema: str | None) -> tuple[str, str]:
        state = current.state_json if current else "{}"
        schema = schema or (current.state_schema_json if current else '{"type":"object"}')
        if migration:
            if set(migration.capabilities) - {"sandbox.exec"}:
                raise ProgramError("migration_capability", "State migrations only execute a pure isolated transform")
            report = self.compiler.executor.execute_candidate(migration, ExecutionSpec(image=self.compiler.environment.image, return_type="Json",
                                                                                       input_json=canonical_json({"state": json.loads(state)})))
            if not report.succeeded:
                raise ProgramError("migration_failed", report.error)
            state = report.output_json
        try:
            parsed = json.loads(schema)
            Draft202012Validator.check_schema(parsed)
            Draft202012Validator(parsed).validate(json.loads(state))
        except (ValueError, SchemaError, ValidationError) as error:
            raise ProgramError("migration_invalid", "State does not satisfy the target schema") from error
        return state, schema

    def start_activity(self, program_id: str, goal_name: str, *, input_json: str = "{}", capsule_digest: str = "") -> RuntimeActivity:
        with self.store.lease(self._head_ref(program_id)):
            if self.effects.pending(program_id):
                raise ProgramError("pending_effect", "Reconcile external operations before starting another activity")
            return self._start_activity(program_id, goal_name, input_json=input_json, capsule_digest=capsule_digest)

    def _start_activity(self, program_id: str, goal_name: str, *, input_json: str, capsule_digest: str) -> RuntimeActivity:
        head = self.status(program_id)
        revision = self.store.get(head.revision, ProgramRevision)
        if revision.environment_digest != self.compiler.environment.digest:
            raise ProgramError("environment_changed", "Build and activate a revision for the current environment")
        validate_artifact(self.compiler, revision, self.store.get(head.artifact_digest, BuildArtifact))
        if goal_name not in {goal.name for goal in revision.program.goals}:
            raise ProgramError("unknown_goal", goal_name)
        activity = RuntimeActivity(activity_id=uuid.uuid4().hex, program_id=program_id, revision=head.revision, artifact_digest=head.artifact_digest, goal=goal_name,
                                   input_json=canonical_json(json.loads(input_json)), capsule_digest=capsule_digest)
        self.store.commit_references([(self._head_ref(program_id), head.digest, head), ("runtime.activity:" + activity.activity_id, None, activity)],
                                     events=[(program_id, ProgramEvent(kind="activity_created", object_id=activity.digest))])
        return activity

    def activity(self, activity_id: str) -> RuntimeActivity:
        value = self.store.reference("runtime.activity:" + activity_id, RuntimeActivity)
        if value is None:
            raise ProgramError("activity_missing", activity_id)
        return value

    def resolve_activity(self, activity_id: str, *, budget: ResolutionBudget | None = None) -> ResolutionResult:
        with self.store.lease("activity:" + activity_id):
            return self._resolve_activity(activity_id, budget=budget)

    def _resolve_activity(self, activity_id: str, *, budget: ResolutionBudget | None) -> ResolutionResult:
        activity = self.activity(activity_id)
        if activity.result is not None:
            return activity.result
        if activity.state != "pending":
            raise ProgramError("activity_not_pending", activity.state)
        running = activity.model_copy(update={"state": "running"})
        self.store.set_reference("runtime.activity:" + activity_id, activity.digest, running)
        revision = self.store.get(activity.revision, ProgramRevision)
        cancel = ActivityCancellation(self.store, activity_id)
        with self._lock:
            self._cancellations[activity_id] = cancel
        try:
            try:
                result, dependencies = self._resolve_graph(activity, revision, budget or ResolutionBudget(), cancel)
            except ProgramError as error:
                result = ResolutionResult(status="blocked", goal_name=activity.goal, reason=error.code)
                dependencies = ()
            state = "completed" if result.status == "accepted" else "cancelled" if result.status == "cancelled" else "blocked"
            completed = running.model_copy(update={"state": state, "result": result, "dependency_results": dependencies})
            self.store.set_reference("runtime.activity:" + activity_id, running.digest, completed,
                                     events=[(activity.program_id, ProgramEvent(kind="activity_" + state, object_id=completed.digest))])
            return result
        finally:
            with self._lock:
                self._cancellations.pop(activity_id, None)

    def _resolve_graph(self, activity: RuntimeActivity, revision: ProgramRevision, budget: ResolutionBudget,
                       cancel: threading.Event) -> tuple[ResolutionResult, tuple[ResolutionResult, ...]]:
        artifact = self.store.get(activity.artifact_digest, BuildArtifact)
        validate_artifact(self.compiler, revision, artifact)
        values = {result.goal_name: result for result in artifact.results}
        goals = {goal.name: goal for goal in revision.program.goals}
        resolved: list[ResolutionResult] = []
        deadline = time.monotonic() + budget.timeout_seconds

        def resolve(name: str) -> ResolutionResult:
            if name in values:
                return values[name]
            goal = goals[name]
            for dependency in goal.depends_on:
                result = resolve(dependency)
                if result.status != "accepted":
                    return result.model_copy(update={"goal_name": name, "reason": "dependency_blocked:" + dependency})
            calls = sum(result.model_calls for result in resolved)
            tokens = sum(result.input_tokens + result.output_tokens for result in resolved)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return ResolutionResult(status="blocked", goal_name=name, reason="resolution_timeout")
            inputs = json.loads(activity.input_json)
            if not isinstance(inputs, dict):
                raise ProgramError("input_type", "Runtime inputs must be a JSON object")
            inputs["dependencies"] = {dependency: json.loads(values[dependency].output_json) for dependency in goal.depends_on}
            inputs["dependency_evidence"] = {dependency: values[dependency].digest for dependency in goal.depends_on}
            available = budget.model_copy(update={"max_model_calls": max(0, budget.max_model_calls - calls) if tokens < budget.max_tokens else 0,
                                                  "max_tokens": max(1, budget.max_tokens - tokens), "timeout_seconds": remaining})
            result = self._resolve_runtime_goal(activity, goal, canonical_json(inputs), available, cancel)
            self.store.put(result)
            values[name] = result
            resolved.append(result)
            return result

        result = resolve(activity.goal)
        summary = result.model_copy(update={"model_calls": sum(item.model_calls for item in resolved),
                                           "input_tokens": sum(item.input_tokens for item in resolved), "output_tokens": sum(item.output_tokens for item in resolved)})
        return summary, tuple(item for item in resolved if item.goal_name != activity.goal)

    def _resolve_runtime_goal(self, activity: RuntimeActivity, goal: GoalSpec, inputs: str, budget: ResolutionBudget,
                              cancel: threading.Event) -> ResolutionResult:
        candidate = None
        evidence = ()
        if activity.capsule_digest and goal.name == activity.goal:
            capsule = self.store.get(activity.capsule_digest, ImplementationCapsule)
            policy = self.compiler.policy_for(goal)
            context = self.compiler.context_for(capsule.candidate, goal, inputs, policy, activity.activity_id)
            decision = match_capsule(capsule, goal, context, policy)
            self.store.set_reference("reuse:" + activity.activity_id, None, decision)
            if decision.status == "rejected":
                return ResolutionResult(status="blocked", goal_name=goal.name, reason="capsule_rejected:" + ",".join(decision.reasons))
            candidate, evidence = decision.candidate, decision.reusable_evidence
        return self.compiler.resolve_goal(goal, input_json=inputs, budget=budget, task_id=activity.activity_id, cancel=cancel,
                                          candidate=candidate, reusable_evidence=evidence)

    def cancel(self, activity_id: str) -> RuntimeActivity:
        activity = self.activity(activity_id)
        if activity.state not in {"pending", "running"}:
            return activity
        ActivityCancellation(self.store, activity_id).set()
        try:
            with self.store.lease("activity:" + activity_id):
                activity = self.activity(activity_id)
                if activity.state == "pending":
                    result = ResolutionResult(status="cancelled", goal_name=activity.goal, reason="cancelled")
                    updated = activity.model_copy(update={"state": "cancelled", "result": result})
                    self.store.set_reference("runtime.activity:" + activity_id, activity.digest, updated)
                    return updated
        except ProgramError as error:
            if error.code != "operation_busy":
                raise
        return self.activity(activity_id)

    def resume(self, program_id: str) -> RuntimeHead:
        # Invoke recovery only after establishing exclusive ownership of the stopped controller.
        with self._lock:
            if self._cancellations:
                raise ProgramError("controller_running", "Cannot recover a live controller")
        self.effects.recover(program_id)
        for activity in self.store.references("runtime.activity:", RuntimeActivity):
            if activity.program_id == program_id and activity.state == "running":
                with self.store.lease("activity:" + activity.activity_id):
                    updated = activity.model_copy(update={"state": "interrupted"})
                    self.store.set_reference("runtime.activity:" + activity.activity_id, activity.digest, updated)
        return self.status(program_id)


class EffectJournal:
    def __init__(self, store: ProgramStore) -> None:
        self.store = store

    def prepare(self, program_id: str, key: str, payload_digest: str, *, idempotent: bool) -> EffectIntent:
        with self.store.lease("runtime:" + content_digest(program_id)):
            return self._prepare(program_id, key, payload_digest, idempotent=idempotent)

    def _prepare(self, program_id: str, key: str, payload_digest: str, *, idempotent: bool) -> EffectIntent:
        operation_id = content_digest((program_id, key))
        existing = self.store.reference("effect:" + operation_id, EffectIntent)
        if existing:
            if existing.payload_digest != payload_digest or existing.idempotent != idempotent:
                raise ProgramError("effect_conflict", "An operation key cannot refer to a changed payload or adapter contract")
            return existing
        intent = EffectIntent(operation_id=operation_id, program_id=program_id, payload_digest=payload_digest, idempotent=idempotent)
        self.store.set_reference("effect:" + operation_id, None, intent)
        return intent

    def _get(self, operation_id: str) -> EffectIntent:
        intent = self.store.reference("effect:" + operation_id, EffectIntent)
        if intent is None:
            raise ProgramError("effect_missing", operation_id)
        return intent

    def execute(self, operation_id: str, handler: Callable[[str], str]) -> str:
        with self.store.lease("effect:" + operation_id):
            return self._execute(operation_id, handler)

    def _execute(self, operation_id: str, handler: Callable[[str], str]) -> str:
        intent = self._get(operation_id)
        if intent.state == "completed":
            return intent.result_json
        if intent.state == "unknown" or intent.state == "started":
            raise ProgramError("effect_unknown", "Recover and reconcile the outstanding operation")
        started = intent.model_copy(update={"state": "started", "attempt": intent.attempt + 1})
        self.store.set_reference("effect:" + operation_id, intent.digest, started)
        result = canonical_json(json.loads(handler(operation_id)))
        completed = started.model_copy(update={"state": "completed", "result_json": result})
        self.store.set_reference("effect:" + operation_id, started.digest, completed,
                                 events=[(intent.program_id, ProgramEvent(kind="effect_completed", object_id=completed.digest))])
        return result

    def pending(self, program_id: str) -> list[EffectIntent]:
        return [intent for intent in self.store.references("effect:", EffectIntent) if intent.program_id == program_id and intent.state != "completed"]

    def recover(self, program_id: str) -> list[EffectIntent]:
        recovered = []
        for intent in self.pending(program_id):
            if intent.state == "started":
                with self.store.lease("effect:" + intent.operation_id):
                    updated = intent.model_copy(update={"state": "prepared" if intent.idempotent else "unknown"})
                    self.store.set_reference("effect:" + intent.operation_id, intent.digest, updated)
                    intent = updated
            recovered.append(intent)
        return recovered

    def reconcile(self, operation_id: str, *, result_json: str, actor: str) -> EffectIntent:
        intent = self._get(operation_id)
        if intent.state != "unknown" or not actor.strip():
            raise ProgramError("reconciliation_invalid", "An unknown operation requires an identified decision maker")
        result = intent.model_copy(update={"state": "completed", "result_json": canonical_json(json.loads(result_json)), "reconciled_by": actor})
        self.store.set_reference("effect:" + operation_id, intent.digest, result,
                                 events=[(intent.program_id, ProgramEvent(kind="effect_reconciled", object_id=result.digest))])
        return result
