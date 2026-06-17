"""
Nexa v2.0 Harness Validator — 编译期六元组约束验证器

H = (E, T, C, S, L, V) 的静态分析引擎，在 parse → AST 阶段执行，
确保 Agent 程序在运行前满足 Harness 各维度约束。

Design Rationale:
  - 纯 AST 分析，不依赖运行时状态
  - 三级模式: STRICT(错误阻断编译) / WARN(警告继续) / OFF(跳过)
  - 规则可扩展: 每个维度独立 checker，通过 register_checker 机制组合
  - 报告结构化: HarnessReport 可序列化为 JSON，供 CI/CD 集成

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type


# ═══════════════════════════════════════════════════════════════════════
#  Core Types
# ═══════════════════════════════════════════════════════════════════════

class HarnessMode(Enum):
    """Harness validation mode — controls how violations are handled."""
    STRICT = "strict"  # Errors block compilation (non-zero exit)
    WARN = "warn"      # Errors become warnings, compilation continues
    OFF = "off"        # Skip validation entirely


class HarnessDimension(Enum):
    """The six dimensions of the Harness tuple H = (E, T, C, S, L, V)."""
    E = "E"  # Execution — autoloop, try_agent, step
    T = "T"  # Tool — @tool annotation, risk levels, approval gates
    C = "C"  # Context — with_context, context_policy, token budgets
    S = "S"  # State — snapshot/restore/fork, stateful branching
    L = "L"  # Lifecycle — hooks, reflect, on_error, before/after_step
    V = "V"  # Verification — verify satisfies/method/semantic


@dataclass
class HarnessViolation:
    """A single constraint violation found during validation."""
    dimension: HarnessDimension
    severity: str  # "error" | "warning" | "info"
    rule_id: str   # e.g., "E-001", "T-003"
    message: str
    location: Optional[str] = None  # AST node reference or line info
    suggestion: Optional[str] = None  # How to fix

    def to_dict(self) -> Dict:
        return {
            "dimension": self.dimension.value,
            "severity": self.severity,
            "rule_id": self.rule_id,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion,
        }


@dataclass
class HarnessReport:
    """Aggregated validation report across all dimensions."""
    errors: List[HarnessViolation] = field(default_factory=list)
    warnings: List[HarnessViolation] = field(default_factory=list)
    info: List[HarnessViolation] = field(default_factory=list)
    dimension_coverage: Dict[str, bool] = field(default_factory=dict)

    def add_error(self, violation: HarnessViolation) -> None:
        self.errors.append(violation)

    def add_warning(self, violation: HarnessViolation) -> None:
        self.warnings.append(violation)

    def add_info(self, violation: HarnessViolation) -> None:
        self.info.append(violation)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def to_dict(self) -> Dict:
        return {
            "valid": not self.has_errors(),
            "errors": [v.to_dict() for v in self.errors],
            "warnings": [v.to_dict() for v in self.warnings],
            "info": [v.to_dict() for v in self.info],
            "dimension_coverage": self.dimension_coverage,
            "summary": {
                "total_errors": len(self.errors),
                "total_warnings": len(self.warnings),
                "total_info": len(self.info),
                "dimensions_checked": list(self.dimension_coverage.keys()),
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ═══════════════════════════════════════════════════════════════════════
#  AST Helpers — extract Harness primitives from AST
# ═══════════════════════════════════════════════════════════════════════

def _node_type(node: Any) -> str:
    """Extract type string from an AST node (dict or dataclass)."""
    if isinstance(node, dict):
        return node.get("type", "")
    if hasattr(node, 'to_dict'):
        d = node.to_dict()
        return d.get("type", "")
    return type(node).__name__


def _flatten_body(ast: Dict) -> List[Any]:
    """Flatten the AST body into a list of nodes."""
    body = ast.get("body", [])
    if isinstance(body, list):
        return body
    return [body]


def _collect_nodes_by_type(body: List[Any], target_type: str) -> List[Any]:
    """Recursively collect all nodes of a given type from the AST body."""
    results = []
    for node in body:
        if _node_type(node) == target_type:
            results.append(node)
        # Recurse into nested bodies
        if isinstance(node, dict):
            for key in ("body", "try_body", "correction_body", "then_body", "else_body"):
                nested = node.get(key, [])
                if isinstance(nested, list):
                    results.extend(_collect_nodes_by_type(nested, target_type))
    return results


def _collect_all_nodes(body: List[Any]) -> List[Any]:
    """Recursively collect all nodes from the AST body."""
    results = []
    for node in body:
        results.append(node)
        if isinstance(node, dict):
            for key in ("body", "try_body", "correction_body", "then_body", "else_body"):
                nested = node.get(key, [])
                if isinstance(nested, list):
                    results.extend(_collect_all_nodes(nested))
    return results


# ═══════════════════════════════════════════════════════════════════════
#  Dimension Checkers — one per Harness dimension
# ═══════════════════════════════════════════════════════════════════════

class DimensionChecker:
    """Base class for per-dimension Harness checkers."""

    dimension: HarnessDimension = HarnessDimension.E

    def check(self, ast: Dict, report: HarnessReport) -> None:
        """Run dimension-specific checks on the AST. Override in subclasses."""
        raise NotImplementedError


class ExecutionChecker(DimensionChecker):
    """E-dimension: validates autoloop, try_agent, step constraints."""

    dimension = HarnessDimension.E

    def check(self, ast: Dict, report: HarnessReport) -> None:
        body = _flatten_body(ast)
        autoloops = _collect_nodes_by_type(body, "AutoLoopStmt")
        try_agents = _collect_nodes_by_type(body, "TryAgentStmt")

        # E-001: autoloop must have exit_when or max_steps
        for al in autoloops:
            node_dict = al if isinstance(al, dict) else (al.to_dict() if hasattr(al, 'to_dict') else {})
            if not node_dict.get("exit_when") and not node_dict.get("max_steps"):
                report.add_error(HarnessViolation(
                    dimension=HarnessDimension.E,
                    severity="error",
                    rule_id="E-001",
                    message="autoloop must specify either exit_when or max_steps to prevent infinite loops",
                    suggestion="Add: autoloop max_steps: 50 exit_when: \"resolved\" { ... }",
                ))

        # E-002: autoloop max_steps should be reasonable (< 1000)
        for al in autoloops:
            node_dict = al if isinstance(al, dict) else (al.to_dict() if hasattr(al, 'to_dict') else {})
            max_steps = node_dict.get("max_steps")
            if max_steps is not None and isinstance(max_steps, int) and max_steps > 1000:
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.E,
                    severity="warning",
                    rule_id="E-002",
                    message=f"autoloop max_steps={max_steps} exceeds recommended limit (1000)",
                    suggestion="Consider reducing max_steps or adding a timeout constraint",
                ))

        # E-003: autoloop should have timeout for production code
        for al in autoloops:
            node_dict = al if isinstance(al, dict) else (al.to_dict() if hasattr(al, 'to_dict') else {})
            if not node_dict.get("timeout"):
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.E,
                    severity="warning",
                    rule_id="E-003",
                    message="autoloop without timeout may hang indefinitely in production",
                    suggestion="Add: timeout: 300 (seconds)",
                ))

        # E-004: try_agent must have catch_correction branch
        for ta in try_agents:
            node_dict = ta if isinstance(ta, dict) else (ta.to_dict() if hasattr(ta, 'to_dict') else {})
            catch_branches = node_dict.get("catch_branches", [])
            if not catch_branches:
                report.add_error(HarnessViolation(
                    dimension=HarnessDimension.E,
                    severity="error",
                    rule_id="E-004",
                    message="try_agent must have at least one catch_correction branch for AI error recovery",
                    suggestion="Add: catch_correction(e: ToolError) { reflect `Error: #{e}. Retry.`; }",
                ))

        # E-005: catch_correction should include reflect for self-correction
        for ta in try_agents:
            node_dict = ta if isinstance(ta, dict) else (ta.to_dict() if hasattr(ta, 'to_dict') else {})
            for branch in node_dict.get("catch_branches", []):
                branch_dict = branch if isinstance(branch, dict) else (branch.to_dict() if hasattr(branch, 'to_dict') else {})
                correction_body = branch_dict.get("correction_body", [])
                has_reflect = any(
                    _node_type(n) == "ReflectStmt" for n in correction_body
                )
                if not has_reflect:
                    report.add_warning(HarnessViolation(
                        dimension=HarnessDimension.E,
                        severity="warning",
                        rule_id="E-005",
                        message="catch_correction without reflect — AI may not self-correct effectively",
                        suggestion="Add reflect statement in catch_correction body",
                    ))

        report.dimension_coverage["E"] = True


class ToolChecker(DimensionChecker):
    """T-dimension: validates @tool annotations, risk levels, approval gates."""

    dimension = HarnessDimension.T

    def check(self, ast: Dict, report: HarnessReport) -> None:
        body = _flatten_body(ast)
        tools = _collect_nodes_by_type(body, "ToolAnnotation")

        # T-001: @tool must have description
        for tool in tools:
            node_dict = tool if isinstance(tool, dict) else (tool.to_dict() if hasattr(tool, 'to_dict') else {})
            desc = node_dict.get("description", "")
            if not desc or desc.strip() == "":
                report.add_error(HarnessViolation(
                    dimension=HarnessDimension.T,
                    severity="error",
                    rule_id="T-001",
                    message="@tool annotation must include a non-empty description for Agent comprehension",
                    suggestion="Add: @tool(\"Execute shell commands safely\")",
                ))

        # T-002: high-risk tools must have requires_approval
        for tool in tools:
            node_dict = tool if isinstance(tool, dict) else (tool.to_dict() if hasattr(tool, 'to_dict') else {})
            risk = node_dict.get("risk_level", "low")
            requires_approval = node_dict.get("requires_approval", False)
            if risk in ("high", "critical") and not requires_approval:
                report.add_error(HarnessViolation(
                    dimension=HarnessDimension.T,
                    severity="error",
                    rule_id="T-002",
                    message=f"@tool with risk_level='{risk}' must set requires_approval: true",
                    suggestion="Add: requires_approval: true to @tool config",
                ))

        # T-003: high-risk tools should have sandbox enabled
        for tool in tools:
            node_dict = tool if isinstance(tool, dict) else (tool.to_dict() if hasattr(tool, 'to_dict') else {})
            risk = node_dict.get("risk_level", "low")
            sandbox = node_dict.get("sandbox", False)
            if risk in ("high", "critical") and not sandbox:
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.T,
                    severity="warning",
                    rule_id="T-003",
                    message=f"@tool with risk_level='{risk}' should enable sandbox for isolation",
                    suggestion="Add: sandbox: true to @tool config",
                ))

        # T-004: @tool fn must have return type annotation
        for tool in tools:
            node_dict = tool if isinstance(tool, dict) else (tool.to_dict() if hasattr(tool, 'to_dict') else {})
            return_type = node_dict.get("return_type")
            if not return_type:
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.T,
                    severity="warning",
                    rule_id="T-004",
                    message="@tool fn without return type — Agent may misinterpret output",
                    suggestion="Add return type: fn name(params): string { ... }",
                ))

        report.dimension_coverage["T"] = True


class ContextChecker(DimensionChecker):
    """C-dimension: validates with_context, context_policy, token budgets."""

    dimension = HarnessDimension.C

    def check(self, ast: Dict, report: HarnessReport) -> None:
        body = _flatten_body(ast)
        with_contexts = _collect_nodes_by_type(body, "WithContextStmt")
        policies = _collect_nodes_by_type(body, "ContextPolicyDecl")

        # C-001: with_context must specify max_tokens
        for wc in with_contexts:
            node_dict = wc if isinstance(wc, dict) else (wc.to_dict() if hasattr(wc, 'to_dict') else {})
            config = node_dict.get("config", {})
            if "max_tokens" not in config and "max_tokens" not in node_dict:
                report.add_error(HarnessViolation(
                    dimension=HarnessDimension.C,
                    severity="error",
                    rule_id="C-001",
                    message="with_context must specify max_tokens to prevent context overflow",
                    suggestion="Add: with_context max_tokens: 100000 { ... }",
                ))

        # C-002: with_context max_tokens should be reasonable
        for wc in with_contexts:
            node_dict = wc if isinstance(wc, dict) else (wc.to_dict() if hasattr(wc, 'to_dict') else {})
            config = node_dict.get("config", {})
            max_tokens = config.get("max_tokens")
            if max_tokens is not None:
                try:
                    mt = int(max_tokens)
                    if mt > 200000:
                        report.add_warning(HarnessViolation(
                            dimension=HarnessDimension.C,
                            severity="warning",
                            rule_id="C-002",
                            message=f"with_context max_tokens={mt} exceeds recommended limit (200K)",
                            suggestion="Consider reducing max_tokens or using importance_weighted strategy",
                        ))
                except (ValueError, TypeError):
                    pass

        # C-003: context_policy should specify strategy
        for policy in policies:
            node_dict = policy if isinstance(policy, dict) else (policy.to_dict() if hasattr(policy, 'to_dict') else {})
            params = node_dict.get("params", {})
            if "strategy" not in params:
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.C,
                    severity="warning",
                    rule_id="C-003",
                    message="context_policy without strategy — default sliding_window may not be optimal",
                    suggestion="Add: strategy: importance_weighted or strategy: sliding_window",
                ))

        # v2.2.1 C-004: Pipeline context compatibility
        # For each A >> B pipeline, check that A's output_schema matches B's input_schema
        # (when both agents declare a context block).
        agents_by_name = {}
        for node in body:
            if isinstance(node, dict) and node.get("type") == "AgentDeclaration":
                name = node.get("name")
                spec = node.get("context_spec")
                if name and spec:
                    agents_by_name[name] = spec

        # v2.2.1: pipelines may be nested deeply (inside flow statements and
        # expression subtrees), so we walk the entire AST as a tree.
        agent_pairs = []
        seen_ids = set()
        stack = [body]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                node_id = id(current)
                if node_id in seen_ids:
                    continue
                seen_ids.add(node_id)
                if current.get("type") == "PipelineExpression":
                    stages = current.get("stages", [])
                    agent_names = [self._stage_agent_name(s) for s in stages]
                    flattened = []
                    for s, name in zip(stages, agent_names):
                        if name is not None:
                            flattened.append(name)
                        elif isinstance(s, dict) and s.get("type") == "PipelineExpression":
                            inner_names = [self._stage_agent_name(inner) for inner in s.get("stages", [])]
                            flattened.extend([x for x in inner_names if x])
                    if len(flattened) >= 2:
                        agent_pairs.append(flattened)
                stack.extend(v for v in current.values() if isinstance(v, (dict, list)))
            elif isinstance(current, list):
                stack.extend(current)

        for chain in agent_pairs:
            for i in range(len(chain) - 1):
                upstream_name, downstream_name = chain[i], chain[i + 1]
                upstream_spec = agents_by_name.get(upstream_name)
                downstream_spec = agents_by_name.get(downstream_name)
                if upstream_spec is None or downstream_spec is None:
                    continue
                out_schema = upstream_spec.get("output_schema")
                in_schema = downstream_spec.get("input_schema")
                if out_schema and in_schema and out_schema != in_schema:
                    report.add_error(HarnessViolation(
                        dimension=HarnessDimension.C,
                        severity="error",
                        rule_id="C-004",
                        message=(
                            f"Context incompatible in pipeline '{upstream_name} >> {downstream_name}': "
                            f"output_schema='{out_schema}' is not a subtype of input_schema='{in_schema}'"
                        ),
                        suggestion=(
                            f"Align {upstream_name}.context.output_schema with "
                            f"{downstream_name}.context.input_schema, or remove the mismatched schema."
                        ),
                    ))

        report.dimension_coverage["C"] = True

    @staticmethod
    def _stage_agent_name(stage: Any) -> Optional[str]:
        """Extract the agent name from a pipeline stage AST node."""
        if not isinstance(stage, dict):
            return None
        stype = stage.get("type")
        if stype == "Identifier":
            return stage.get("value")
        if stype == "MethodCallExpression":
            return stage.get("object")
        return None


class StateChecker(DimensionChecker):
    """S-dimension: validates snapshot/restore/fork, stateful branching."""

    dimension = HarnessDimension.S

    def check(self, ast: Dict, report: HarnessReport) -> None:
        body = _flatten_body(ast)
        snapshots = _collect_nodes_by_type(body, "SnapshotStmt")
        restores = _collect_nodes_by_type(body, "RestoreStmt")
        forks = _collect_nodes_by_type(body, "ForkStmt")

        # S-001: restore must reference a previously defined snapshot variable
        snapshot_vars: Set[str] = set()
        for snap in snapshots:
            node_dict = snap if isinstance(snap, dict) else (snap.to_dict() if hasattr(snap, 'to_dict') else {})
            var_name = node_dict.get("var_name")
            if var_name:
                snapshot_vars.add(var_name)

        for rest in restores:
            node_dict = rest if isinstance(rest, dict) else (rest.to_dict() if hasattr(rest, 'to_dict') else {})
            target_var = node_dict.get("target_var", "")
            if target_var and target_var not in snapshot_vars:
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.S,
                    severity="warning",
                    rule_id="S-001",
                    message=f"restore('{target_var}') references undefined snapshot variable",
                    suggestion=f"Define snapshot first: {target_var} = snapshot();",
                ))

        # S-002: fork must have at least 2 branches
        for fork in forks:
            node_dict = fork if isinstance(fork, dict) else (fork.to_dict() if hasattr(fork, 'to_dict') else {})
            branches = node_dict.get("branches", [])
            if len(branches) < 2:
                report.add_error(HarnessViolation(
                    dimension=HarnessDimension.S,
                    severity="error",
                    rule_id="S-002",
                    message="fork must have at least 2 branches for meaningful parallel exploration",
                    suggestion="Add more branches: fork [A.run(x), B.run(x), C.run(x)] merge best;",
                ))

        # S-003: fork merge strategy should be one of: best, first, all, vote
        valid_strategies = {"best", "first", "all", "vote"}
        for fork in forks:
            node_dict = fork if isinstance(fork, dict) else (fork.to_dict() if hasattr(fork, 'to_dict') else {})
            strategy = node_dict.get("merge_strategy", "best")
            if strategy not in valid_strategies:
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.S,
                    severity="warning",
                    rule_id="S-003",
                    message=f"fork merge strategy '{strategy}' is not standard (best/first/all/vote)",
                    suggestion="Use one of: best, first, all, vote",
                ))

        report.dimension_coverage["S"] = True


class LifecycleChecker(DimensionChecker):
    """L-dimension: validates hooks, reflect, on_error lifecycle constraints."""

    dimension = HarnessDimension.L

    def check(self, ast: Dict, report: HarnessReport) -> None:
        body = _flatten_body(ast)
        hooks = _collect_nodes_by_type(body, "LifecycleHook")
        reflects = _collect_nodes_by_type(body, "ReflectStmt")

        # L-001: before_step/after_step hooks should not be empty
        for hook in hooks:
            node_dict = hook if isinstance(hook, dict) else (hook.to_dict() if hasattr(hook, 'to_dict') else {})
            hook_type = node_dict.get("hook_type", "")
            hook_body = node_dict.get("body", [])
            if hook_type in ("before_step", "after_step") and not hook_body:
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.L,
                    severity="warning",
                    rule_id="L-001",
                    message=f"{hook_type} hook with empty body — consider removing or adding trace logic",
                    suggestion="Add body: { trace.log(\"step event\"); } or remove the hook",
                ))

        # L-002: on_error hook should capture error info
        for hook in hooks:
            node_dict = hook if isinstance(hook, dict) else (hook.to_dict() if hasattr(hook, 'to_dict') else {})
            hook_type = node_dict.get("hook_type", "")
            if hook_type == "on_error":
                error_var = node_dict.get("error_var")
                if not error_var:
                    report.add_warning(HarnessViolation(
                        dimension=HarnessDimension.L,
                        severity="warning",
                        rule_id="L-002",
                        message="on_error hook without error binding — error details unavailable",
                        suggestion="Add: on_error(e: ToolError) { ... }",
                    ))

        # L-003: reflect text should not be empty
        for ref in reflects:
            node_dict = ref if isinstance(ref, dict) else (ref.to_dict() if hasattr(ref, 'to_dict') else {})
            text = node_dict.get("text", "")
            if not text.strip():
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.L,
                    severity="warning",
                    rule_id="L-003",
                    message="reflect with empty text — no self-correction guidance for Agent",
                    suggestion="Add meaningful reflection text: reflect `Error: #{e}. Retry with different approach.`",
                ))

        report.dimension_coverage["L"] = True


class VerificationChecker(DimensionChecker):
    """V-dimension: validates verify constraints, acceptance criteria."""

    dimension = HarnessDimension.V

    def check(self, ast: Dict, report: HarnessReport) -> None:
        body = _flatten_body(ast)
        verifies = _collect_nodes_by_type(body, "VerifyStmt")

        # V-001: verify satisfies must reference a valid type/protocol
        for v in verifies:
            node_dict = v if isinstance(v, dict) else (v.to_dict() if hasattr(v, 'to_dict') else {})
            check_type = node_dict.get("check_type", "")
            if check_type == "satisfies":
                check_value = node_dict.get("check_value")
                if not check_value:
                    report.add_error(HarnessViolation(
                        dimension=HarnessDimension.V,
                        severity="error",
                        rule_id="V-001",
                        message="verify satisfies must specify a type or protocol to check against",
                        suggestion="Add: verify result satisfies AuthProtocol;",
                    ))

        # V-002: verify semantic should have meaningful condition text
        for v in verifies:
            node_dict = v if isinstance(v, dict) else (v.to_dict() if hasattr(v, 'to_dict') else {})
            check_type = node_dict.get("check_type", "")
            if check_type == "semantic":
                check_value = node_dict.get("check_value", "")
                if isinstance(check_value, str) and len(check_value.strip()) < 10:
                    report.add_warning(HarnessViolation(
                        dimension=HarnessDimension.V,
                        severity="warning",
                        rule_id="V-002",
                        message="verify semantic with short condition — may be too vague for LLM evaluation",
                        suggestion="Use more specific condition: verify \"output contains valid authentication token\" against result;",
                    ))

        # V-003: autoloop should have at least one verify for acceptance
        autoloops = _collect_nodes_by_type(body, "AutoLoopStmt")
        if autoloops and not verifies:
            report.add_warning(HarnessViolation(
                dimension=HarnessDimension.V,
                severity="warning",
                rule_id="V-003",
                message="autoloop without verify — no acceptance criteria for autonomous execution",
                suggestion="Add verify statement: verify result satisfies ExpectedOutput;",
            ))

        report.dimension_coverage["V"] = True


# ═══════════════════════════════════════════════════════════════════════
#  Cross-Dimension Checkers — holistic constraints across dimensions
# ═══════════════════════════════════════════════════════════════════════

class CrossDimensionChecker:
    """Validates constraints that span multiple Harness dimensions."""

    def check(self, ast: Dict, report: HarnessReport) -> None:
        body = _flatten_body(ast)
        all_nodes = _collect_all_nodes(body)

        # X-001: unharnessed blocks should be minimal and justified
        unharnessed = _collect_nodes_by_type(body, "UnharnessedStmt")
        for uh in unharnessed:
            node_dict = uh if isinstance(uh, dict) else (uh.to_dict() if hasattr(uh, 'to_dict') else {})
            reason = node_dict.get("reason")
            if not reason:
                report.add_error(HarnessViolation(
                    dimension=HarnessDimension.E,
                    severity="error",
                    rule_id="X-001",
                    message="unharnessed block must specify a reason for bypassing Harness constraints",
                    suggestion="Add: unharnessed(\"Legacy system requires direct shell access\") { ... }",
                ))
            uh_body = node_dict.get("body", [])
            if len(uh_body) > 5:
                report.add_warning(HarnessViolation(
                    dimension=HarnessDimension.E,
                    severity="warning",
                    rule_id="X-001b",
                    message=f"unharnessed block with {len(uh_body)} statements — consider reducing scope",
                    suggestion="Minimize unharnessed scope to only the necessary operations",
                ))

        # X-002: Agent declarations should use at least 3 Harness dimensions
        agent_nodes = _collect_nodes_by_type(body, "AgentDeclaration")
        for agent in agent_nodes:
            node_dict = agent if isinstance(agent, dict) else (agent.to_dict() if hasattr(agent, 'to_dict') else {})
            agent_body = node_dict.get("body", [])
            if isinstance(agent_body, list):
                dimensions_used: Set[str] = set()
                for stmt in agent_body:
                    stmt_type = _node_type(stmt)
                    dim_map = {
                        "AutoLoopStmt": "E", "TryAgentStmt": "E",
                        "ToolAnnotation": "T",
                        "WithContextStmt": "C", "ContextPolicyDecl": "C",
                        "SnapshotStmt": "S", "RestoreStmt": "S", "ForkStmt": "S",
                        "LifecycleHook": "L", "ReflectStmt": "L",
                        "VerifyStmt": "V",
                    }
                    if stmt_type in dim_map:
                        dimensions_used.add(dim_map[stmt_type])

                if len(dimensions_used) < 3:
                    report.add_warning(HarnessViolation(
                        dimension=HarnessDimension.E,
                        severity="warning",
                        rule_id="X-002",
                        message=f"Agent uses only {len(dimensions_used)} Harness dimensions ({', '.join(dimensions_used)}) — recommend ≥3 for robust Agent behavior",
                        suggestion="Add more Harness primitives: autoloop (E), verify (V), reflect (L)",
                    ))


# ═══════════════════════════════════════════════════════════════════════
#  Harness Validator — orchestrates all checkers
# ═══════════════════════════════════════════════════════════════════════

class HarnessValidator:
    """
    Compile-time Harness constraint validator.

    Orchestrates per-dimension checkers and cross-dimension checks,
    producing a structured HarnessReport.

    Usage:
        hv = HarnessValidator(mode=HarnessMode.STRICT)
        report = hv.validate(ast)
        if report.has_errors():
            print(report.to_json())
    """

    def __init__(self, mode: HarnessMode = HarnessMode.WARN) -> None:
        self.mode = mode
        self._checkers: List[DimensionChecker] = [
            ExecutionChecker(),
            ToolChecker(),
            ContextChecker(),
            StateChecker(),
            LifecycleChecker(),
            VerificationChecker(),
        ]
        self._cross_checkers: List[CrossDimensionChecker] = [
            CrossDimensionChecker(),
        ]
        self._custom_checkers: List[Callable[[Dict, HarnessReport], None]] = []

    def register_checker(self, checker: Callable[[Dict, HarnessReport], None]) -> None:
        """Register a custom validation checker function."""
        self._custom_checkers.append(checker)

    def validate(self, ast: Dict) -> HarnessReport:
        """
        Run all dimension checkers on the AST and return a HarnessReport.

        In WARN mode, errors are downgraded to warnings.
        In OFF mode, validation is skipped entirely.
        """
        if self.mode == HarnessMode.OFF:
            return HarnessReport()

        report = HarnessReport()

        # Run per-dimension checkers
        for checker in self._checkers:
            checker.check(ast, report)

        # Run cross-dimension checkers
        for cross_checker in self._cross_checkers:
            cross_checker.check(ast, report)

        # Run custom checkers
        for custom_checker in self._custom_checkers:
            custom_checker(ast, report)

        # In WARN mode, downgrade errors to warnings
        if self.mode == HarnessMode.WARN:
            for violation in report.errors:
                violation.severity = "warning"
                report.warnings.append(violation)
            report.errors = []
        # In STRICT mode, upgrade warnings to errors
        elif self.mode == HarnessMode.STRICT:
            for violation in report.warnings:
                violation.severity = "error"
                report.errors.append(violation)
            report.warnings = []

        return report