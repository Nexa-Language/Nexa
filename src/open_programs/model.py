"""Immutable values shared by the Open Programs compiler and runtime."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
TypeName = Literal["Int", "Float", "String", "Bool", "Json", "Unit", "Patch", "Repository", "ChangeRequest"]
Capability = Literal["repo.read", "sandbox.exec", "sandbox.write", "model.call"]


class ProgramError(ValueError):
    def __init__(self, code: str, message: str, *, object_id: str = "", retryable: bool = False, span: SourceSpan | None = None) -> None:
        self.code = code
        self.object_id = object_id
        self.retryable = retryable
        self.span = span
        super().__init__(f"{code}: {message}")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def content_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _semantic(value: object) -> object:
    if isinstance(value, dict):
        return {key: _semantic(item) for key, item in value.items() if key != "span"}
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    return value


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    @property
    def digest(self) -> str:
        return content_digest(_semantic(self.model_dump(mode="json")))


class SourceSpan(FrozenModel):
    path: str = "<source>"
    line: int = Field(default=1, ge=1)
    column: int = Field(default=1, ge=1)
    end_line: int = Field(default=1, ge=1)
    end_column: int = Field(default=1, ge=1)


class SourceBundle(FrozenModel):
    text: str
    path: str = "<source>"
    language_version: Literal["3.0"] = "3.0"


class Diagnostic(FrozenModel):
    code: str
    message: str
    span: SourceSpan = SourceSpan()
    severity: Literal["error", "warning"] = "error"
    obligation: str = ""


class Parameter(FrozenModel):
    name: Identifier
    type: TypeName


class Implementation(FrozenModel):
    kind: Literal["value", "python"]
    body: str


class GoalSpec(FrozenModel):
    name: Identifier
    parameters: tuple[Parameter, ...] = ()
    return_type: TypeName
    intent: str = Field(min_length=1)
    stage: Literal["build", "runtime"] = "build"
    context: tuple[str, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    checks: tuple[str, ...] = ()
    reviews: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    implementation: Implementation | None = None
    span: SourceSpan = SourceSpan()

    @model_validator(mode="after")
    def unique_parameters(self) -> GoalSpec:
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("duplicate_parameter")
        return self


class EventHandler(FrozenModel):
    event: Identifier
    parameter: Identifier
    goal: Identifier
    result: Identifier
    repository: Identifier
    span: SourceSpan = SourceSpan()


class ProgramIR(FrozenModel):
    schema_version: Literal[1] = 1
    language_version: Literal["3.0"] = "3.0"
    name: Identifier
    parameters: tuple[Parameter, ...] = ()
    environment: str = "developer"
    sandbox: str = "repository_image"
    acceptance: str = "repo_maintenance"
    goals: tuple[GoalSpec, ...] = ()
    handlers: tuple[EventHandler, ...] = ()

    @model_validator(mode="after")
    def validate_graph(self) -> ProgramIR:
        names = [goal.name for goal in self.goals]
        if len(names) != len(set(names)):
            raise ValueError("duplicate_goal")
        graph = {goal.name: goal.depends_on for goal in self.goals}
        for goal, dependencies in graph.items():
            if any(dependency not in graph for dependency in dependencies):
                raise ValueError(f"unknown_dependency: {goal}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise ValueError(f"goal_cycle: {name}")
            if name in visited:
                return
            visiting.add(name)
            for dependency in graph[name]:
                visit(dependency)
            visiting.remove(name)
            visited.add(name)

        for name in graph:
            visit(name)
        return self


class CheckReport(FrozenModel):
    program: ProgramIR | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    obligations: tuple[str, ...] = ()
    source_digest: str = ""

    @property
    def ok(self) -> bool:
        return self.program is not None and not any(item.severity == "error" for item in self.diagnostics)


class GoalState(str, Enum):
    OPEN = "open"
    SOLVING = "solving"
    EVALUATING = "evaluating"
    SATISFIED = "satisfied"
    BLOCKED = "blocked"
    STALE = "stale"
    CANCELLED = "cancelled"


class CandidateState(str, Enum):
    PROPOSED = "proposed"
    CHECKED = "checked"
    EVALUATED = "evaluated"
    ADMITTED = "admitted"
    REJECTED = "rejected"


class EvidenceValidity(str, Enum):
    VALID = "valid"
    STALE = "stale"
    REVOKED = "revoked"


_GOAL_TRANSITIONS: dict[GoalState, frozenset[GoalState]] = {
    GoalState.OPEN: frozenset({GoalState.SOLVING, GoalState.BLOCKED, GoalState.CANCELLED}),
    GoalState.SOLVING: frozenset({GoalState.EVALUATING, GoalState.BLOCKED, GoalState.CANCELLED}),
    GoalState.EVALUATING: frozenset({GoalState.SATISFIED, GoalState.SOLVING, GoalState.BLOCKED, GoalState.CANCELLED}),
    GoalState.SATISFIED: frozenset({GoalState.STALE, GoalState.CANCELLED}),
    GoalState.STALE: frozenset({GoalState.SOLVING, GoalState.BLOCKED, GoalState.CANCELLED}),
    GoalState.BLOCKED: frozenset({GoalState.SOLVING, GoalState.CANCELLED}),
    GoalState.CANCELLED: frozenset(),
}


def transition_goal(before: GoalState, after: GoalState) -> GoalState:
    if after not in _GOAL_TRANSITIONS[before]:
        raise ProgramError("invalid_transition", f"{before.value} -> {after.value}")
    return after


class Dependency(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    digest: str = Field(min_length=1)


class Requirement(FrozenModel):
    name: str = Field(min_length=1)
    kind: Literal["deterministic", "model_review", "human_decision"]
    checker_digest: str = Field(min_length=1)
    dependencies: tuple[str, ...] = ()


class AcceptancePolicy(FrozenModel):
    name: str = Field(min_length=1)
    requirements: tuple[Requirement, ...]

    @model_validator(mode="after")
    def nonempty_unique_requirements(self) -> AcceptancePolicy:
        keys = [(item.name, item.kind) for item in self.requirements]
        if not keys or len(keys) != len(set(keys)):
            raise ValueError("Policy requires at least one uniquely named check per evidence kind")
        return self


class ContextSnapshot(FrozenModel):
    subject_digest: str
    policy_digest: str
    dependencies: tuple[Dependency, ...]
    now: float = Field(ge=0)
    task_id: str
    revoked: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unique_dependencies(self) -> ContextSnapshot:
        names = [item.name for item in self.dependencies]
        if len(names) != len(set(names)):
            raise ValueError("duplicate_dependency")
        return self


class EvidenceRecord(FrozenModel):
    schema_version: Literal[1] = 1
    requirement: str
    kind: Literal["deterministic", "model_review", "human_decision"]
    subject_digest: str
    policy_digest: str
    checker_digest: str
    dependencies: tuple[Dependency, ...]
    passed: bool
    issued_at: float = Field(ge=0)
    expires_at: float | None = Field(default=None, ge=0)
    task_id: str
    model_pinned: bool = True
    detail: str = ""
    artifact_digests: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unique_dependencies(self) -> EvidenceRecord:
        names = [item.name for item in self.dependencies]
        if len(names) != len(set(names)):
            raise ValueError("duplicate_dependency")
        return self


class EvidenceStatus(FrozenModel):
    validity: EvidenceValidity
    reasons: tuple[str, ...] = ()


class AdmissionDecision(FrozenModel):
    accepted: bool
    reasons: tuple[str, ...] = ()
    evidence_digests: tuple[str, ...] = ()


class ProgramRevision(FrozenModel):
    schema_version: Literal[1] = 1
    program_id: str = Field(min_length=1)
    parent: str | None = None
    program: ProgramIR
    environment_digest: str = ""
    policy_digest: str = ""


class ProgramEvent(FrozenModel):
    kind: str = Field(min_length=1)
    object_id: str
    detail: str = ""


class Candidate(FrozenModel):
    schema_version: Literal[1] = 1
    goal_digest: str
    implementation: Implementation
    capabilities: tuple[Capability, ...] = ()
    origin: str = "author"
    dependencies: tuple[Dependency, ...] = ()


class ExecutionSpec(FrozenModel):
    image: str = Field(pattern=r"^[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}$")
    return_type: TypeName
    input_json: str = "{}"
    timeout_seconds: float = Field(default=30, gt=0, le=3600)
    memory_mb: int = Field(default=128, ge=32, le=4096)
    cpus: float = Field(default=1, gt=0, le=8)
    pids: int = Field(default=64, ge=8, le=256)
    max_output_bytes: int = Field(default=1048576, ge=1024, le=10485760)


class ExecutionReport(FrozenModel):
    succeeded: bool
    output_json: str = "null"
    error: str = ""
    exit_code: int
    container_name: str = ""
    log: str = ""


class CheckCase(FrozenModel):
    input_json: str = "{}"
    expected_json: str


class OutputCheck(FrozenModel):
    name: str
    cases: tuple[CheckCase, ...] = Field(min_length=1)


class RepositoryCase(FrozenModel):
    argv: tuple[str, ...] = Field(min_length=1, max_length=32)
    input_text: str = ""
    expected_output: str
    expected_exit: int = 0


class RepositoryCheck(FrozenModel):
    name: str
    cases: tuple[RepositoryCase, ...] = Field(min_length=1)


class CommandReport(FrozenModel):
    output: str
    exit_code: int
    error: str = ""
    container_name: str


class ProviderBinding(FrozenModel):
    protocol: Literal["chat"] = "chat"
    api_key_env: str = Field(default="OPENAI_API_KEY", pattern=r"^[A-Z][A-Z0-9_]*$")
    base_url_env: str = Field(default="OPENAI_BASE_URL", pattern=r"^[A-Z][A-Z0-9_]*$")
    enable_thinking: bool | None = None


class CompilerEnvironment(FrozenModel):
    image: str = Field(pattern=r"^[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}$")
    model: str = "unconfigured"
    model_pinned: bool = False
    allow_model: bool = False
    provider: ProviderBinding | None = None
    checks: tuple[OutputCheck | RepositoryCheck, ...] = ()
    dependencies: tuple[Dependency, ...] = ()
    capabilities: tuple[Capability, ...] = ("repo.read", "sandbox.exec", "sandbox.write")

    @model_validator(mode="after")
    def unique_checks(self) -> CompilerEnvironment:
        names = [check.name for check in self.checks]
        if len(names) != len(set(names)):
            raise ValueError("duplicate_checker")
        return self


class ResolutionBudget(FrozenModel):
    max_model_calls: int = Field(default=4, ge=0, le=100)
    max_tokens: int = Field(default=20000, gt=0)
    max_output_tokens: int = Field(default=4096, gt=0)
    timeout_seconds: float = Field(default=120, gt=0, le=3600)


class ResolutionResult(FrozenModel):
    status: Literal["accepted", "blocked", "rejected", "cancelled"]
    goal_name: str
    candidate: Candidate | None = None
    evidence: tuple[EvidenceRecord, ...] = ()
    policy: AcceptancePolicy | None = None
    context: ContextSnapshot | None = None
    output_json: str = "null"
    reason: str = ""
    clarification: str = ""
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class BuildArtifact(FrozenModel):
    schema_version: Literal[1] = 1
    language_version: Literal["3.0"] = "3.0"
    compiler_version: Literal["3.0.reference.1"] = "3.0.reference.1"
    program_digest: str
    environment_digest: str
    results: tuple[ResolutionResult, ...]
    runtime_goals: tuple[str, ...] = ()


class BuildLock(FrozenModel):
    schema_version: Literal[1] = 1
    compiler_version: Literal["3.0.reference.1"] = "3.0.reference.1"
    program_digest: str
    environment_digest: str
    artifact_digest: str


class RuntimeHead(FrozenModel):
    schema_version: Literal[1] = 1
    program_id: str
    revision: str
    generation: int = Field(ge=1)
    artifact_digest: str
    state_json: str = "{}"
    state_schema_json: str = '{"type":"object"}'


class RuntimeCheckpoint(FrozenModel):
    program_id: str
    head_digest: str
    revision: str


class RevisionProposal(FrozenModel):
    program_id: str
    base: str | None
    revision: str
    artifact_digest: str
    invalidated: tuple[tuple[str, ...], ...] = ()


class RuntimeActivity(FrozenModel):
    activity_id: str
    program_id: str
    revision: str
    artifact_digest: str
    capsule_digest: str = ""
    goal: str
    input_json: str = "{}"
    state: Literal["pending", "running", "completed", "blocked", "interrupted", "cancelled"] = "pending"
    result: ResolutionResult | None = None
    dependency_results: tuple[ResolutionResult, ...] = ()


class EffectIntent(FrozenModel):
    operation_id: str
    program_id: str
    payload_digest: str
    idempotent: bool
    state: Literal["prepared", "started", "completed", "unknown"] = "prepared"
    attempt: int = 0
    result_json: str = "null"
    reconciled_by: str = ""


class SnapshotFile(FrozenModel):
    path: str
    content: str | None
    mode: int = 0o644


class WorkspaceSnapshot(FrozenModel):
    root: str
    device: int
    inode: int
    files: tuple[SnapshotFile, ...]


class FileChange(FrozenModel):
    path: str
    before_digest: str | None
    content: str | None


class PatchValue(FrozenModel):
    base_digest: str
    changes: tuple[FileChange, ...] = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def unique_paths(self) -> PatchValue:
        paths = [change.path for change in self.changes]
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate_patch_path")
        return self


class PatchProposal(FrozenModel):
    schema_version: Literal[1] = 1
    baseline: WorkspaceSnapshot
    candidate_digest: str
    changes: tuple[FileChange, ...]
    policy_digest: str
    evidence: tuple[EvidenceRecord, ...]
    task_id: str
    diff: str


class ApprovalGrant(FrozenModel):
    actor: str = Field(min_length=1)
    proposal_digest: str
    baseline_digest: str
    policy_digest: str
    evidence_digests: tuple[str, ...]
    scope: tuple[str, ...]
    task_id: str
    issued_at: float
    expires_at: float


class ApprovalState(FrozenModel):
    grant: ApprovalGrant
    revoked: bool = False


class PreservedFile(FrozenModel):
    path: str
    recovery_path: str


class ApplyResult(FrozenModel):
    proposal_digest: str
    grant_digest: str
    state: Literal["applying", "applied", "interrupted", "conflict"]
    written: tuple[str, ...] = ()
    pending_path: str = ""
    pending_temporary: str = ""
    preserved: tuple[PreservedFile, ...] = ()
    reason: str = ""
