"""Bounded comparison of 2.4 AgentRunner and Open Programs on frozen fixtures."""
from __future__ import annotations

import argparse
import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

from src.open_programs.compiler import OpenCompiler
from src.open_programs.environment import load_environment, model_provider
from src.open_programs.executor import OCIExecutor
from src.open_programs.model import (
    Candidate,
    CompilerEnvironment,
    ExecutionSpec,
    GoalSpec,
    Implementation,
    PatchValue,
    ProgramError,
    ProgramRevision,
    RepositoryCase,
    RepositoryCheck,
    ResolutionBudget,
    ResolutionResult,
    canonical_json,
    content_digest,
)
from src.open_programs.operations import ProgramSession
from src.open_programs.reuse import CapsuleOrigin, export_capsule
from src.open_programs.store import ProgramStore
from src.open_programs.workspace import WorkspaceManager, snapshot_workspace
from src.runtime.agent_runner import AgentRunner
from src.runtime.providers import ModelProvider, ModelReply, ModelRequest
from src.runtime.run_state import RunConfig, RunContext, RunState
from src.runtime.tool_dispatch import ToolDispatcher


class UsageMeter:
    def __init__(self, calls: int, tokens: int) -> None:
        self.max_calls, self.max_tokens = calls, tokens
        self.calls = self.input_tokens = self.output_tokens = 0
        self.lock = threading.Lock()


class MeteredProvider:
    name = "chat"

    def __init__(self, provider: ModelProvider, meter: UsageMeter, *, feedback: bool) -> None:
        self.provider, self.meter, self.feedback = provider, meter, feedback

    def complete(self, request: ModelRequest, on_text: Callable[[str], None] | None = None) -> ModelReply:
        with self.meter.lock:
            if self.meter.calls >= self.meter.max_calls or self.meter.input_tokens + self.meter.output_tokens >= self.meter.max_tokens:
                raise ProgramError("experiment_budget", "Global experiment budget reached")
            self.meter.calls += 1
        if not self.feedback and len(request.messages) == 1:
            prefix, _, payload = request.messages[0]["content"].partition("\n")
            body = json.loads(payload)
            if body.get("operation") == "implement":
                body["feedback"] = ""
                request = replace(request, messages=[{"role": "user", "content": prefix + "\n" + canonical_json(body)}])
        reply = self.provider.complete(request, on_text)
        with self.meter.lock:
            self.meter.input_tokens += reply.input_tokens
            self.meter.output_tokens += reply.output_tokens
        return reply


def _source(requirement: str) -> str:
    intent = ("Modify worker.py to implement transform(value). " + requirement + " Use Python standard library only. Preserve settings.py. "
              "Provide a reusable Python solve(inputs) that returns a Patch with base_digest=inputs.repository_digest and changes containing path, "
              "before_digest=inputs.file_digests[path], and complete new file content. Inputs.repository.files contains selected source. "
              "Read current hashes from inputs; never hardcode a particular workspace's hashes.")
    review = "The resulting transform implements the requested behavior; scope is worker.py, and current snapshot hashes are read from input."
    return ('language "3.0" program Fixture(repo: Repository) { goal repair(change: ChangeRequest) -> Patch { stage runtime intent ' + json.dumps(intent)
            + ' capabilities [repo.read, sandbox.exec, sandbox.write] context repo.snapshot ensure checks.regression review model(' + json.dumps(review)
            + ') implementation open } on change_request as request { let result = resolve repair(request) propose repo.apply(result) requires human.approval } }')


def _checks(stage: dict) -> RepositoryCheck:
    command = "import json,sys; from worker import transform; print(json.dumps(transform(json.load(sys.stdin)), sort_keys=True, separators=(',', ':')))"
    return RepositoryCheck(name="checks.regression", cases=tuple(RepositoryCase(argv=("python", "-c", command), input_text=canonical_json(case["input"]),
                                                                               expected_output=canonical_json(case["expected"]) + "\n") for case in stage["checks"]))


def _inputs(repository: Path, description: str) -> str:
    base = snapshot_workspace(repository, ["worker.py", "settings.py"])
    return canonical_json({"change": {"description": description}, "repository": base.model_dump(mode="json"), "repository_digest": base.digest,
                           "file_digests": {item.path: item.digest for item in base.files}})


