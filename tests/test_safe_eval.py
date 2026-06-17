import json
from pathlib import Path

from src.runtime.contracts import _evaluate_deterministic_expression
from src.runtime.safe_eval import UnsafeExpressionError, parse_safe_command, safe_arithmetic_eval, safe_eval
from src.runtime.stdlib import _file_write, _math_calc, _shell_exec
from src.runtime.tools_registry import std_shell_execute


def test_safe_eval_supports_contract_type_checks():
    assert safe_eval("isinstance(value, int)", {"value": 42}) is True
    assert safe_eval("isinstance(value, (int, float))", {"value": 3.14}) is True
    assert _evaluate_deterministic_expression("isinstance(amount, int) and amount > 0", {"amount": 5})


def test_safe_eval_rejects_attribute_and_import_escape():
    for expression in (
        "value.__class__",
        "__import__('os').system('echo unsafe')",
        "(lambda: 1)()",
    ):
        try:
            safe_eval(expression, {"value": 1})
        except UnsafeExpressionError:
            pass
        else:
            raise AssertionError(f"unsafe expression was allowed: {expression}")


def test_arithmetic_eval_does_not_execute_calls():
    assert safe_arithmetic_eval("2 + 3 * 4") == 14
    assert json.loads(_math_calc("2 + 3"))["result"] == 5
    assert "not allowed" in _math_calc("__import__('os').system('echo unsafe')")


def test_parse_safe_command_rejects_shell_metacharacters():
    assert parse_safe_command("echo hello") == ["echo", "hello"]
    assert parse_safe_command('["echo", "hello world"]') == ["echo", "hello world"]

    try:
        parse_safe_command("echo hello; uname -a")
    except ValueError as exc:
        assert "metacharacters" in str(exc)
    else:
        raise AssertionError("shell metacharacters were allowed")


def test_dangerous_tools_are_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("NEXA_ENABLE_DANGEROUS_TOOLS", raising=False)

    write_result = _file_write(str(tmp_path / "blocked.txt"), "content")
    assert "disabled by default" in write_result
    assert not (tmp_path / "blocked.txt").exists()

    shell_result = json.loads(_shell_exec("echo blocked"))
    assert shell_result["success"] is False
    assert "disabled by default" in shell_result["stderr"]

    registry_result = std_shell_execute("echo blocked")
    assert "disabled by default" in registry_result


def test_dangerous_tools_require_allowed_write_roots(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXA_ENABLE_DANGEROUS_TOOLS", "1")
    monkeypatch.setenv("NEXA_ALLOWED_WRITE_ROOTS", str(tmp_path))

    allowed_file = tmp_path / "allowed.txt"
    assert "Successfully wrote" in _file_write(str(allowed_file), "content")
    assert allowed_file.read_text() == "content"

    outside_file = tmp_path.parent / "outside.txt"
    outside_result = _file_write(str(outside_file), "content")
    assert "outside NEXA_ALLOWED_WRITE_ROOTS" in outside_result
    assert not outside_file.exists()


def test_shell_exec_uses_argv_without_shell(monkeypatch):
    monkeypatch.setenv("NEXA_ENABLE_DANGEROUS_TOOLS", "1")
    result = json.loads(_shell_exec('["echo", "hello shell"]'))
    assert result["success"] is True
    assert result["stdout"].strip() == "hello shell"

    blocked = json.loads(_shell_exec("echo blocked; uname -a"))
    assert blocked["success"] is False
    assert "metacharacters" in blocked["stderr"]
