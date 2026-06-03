"""
Nexa v2.0 Harness Validator Tests — 六元组约束验证器单元测试

Tests cover:
  - E-dimension: autoloop, try_agent constraints
  - T-dimension: @tool annotation, risk levels
  - C-dimension: with_context, context_policy
  - S-dimension: snapshot/restore/fork
  - L-dimension: lifecycle hooks, reflect
  - V-dimension: verify constraints
  - Cross-dimension: unharnessed, Agent dimension coverage
  - Mode behavior: STRICT vs WARN vs OFF
  - Report serialization: to_dict / to_json

Author: Owen (AI Pair Programmer)
"""

import json
import pytest
from src.harness_validator import (
    HarnessMode, HarnessDimension, HarnessViolation, HarnessReport,
    HarnessValidator, ExecutionChecker, ToolChecker, ContextChecker,
    StateChecker, LifecycleChecker, VerificationChecker,
    CrossDimensionChecker, _node_type, _flatten_body,
    _collect_nodes_by_type, _collect_all_nodes,
)


# ═══════════════════════════════════════════════════════════════════════
#  Helper: build minimal AST for testing
# ═══════════════════════════════════════════════════════════════════════

def _make_ast(body: list) -> dict:
    """Create a minimal AST dict with the given body."""
    return {"type": "Program", "body": body}


def _make_autoloop(max_steps=None, exit_when=None, timeout=None, body=None):
    """Create an AutoLoopStmt dict."""
    return {
        "type": "AutoLoopStmt",
        "max_steps": max_steps,
        "exit_when": exit_when,
        "timeout": timeout,
        "body": body or [],
    }


def _make_try_agent(try_body=None, catch_branches=None):
    """Create a TryAgentStmt dict."""
    return {
        "type": "TryAgentStmt",
        "try_body": try_body or [],
        "catch_branches": catch_branches or [],
    }


def _make_catch_correction(error_var="e", error_type="ToolError", correction_body=None):
    """Create a CatchCorrectionBranch dict."""
    return {
        "type": "CatchCorrectionBranch",
        "error_var": error_var,
        "error_type": error_type,
        "correction_body": correction_body or [],
    }


def _make_tool_annotation(description="", fn_name="test_fn", risk_level="low",
                           requires_approval=False, sandbox=False, return_type=None):
    """Create a ToolAnnotation dict."""
    return {
        "type": "ToolAnnotation",
        "description": description,
        "fn_name": fn_name,
        "risk_level": risk_level,
        "requires_approval": requires_approval,
        "sandbox": sandbox,
        "return_type": return_type,
    }


def _make_with_context(config=None, body=None):
    """Create a WithContextStmt dict."""
    return {
        "type": "WithContextStmt",
        "config": config or {},
        "body": body or [],
    }


def _make_context_policy(params=None):
    """Create a ContextPolicyDecl dict."""
    return {
        "type": "ContextPolicyDecl",
        "params": params or {},
    }


def _make_snapshot(var_name=None):
    """Create a SnapshotStmt dict."""
    return {"type": "SnapshotStmt", "var_name": var_name}


def _make_restore(target_var="", condition=None):
    """Create a RestoreStmt dict."""
    return {"type": "RestoreStmt", "target_var": target_var, "condition": condition}


def _make_fork(branches=None, merge_strategy="best"):
    """Create a ForkStmt dict."""
    return {
        "type": "ForkStmt",
        "branches": branches or [],
        "merge_strategy": merge_strategy,
    }


def _make_verify(check_type="satisfies", target=None, check_value=None):
    """Create a VerifyStmt dict."""
    return {
        "type": "VerifyStmt",
        "check_type": check_type,
        "target": target,
        "check_value": check_value,
    }


def _make_reflect(text=""):
    """Create a ReflectStmt dict."""
    return {"type": "ReflectStmt", "text": text}


