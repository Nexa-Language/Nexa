"""Offline compilation checks source contracts without constructing a model."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = '''language "3.0"
program Demo(repo: Repository) {
    environment developer
    sandbox repository_image
    acceptance repo_maintenance
    goal answer() -> Int {
        intent "Return an integer"
        implementation value 42
    }
    goal repair(change: ChangeRequest) -> Patch {
        stage runtime
        intent "Repair the repository"
        context repo.snapshot
        capabilities [repo.read, sandbox.exec, sandbox.write]
        ensure checks.regression
        review model("compatibility")
        implementation open
    }
    on change_request as request {
        let result = resolve repair(request)
        propose repo.apply(result) requires human.approval
    }
}
'''


def check_source(source: str):
    from src.open_programs.frontend import check
    from src.open_programs.model import SourceBundle

    return check(SourceBundle(text=source, path="demo.nx"))


def test_check_preserves_holes_types_handlers_and_positions() -> None:
    report = check_source(SOURCE)
    assert report.ok, report.diagnostics
    assert report.obligations == ("repair",)
    assert report.program.goals[0].implementation.body == "42"
    assert report.program.goals[1].span.line == 10
    assert report.program.handlers[0].goal == "repair"


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [('value 42', 'value "forty two"', 'type_mismatch'),
     ('repo.read', 'host.exec', 'unknown_capability'),
     ('repair(request)', 'missing(request)', 'unknown_goal'),
     ('repo.snapshot', 'missing.snapshot', 'unknown_context'),
     ('let result', 'let request', 'binding_conflict'),
     ('-> Int', '-> Unknown', 'unknown_type'),
     ('language "3.0"', 'language "4.0"', 'unsupported_language'),
     ('stage runtime', 'stage build', 'stage_mismatch'),
     ('repo.apply(result)', 'missing.apply(result)', 'unknown_repository'),
     ('review model("compatibility")', 'review model(42)', 'syntax_error')],
)
def test_invalid_programs_have_source_diagnostics(old: str, new: str, code: str) -> None:
    report = check_source(SOURCE.replace(old, new))
    assert not report.ok
    assert code in {item.code for item in report.diagnostics}
    assert all(item.span.path == "demo.nx" and item.span.line >= 1 for item in report.diagnostics)


def test_cycle_diagnostic_and_duplicate_fields() -> None:
    source = 'language "3.0" program Cycle { goal a() -> Int { intent "A" depends [b] } goal b() -> Int { intent "B" depends [a] } }'
    assert "goal_cycle" in {item.code for item in check_source(source).diagnostics}
    assert "duplicate_field" in {item.code for item in check_source(SOURCE.replace('stage runtime', 'stage runtime stage build')).diagnostics}


def test_canonical_entry_dispatches_explicit_versions() -> None:
    from src.compiler import CompilationError, compile_program, compile_source

    assert compile_source('flow main() { print(42) }').python_code
    from src.open_programs.model import CheckReport

    result = compile_program(SOURCE)
    assert isinstance(result, CheckReport) and result.program is not None
    assert result.ok
    assert result.program.name == "Demo"
    with pytest.raises(CompilationError, match="version_conflict"):
        compile_program(SOURCE, language_version="2.4")


def test_cli_check_is_offline_and_writes_no_generated_python(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / "demo.nx"
    source.write_text(SOURCE)
    result = subprocess.run([sys.executable, "-m", "src.cli", "check", str(source), "--json"], cwd=root, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["obligations"] == ["repair"]
    assert not source.with_suffix('.py').exists()


def test_diagnostics_locate_the_obligation_that_needs_repair() -> None:
    report = check_source(SOURCE.replace("repo.read", "host.exec"))
    diagnostic = report.diagnostics[0]
    assert diagnostic.span.line == 14
    assert diagnostic.obligation == "repair"
    report = check_source(SOURCE.replace("repo.snapshot", "missing.snapshot"))
    assert report.diagnostics[0].span.line == 10
    assert report.diagnostics[0].obligation == "repair"
    report = check_source(SOURCE.replace("repair(request)", "missing(request)"))
    assert report.diagnostics[0].span.line == 19
    assert report.diagnostics[0].obligation == "missing"
