"""Six-stage local maintenance demonstration; each invocation creates new fixtures."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from src.open_programs.compiler import OpenCompiler
from src.open_programs.environment import load_environment, model_provider
from src.open_programs.evolution import CompilerIdentity, EvolutionManager, EvolutionProposal, SemanticSuite, compiler_core_digest, evaluate_evolution
from src.open_programs.executor import OCIExecutor
from src.open_programs.frontend import check
from src.open_programs.model import (
    Candidate,
    CheckCase,
    CompilerEnvironment,
    Dependency,
    Implementation,
    OutputCheck,
    ProgramError,
    ProgramRevision,
    RepositoryCase,
    RepositoryCheck,
    ResolutionBudget,
    ResolutionResult,
    SourceBundle,
    canonical_json,
    content_digest,
)
from src.open_programs.operations import ProgramSession
from src.open_programs.protocol import AuthorActivity, AuthorProtocol
from src.open_programs.reuse import CapsuleOrigin, export_capsule, match_capsule, read_capsule, write_capsule
from src.open_programs.store import ProgramStore
from src.runtime.providers import ModelProvider, ModelReply, ModelRequest

ROOT = Path(__file__).resolve().parents[2]
BUDGET = ResolutionBudget(max_model_calls=4, max_tokens=16000, timeout_seconds=90)


class RecordedProvider:
    """Bound total real calls and retain fixture-only replies for offline replay."""
    name = "recorded"

    def __init__(self, provider: ModelProvider | None = None, replies: list[ModelReply] | None = None) -> None:
        self.provider = provider
        self.replies = list(replies or [])
        self.observed: list[ModelReply] = []
        self.calls = 0

    def complete(self, request: ModelRequest, on_text: Callable[[str], None] | None = None) -> ModelReply:
        if self.calls >= 24 or sum(reply.input_tokens + reply.output_tokens for reply in self.observed) >= 120000:
            raise ProgramError("demo_budget", "Flagship session budget exhausted")
        self.calls += 1
        if self.provider:
            reply = self.provider.complete(request, on_text)
        elif self.replies:
            reply = self.replies.pop(0)
        else:
            raise ProgramError("replay_exhausted", "No recorded response remains")
        self.observed.append(reply)
        return reply


def summarize(result: ResolutionResult) -> dict[str, object]:
    return {"status": result.status, "reason": result.reason, "candidate": result.candidate.digest if result.candidate else None,
            "model_calls": result.model_calls, "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
            "checks": [{"kind": record.kind, "passed": record.passed, "digest": record.digest} for record in result.evidence]}


def _rpc(service: AuthorProtocol, method: str, params: dict[str, object]) -> dict:
    response = service.handle({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if response is None or "error" in response:
        raise ProgramError("demo_protocol_failed", method)
    result = response["result"]
    if not isinstance(result, dict):
        raise ProgramError("demo_protocol_failed", "Expected an object response")
    return result


def _clarify(source: Path, compiler: OpenCompiler, repository: Path) -> str:
    from src.open_programs.workspace import snapshot_workspace

    text = source.read_text()
    report = check(SourceBundle(text=text))
    assert report.program is not None
    original = report.program.goals[0].intent
    ambiguous = original + " Before implementation, ask the author whether None inputs should be rejected or treated as zero, unless Author clarification is already present."
    text = text.replace(json.dumps(original), json.dumps(ambiguous))
    snapshot = snapshot_workspace(repository, ["calc.py", "precision.py"])
    inputs = {"change": {"description": "Fix addition; the None-input policy needs the author's decision."}, "repository": snapshot.model_dump(mode="json"),
              "repository_digest": snapshot.digest, "file_digests": {item.path: item.digest for item in snapshot.files}}
    service = AuthorProtocol(compiler.store, compiler)
    try:
        _rpc(service, "initialize", {"protocol_version": "3.0", "client": "flagship-author-agent"})
        revision = _rpc(service, "revision/propose", {"program_id": "flagship", "source": text, "expected_revision": None})["revision"]
        activity = _rpc(service, "goal/resolve", {"program_id": "flagship", "expected_revision": revision, "goal": "repair", "input_json": canonical_json(inputs),
                                                "budget": BUDGET.model_dump(mode="json")})["activity_id"]
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            record = compiler.store.reference("activity:" + activity, AuthorActivity)
            if record is not None and record.state != "running":
                break
            time.sleep(.05)
        else:
            raise ProgramError("demo_timeout", "Author clarification timed out")
        if record is None or not record.request_id:
            raise ProgramError("demo_clarification_missing", "The ambiguous fixture did not produce a clarification")
        answered = _rpc(service, "author/answer", {"program_id": "flagship", "expected_revision": revision, "request_id": record.request_id,
                                                "answer": "Reject None inputs with TypeError; ordinary numeric inputs use addition."})["revision"]
        updated = compiler.store.get(answered, ProgramRevision)
        source.write_text(text.replace(json.dumps(ambiguous), json.dumps(updated.program.goals[0].intent)))
        return answered
    finally:
        service.close()


def _maintain(session: ProgramSession, repository: Path, request: str, *, capsule: str = "") -> tuple[str, ResolutionResult, dict[str, object]]:
    before = {str(path.relative_to(repository)): path.read_text() for path in repository.rglob("*") if path.is_file()}
    activity, result, patch = session.maintain("flagship", repository, ["calc.py", "precision.py"], request, budget=BUDGET, capsule_digest=capsule)
    unchanged = before == {str(path.relative_to(repository)): path.read_text() for path in repository.rglob("*") if path.is_file()}
    summary = {**summarize(result), "activity": activity, "host_unchanged_before_approval": unchanged}
    if result.status != "accepted" or patch is None or not unchanged:
        raise ProgramError("demo_maintenance_failed", result.reason or "Missing validated patch")
    grant = session.workspace.approve(patch, actor="flagship-fixture-operator")
    applied = session.apply(patch, grant)
    summary.update(proposal=patch.digest, grant=grant.digest, application=applied.state)
    return activity, result, summary


def compiler_evolution(root: Path, environment: CompilerEnvironment, provider: ModelProvider) -> dict[str, object]:
    cases = (CheckCase(input_json='{"diagnostics":[{"code":"unknown_goal","message":"unknown_goal: repiar"}],"known_goals":["repair"]}',
                       expected_json='{"suggestions":[{"code":"unknown_goal","replacement":"repair"}]}'),
             CheckCase(input_json='{"diagnostics":[],"known_goals":["repair"]}', expected_json='{"suggestions":[]}'),
             CheckCase(input_json='{"diagnostics":[{"code":"capability_denied","message":"Forbidden"}],"known_goals":["repair"]}', expected_json='{"suggestions":[]}'))
    suite = SemanticSuite(name="diagnostic-advice.v1", cases=cases)
    environment = environment.model_copy(update={"checks": (OutputCheck(name="checks.advice", cases=cases),)})
    compiler = OpenCompiler(environment, ProgramStore(root / "compiler.db"), executor=OCIExecutor(), provider=provider)
    report = check(SourceBundle(text=(ROOT / "examples/open_programs/compiler_pass.nx").read_text()))
    assert report.program is not None
    lock = root / "compiler.lock"
    artifact = compiler.build(report.program, lock_path=lock, budget=BUDGET)
    seed = CompilerIdentity(core_digest=compiler_core_digest(), environment_digest=environment.digest, version="C0",
                            pass_candidate=Candidate(goal_digest="seed", implementation=Implementation(kind="value", body='{"suggestions":[]}')))
    proposal = EvolutionProposal(seed_digest=seed.digest, version="C1", program=report.program, artifact_digest=artifact.digest,
                                 pass_goal="advice", verifier_digest=suite.digest, touched_paths=("diagnostic_advice.py",))
    evaluation = evaluate_evolution(proposal, seed, suite, compiler, lock_path=lock)
    if not evaluation.accepted:
        raise ProgramError("demo_evolution_failed", ",".join(evaluation.reasons))
    manager = EvolutionManager(compiler.store)
    manager.initialize(seed)
    grant = manager.approve(evaluation, actor="flagship-fixture-operator")
    selected = manager.select(evaluation, grant)
    (root / "evolution-report.json").write_text(evaluation.model_dump_json(indent=2) + "\n")
    return {"report": evaluation.digest, "seed_failures": evaluation.seed_failures, "candidate_failures": evaluation.candidate_failures,
            "bootstrap_identical": evaluation.c1_artifact_digest == evaluation.c2_artifact_digest, "bootstrap_generation_requests": evaluation.generation_requests,
            "selected": selected.digest, **summarize(artifact.results[0])}


def run_flagship(root: Path, environment: CompilerEnvironment, provider: RecordedProvider) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=False)
    repository = root / "repository"
    repository.mkdir()
    (repository / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (repository / "precision.py").write_text("DIGITS = 2\n")
    source = root / "maintain.nx"
    source.write_text((ROOT / "examples/open_programs/maintain.nx").read_text())
    compiler = OpenCompiler(environment, ProgramStore(root / "state.db"), executor=OCIExecutor(), provider=provider)
    session = ProgramSession(compiler)
    stages: list[dict[str, object]] = []
    started = time.monotonic()
    summary: dict[str, object] = {"schema_version": 1, "model": environment.model, "environment": environment.digest, "stages": stages}
    try:
        clarified = _clarify(source, compiler, repository)
        head = session.activate(source, program_id="flagship", expected_revision=clarified, budget=BUDGET)
        _, _, first = _maintain(session, repository, "Fix addition and reject None with TypeError.")
        stages.append({"stage": "clarification_and_solve", "revision": head.revision, **first})
        env_path = root / "environment.json"
        config = environment.model_copy(update={"dependencies": tuple(item for item in environment.dependencies if item.name != "provider.endpoint")})
        env_path.write_text(config.model_dump_json(indent=2))
        process = subprocess.run([sys.executable, "-m", "src.cli", "open", "resume", "flagship", "--state", str(compiler.store.path), "--environment", str(env_path)],
                                 capture_output=True, text=True, check=False)
        if process.returncode or json.loads(process.stdout)["revision"] != head.revision:
            raise ProgramError("demo_restart_failed", "The separate controller process did not restore the active revision")
        stages.append({"stage": "approval_and_restart", "revision_preserved": True, "application": first["application"]})
        old_activity = session.runtime.start_activity("flagship", "repair", input_json='{"change":{}}')
        text = source.read_text()
        goal = compiler.store.get(head.revision, ProgramRevision).program.goals[0]
        intent = goal.intent + " New requirement: round numeric results to precision.DIGITS from precision.py; preserve None rejection."
        source.write_text(text.replace(json.dumps(goal.intent), json.dumps(intent)))
        precision_check = RepositoryCase(argv=("python", "-c", "from calc import add; print(add(0.1234, 0.0001))"), expected_output="0.12\n")
        original = environment.checks[0]
        assert isinstance(original, RepositoryCheck)
        updated_env = environment.model_copy(update={"checks": (original.model_copy(update={"cases": (*original.cases, precision_check)}),)})
        session = ProgramSession(OpenCompiler(updated_env, compiler.store, executor=OCIExecutor(), provider=provider))
        revised = session.activate(source, program_id="flagship", expected_revision=head.revision, budget=BUDGET)
        _, second_result, second = _maintain(session, repository, "Round addition using precision.DIGITS, retaining TypeError for None.")
        stages.append({"stage": "goal_revision", "revision": revised.revision, "old_activity_pinned": session.runtime.activity(old_activity.activity_id).revision == head.revision,
                       **second})
        goal = compiler.store.get(revised.revision, ProgramRevision).program.goals[0]
        capsule = export_capsule(goal, second_result, CapsuleOrigin(source="flagship/repository", creator="flagship-model", license="MIT"))
        capsule_path = root / "repair.capsule.json"
        write_capsule(capsule, capsule_path)
        compiler.store.put(read_capsule(capsule_path))
        # A different selected repository instance forces fresh snapshot evidence while preserving implementation conditions.
        another = root / "second-repository"
        another.mkdir()
        (another / "calc.py").write_text("def add(a, b):\n    return a - b\n")
        (another / "precision.py").write_text("DIGITS = 2\n")
        _, reused, reuse_summary = _maintain(session, another, "Round addition using precision.DIGITS, retaining TypeError for None.", capsule=capsule.digest)
        assert second_result.context is not None and second_result.policy is not None
        rejected = match_capsule(capsule, goal.model_copy(update={"return_type": "Int"}), second_result.context, second_result.policy)
        stages.append({"stage": "cross_task_reuse", "capsule": capsule.digest, "same_implementation": reused.candidate == second_result.candidate,
                       "incompatible_task": rejected.status, **reuse_summary})
        (repository / "precision.py").write_text("DIGITS = 3\n")
        drift_check = precision_check.model_copy(update={"expected_output": "0.123\n"})
        changed_env = updated_env.model_copy(update={"checks": (original.model_copy(update={"cases": (*original.cases, drift_check)}),),
                                                   "dependencies": (*updated_env.dependencies, Dependency(name="precision", digest=content_digest("DIGITS = 3\n")))})
        session = ProgramSession(OpenCompiler(changed_env, compiler.store, executor=OCIExecutor(), provider=provider))
        new_head = session.activate(source, program_id="flagship", expected_revision=revised.revision, budget=BUDGET)
        _, _, drift = _maintain(session, repository, "Revalidate against DIGITS=3. Return calc.py with the correct implementation even if its text already matches.")
        stages.append({"stage": "dependency_revision", "revision": new_head.revision, "old_evidence_retained": all(compiler.store.get(record.digest, type(record)) == record for record in second_result.evidence), **drift})
        stages.append({"stage": "compiler_evolution", **compiler_evolution(root, environment, provider)})
        summary["status"] = "passed"
    except Exception as error:  # noqa: BLE001 - Persist a sanitized terminal report at the experiment boundary.
        summary.update(status="failed", error=error.code if isinstance(error, ProgramError) else type(error).__name__)
    summary.update(elapsed_seconds=round(time.monotonic() - started, 3), model_calls=provider.calls,
                   input_tokens=sum(reply.input_tokens for reply in provider.observed), output_tokens=sum(reply.output_tokens for reply in provider.observed))
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    from dataclasses import asdict
    (root / "responses.json").write_text(json.dumps([asdict(reply) for reply in provider.observed], indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    environment = load_environment(args.environment)
    if args.replay:
        replies = [ModelReply(**item) for item in json.loads(args.replay.read_text())]
        summary = run_flagship(args.output, environment, RecordedProvider(replies=replies))
    else:
        with model_provider(environment) as provider:
            summary = run_flagship(args.output, environment, RecordedProvider(provider))
    print(json.dumps(summary))
    raise SystemExit(0 if summary["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
