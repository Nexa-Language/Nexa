"""Frozen diagnostic-pass evaluation and locked partial compiler bootstrapping."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from .compiler import OpenCompiler
from .controller import validate_artifact
from .frontend import check, diagnostic_context
from .model import (
    BuildArtifact,
    Candidate,
    CheckCase,
    CheckReport,
    ExecutionSpec,
    FrozenModel,
    ProgramError,
    ProgramEvent,
    ProgramIR,
    ProgramRevision,
    SourceBundle,
    canonical_json,
    content_digest,
)
from .store import ProgramStore


class Suggestion(FrozenModel):
    code: str
    replacement: str


class Advice(FrozenModel):
    suggestions: tuple[Suggestion, ...] = Field(max_length=100)


class AdvisedCheck(FrozenModel):
    check: CheckReport
    suggestions: tuple[Suggestion, ...]


class SemanticSuite(FrozenModel):
    name: str
    evaluator_version: Literal["diagnostic-advice.1"] = "diagnostic-advice.1"
    cases: tuple[CheckCase, ...] = Field(min_length=1)


class CompilerIdentity(FrozenModel):
    core_digest: str
    pass_candidate: Candidate
    environment_digest: str
    version: str


class EvolutionProposal(FrozenModel):
    schema_version: Literal[1] = 1
    seed_digest: str
    version: str
    program: ProgramIR
    artifact_digest: str
    pass_goal: str
    verifier_digest: str
    touched_paths: tuple[str, ...]


class EvolutionReport(FrozenModel):
    proposal_digest: str
    accepted: bool
    reasons: tuple[str, ...] = ()
    compiler: CompilerIdentity | None = None
    seed_failures: tuple[int, ...] = ()
    candidate_failures: tuple[int, ...] = ()
    c1_artifact_digest: str = ""
    c2_artifact_digest: str = ""
    c1_observations: tuple[str, ...] = ()
    c2_observations: tuple[str, ...] = ()
    generation_requests: int = 0


def compiler_core_digest() -> str:
    root = Path(__file__).parent
    files = ("compiler.py", "frontend.py", "model.py", "evidence.py", "executor.py", "evolution.py")
    return content_digest({name: (root / name).read_text(encoding="utf-8") for name in files})


class AdvisoryCompiler:
    def __init__(self, compiler: OpenCompiler, identity: CompilerIdentity) -> None:
        if identity.core_digest != compiler_core_digest() or identity.environment_digest != compiler.environment.digest:
            raise ProgramError("compiler_identity_changed", "The selected pass belongs to a different core or environment")
        if set(identity.pass_candidate.capabilities) - {"sandbox.exec"}:
            raise ProgramError("evolution_capability", "A diagnostic pass only needs isolated computation")
        self.compiler = compiler
        self.identity = identity

    def advise(self, input_json: str) -> Advice:
        report = self.compiler.executor.execute_candidate(self.identity.pass_candidate, ExecutionSpec(image=self.compiler.environment.image,
                                                                                                      return_type="Json", input_json=input_json))
        if not report.succeeded:
            raise ProgramError("diagnostic_pass_failed", report.error)
        advice = Advice.model_validate_json(report.output_json)
        context = json.loads(input_json)
        errors = {diagnostic["code"] for diagnostic in context.get("diagnostics", [])}
        names = set(context.get("known_goals", []))
        if any(item.code not in errors or item.replacement not in names for item in advice.suggestions):
            raise ProgramError("diagnostic_advice_invalid", "Advice must refer to existing errors and known declarations")
        return advice

    def check(self, source: str, *, path: str = "<source>") -> AdvisedCheck:
        bundle = SourceBundle(text=source, path=path)
        report = check(bundle)
        advice = self.advise(canonical_json(diagnostic_context(bundle, report)))
        return AdvisedCheck(check=report, suggestions=advice.suggestions)

    def build_locked(self, program: ProgramIR, lock_path: Path) -> BuildArtifact:
        # This compiler stage runs on each build, including builds of the pass itself.
        self.advise(canonical_json({"diagnostics": [], "known_goals": [goal.name for goal in program.goals]}))
        return self.compiler.build(program, lock_path=lock_path, locked=True)


def _observations(compiler: AdvisoryCompiler, suite: SemanticSuite) -> tuple[tuple[str, ...], tuple[int, ...]]:
    outputs, failures = [], []
    for index, case in enumerate(suite.cases):
        try:
            output = canonical_json(compiler.advise(case.input_json).model_dump(mode="json"))
        except (ProgramError, ValidationError, ValueError) as error:
            output = canonical_json({"error": error.code if isinstance(error, ProgramError) else type(error).__name__})
        outputs.append(output)
        if output != canonical_json(json.loads(case.expected_json)):
            failures.append(index)
    return tuple(outputs), tuple(failures)


def evaluate_evolution(proposal: EvolutionProposal, seed: CompilerIdentity, suite: SemanticSuite,
                       compiler: OpenCompiler, *, lock_path: Path) -> EvolutionReport:
    reasons = []
    if proposal.seed_digest != seed.digest or seed.core_digest != compiler_core_digest():
        reasons.append("seed_changed")
    if proposal.verifier_digest != suite.digest:
        reasons.append("verifier_changed")
    if proposal.touched_paths != ("diagnostic_advice.py",):
        reasons.append("evolution_scope_denied")
    if seed.environment_digest != compiler.environment.digest:
        reasons.append("environment_changed")
    if reasons:
        return EvolutionReport(proposal_digest=proposal.digest, accepted=False, reasons=tuple(reasons))
    try:
        return _bootstrap(proposal, seed, suite, compiler, lock_path)
    except (ProgramError, ValidationError, ValueError) as error:
        return EvolutionReport(proposal_digest=proposal.digest, accepted=False,
                               reasons=(error.code if isinstance(error, ProgramError) else type(error).__name__,))


def _bootstrap(proposal: EvolutionProposal, seed: CompilerIdentity, suite: SemanticSuite, compiler: OpenCompiler, lock: Path) -> EvolutionReport:
    artifact = compiler.store.get(proposal.artifact_digest, BuildArtifact)
    revision = ProgramRevision(program_id="compiler-evolution", program=proposal.program, environment_digest=compiler.environment.digest)
    validate_artifact(compiler, revision, artifact)
    result = next((result for result in artifact.results if result.goal_name == proposal.pass_goal), None)
    if result is None or result.candidate is None:
        raise ProgramError("compiler_pass_missing", proposal.pass_goal)
    identity = CompilerIdentity(core_digest=seed.core_digest, pass_candidate=result.candidate,
                                environment_digest=compiler.environment.digest, version=proposal.version)
    _, seed_failures = _observations(AdvisoryCompiler(compiler, seed), suite)
    first = AdvisoryCompiler(compiler, identity)
    c1_outputs, failures = _observations(first, suite)
    c1 = first.build_locked(proposal.program, lock)
    rebuilt = next(result.candidate for result in c1.results if result.goal_name == proposal.pass_goal)
    if rebuilt is None:
        raise ProgramError("bootstrap_missing_pass", proposal.pass_goal)
    second = AdvisoryCompiler(compiler, identity.model_copy(update={"pass_candidate": rebuilt, "version": proposal.version + ".bootstrap"}))
    c2 = second.build_locked(proposal.program, lock)
    c2_outputs, c2_failures = _observations(second, suite)
    reasons = []
    if failures or c2_failures:
        reasons.append("semantic_suite_failed")
    if c1.digest != c2.digest or c1.program_digest != c2.program_digest or c1_outputs != c2_outputs or identity.pass_candidate.digest != rebuilt.digest:
        reasons.append("bootstrap_inconsistent")
    report = EvolutionReport(proposal_digest=proposal.digest, accepted=not reasons, reasons=tuple(reasons), compiler=identity,
                             seed_failures=seed_failures, candidate_failures=failures, c1_artifact_digest=c1.digest, c2_artifact_digest=c2.digest,
                             c1_observations=c1_outputs, c2_observations=c2_outputs)
    compiler.store.put(proposal)
    compiler.store.put(report)
    return report


class EvolutionApproval(FrozenModel):
    report_digest: str
    proposal_digest: str
    seed_digest: str
    actor: str = Field(min_length=1)
    issued_at: float
    expires_at: float


class EvolutionManager:
    def __init__(self, store: ProgramStore) -> None:
        self.store = store

    def initialize(self, seed: CompilerIdentity) -> None:
        if seed.core_digest != compiler_core_digest():
            raise ProgramError("seed_changed", "Seed core does not match the current implementation")
        self.store.set_reference("compiler.active", None, seed)

    def approve(self, report: EvolutionReport, *, actor: str, expires_at: float | None = None) -> EvolutionApproval:
        self.store.get(report.digest, EvolutionReport)
        if not report.accepted or report.compiler is None or not actor.strip():
            raise ProgramError("evolution_unaccepted", "A successful evaluation and an identified approver are required")
        proposal = self.store.get(report.proposal_digest, EvolutionProposal)
        now = time.time()
        grant = EvolutionApproval(report_digest=report.digest, proposal_digest=proposal.digest, seed_digest=proposal.seed_digest,
                                  actor=actor, issued_at=now, expires_at=expires_at if expires_at is not None else now + 3600)
        self.store.set_reference("evolution.approval:" + grant.digest, None, grant)
        return grant

    def select(self, report: EvolutionReport, grant: EvolutionApproval) -> CompilerIdentity:
        stored = self.store.reference("evolution.approval:" + grant.digest, EvolutionApproval)
        if stored != grant or grant.report_digest != report.digest or grant.proposal_digest != report.proposal_digest:
            raise ProgramError("evolution_approval_invalid", "Approval must bind the exact evaluation and proposal")
        if not grant.issued_at <= time.time() < grant.expires_at:
            raise ProgramError("evolution_approval_expired", "Obtain a current compiler selection approval")
        if not report.accepted or report.compiler is None or report.compiler.core_digest != compiler_core_digest():
            raise ProgramError("evolution_unaccepted", "Reevaluate the candidate with the current fixed core")
        current = self.store.reference("compiler.active", CompilerIdentity)
        if current is None or current.digest != grant.seed_digest:
            raise ProgramError("compiler_selection_conflict", "The selected compiler changed after evaluation")
        self.store.set_reference("compiler.active", current.digest, report.compiler,
                                 events=[("compiler", ProgramEvent(kind="compiler_selected", object_id=report.compiler.digest, detail=grant.digest))])
        return report.compiler
