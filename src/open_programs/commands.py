"""CLI commands for persistent Open Programs and exact workspace approvals."""

from __future__ import annotations

import argparse
import json
import time
from contextlib import nullcontext
from pathlib import Path

from pydantic import ValidationError

from .cli import _failure
from .compiler import OpenCompiler
from .controller import RuntimeController
from .environment import load_environment, model_provider
from .evidence import current_evidence, evaluate_policy, validate_evidence
from .executor import OCIExecutor
from .model import ApprovalState, BuildArtifact, PatchProposal, ProgramError, ProgramRevision, ResolutionBudget, RuntimeActivity, RuntimeHead, content_digest
from .operations import ProgramSession
from .reuse import CapsuleOrigin, export_capsule, read_capsule, write_capsule
from .store import ProgramStore
from .workspace import WorkspaceManager


def add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--environment")
    parser.add_argument("--state", default=".nexa/open-programs.sqlite3")
    parser.add_argument("--docker-context")
    parser.add_argument("--program-id")
    parser.add_argument("--goal")
    parser.add_argument("--capsule", default="", help="Explicitly select an imported capsule digest")
    parser.add_argument("--input", help="JSON file containing named goal inputs")
    parser.add_argument("--repository")
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--request")
    parser.add_argument("--event", default="change_request")
    parser.add_argument("--expected-revision")
    parser.add_argument("--locked", action="store_true")
    parser.add_argument("--lock")
    parser.add_argument("--max-model-calls", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=20000)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--json", action="store_true")


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("open", help="Manage persistent Open Programs, evidence and workspace applications")
    commands = parser.add_subparsers(dest="open_command", required=True)
    for name in ("approve", "apply", "recover", "evidence"):
        command = commands.add_parser(name)
        command.add_argument("proposal_id")
        command.add_argument("--state", default=".nexa/open-programs.sqlite3")
        if name == "approve":
            command.add_argument("--actor", required=True)
            command.add_argument("--expires-in", type=float, default=3600)
        if name in {"apply", "evidence"}:
            command.add_argument("--environment", required=True)
        if name == "apply":
            command.add_argument("--grant", required=True)
            command.add_argument("--resume", action="store_true")
    status = commands.add_parser("status")
    status.add_argument("program_id")
    status.add_argument("--state", default=".nexa/open-programs.sqlite3")
    for name in ("resume", "cancel"):
        command = commands.add_parser(name)
        command.add_argument("object_id")
        command.add_argument("--state", default=".nexa/open-programs.sqlite3")
        command.add_argument("--environment", required=True)
    migrate = commands.add_parser("migrate", help="Archive a 2.4 checkpoint into a new 3.0 database")
    migrate.add_argument("source")
    migrate.add_argument("--target", required=True)
    schema = commands.add_parser("schema", help="Print an installed 3.0 JSON schema")
    schema.add_argument("name")
    _compiler_arguments(commands)
    revise = commands.add_parser("revise")
    revise.add_argument("file")
    add_run_arguments(revise)
    capsule = commands.add_parser("capsule")
    actions = capsule.add_subparsers(dest="capsule_command", required=True)
    for name in ("import", "export"):
        command = actions.add_parser(name)
        command.add_argument("path")
        command.add_argument("--state", default=".nexa/open-programs.sqlite3")
        if name == "export":
            command.add_argument("--activity", required=True)
            command.add_argument("--source", required=True)
            command.add_argument("--creator", required=True)
            command.add_argument("--license", required=True)


