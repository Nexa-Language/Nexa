"""Compiler behavior shared by the CLI, SDK, and embedded API."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src import nexa_sdk
from src.api import NexaRuntime
from src.cli import build_file
from src.compiler import CompilationError, compile_file


def test_recursive_includes_execute_in_sdk_and_api(tmp_path: Path) -> None:
    (tmp_path / "leaf.nx").write_text('flow answer { result = 42; }')
    (tmp_path / "middle.nx").write_text('include "leaf.nx";')
    main = tmp_path / "main.nx"
    main.write_text('include "middle.nx"; flow main { result = answer(); }')
    result = nexa_sdk.run(str(main))
    assert result.success, result.stderr
    assert result.result == 42
    assert NexaRuntime.run_script(str(main), {})["result"] == 42
    code = Path(build_file(str(main))).read_text()
    assert code == nexa_sdk.compile(str(main)).python_code


@pytest.mark.parametrize("source", ["", "protocol Answer { value: int }"])
def test_declaration_only_programs_generate_valid_python(source: str) -> None:
    result = nexa_sdk.compile(source)
    assert result.success, result.error
    assert result.python_code is not None
    ast.parse(result.python_code)


def test_include_cycle_is_a_diagnostic(tmp_path: Path) -> None:
    first = tmp_path / "first.nx"
    first.write_text('include "second.nx";')
    (tmp_path / "second.nx").write_text('include "first.nx";')
    result = nexa_sdk.compile(str(first))
    assert not result.success
    assert result.error is not None
    assert "cycle" in result.error.lower()
    assert "first.nx" in result.error and "second.nx" in result.error


def test_missing_include_is_reported_by_every_entry(tmp_path: Path) -> None:
    main = tmp_path / "main.nx"
    main.write_text('include "missing.nx"; flow main { print("ready"); }')
    result = nexa_sdk.compile(str(main))
    assert not result.success
    assert result.error is not None
    assert "missing.nx" in result.error
    with pytest.raises(Exception, match="missing.nx"):
        NexaRuntime.run_script(str(main), {})


def test_nested_harness_nodes_are_validated() -> None:
    from src.ast_transformer import NexaTransformer
    from src.harness_validator import HarnessMode, HarnessValidator
    from src.nexa_parser import parse

    program = NexaTransformer().transform(parse('flow main { with_context max_tokens: 99 { autoloop { print("step"); } } }'))
    report = HarnessValidator(HarnessMode.STRICT).validate(program)
    assert "E-001" in [error.rule_id for error in report.errors]


def test_print_only_flow_executes_without_implicit_result() -> None:
    result = nexa_sdk.run('flow main { print("ready"); }')
    assert result.success, result.stderr
    assert result.stdout == "ready\n"
    assert result.result is None


def test_empty_stdlib_call_executes() -> None:
    result = nexa_sdk.run('flow main { result = std.time.now(); }')
    assert result.success, result.stderr
    assert result.result


@pytest.mark.parametrize('body,line,column', [
    ('\n  autoloop max_steps: 2 { result = "x"; }', 3, 3),
    ('\n  with_context budget: 1000 {\n    autoloop max_steps: 2 { result = "x"; }\n  }', 4, 5),
])
def test_included_harness_error_reports_its_source_span(tmp_path: Path, body: str, line: int, column: int) -> None:
    child = tmp_path / 'child.nx'
    child.write_text('\nflow inner {' + body + '\n}')
    main = tmp_path / 'main.nx'
    main.write_text('include "child.nx"; flow main {}')
    result = compile_file(main)
    deadline = next(item for item in result.diagnostics.warnings if item.rule_id == 'E-003')
    assert deadline.location == f'{child}:{line}:{column}'
    with pytest.raises(CompilationError, match=f'child.nx:{line}:{column}'):
        compile_file(main, harness_mode='strict')