def _legacy(compiler: OpenCompiler, goal: GoalSpec, inputs: str, budget: ResolutionBudget) -> ResolutionResult:
    assert compiler.provider is not None
    calls = input_tokens = output_tokens = 0
    deadline = time.monotonic() + budget.timeout_seconds
    feedback = ""
    result = ResolutionResult(status="blocked", goal_name=goal.name, reason="model_call_budget")
    while calls < budget.max_model_calls and input_tokens + output_tokens < budget.max_tokens and time.monotonic() < deadline:
        schema = {"type": "object", "properties": {"kind": {"const": "python"}, "body": {"type": "string"}}, "required": ["kind", "body"], "additionalProperties": False}
        prompt = canonical_json({"goal": goal.intent, "inputs": json.loads(inputs), "feedback": feedback,
                                 "output_contract": PatchValue.model_json_schema(),
                                 "instructions": "Return a JSON object with kind=python and body=Python source defining solve(inputs). "
                                                 "The solve function must return the goal value directly, never another implementation wrapper. "
                                                 "Its return value must satisfy output_contract."})
        state = RunState(model=compiler.environment.model, messages=[{"role": "user", "content": prompt}])
        limits = RunConfig(timeout=max(.01, deadline - time.monotonic()), max_model_calls=1, max_tool_calls=0,
                           max_tokens=max(1, budget.max_tokens - input_tokens - output_tokens), retries=0)
        runner = AgentRunner(RunContext(state, limits), compiler.provider, ToolDispatcher([]), validate_output=Implementation.model_validate_json,
                             max_output_tokens=4096, response_format={"type": "json_schema", "json_schema": {"name": "implementation", "strict": True, "schema": schema}})
        generated = runner.run()
        calls += generated.model_calls
        input_tokens += generated.input_tokens
        output_tokens += generated.output_tokens
        if not generated.success:
            result = ResolutionResult(status="blocked", goal_name=goal.name, reason=generated.status.value)
            break
        candidate = Candidate(goal_digest=goal.digest, implementation=Implementation.model_validate_json(generated.output), capabilities=goal.capabilities,
                              dependencies=compiler.environment.dependencies, origin="2.4.AgentRunner")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        available = budget.model_copy(update={"max_model_calls": max(0, budget.max_model_calls - calls),
                                              "max_tokens": max(1, budget.max_tokens - input_tokens - output_tokens), "timeout_seconds": remaining})
        result = compiler.resolve_goal(goal, input_json=inputs, candidate=candidate, budget=available)
        calls += result.model_calls
        input_tokens += result.input_tokens
        output_tokens += result.output_tokens
        if result.status == "accepted":
            break
        feedback = result.reason
    return result.model_copy(update={"model_calls": calls, "input_tokens": input_tokens, "output_tokens": output_tokens})


def _counterfactual(candidate: Candidate, inputs: str, compiler: OpenCompiler, checker: RepositoryCheck) -> bool:
    """Would assuming yesterday's passing checks accept a failing result today?"""
    values = json.loads(inputs)
    from src.open_programs.model import WorkspaceSnapshot
    spec = ExecutionSpec(image=compiler.environment.image, return_type="Patch", input_json=inputs)
    try:
        output = compiler.executor.execute_candidate(candidate, spec)
        if not output.succeeded:
            return True
        patch = PatchValue.model_validate_json(output.output_json)
        base = WorkspaceSnapshot.model_validate(values["repository"])
        for case in checker.cases:
            report = compiler.executor.execute_repository(base, patch, case, spec)
            if report.error or report.exit_code != case.expected_exit or report.output != case.expected_output:
                return True
    except (ValueError, ProgramError):
        return True
    return False