def run_file(args: argparse.Namespace, *, activate_only: bool = False) -> int:
    try:
        if not args.environment:
            raise ProgramError("environment_required", "Open Programs execution requires --environment")
        environment = load_environment(Path(args.environment))
        budget = ResolutionBudget(max_model_calls=args.max_model_calls, max_tokens=args.max_tokens, timeout_seconds=args.timeout)
        deadline = time.monotonic() + budget.timeout_seconds
        if args.locked:
            budget = budget.model_copy(update={"max_model_calls": 0})
        with nullcontext(None) if args.locked else model_provider(environment) as provider:
            compiler = OpenCompiler(environment, ProgramStore(Path(args.state)), executor=OCIExecutor(context=args.docker_context), provider=provider)
            session = ProgramSession(compiler)
            head = session.activate(Path(args.file), program_id=args.program_id or Path(args.file).stem, expected_revision=args.expected_revision,
                                    locked=args.locked, lock_path=Path(args.lock) if args.lock else None, budget=budget)
            if activate_only:
                print(head.model_dump_json())
                return 0
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProgramError("resolution_timeout", "Command deadline exhausted during compilation")
            artifact = compiler.store.get(head.artifact_digest, BuildArtifact)
            calls = 0 if args.locked else sum(result.model_calls for result in artifact.results)
            tokens = 0 if args.locked else sum(result.input_tokens + result.output_tokens for result in artifact.results)
            budget = budget.model_copy(update={"max_model_calls": max(0, budget.max_model_calls - calls) if tokens < budget.max_tokens else 0,
                                                "max_tokens": max(1, budget.max_tokens - tokens), "timeout_seconds": remaining})
            return _execute(args, session, head, budget)
    except (ProgramError, OSError, ValidationError) as error:
        return _failure(error, json_output=True)


def _execute(args: argparse.Namespace, session: ProgramSession, head: RuntimeHead, budget: ResolutionBudget) -> int:
    if args.repository:
        if not args.include or not args.request:
            raise ProgramError("maintenance_input", "Repository events require --include paths and --request text")
        activity, result, patch = session.maintain(head.program_id, Path(args.repository), args.include, args.request, event=args.event, budget=budget,
                                                 capsule_digest=args.capsule)
        output = {"status": "awaiting_approval" if patch else result.status, "activity_id": activity, "revision": head.revision,
                  "proposal_id": patch.digest if patch else None, "diff": patch.diff if patch else None, "result": result.model_dump(mode="json")}
    else:
        if not args.goal:
            raise ProgramError("goal_required", "Select --goal or a --repository maintenance event")
        inputs = Path(args.input).read_text(encoding="utf-8") if args.input else "{}"
        activity, result = session.run_goal(head.program_id, args.goal, inputs=inputs, budget=budget, capsule_digest=args.capsule)
        output = {"status": result.status, "activity_id": activity, "revision": head.revision, "result": result.model_dump(mode="json")}
    print(json.dumps(output, ensure_ascii=False))
    return 0 if result.status == "accepted" else 1


def dispatch(args: argparse.Namespace) -> int:
    if args.open_command == "revise":
        return run_file(args, activate_only=True)
    try:
        if args.open_command == "migrate":
            from .migration import migrate_checkpoint
            report = migrate_checkpoint(Path(args.source), Path(args.target))
            print(report.model_dump_json())
            return 1 if report.errors else 0
        if args.open_command == "schema":
            from .schemas import schema_for
            print(json.dumps(schema_for(args.name)))
            return 0
        store = ProgramStore(Path(args.state))
        if args.open_command == "compiler":
            return _compiler_command(args, store)
        if args.open_command in {"resume", "cancel"}:
            runtime = RuntimeController(OpenCompiler(load_environment(Path(args.environment)), store, executor=OCIExecutor()))
            result = runtime.resume(args.object_id) if args.open_command == "resume" else runtime.cancel(args.object_id)
            print(result.model_dump_json())
            return 0
        if args.open_command == "capsule":
            return _capsule(args, store)
        if args.open_command == "status":
            status = store.reference("runtime:" + content_digest(args.program_id), RuntimeHead)
            if status is None:
                raise ProgramError("program_inactive", args.program_id)
            print(status.model_dump_json())
            return 0
        proposal = store.get(args.proposal_id, PatchProposal)
        manager = WorkspaceManager(store)
        if args.open_command == "approve":
            grant = manager.approve(proposal, actor=args.actor, expires_at=time.time() + args.expires_in)
            print(json.dumps({"grant_id": grant.digest, "grant": grant.model_dump(mode="json")}, ensure_ascii=False))
            return 0
        if args.open_command == "recover":
            print(manager.recover(proposal).model_dump_json())
            return 0
        environment = load_environment(Path(args.environment))
        session = ProgramSession(OpenCompiler(environment, store, executor=OCIExecutor()))
        if args.open_command == "evidence":
            policy, context = session.current_patch_context(proposal)
            records = current_evidence(store, list(proposal.evidence), context)
            print(json.dumps({"admission": evaluate_policy(policy, records, context).model_dump(mode="json"),
                              "evidence": [{"record": record.model_dump(mode="json"), "validity": validate_evidence(record, context).model_dump(mode="json")}
                                           for record in records]}, ensure_ascii=False))
            return 0
        registered = store.reference("approval:" + args.grant, ApprovalState)
        if registered is None:
            raise ProgramError("approval_invalid", "Unknown grant")
        result = session.apply(proposal, registered.grant, resume=args.resume)
        print(result.model_dump_json())
        return 0 if result.state == "applied" else 1
    except (ProgramError, OSError, ValidationError) as error:
        return _failure(error, json_output=True)


