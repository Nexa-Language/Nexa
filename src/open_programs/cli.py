"""Machine-readable and human-readable Open Programs CLI surfaces."""

from __future__ import annotations

import json
import sys
from contextlib import nullcontext
from pathlib import Path

from pydantic import ValidationError

from .compiler import OpenCompiler
from .environment import load_environment, model_provider
from .executor import OCIExecutor
from .frontend import check
from .model import ProgramError, ResolutionBudget, SourceBundle
from .protocol import AuthorProtocol, serve_stdio
from .store import ProgramStore


def check_file(path: str, *, json_output: bool = False) -> int:
    report = check(SourceBundle(text=Path(path).read_text(encoding="utf-8"), path=path))
    if json_output:
        print(report.model_dump_json())
    else:
        for diagnostic in report.diagnostics:
            print(f"{diagnostic.span.path}:{diagnostic.span.line}:{diagnostic.span.column}: {diagnostic.code}: {diagnostic.message}")
        if report.ok:
            print(f"Checked {path}; {len(report.obligations)} open obligation(s)")
    return 0 if report.ok else 1


def build_file(path: str, *, environment_path: str, state: str, docker_context: str | None = None,
               locked: bool = False, lock: str | None = None, json_output: bool = False,
               max_model_calls: int = 4, max_tokens: int = 20000, timeout: float = 120) -> int:
    try:
        report = check(SourceBundle(text=Path(path).read_text(encoding="utf-8"), path=path))
        if not report.ok or report.program is None:
            return check_file(path, json_output=json_output)
        environment = load_environment(Path(environment_path))
        # Replaying a lock needs the endpoint identity, but never its credential or a client.
        with nullcontext(None) if locked else model_provider(environment) as provider:
            compiler = OpenCompiler(environment, ProgramStore(Path(state)), executor=OCIExecutor(context=docker_context), provider=provider)
            artifact = compiler.build(report.program, lock_path=Path(lock) if lock else Path(path).with_suffix(".nx.lock"), locked=locked,
                                      budget=ResolutionBudget(max_model_calls=max_model_calls, max_tokens=max_tokens, timeout_seconds=timeout))
        print(artifact.model_dump_json() if json_output else f"Built {path}: {artifact.digest}; {len(artifact.runtime_goals)} runtime goal(s)")
        return 0
    except (ProgramError, OSError, ValidationError) as error:
        return _failure(error, json_output=json_output)


def author_stdio(*, state: str, environment_path: str | None = None, docker_context: str | None = None) -> int:
    try:
        store = ProgramStore(Path(state))
        environment = load_environment(Path(environment_path)) if environment_path else None
        with model_provider(environment) if environment else nullcontext(None) as provider:
            compiler = OpenCompiler(environment, store, executor=OCIExecutor(context=docker_context), provider=provider) if environment else None
            service = AuthorProtocol(store, compiler)
            try:
                serve_stdio(service, sys.stdin, sys.stdout)
            finally:
                service.close()
        return 0
    except (ProgramError, OSError, ValidationError) as error:
        return _failure(error, json_output=True)


def _failure(error: Exception, *, json_output: bool) -> int:
    code = error.code if isinstance(error, ProgramError) else type(error).__name__
    # Configuration validation can include secret input values in its default representation.
    message = str(error) if isinstance(error, ProgramError) else "Cannot read or validate Open Programs input"
    print(json.dumps({"error": code, "message": message}) if json_output else f"{code}: {message}", file=sys.stderr)
    return 1