def _make_lifecycle_hook(hook_type="before_step", body=None, tool_name=None,
                          error_var=None, error_type=None):
    """Create a LifecycleHook dict."""
    d = {"type": "LifecycleHook", "hook_type": hook_type, "body": body or []}
    if tool_name:
        d["tool_name"] = tool_name
    if error_var:
        d["error_var"] = error_var
    if error_type:
        d["error_type"] = error_type
    return d


def _make_unharnessed(reason=None, body=None):
    """Create an UnharnessedStmt dict."""
    return {
        "type": "UnharnessedStmt",
        "reason": reason,
        "body": body or [],
    }


def _make_agent_decl(name="TestAgent", body=None):
    """Create an AgentDeclaration dict."""
    return {
        "type": "AgentDeclaration",
        "name": name,
        "body": body or [],
    }


# ═══════════════════════════════════════════════════════════════════════
#  E-Dimension Tests
# ═══════════════════════════════════════════════════════════════════════

class TestExecutionChecker:
    """E-dimension: autoloop and try_agent constraints."""

    def test_autoloop_no_exit_condition_is_error(self):
        """E-001: autoloop without exit_when or max_steps → error."""
        ast = _make_ast([_make_autoloop()])
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        report = hv.validate(ast)
        assert report.has_errors()
        e001_found = any(v.rule_id == "E-001" for v in report.errors)
        assert e001_found, "Expected E-001 violation for autoloop without exit condition"

    def test_autoloop_with_max_steps_is_valid(self):
        """E-001: autoloop with max_steps → no E-001 error."""
        ast = _make_ast([_make_autoloop(max_steps=50)])
        checker = ExecutionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        e001_found = any(v.rule_id == "E-001" for v in report.errors)
        assert not e001_found

    def test_autoloop_with_exit_when_is_valid(self):
        """E-001: autoloop with exit_when → no E-001 error."""
        ast = _make_ast([_make_autoloop(exit_when="resolved")])
        checker = ExecutionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        e001_found = any(v.rule_id == "E-001" for v in report.errors)
        assert not e001_found

    def test_autoloop_excessive_max_steps_is_warning(self):
        """E-002: autoloop max_steps > 1000 → warning."""
        ast = _make_ast([_make_autoloop(max_steps=2000, exit_when="resolved")])
        checker = ExecutionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        e002_found = any(v.rule_id == "E-002" for v in report.warnings)
        assert e002_found

    def test_autoloop_no_timeout_is_warning(self):
        """E-003: autoloop without timeout → warning."""
        ast = _make_ast([_make_autoloop(max_steps=50, exit_when="resolved")])
        checker = ExecutionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        e003_found = any(v.rule_id == "E-003" for v in report.warnings)
        assert e003_found

    def test_try_agent_no_catch_is_error(self):
        """E-004: try_agent without catch_correction → error."""
        ast = _make_ast([_make_try_agent()])
        checker = ExecutionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        e004_found = any(v.rule_id == "E-004" for v in report.errors)
        assert e004_found

    def test_try_agent_with_catch_is_valid(self):
        """E-004: try_agent with catch_correction → no error."""
        ast = _make_ast([_make_try_agent(
            catch_branches=[_make_catch_correction()]
        )])
        checker = ExecutionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        e004_found = any(v.rule_id == "E-004" for v in report.errors)
        assert not e004_found

    def test_catch_correction_no_reflect_is_warning(self):
        """E-005: catch_correction without reflect → warning."""
        ast = _make_ast([_make_try_agent(
            catch_branches=[_make_catch_correction(correction_body=[])]
        )])
        checker = ExecutionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        e005_found = any(v.rule_id == "E-005" for v in report.warnings)
        assert e005_found

    def test_catch_correction_with_reflect_is_valid(self):
        """E-005: catch_correction with reflect → no warning."""
        ast = _make_ast([_make_try_agent(
            catch_branches=[_make_catch_correction(
                correction_body=[_make_reflect("Error: retry")]
            )]
        )])
        checker = ExecutionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        e005_found = any(v.rule_id == "E-005" for v in report.warnings)
        assert not e005_found