def _capsule(args: argparse.Namespace, store: ProgramStore) -> int:
    if args.capsule_command == "import":
        capsule = read_capsule(Path(args.path))
    else:
        activity = store.reference("runtime.activity:" + args.activity, RuntimeActivity)
        if activity is None or activity.result is None:
            raise ProgramError("activity_missing", "Export requires a completed activity")
        revision = store.get(activity.revision, ProgramRevision)
        goal = next(goal for goal in revision.program.goals if goal.name == activity.goal)
        result = activity.result
        if result.context is not None:
            records = current_evidence(store, list(result.evidence), result.context)
            result = result.model_copy(update={"evidence": tuple(records)})
        capsule = export_capsule(goal, result, CapsuleOrigin(source=args.source, creator=args.creator, license=args.license))
        write_capsule(capsule, Path(args.path))
    store.put(capsule)
    print(json.dumps({"capsule_id": capsule.digest, "goal": capsule.goal.name, "origin": capsule.origin.model_dump(mode="json")}))
    return 0


def _compiler_arguments(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = commands.add_parser("compiler", help="Select an independently evaluated diagnostic compiler pass")
    actions = parser.add_subparsers(dest="compiler_command", required=True)
    for name in ("init", "status", "approve", "select", "check"):
        command = actions.add_parser(name)
        command.add_argument("--state", default=".nexa/open-programs.sqlite3")
        if name in {"init", "check"}:
            command.add_argument("file")
        if name in {"approve", "select"}:
            command.add_argument("report_id")
        if name == "approve":
            command.add_argument("--actor", required=True)
        if name == "select":
            command.add_argument("--grant", required=True)
        if name == "check":
            command.add_argument("--environment", required=True)
            command.add_argument("--docker-context")


def _compiler_command(args: argparse.Namespace, store: ProgramStore) -> int:
    from .evolution import AdvisoryCompiler, CompilerIdentity, EvolutionApproval, EvolutionManager, EvolutionReport

    manager = EvolutionManager(store)
    if args.compiler_command == "init":
        seed = CompilerIdentity.model_validate_json(Path(args.file).read_text())
        manager.initialize(seed)
        print(seed.model_dump_json())
        return 0
    if args.compiler_command in {"approve", "select"}:
        report = store.get(args.report_id, EvolutionReport)
        if args.compiler_command == "approve":
            grant = manager.approve(report, actor=args.actor)
            print(json.dumps({"grant_id": grant.digest, "grant": grant.model_dump(mode="json")}))
        else:
            grant = store.reference("evolution.approval:" + args.grant, EvolutionApproval)
            if grant is None:
                raise ProgramError("evolution_approval_invalid", "Unknown compiler selection approval")
            print(manager.select(report, grant).model_dump_json())
        return 0
    identity = store.reference("compiler.active", CompilerIdentity)
    if identity is None:
        raise ProgramError("compiler_unselected", "Initialize a seed compiler first")
    if args.compiler_command == "status":
        print(identity.model_dump_json())
        return 0
    compiler = OpenCompiler(load_environment(Path(args.environment)), store, executor=OCIExecutor(context=args.docker_context))
    report = AdvisoryCompiler(compiler, identity).check(Path(args.file).read_text(encoding="utf-8"), path=args.file)
    print(report.model_dump_json())
    return 0 if report.check.ok else 1
