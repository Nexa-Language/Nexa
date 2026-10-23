"""Shared application operations for CLI and author clients."""

from __future__ import annotations

import time
from pathlib import Path

from .compiler import OpenCompiler
from .controller import RuntimeController
from .frontend import check
from .model import (
    AcceptancePolicy,
    ApplyResult,
    ApprovalGrant,
    ContextSnapshot,
    Dependency,
    FrozenModel,
    PatchProposal,
    ProgramError,
    ProgramEvent,
    ProgramRevision,
    ResolutionBudget,
    ResolutionResult,
    RuntimeHead,
    SourceBundle,
    canonical_json,
)
from .workspace import WorkspaceManager, snapshot_workspace


class PatchBinding(FrozenModel):
    proposal_digest: str
    program_id: str
    revision: str
    activity_id: str
    goal: str
    policy: AcceptancePolicy
    context: ContextSnapshot


class ProgramSession:
    def __init__(self, compiler: OpenCompiler) -> None:
        self.compiler = compiler
        self.store = compiler.store
        self.runtime = RuntimeController(compiler)
        self.workspace = WorkspaceManager(self.store)

    def activate(self, source: Path, *, program_id: str, expected_revision: str | None = None,
                 locked: bool = False, lock_path: Path | None = None, budget: ResolutionBudget | None = None) -> RuntimeHead:
        report = check(SourceBundle(text=source.read_text(encoding="utf-8"), path=str(source)))
        if not report.ok or report.program is None:
            raise ProgramError("source_invalid", "; ".join(f"{item.code}@{item.span.line}:{item.span.column}" for item in report.diagnostics))
        previous = self.store.current_revision(program_id)
        environment = self.compiler.environment.digest
        if previous and previous.program.digest == report.program.digest and previous.environment_digest == environment:
            revision = previous
        else:
            if (previous.digest if previous else None) != expected_revision:
                raise ProgramError("revision_conflict", "Supply --expected-revision for the current source revision")
            revision = ProgramRevision(program_id=program_id, parent=expected_revision, program=report.program, environment_digest=environment)
        artifact = self.compiler.build(report.program, lock_path=lock_path or source.with_suffix(".nx.lock"), locked=locked, budget=budget)
        if revision != previous:
            self.store.commit_revision(expected_revision, revision, [ProgramEvent(kind="source_compiled", object_id=revision.digest)])
        try:
            active = self.runtime.status(program_id)
        except ProgramError as error:
            if error.code != "program_inactive":
                raise
            active = None
        if active and active.revision == revision.digest and active.artifact_digest == artifact.digest:
            return active
        proposal = self.runtime.propose_revision(active.revision if active else None, revision, artifact)
        return self.runtime.activate_revision(proposal, self.runtime.checkpoint(program_id) if active else None)

    def run_goal(self, program_id: str, goal: str, *, inputs: str = "{}", budget: ResolutionBudget | None = None,
                 capsule_digest: str = "") -> tuple[str, ResolutionResult]:
        activity = self.runtime.start_activity(program_id, goal, input_json=inputs, capsule_digest=capsule_digest)
        result = self.runtime.resolve_activity(activity.activity_id, budget=budget)
        return activity.activity_id, result

    def maintain(self, program_id: str, repository: Path, paths: list[str], request: str, *, event: str = "change_request",
                 budget: ResolutionBudget | None = None, capsule_digest: str = "") -> tuple[str, ResolutionResult, PatchProposal | None]:
        head = self.runtime.status(program_id)
        revision = self.store.get(head.revision, ProgramRevision)
        handlers = [handler for handler in revision.program.handlers if handler.event == event]
        if len(handlers) != 1:
            raise ProgramError("event_ambiguous", "Select an event with exactly one maintenance handler")
        goal = next(goal for goal in revision.program.goals if goal.name == handlers[0].goal)
        if "repo.read" not in goal.capabilities or "repo.read" not in self.compiler.environment.capabilities:
            raise ProgramError("capability_denied", "Maintenance requires repo.read in both the goal and compiler environment before reading any file")
        snapshot = snapshot_workspace(repository, paths)
        inputs = {goal.parameters[0].name: {"description": request}, "repository": snapshot.model_dump(mode="json"), "repository_digest": snapshot.digest,
                  "file_digests": {file.path: file.digest if file.content is not None else None for file in snapshot.files}}
        activity_id, result = self.run_goal(program_id, goal.name, inputs=canonical_json(inputs), budget=budget, capsule_digest=capsule_digest)
        if result.status != "accepted":
            return activity_id, result, None
        patch = self.workspace.prepare_patch(snapshot, result)
        assert result.policy is not None and result.context is not None
        binding = PatchBinding(proposal_digest=patch.digest, program_id=program_id, revision=head.revision, activity_id=activity_id,
                               goal=goal.name, policy=result.policy, context=result.context)
        self.store.set_reference("patch.binding:" + patch.digest, None, binding)
        return activity_id, result, patch

    def current_patch_context(self, proposal: PatchProposal) -> tuple[AcceptancePolicy, ContextSnapshot]:
        binding = self.store.reference("patch.binding:" + proposal.digest, PatchBinding)
        if binding is None:
            raise ProgramError("patch_binding_missing", "Patch has no runtime source binding")
        head = self.runtime.status(binding.program_id)
        if head.revision != binding.revision:
            raise ProgramError("evidence_stale", "The active program revision changed after this proposal")
        revision = self.store.get(head.revision, ProgramRevision)
        goal = next(goal for goal in revision.program.goals if goal.name == binding.goal)
        policy = self.compiler.policy_for(goal)
        replacements = {"goal": goal.digest, "environment": self.compiler.environment.digest}
        replacements.update({item.name: item.digest for item in self.compiler.environment.dependencies})
        dependencies = tuple(Dependency(name=item.name, digest=replacements.get(item.name, item.digest)) for item in binding.context.dependencies)
        return policy, binding.context.model_copy(update={"now": time.time(), "policy_digest": policy.digest, "dependencies": dependencies})

    def apply(self, proposal: PatchProposal, grant: ApprovalGrant, *, resume: bool = False) -> ApplyResult:
        binding = self.store.reference("patch.binding:" + proposal.digest, PatchBinding)
        if binding is None:
            raise ProgramError("patch_binding_missing", "Patch has no runtime source binding")
        with self.store.lease(self.runtime._head_ref(binding.program_id)):
            if self.runtime.effects.pending(binding.program_id):
                raise ProgramError("pending_effect", "Reconcile external operations before applying a patch")
            policy, context = self.current_patch_context(proposal)
            return self.workspace.apply_patch(proposal, grant, context=context, policy=policy, resume=resume)