# ═══════════════════════════════════════════════════════════════════════
#  T-Dimension Tests
# ═══════════════════════════════════════════════════════════════════════

class TestToolChecker:
    """T-dimension: @tool annotation constraints."""

    def test_tool_no_description_is_error(self):
        """T-001: @tool without description → error."""
        ast = _make_ast([_make_tool_annotation(description="")])
        checker = ToolChecker()
        report = HarnessReport()
        checker.check(ast, report)
        t001_found = any(v.rule_id == "T-001" for v in report.errors)
        assert t001_found

    def test_tool_with_description_is_valid(self):
        """T-001: @tool with description → no error."""
        ast = _make_ast([_make_tool_annotation(description="Execute shell commands")])
        checker = ToolChecker()
        report = HarnessReport()
        checker.check(ast, report)
        t001_found = any(v.rule_id == "T-001" for v in report.errors)
        assert not t001_found

    def test_high_risk_without_approval_is_error(self):
        """T-002: @tool risk_level=high without requires_approval → error."""
        ast = _make_ast([_make_tool_annotation(
            description="Shell exec", risk_level="high", requires_approval=False
        )])
        checker = ToolChecker()
        report = HarnessReport()
        checker.check(ast, report)
        t002_found = any(v.rule_id == "T-002" for v in report.errors)
        assert t002_found

    def test_high_risk_with_approval_is_valid(self):
        """T-002: @tool risk_level=high with requires_approval → no error."""
        ast = _make_ast([_make_tool_annotation(
            description="Shell exec", risk_level="high", requires_approval=True
        )])
        checker = ToolChecker()
        report = HarnessReport()
        checker.check(ast, report)
        t002_found = any(v.rule_id == "T-002" for v in report.errors)
        assert not t002_found

    def test_high_risk_without_sandbox_is_warning(self):
        """T-003: @tool risk_level=high without sandbox → warning."""
        ast = _make_ast([_make_tool_annotation(
            description="Shell exec", risk_level="high", requires_approval=True, sandbox=False
        )])
        checker = ToolChecker()
        report = HarnessReport()
        checker.check(ast, report)
        t003_found = any(v.rule_id == "T-003" for v in report.warnings)
        assert t003_found

    def test_tool_no_return_type_is_warning(self):
        """T-004: @tool fn without return type → warning."""
        ast = _make_ast([_make_tool_annotation(
            description="Shell exec", return_type=None
        )])
        checker = ToolChecker()
        report = HarnessReport()
        checker.check(ast, report)
        t004_found = any(v.rule_id == "T-004" for v in report.warnings)
        assert t004_found


# ═══════════════════════════════════════════════════════════════════════
#  C-Dimension Tests
# ═══════════════════════════════════════════════════════════════════════

class TestContextChecker:
    """C-dimension: with_context and context_policy constraints."""

    def test_with_context_no_max_tokens_is_error(self):
        """C-001: with_context without max_tokens → error."""
        ast = _make_ast([_make_with_context(config={})])
        checker = ContextChecker()
        report = HarnessReport()
        checker.check(ast, report)
        c001_found = any(v.rule_id == "C-001" for v in report.errors)
        assert c001_found

    def test_with_context_with_max_tokens_is_valid(self):
        """C-001: with_context with max_tokens → no error."""
        ast = _make_ast([_make_with_context(config={"max_tokens": 100000})])
        checker = ContextChecker()
        report = HarnessReport()
        checker.check(ast, report)
        c001_found = any(v.rule_id == "C-001" for v in report.errors)
        assert not c001_found

    def test_with_context_excessive_max_tokens_is_warning(self):
        """C-002: with_context max_tokens > 200K → warning."""
        ast = _make_ast([_make_with_context(config={"max_tokens": 300000})])
        checker = ContextChecker()
        report = HarnessReport()
        checker.check(ast, report)
        c002_found = any(v.rule_id == "C-002" for v in report.warnings)
        assert c002_found

    def test_context_policy_no_strategy_is_warning(self):
        """C-003: context_policy without strategy → warning."""
        ast = _make_ast([_make_context_policy(params={})])
        checker = ContextChecker()
        report = HarnessReport()
        checker.check(ast, report)
        c003_found = any(v.rule_id == "C-003" for v in report.warnings)
        assert c003_found


