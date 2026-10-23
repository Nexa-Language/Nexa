"""Model-assisted elaboration with contextual evidence and locked artifacts."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from ..runtime.providers import ModelProvider, ModelRequest
from .evidence import current_evidence, evaluate_policy, evaluate_requirement
from .frontend import _literal_matches
from .model import (
    AcceptancePolicy,
    BuildArtifact,
    BuildLock,
    Candidate,
    CommandReport,
    CompilerEnvironment,
    ContextSnapshot,
    Dependency,
    EvidenceRecord,
    ExecutionReport,
    ExecutionSpec,
    GoalSpec,
    Implementation,
    PatchValue,
    ProgramError,
    ProgramIR,
    RepositoryCase,
    RepositoryCheck,
    Requirement,
    ResolutionBudget,
    ResolutionResult,
    WorkspaceSnapshot,
    canonical_json,
    content_digest,
)
from .store import ProgramStore


class CandidateExecutor(Protocol):
    def execute_candidate(self, candidate: Candidate, spec: ExecutionSpec) -> ExecutionReport: ...

    def execute_repository(self, base: WorkspaceSnapshot, patch: PatchValue, case: RepositoryCase, spec: ExecutionSpec) -> CommandReport: ...


@dataclass
class _Activity:
    budget: ResolutionBudget
    cancel: threading.Event
    deadline: float
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    candidate: Candidate | None = None
    context: ContextSnapshot | None = None
    evidence: list[EvidenceRecord] = field(default_factory=list)

    def remaining(self) -> float:
        if self.cancel.is_set():
            raise ProgramError("cancelled", "Activity cancelled")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProgramError("resolution_timeout", "Resolution deadline exceeded")
        return remaining


class OpenCompiler:
    def __init__(self, environment: CompilerEnvironment, store: ProgramStore, *, executor: CandidateExecutor, provider: ModelProvider | None = None) -> None:
        self.environment = environment
        self.store = store
        self.executor = executor
        self.provider = provider

    def policy_for(self, goal: GoalSpec) -> AcceptancePolicy:
        checks = {check.name: check for check in self.environment.checks}
        dependencies = ("goal", "environment", "input")
        requirements = [Requirement(name="typecheck", kind="deterministic", checker_digest=content_digest(("typecheck.1", goal.return_type)), dependencies=dependencies)]
        for name in goal.checks:
            if name not in checks:
                raise ProgramError("checker_missing", name)
            requirements.append(Requirement(name=name, kind="deterministic", checker_digest=checks[name].digest, dependencies=dependencies))
        for name in goal.reviews:
            requirements.append(Requirement(name=name, kind="model_review", checker_digest=content_digest(("review.1", name, self.environment.model)), dependencies=dependencies))
        return AcceptancePolicy(name="goal:" + goal.name, requirements=tuple(requirements))

    def _request(self, prompt: str, activity: _Activity, *, schema: dict[str, object] | None = None) -> dict[str, object]:
        timeout = activity.remaining()
        if not self.environment.allow_model or self.provider is None:
            raise ProgramError("model_unavailable", "The environment has no authorized model binding")
        if activity.calls >= activity.budget.max_model_calls:
            raise ProgramError("model_call_budget", "Model call budget exhausted")
        remaining_tokens = activity.budget.max_tokens - activity.input_tokens - activity.output_tokens
        if remaining_tokens <= 0:
            raise ProgramError("model_token_budget", "Reported token budget exhausted")
        activity.calls += 1
        response_format = {"type": "json_schema", "json_schema": {"name": "nexa_response", "strict": True, "schema": schema}} if schema else {"type": "json_object"}
        request = ModelRequest(model=self.environment.model, messages=[{"role": "user", "content": "Return only a JSON object.\n" + prompt}], tools=[], timeout=timeout,
                               max_output_tokens=min(activity.budget.max_output_tokens, remaining_tokens), response_format=response_format)
        try:
            reply = self.provider.complete(request)
        except Exception as error:
            raise ProgramError("provider_failed", f"Provider failed: {type(error).__name__}", retryable=True) from error
        activity.input_tokens += reply.input_tokens
        activity.output_tokens += reply.output_tokens
        activity.remaining()
        if not reply.usage_reported:
            raise ProgramError("usage_unreported", "Provider must report usage for bounded compilation")
        if activity.input_tokens + activity.output_tokens > activity.budget.max_tokens:
            raise ProgramError("model_token_budget", "Reported token budget exceeded")
        if reply.tool_calls or len(reply.text) > 1048576:
            raise ProgramError("invalid_proposal", "Expected a bounded JSON proposal without tool calls")
        value = json.loads(reply.text)
        if not isinstance(value, dict):
            raise ProgramError("invalid_proposal", "Expected a JSON object")
        return value

    def _propose(self, goal: GoalSpec, inputs: str, feedback: str, activity: _Activity) -> tuple[Candidate | None, str]:
        if goal.implementation is not None:
            implementation = goal.implementation
        else:
            kind = "python" if "sandbox.exec" in goal.capabilities else "value"
            implementation_schema = Implementation.model_json_schema()
            implementation_schema["properties"]["kind"]["enum"] = [kind]
            schema: dict[str, object] = {
                "type": "object", "additionalProperties": False, "required": ["implementation", "clarification"],
                "properties": {"implementation": {"anyOf": [implementation_schema, {"type": "null"}]}, "clarification": {"type": "string"}},
            }
            prompt = canonical_json({"operation": "implement", "goal": goal.model_dump(mode="json"), "inputs": json.loads(inputs), "feedback": feedback,
                                     "instructions": "Implement the goal and honor its implementation and reuse constraints. Use kind=python when the goal requests reusable Python. "
                                                     "Return kind=value with JSON text in body, or kind=python with Python source defining solve(inputs). "
                                                     "The solve function must return the goal value directly, never another implementation wrapper. "
                                                     "Set clarification to an empty string when implementing. Only return implementation=null with a clarification question "
                                                     "when a necessary author decision is missing.", "response_schema": schema,
                                     "output_contract": PatchValue.model_json_schema() if goal.return_type == "Patch" else {"type": goal.return_type}})
            value = self._request(prompt, activity, schema=schema)
            if isinstance(value.get("clarification"), str) and value["clarification"]:
                return None, str(value["clarification"])
            implementation = Implementation.model_validate(value.get("implementation"))
            if implementation.kind != kind:
                raise ProgramError("invalid_proposal", "Provider ignored the selected implementation backend")
        candidate = Candidate(goal_digest=goal.digest, implementation=implementation, capabilities=goal.capabilities,
                              origin="author" if goal.implementation else self.environment.model, dependencies=self.environment.dependencies)
        return candidate, ""

    def context_for(self, candidate: Candidate, goal: GoalSpec, inputs: str, policy: AcceptancePolicy, task_id: str) -> ContextSnapshot:
        dependencies = (Dependency(name="goal", digest=goal.digest), Dependency(name="environment", digest=self.environment.digest),
                        Dependency(name="input", digest=content_digest(json.loads(inputs))), *self.environment.dependencies)
        return ContextSnapshot(subject_digest=candidate.digest, policy_digest=policy.digest, dependencies=dependencies, now=time.time(), task_id=task_id)

    def _execute(self, candidate: Candidate, goal: GoalSpec, inputs: str, activity: _Activity) -> ExecutionReport:
        return self.executor.execute_candidate(candidate, ExecutionSpec(image=self.environment.image, return_type=goal.return_type,
                                                                       input_json=inputs, timeout_seconds=min(activity.remaining(), 30)))

    def _record(self, requirement: Requirement, context: ContextSnapshot, passed: bool, detail: str = "", *, artifacts: tuple[str, ...] = ()) -> EvidenceRecord:
        record = EvidenceRecord(requirement=requirement.name, kind=requirement.kind, subject_digest=context.subject_digest,
                                policy_digest=context.policy_digest, checker_digest=requirement.checker_digest, dependencies=context.dependencies,
                                passed=passed, issued_at=time.time(), task_id=context.task_id, model_pinned=self.environment.model_pinned, detail=detail,
                                artifact_digests=artifacts)
        self.store.put(record)
        return record

    def _evaluate(self, candidate: Candidate, goal: GoalSpec, inputs: str, policy: AcceptancePolicy,
                  context: ContextSnapshot, activity: _Activity, reusable: tuple[EvidenceRecord, ...] = ()) -> tuple[list[EvidenceRecord], str]:
        records = activity.evidence
        records.clear()
        report = self._execute(candidate, goal, inputs, activity)
        detail = (report.error + "\n" + report.log[-2000:]).strip() if not report.succeeded else ""
        records.append(self._record(policy.requirements[0], context, report.succeeded, detail))
        if not report.succeeded:
            return records, report.output_json
        checks = {check.name: check for check in self.environment.checks}
        for requirement in policy.requirements[1:]:
            available = current_evidence(self.store, list(reusable), context) if reusable else []
            reuse = evaluate_requirement(requirement, available, context)
            if reuse.accepted:
                records.extend(record for record in available if record.digest in reuse.evidence_digests)
                continue
            if requirement.kind == "deterministic":
                checker = checks[requirement.name]
                if isinstance(checker, RepositoryCheck):
                    records.append(self._repository_evidence(checker, goal, inputs, report.output_json, requirement, context, activity))
                    continue
                passed = True
                for case in checker.cases:
                    result = self._execute(candidate, goal, case.input_json, activity)
                    passed = passed and result.succeeded and result.output_json == canonical_json(json.loads(case.expected_json))
                records.append(self._record(requirement, context, passed))
            else:
                if any(not record.passed for record in records):
                    continue
                schema: dict[str, object] = {"type": "object", "properties": {"passed": {"type": "boolean"}, "detail": {"type": "string"}},
                          "required": ["passed", "detail"], "additionalProperties": False}
                review = self._request(canonical_json({"operation": "review", "rule": requirement.name, "goal": goal.model_dump(mode="json"),
                                                      "inputs": json.loads(inputs),
                                                      "instructions": "Evaluate the named rule against the goal and this input. An already compliant snapshot may need only revalidation. Do not add unstated requirements.",
                                                      "implementation": candidate.implementation.model_dump(), "output": json.loads(report.output_json),
                                                      "response_schema": schema}), activity, schema=schema)
                if type(review.get("passed")) is not bool:
                    raise ProgramError("invalid_review", "Review must return a boolean passed field")
                records.append(self._record(requirement, context, review["passed"] is True, str(review.get("detail", ""))))
        return records, report.output_json

    def _repository_evidence(self, checker: RepositoryCheck, goal: GoalSpec, inputs: str, output: str,
                             requirement: Requirement, context: ContextSnapshot, activity: _Activity) -> EvidenceRecord:
        if goal.return_type != "Patch" or not {"repo.read", "sandbox.write"} <= set(goal.capabilities):
            raise ProgramError("capability_denied", "Repository checks require a Patch goal with repo.read and sandbox.write")
        values = json.loads(inputs)
        base = WorkspaceSnapshot.model_validate(values.get("repository"))
        patch = PatchValue.model_validate_json(output)
        artifacts = []
        failures = []
        passed = True
        for index, case in enumerate(checker.cases):
            result = self.executor.execute_repository(base, patch, case, ExecutionSpec(image=self.environment.image, return_type="Unit",
                                                                                      timeout_seconds=min(activity.remaining(), 30)))
            artifacts.append(self.store.put(result))
            matches = not result.error and result.exit_code == case.expected_exit and result.output == case.expected_output
            passed = passed and matches
            if not matches:
                failures.append(f"case {index}: exit={result.exit_code}, error={result.error}, observed={result.output[:512]!r}")
        return self._record(requirement, context, passed, "\n".join(failures), artifacts=tuple(artifacts))

    def resolve_goal(self, goal: GoalSpec, *, input_json: str = "{}", budget: ResolutionBudget | None = None,
                     task_id: str | None = None, cancel: threading.Event | None = None, candidate: Candidate | None = None,
                     reusable_evidence: tuple[EvidenceRecord, ...] = ()) -> ResolutionResult:
        policy = self.policy_for(goal)
        if not set(goal.capabilities) <= set(self.environment.capabilities):
            raise ProgramError("capability_denied", goal.name)
        if candidate and (candidate.goal_digest != goal.digest or not set(candidate.capabilities) <= set(goal.capabilities)):
            raise ProgramError("candidate_mismatch", "Reused candidate does not satisfy this goal's identity or capabilities")
        if candidate and goal.implementation is not None and candidate.implementation != goal.implementation:
            raise ProgramError("candidate_mismatch", "Reused candidate differs from the author's explicit implementation")
        trusted = self._trusted_evidence(reusable_evidence)
        supplied = candidate
        inputs = json.loads(input_json)
        if not isinstance(inputs, dict):
            raise ProgramError("input_type", "Goal inputs must be a JSON object")
        for parameter in goal.parameters:
            if parameter.name not in inputs or not _literal_matches(inputs[parameter.name], parameter.type):
                raise ProgramError("input_type", f"{goal.name}.{parameter.name} requires {parameter.type}")
        budget = budget or ResolutionBudget()
        activity = _Activity(budget, cancel or threading.Event(), time.monotonic() + budget.timeout_seconds)
        task_id = task_id or uuid.uuid4().hex
        feedback = ""
        try:
            while True:
                activity.remaining()
                candidate, question = (supplied, "") if supplied else self._propose(goal, input_json, feedback, activity)
                if candidate is None:
                    return self._result(goal, activity, "blocked", reason="clarification_required", clarification=question, policy=policy)
                self.store.put(candidate)
                context = self.context_for(candidate, goal, input_json, policy, task_id)
                activity.candidate, activity.context = candidate, context
                evidence, output = self._evaluate(candidate, goal, input_json, policy, context, activity, trusted)
                activity.remaining()
                context = context.model_copy(update={"now": time.time()})
                activity.context = context
                observed = current_evidence(self.store, evidence, context)
                decision = evaluate_policy(policy, observed, context)
                if decision.accepted:
                    evidence = [record for record in observed if record.digest in decision.evidence_digests]
                    return self._result(goal, activity, "accepted", candidate=candidate, evidence=tuple(evidence), policy=policy, context=context, output_json=output)
                feedback = canonical_json({"previous_implementation": candidate.implementation.model_dump(), "admission_reasons": decision.reasons,
                                           "failed_requirements": [{"name": record.requirement, "detail": record.detail} for record in evidence if not record.passed]})
                if goal.implementation is not None or supplied is not None:
                    return self._result(goal, activity, "rejected", reason=feedback, candidate=candidate, evidence=tuple(evidence), policy=policy, context=context)
        except ProgramError as error:
            return self._result(goal, activity, "cancelled" if error.code == "cancelled" else "blocked", reason=error.code, policy=policy)
        except (ValidationError, ValueError) as error:
            return self._result(goal, activity, "rejected", reason=f"invalid_proposal:{type(error).__name__}", policy=policy)

    def _trusted_evidence(self, records: tuple[EvidenceRecord, ...]) -> tuple[EvidenceRecord, ...]:
        trusted = []
        for record in records:
            try:
                if self.store.get(record.digest, EvidenceRecord) == record:
                    trusted.append(record)
            except ProgramError as error:
                if error.code != "object_missing":
                    raise
        return tuple(trusted)

    def _result(self, goal: GoalSpec, activity: _Activity, status: str, **fields: object) -> ResolutionResult:
        return ResolutionResult.model_validate({"status": status, "goal_name": goal.name, "model_calls": activity.calls,
                                               "input_tokens": activity.input_tokens, "output_tokens": activity.output_tokens,
                                               "candidate": activity.candidate, "context": activity.context, "evidence": tuple(activity.evidence), **fields})

    def build(self, program: ProgramIR, *, lock_path: Path, locked: bool = False, budget: ResolutionBudget | None = None) -> BuildArtifact:
        if locked:
            return self._locked(program, lock_path)
        results: dict[str, ResolutionResult] = {}
        goals = {goal.name: goal for goal in program.goals}
        total_budget = budget or ResolutionBudget()
        deadline = time.monotonic() + total_budget.timeout_seconds

        def resolve(name: str) -> None:
            if name in results or goals[name].stage == "runtime":
                return
            for dependency in goals[name].depends_on:
                resolve(dependency)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProgramError("build_blocked", "resolution_timeout")
            calls = sum(result.model_calls for result in results.values())
            tokens = sum(result.input_tokens + result.output_tokens for result in results.values())
            available_calls = max(0, total_budget.max_model_calls - calls) if tokens < total_budget.max_tokens else 0
            remaining_budget = total_budget.model_copy(update={"max_model_calls": available_calls, "max_tokens": max(1, total_budget.max_tokens - tokens),
                                                              "timeout_seconds": remaining})
            inputs = {"dependencies": {dependency: json.loads(results[dependency].output_json) for dependency in goals[name].depends_on}}
            result = self.resolve_goal(goals[name], input_json=canonical_json(inputs), budget=remaining_budget)
            if result.status != "accepted":
                raise ProgramError("build_blocked", f"{name}: {result.reason}", object_id=name)
            results[name] = result

        for goal in program.goals:
            resolve(goal.name)
        artifact = BuildArtifact(program_digest=program.digest, environment_digest=self.environment.digest, results=tuple(results.values()),
                                 runtime_goals=tuple(goal.name for goal in program.goals if goal.stage == "runtime"))
        self.store.put(artifact)
        lock = BuildLock(program_digest=program.digest, environment_digest=self.environment.digest, artifact_digest=artifact.digest)
        self._write_lock(lock_path, lock)
        return artifact

    def _locked(self, program: ProgramIR, path: Path) -> BuildArtifact:
        try:
            lock = BuildLock.model_validate_json(path.read_text())
        except (OSError, ValidationError) as error:
            raise ProgramError("lock_invalid", "Missing or invalid lock file") from error
        if (lock.program_digest, lock.environment_digest) != (program.digest, self.environment.digest):
            raise ProgramError("lock_mismatch", "Program or compiler environment changed")
        artifact = self.store.get(lock.artifact_digest, BuildArtifact)
        if (artifact.program_digest, artifact.environment_digest) != (program.digest, self.environment.digest):
            raise ProgramError("lock_mismatch", "Artifact context does not match the lock")
        for result in artifact.results:
            if result.context is None or result.policy is None or result.candidate is None:
                raise ProgramError("lock_invalid", "Artifact is missing admission evidence")
            context = result.context.model_copy(update={"now": time.time()})
            if not evaluate_policy(result.policy, current_evidence(self.store, list(result.evidence), context), context).accepted:
                raise ProgramError("evidence_stale", result.goal_name)
        return artifact

    def _write_lock(self, path: Path, lock: BuildLock) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".nexa-lock-")
        try:
            with os.fdopen(descriptor, "w") as handle:
                handle.write(lock.model_dump_json(indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