def run_sequence(root: Path, task: dict, variant: str, trial: int, environment: CompilerEnvironment, meter: UsageMeter, budget: ResolutionBudget) -> list[dict]:
    folder = root / f'{task["id"]}-{variant}-{trial}'
    folder.mkdir()
    repository = folder / "repository"
    repository.mkdir()
    for name, content in task["initial_files"].items():
        (repository / name).write_text(content)
    rows: list[dict] = []
    capsule = None
    previous_result = None
    revision = None
    with model_provider(environment) as provider:
        if provider is None:
            raise ProgramError("model_unavailable", "Experiment requires a configured provider")
        measured = MeteredProvider(provider, meter, feedback=variant != "no_feedback")
        for index, stage in enumerate(task["stages"]):
            started = time.monotonic()
            row = {"task": task["id"], "split": task["split"], "variant": variant, "trial": trial, "stage": stage["name"], "status": "failed"}
            try:
                (repository / "settings.py").write_text(stage["settings"])
                checker = _checks(stage)
                current = environment.model_copy(update={"checks": (checker,)})
                compiler = OpenCompiler(current, ProgramStore(folder / "state.db"), executor=OCIExecutor(), provider=measured)
                session = ProgramSession(compiler)
                source = folder / "maintain.nx"
                source.write_text(_source(stage["requirement"]))
                head = session.activate(source, program_id=task["id"], expected_revision=revision, budget=budget)
                revision = head.revision
                goal = compiler.store.get(revision, ProgramRevision).program.goals[0]
                inputs = _inputs(repository, stage["requirement"])
                before = {str(path.relative_to(repository)): path.read_text() for path in repository.rglob("*") if path.is_file()}
                if previous_result and previous_result.status == "accepted" and previous_result.candidate and variant == "open_programs":
                    row["untracked_evidence_false_acceptance"] = _counterfactual(previous_result.candidate, inputs, compiler, checker)
                selected = capsule if capsule and capsule.goal.digest == goal.digest and variant in {"open_programs", "no_feedback"} else None
                if variant == "legacy_2_4":
                    result = _legacy(compiler, goal, inputs, budget)
                else:
                    _, result = session.run_goal(task["id"], goal.name, inputs=inputs, budget=budget, capsule_digest=selected.digest if selected else "")
                row.update(status=result.status, reason=result.reason, model_calls=result.model_calls, input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                           revision=revision, candidate=result.candidate.digest if result.candidate else None, reuse_selected=selected is not None,
                           evidence_records=len(result.evidence), required_checks_passed=all(record.passed for record in result.evidence))
                if result.status == "accepted":
                    manager = WorkspaceManager(compiler.store)
                    patch = manager.prepare_patch(snapshot_workspace(repository, ["worker.py", "settings.py"]), result)
                    row["unauthorized_writes"] = int(before != {str(path.relative_to(repository)): path.read_text() for path in repository.rglob("*") if path.is_file()})
                    grant = manager.approve(patch, actor="benchmark-fixture-operator")
                    assert result.policy is not None and result.context is not None
                    row["application"] = manager.apply_patch(patch, grant, context=result.context, policy=result.policy).state
                    capsule = export_capsule(goal, result, CapsuleOrigin(source="benchmark/" + task["id"], creator="benchmark-model", license="AGPL-3.0-or-later"))
                    compiler.store.put(capsule)
                previous_result = result
                (folder / (str(index) + "-result.json")).write_text(result.model_dump_json(indent=2))
            except Exception as error:  # noqa: BLE001 - Each experiment cell persists its sanitized failure and the matrix continues.
                row.update(status="failed", reason=error.code if isinstance(error, ProgramError) else type(error).__name__)
            row["elapsed_seconds"] = round(time.monotonic() - started, 3)
            rows.append(row)
            (folder / "rows.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=3)
    parser.add_argument("--limit-tasks", type=int)
    parser.add_argument("--trials", type=int)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    environment = load_environment(args.environment)
    if environment.image != manifest["image"]:
        raise ProgramError("manifest_environment", "Use the pinned experiment image")
    args.output.mkdir(parents=True, exist_ok=False)
    meter = UsageMeter(manifest["global_budget"]["max_model_calls"], manifest["global_budget"]["max_reported_tokens"])
    budget = ResolutionBudget.model_validate(manifest["budget"])
    tasks = manifest["tasks"][:args.limit_tasks] if args.limit_tasks else manifest["tasks"]
    trials = args.trials or manifest["trials"]
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    source_root = Path(__file__).resolve().parents[2]
    sources = [*sorted((source_root / "src/open_programs").glob("*.py")), *sorted(Path(__file__).parent.glob("*.py")),
               source_root / "src/runtime/agent_runner.py", source_root / "src/runtime/providers.py"]
    snapshot = {str(path.relative_to(source_root)): content_digest(path.read_text()) for path in sources}
    (args.output / "source-snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_sequence, args.output, task, variant, trial, environment, meter, budget)
                   for task in tasks for variant in manifest["variants"] for trial in range(trials)]
        for future in as_completed(futures):
            rows.extend(future.result())
            summary = {"source_snapshot_digest": content_digest(snapshot), "manifest_digest": content_digest(manifest), "environment": environment.digest, "model": environment.model,
                       "completed_cells": len(rows), "model_calls": meter.calls, "input_tokens": meter.input_tokens, "output_tokens": meter.output_tokens,
                       "price_basis": None, "cost": None, "rows": rows}
            (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(json.dumps({key: value for key, value in summary.items() if key != "rows"}), flush=True)


if __name__ == "__main__":
    main()