# ═══════════════════════════════════════════════════════════════════════
#  S-Dimension Tests
# ═══════════════════════════════════════════════════════════════════════

class TestStateChecker:
    """S-dimension: snapshot/restore/fork constraints."""

    def test_restore_unknown_snapshot_is_warning(self):
        """S-001: restore referencing undefined snapshot → warning."""
        ast = _make_ast([
            _make_snapshot(var_name="snap1"),
            _make_restore(target_var="snap2"),
        ])
        checker = StateChecker()
        report = HarnessReport()
        checker.check(ast, report)
        s001_found = any(v.rule_id == "S-001" for v in report.warnings)
        assert s001_found

    def test_restore_known_snapshot_is_valid(self):
        """S-001: restore referencing defined snapshot → no warning."""
        ast = _make_ast([
            _make_snapshot(var_name="snap1"),
            _make_restore(target_var="snap1"),
        ])
        checker = StateChecker()
        report = HarnessReport()
        checker.check(ast, report)
        s001_found = any(v.rule_id == "S-001" for v in report.warnings)
        assert not s001_found

    def test_fork_single_branch_is_error(self):
        """S-002: fork with < 2 branches → error."""
        ast = _make_ast([_make_fork(branches=[("A", "expr1")])])
        checker = StateChecker()
        report = HarnessReport()
        checker.check(ast, report)
        s002_found = any(v.rule_id == "S-002" for v in report.errors)
        assert s002_found

    def test_fork_two_branches_is_valid(self):
        """S-002: fork with ≥ 2 branches → no error."""
        ast = _make_ast([_make_fork(branches=[("A", "expr1"), ("B", "expr2")])])
        checker = StateChecker()
        report = HarnessReport()
        checker.check(ast, report)
        s002_found = any(v.rule_id == "S-002" for v in report.errors)
        assert not s002_found

    def test_fork_invalid_merge_strategy_is_warning(self):
        """S-003: fork with non-standard merge strategy → warning."""
        ast = _make_ast([_make_fork(
            branches=[("A", "expr1"), ("B", "expr2")],
            merge_strategy="random",
        )])
        checker = StateChecker()
        report = HarnessReport()
        checker.check(ast, report)
        s003_found = any(v.rule_id == "S-003" for v in report.warnings)
        assert s003_found


# ═══════════════════════════════════════════════════════════════════════
#  L-Dimension Tests
# ═══════════════════════════════════════════════════════════════════════

class TestLifecycleChecker:
    """L-dimension: lifecycle hooks and reflect constraints."""

    def test_empty_before_step_hook_is_warning(self):
        """L-001: before_step hook with empty body → warning."""
        ast = _make_ast([_make_lifecycle_hook(hook_type="before_step", body=[])])
        checker = LifecycleChecker()
        report = HarnessReport()
        checker.check(ast, report)
        l001_found = any(v.rule_id == "L-001" for v in report.warnings)
        assert l001_found

    def test_non_empty_before_step_hook_is_valid(self):
        """L-001: before_step hook with body → no warning."""
        ast = _make_ast([_make_lifecycle_hook(
            hook_type="before_step", body=[{"type": "PrintStatement", "value": "starting"}]
        )])
        checker = LifecycleChecker()
        report = HarnessReport()
        checker.check(ast, report)
        l001_found = any(v.rule_id == "L-001" for v in report.warnings)
        assert not l001_found

    def test_on_error_no_binding_is_warning(self):
        """L-002: on_error hook without error binding → warning."""
        ast = _make_ast([_make_lifecycle_hook(hook_type="on_error", body=[])])
        checker = LifecycleChecker()
        report = HarnessReport()
        checker.check(ast, report)
        l002_found = any(v.rule_id == "L-002" for v in report.warnings)
        assert l002_found

    def test_reflect_empty_text_is_warning(self):
        """L-003: reflect with empty text → warning."""
        ast = _make_ast([_make_reflect(text="")])
        checker = LifecycleChecker()
        report = HarnessReport()
        checker.check(ast, report)
        l003_found = any(v.rule_id == "L-003" for v in report.warnings)
        assert l003_found


# ═══════════════════════════════════════════════════════════════════════
#  V-Dimension Tests
# ═══════════════════════════════════════════════════════════════════════

class TestVerificationChecker:
    """V-dimension: verify constraints."""

    def test_verify_satisfies_no_type_is_error(self):
        """V-001: verify satisfies without type → error."""
        ast = _make_ast([_make_verify(check_type="satisfies", check_value=None)])
        checker = VerificationChecker()
        report = HarnessReport()
        checker.check(ast, report)
        v001_found = any(v.rule_id == "V-001" for v in report.errors)
        assert v001_found

    def test_verify_satisfies_with_type_is_valid(self):
        """V-001: verify satisfies with type → no error."""
        ast = _make_ast([_make_verify(check_type="satisfies", check_value="AuthProtocol")])
        checker = VerificationChecker()
        report = HarnessReport()
        checker.check(ast, report)
        v001_found = any(v.rule_id == "V-001" for v in report.errors)
        assert not v001_found

    def test_verify_semantic_short_condition_is_warning(self):
        """V-002: verify semantic with short condition → warning."""
        ast = _make_ast([_make_verify(check_type="semantic", check_value="ok")])
        checker = VerificationChecker()
        report = HarnessReport()
        checker.check(ast, report)
        v002_found = any(v.rule_id == "V-002" for v in report.warnings)
        assert v002_found

    def test_autoloop_without_verify_is_warning(self):
        """V-003: autoloop without verify → warning."""
        ast = _make_ast([_make_autoloop(max_steps=50, exit_when="resolved")])
        checker = VerificationChecker()
        report = HarnessReport()
        checker.check(ast, report)
        v003_found = any(v.rule_id == "V-003" for v in report.warnings)
        assert v003_found


# ═══════════════════════════════════════════════════════════════════════
#  Cross-Dimension Tests
# ═══════════════════════════════════════════════════════════════════════

class TestCrossDimensionChecker:
    """Cross-dimension: unharnessed and Agent coverage constraints."""

    def test_unharnessed_no_reason_is_error(self):
        """X-001: unharnessed without reason → error."""
        ast = _make_ast([_make_unharnessed(reason=None)])
        checker = CrossDimensionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        x001_found = any(v.rule_id == "X-001" for v in report.errors)
        assert x001_found

    def test_unharnessed_with_reason_is_valid(self):
        """X-001: unharnessed with reason → no error."""
        ast = _make_ast([_make_unharnessed(reason="Legacy system requires direct access")])
        checker = CrossDimensionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        x001_found = any(v.rule_id == "X-001" for v in report.errors)
        assert not x001_found

    def test_unharnessed_large_body_is_warning(self):
        """X-001b: unharnessed with >5 statements → warning."""
        body = [{"type": "ExprStmt"} for _ in range(6)]
        ast = _make_ast([_make_unharnessed(reason="needed", body=body)])
        checker = CrossDimensionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        x001b_found = any(v.rule_id == "X-001b" for v in report.warnings)
        assert x001b_found

    def test_agent_low_dimension_coverage_is_warning(self):
        """X-002: Agent using <3 Harness dimensions → warning."""
        ast = _make_ast([_make_agent_decl(body=[
            _make_autoloop(max_steps=50, exit_when="resolved"),
        ])])
        checker = CrossDimensionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        x002_found = any(v.rule_id == "X-002" for v in report.warnings)
        assert x002_found

    def test_agent_high_dimension_coverage_is_valid(self):
        """X-002: Agent using ≥3 Harness dimensions → no warning."""
        ast = _make_ast([_make_agent_decl(body=[
            _make_autoloop(max_steps=50, exit_when="resolved"),
            _make_verify(check_type="satisfies", check_value="Protocol"),
            _make_reflect(text="Check result quality"),
        ])])
        checker = CrossDimensionChecker()
        report = HarnessReport()
        checker.check(ast, report)
        x002_found = any(v.rule_id == "X-002" for v in report.warnings)
        assert not x002_found


# ═══════════════════════════════════════════════════════════════════════
#  Mode Behavior Tests
# ═══════════════════════════════════════════════════════════════════════

class TestHarnessModeBehavior:
    """Test STRICT vs WARN vs OFF mode behavior."""

    def test_strict_mode_errors_block(self):
        """STRICT mode: errors remain as errors."""
        ast = _make_ast([_make_autoloop()])  # No exit condition → E-001
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        report = hv.validate(ast)
        assert report.has_errors()

    def test_warn_mode_downgrades_errors(self):
        """WARN mode: errors are downgraded to warnings."""
        ast = _make_ast([_make_autoloop()])  # No exit condition → E-001
        hv = HarnessValidator(mode=HarnessMode.WARN)
        report = hv.validate(ast)
        assert not report.has_errors()
        assert report.has_warnings()

    def test_off_mode_skips_validation(self):
        """OFF mode: no validation performed."""
        ast = _make_ast([_make_autoloop()])
        hv = HarnessValidator(mode=HarnessMode.OFF)
        report = hv.validate(ast)
        assert not report.has_errors()
        assert not report.has_warnings()


# ═══════════════════════════════════════════════════════════════════════
#  Report Serialization Tests
# ═══════════════════════════════════════════════════════════════════════

class TestHarnessReportSerialization:
    """Test HarnessReport to_dict / to_json serialization."""

    def test_report_to_dict_structure(self):
        """Report to_dict has expected keys."""
        report = HarnessReport()
        report.add_error(HarnessViolation(
            dimension=HarnessDimension.E, severity="error",
            rule_id="E-001", message="test error",
        ))
        report.add_warning(HarnessViolation(
            dimension=HarnessDimension.T, severity="warning",
            rule_id="T-003", message="test warning",
        ))
        d = report.to_dict()
        assert "valid" in d
        assert d["valid"] is False
        assert "errors" in d
        assert "warnings" in d
        assert "summary" in d
        assert d["summary"]["total_errors"] == 1
        assert d["summary"]["total_warnings"] == 1

    def test_report_to_json_is_valid_json(self):
        """Report to_json produces valid JSON string."""
        report = HarnessReport()
        report.add_error(HarnessViolation(
            dimension=HarnessDimension.E, severity="error",
            rule_id="E-001", message="test",
        ))
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["valid"] is False

    def test_violation_to_dict(self):
        """HarnessViolation to_dict has expected structure."""
        v = HarnessViolation(
            dimension=HarnessDimension.E, severity="error",
            rule_id="E-001", message="test error",
            location="line 5", suggestion="Add exit_when",
        )
        d = v.to_dict()
        assert d["dimension"] == "E"
        assert d["severity"] == "error"
        assert d["rule_id"] == "E-001"
        assert d["message"] == "test error"
        assert d["location"] == "line 5"
        assert d["suggestion"] == "Add exit_when"


# ═══════════════════════════════════════════════════════════════════════
#  Custom Checker Registration Tests
# ═══════════════════════════════════════════════════════════════════════

class TestCustomCheckerRegistration:
    """Test register_checker for custom validation rules."""

    def test_custom_checker_is_called(self):
        """Custom checker function is invoked during validate."""
        called = False

        def my_checker(ast, report):
            nonlocal called
            called = True

        hv = HarnessValidator(mode=HarnessMode.STRICT)
        hv.register_checker(my_checker)
        hv.validate(_make_ast([]))
        assert called

    def test_custom_checker_can_add_violations(self):
        """Custom checker can add violations to the report."""
        def my_checker(ast, report):
            report.add_warning(HarnessViolation(
                dimension=HarnessDimension.E, severity="warning",
                rule_id="CUSTOM-001", message="Custom check warning",
            ))

        # In STRICT mode, warnings are upgraded to errors
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        hv.register_checker(my_checker)
        report = hv.validate(_make_ast([]))
        custom_found = any(v.rule_id == "CUSTOM-001" for v in report.errors)
        assert custom_found


# ═══════════════════════════════════════════════════════════════════════
#  AST Helper Tests
# ═══════════════════════════════════════════════════════════════════════

class TestASTHelpers:
    """Test AST extraction helper functions."""

    def test_node_type_dict(self):
        """_node_type extracts type from dict."""
        assert _node_type({"type": "AutoLoopStmt"}) == "AutoLoopStmt"

    def test_node_type_unknown(self):
        """_node_type returns class name for unknown objects."""
        assert _node_type(42) == "int"

    def test_flatten_body(self):
        """_flatten_body extracts body list from AST."""
        ast = {"body": [{"type": "A"}, {"type": "B"}]}
        result = _flatten_body(ast)
        assert len(result) == 2

    def test_collect_nodes_by_type(self):
        """_collect_nodes_by_type finds nodes of target type."""
        body = [
            {"type": "AutoLoopStmt", "max_steps": 50},
            {"type": "VerifyStmt", "check_type": "satisfies"},
            {"type": "AutoLoopStmt", "max_steps": 100},
        ]
        result = _collect_nodes_by_type(body, "AutoLoopStmt")
        assert len(result) == 2

    def test_collect_all_nodes(self):
        """_collect_all_nodes recursively collects all nodes."""
        body = [
            {"type": "TryAgentStmt", "try_body": [{"type": "ExprStmt"}]},
            {"type": "VerifyStmt"},
        ]
        result = _collect_all_nodes(body)
        assert len(result) >= 3  # TryAgentStmt + ExprStmt + VerifyStmt


# ═══════════════════════════════════════════════════════════════════════
#  Integration: Full Validator Pipeline
# ═══════════════════════════════════════════════════════════════════════

class TestFullValidatorPipeline:
    """Integration tests: full validator pipeline with multiple dimensions."""

    def test_well_harnessed_agent_passes(self):
        """A well-harnessed Agent with all 6 dimensions passes validation."""
        ast = _make_ast([
            _make_autoloop(max_steps=50, exit_when="resolved", timeout=300),
            _make_tool_annotation(description="Shell exec", fn_name="shell",
                                   risk_level="low", return_type="string"),
            _make_with_context(config={"max_tokens": 100000}),
            _make_snapshot(var_name="snap1"),
            _make_lifecycle_hook(hook_type="before_step",
                                  body=[{"type": "PrintStatement", "value": "starting"}]),
            _make_verify(check_type="satisfies", check_value="Protocol"),
        ])
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        report = hv.validate(ast)
        # May have warnings (e.g., restore referencing snap1 not used), but no errors
        assert not report.has_errors()

    def test_poorly_harnessed_agent_fails_strict(self):
        """A poorly-harnessed Agent fails strict validation."""
        ast = _make_ast([
            _make_autoloop(),  # No exit condition → E-001
            _make_tool_annotation(description="", risk_level="high", requires_approval=False),  # T-001, T-002
        ])
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        report = hv.validate(ast)
        assert report.has_errors()

    def test_poorly_harnessed_agent_warn_mode_continues(self):
        """A poorly-harnessed Agent in warn mode continues with warnings."""
        ast = _make_ast([
            _make_autoloop(),  # No exit condition → E-001
        ])
        hv = HarnessValidator(mode=HarnessMode.WARN)
        report = hv.validate(ast)
        assert not report.has_errors()
        assert report.has_warnings()

    def test_dimension_coverage_tracking(self):
        """Validator tracks which dimensions were checked."""
        ast = _make_ast([_make_autoloop(max_steps=50, exit_when="resolved")])
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        report = hv.validate(ast)
        # E dimension should be checked
        assert "E" in report.dimension_coverage