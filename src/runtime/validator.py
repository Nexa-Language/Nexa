"""
Nexa Validator — Agent-Native Syntax Validation with Machine-Readable Error Output

Provides `validate_nexa_file()` to verify .nx files and return structured JSON error reports,
enabling AI Agents to understand and fix errors programmatically.

Key capabilities:
- Parse validation (detect syntax errors with file:line:column)
- Semantic validation (unused declarations, missing references)
- Every error includes fix_hint for Agent-driven auto-fix
- Dual output mode: JSON (machine-readable) + colored text (human-readable)
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ValidationError:
    """Represents a single validation error or warning."""

    def __init__(
        self,
        file: str,
        line: int,
        column: int,
        error_type: str,
        message: str,
        fix_hint: str = "",
        severity: str = "error"
    ):
        self.file = file
        self.line = line
        self.column = column
        self.error_type = error_type
        self.message = message
        self.fix_hint = fix_hint
        self.severity = severity  # "error" or "warning"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-compatible dictionary."""
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "error_type": self.error_type,
            "message": self.message,
            "fix_hint": self.fix_hint,
            "severity": self.severity,
        }


def validate_nexa_file(file_path: str) -> Dict[str, Any]:
    """
    Validate a .nx file and return a machine-readable JSON validation result.

    This function performs two levels of validation:
    1. Parse validation — attempt to parse the file, collect syntax errors
    2. Semantic validation — check for unused declarations, missing references, etc.

    Args:
        file_path: Path to the .nx file to validate

    Returns:
        Dict with structure:
        {
            "valid": bool,
            "errors": [ValidationError dicts],
            "warnings": [ValidationError dicts],
            "summary": {"errors": N, "warnings": N, "total_checks": N}
        }
    """
    input_path = Path(file_path)
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []

    # Step 1: File existence check
    if not input_path.exists():
        errors.append(ValidationError(
            file=file_path,
            line=0,
            column=0,
            error_type="FileNotFound",
            message=f"File '{file_path}' does not exist",
            fix_hint="Create the file or check the file path for typos",
            severity="error"
        ))
        return _build_result(errors, warnings)

    # Step 2: File extension check
    if input_path.suffix != '.nx':
        warnings.append(ValidationError(
            file=file_path,
            line=0,
            column=0,
            error_type="WrongExtension",
            message=f"File '{file_path}' does not have a .nx extension",
            fix_hint="Rename the file to use the .nx extension",
            severity="warning"
        ))

    # Step 3: Read source and attempt to parse
    with open(input_path, 'r', encoding='utf-8') as f:
        source_code = f.read()

    ast = None
    try:
        from nexa_parser import parse
        ast = parse(source_code)
    except Exception as e:
        # Parse error — extract location info if available
        parse_error = _parse_error_to_validation_error(e, file_path, source_code)
        if parse_error:
            errors.append(parse_error)
        else:
            # Generic parse error
            errors.append(ValidationError(
                file=file_path,
                line=_extract_line_from_error(e),
                column=_extract_column_from_error(e),
                error_type="ParseError",
                message=str(e),
                fix_hint="Check syntax against Nexa language specification",
                severity="error"
            ))
        # If parse failed, we can't do semantic validation
        return _build_result(errors, warnings, total_checks=1)

    # Step 4: Semantic validation (only if parsing succeeded)
    semantic_errors, semantic_warnings = _semantic_validation(ast, file_path, source_code)
    errors.extend(semantic_errors)
    warnings.extend(semantic_warnings)

    total_checks = 1 + len(_SEMANTIC_CHECK_NAMES)  # 1 parse + semantic checks
    return _build_result(errors, warnings, total_checks=total_checks)


# ===== Semantic Validation Checks =====

_SEMANTIC_CHECK_NAMES = [
    "UnusedAgent",
    "UnusedTool",
    "UnusedProtocol",
    "MissingProtocolReference",
    "MissingToolReference",
    "EmptyFlowBody",
    "MissingAgentPrompt",
]


def _semantic_validation(
    ast: Dict[str, Any],
    file_path: str,
    source_code: str
) -> Tuple[List[ValidationError], List[ValidationError]]:
    """
    Perform semantic validation checks on a parsed AST.

    Checks:
    - Unused agents/tools/protocols (declared but never referenced in flows)
    - implements references non-existent protocol
    - uses references non-existent tool
    - Empty flow body
    - Agent missing prompt
    """
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []

    body = ast.get("body", [])

    # Collect all declarations
    agent_names = set()
    tool_names = set()
    protocol_names = set()
    flow_names = set()

    # Collect all references (from flows and agent uses/implements)
    referenced_agents = set()
    referenced_tools = set()
    referenced_protocols = set()

    # First pass: collect declarations
    for item in body:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type", "")

        if item_type == "AgentDeclaration":
            name = item.get("name", "")
            agent_names.add(name)

            # Check implements reference
            implements = item.get("implements")
            if implements:
                referenced_protocols.add(implements)

            # Check uses reference
            uses = item.get("uses", []) or []
            for u in uses:
                if isinstance(u, str):
                    # Stdlib references (std.xxx) don't need tool declarations
                    if not u.startswith("std.") and not u.startswith("mcp:"):
                        referenced_tools.add(u)

            # Check for missing prompt
            properties = item.get("properties", {})
            prompt = item.get("prompt", properties.get("prompt", ""))
            if not prompt:
                # Find approximate line number
                line = _find_declaration_line(source_code, "agent", name)
                warnings.append(ValidationError(
                    file=file_path,
                    line=line,
                    column=1,
                    error_type="MissingAgentPrompt",
                    message=f"Agent '{name}' has no prompt defined",
                    fix_hint=f"Add a 'prompt' property to agent '{name}', e.g.: prompt: \"You are a helpful assistant\"",
                    severity="warning"
                ))

        elif item_type == "ToolDeclaration":
            tool_names.add(item.get("name", ""))

        elif item_type == "ProtocolDeclaration":
            protocol_names.add(item.get("name", ""))

        elif item_type == "FlowDeclaration":
            flow_names.add(item.get("name", ""))

    # Second pass: collect references from flow bodies
    for item in body:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "FlowDeclaration":
            flow_name = item.get("name", "")
            flow_body = item.get("body", []) or []

            # Check for empty flow body
            if not flow_body:
                line = _find_declaration_line(source_code, "flow", flow_name)
                warnings.append(ValidationError(
                    file=file_path,
                    line=line,
                    column=1,
                    error_type="EmptyFlowBody",
                    message=f"Flow '{flow_name}' has an empty body",
                    fix_hint=f"Add statements to flow '{flow_name}' or remove the declaration",
                    severity="warning"
                ))

            # Collect agent/tool references from flow body
            _collect_references_from_body(
                flow_body, referenced_agents, referenced_tools, agent_names, tool_names
            )

    # Also check: match statements reference agents
    for item in body:
        if isinstance(item, dict) and item.get("type") == "FlowDeclaration":
            flow_body = item.get("body", []) or []
            for stmt in flow_body:
                if isinstance(stmt, dict) and stmt.get("type") == "MatchIntentStatement":
                    cases = stmt.get("cases", [])
                    for case in cases:
                        if isinstance(case, dict):
                            expr = case.get("expression")
                            _collect_agent_refs_from_expr(expr, referenced_agents, agent_names)
                    default = stmt.get("default")
                    if isinstance(default, dict):
                        expr = default.get("expression")
                        _collect_agent_refs_from_expr(expr, referenced_agents, agent_names)

    # Check: implements references non-existent protocol
    for item in body:
        if isinstance(item, dict) and item.get("type") == "AgentDeclaration":
            name = item.get("name", "")
            implements = item.get("implements")
            if implements and implements not in protocol_names:
                line = _find_declaration_line(source_code, "agent", name)
                errors.append(ValidationError(
                    file=file_path,
                    line=line,
                    column=1,
                    error_type="MissingProtocolReference",
                    message=f"Agent '{name}' implements non-existent protocol '{implements}'",
                    fix_hint=f"Define protocol '{implements}' or fix the implements reference in agent '{name}'",
                    severity="error"
                ))

    # Check: uses references non-existent tool
    for item in body:
        if isinstance(item, dict) and item.get("type") == "AgentDeclaration":
            name = item.get("name", "")
            uses = item.get("uses", []) or []
            for u in uses:
                if isinstance(u, str):
                    if not u.startswith("std.") and not u.startswith("mcp:") and u not in tool_names:
                        line = _find_declaration_line(source_code, "agent", name)
                        errors.append(ValidationError(
                            file=file_path,
                            line=line,
                            column=1,
                            error_type="MissingToolReference",
                            message=f"Agent '{name}' uses non-existent tool '{u}'",
                            fix_hint=f"Define tool '{u}' or remove it from the uses clause in agent '{name}'",
                            severity="error"
                        ))

    # Check: unused agents
    for name in agent_names:
        if name not in referenced_agents:
            line = _find_declaration_line(source_code, "agent", name)
            warnings.append(ValidationError(
                file=file_path,
                line=line,
                column=1,
                error_type="UnusedAgent",
                message=f"Agent '{name}' is declared but never used in any flow",
                fix_hint=f"Add '{name}' to a flow pipeline or remove the declaration",
                severity="warning"
            ))

    # Check: unused tools (only warn for local tools, MCP tools may be used dynamically)
    for name in tool_names:
        if name not in referenced_tools:
            line = _find_declaration_line(source_code, "tool", name)
            warnings.append(ValidationError(
                file=file_path,
                line=line,
                column=1,
                error_type="UnusedTool",
                message=f"Tool '{name}' is declared but never used by any agent",
                fix_hint=f"Add '{name}' to an agent's uses clause or remove the declaration",
                severity="warning"
            ))

    # Check: unused protocols
    for name in protocol_names:
        if name not in referenced_protocols:
            line = _find_declaration_line(source_code, "protocol", name)
            warnings.append(ValidationError(
                file=file_path,
                line=line,
                column=1,
                error_type="UnusedProtocol",
                message=f"Protocol '{name}' is declared but never implemented by any agent",
                fix_hint=f"Add 'implements {name}' to an agent declaration or remove the protocol",
                severity="warning"
            ))

    return errors, warnings


def _collect_references_from_body(
    body: List[Any],
    referenced_agents: set,
    referenced_tools: set,
    agent_names: set,
    tool_names: set,
):
    """Collect agent and tool references from flow body statements."""
    for stmt in body:
        if not isinstance(stmt, dict):
            continue

        stmt_type = stmt.get("type", "")

        if stmt_type == "AssignmentStatement":
            value = stmt.get("value")
            _collect_agent_refs_from_expr(value, referenced_agents, agent_names)
            _collect_tool_refs_from_expr(value, referenced_tools, tool_names)

        elif stmt_type == "ExpressionStatement":
            expr = stmt.get("expression")
            _collect_agent_refs_from_expr(expr, referenced_agents, agent_names)
            _collect_tool_refs_from_expr(expr, referenced_tools, tool_names)

        elif stmt_type == "MatchIntentStatement":
            cases = stmt.get("cases", [])
            for case in cases:
                if isinstance(case, dict):
                    _collect_agent_refs_from_expr(case.get("expression"), referenced_agents, agent_names)
            default = stmt.get("default")
            if isinstance(default, dict):
                _collect_agent_refs_from_expr(default.get("expression"), referenced_agents, agent_names)


def _collect_agent_refs_from_expr(expr: Any, referenced_agents: set, agent_names: set):
    """Recursively collect agent name references from an expression."""
    if expr is None:
        return
    if isinstance(expr, str):
        if expr in agent_names:
            referenced_agents.add(expr)
        return
    if not isinstance(expr, dict):
        return

    expr_type = expr.get("type", "")

    if expr_type == "Identifier" or expr_type == "id_expr":
        name = expr.get("value", expr.get("name", ""))
        if name in agent_names:
            referenced_agents.add(name)

    elif expr_type == "PipelineExpression":
        for stage in expr.get("stages", []):
            _collect_agent_refs_from_expr(stage, referenced_agents, agent_names)

    elif expr_type == "DAGForkExpression":
        _collect_agent_refs_from_expr(expr.get("input"), referenced_agents, agent_names)
        for agent in expr.get("agents", []):
            if isinstance(agent, str) and agent in agent_names:
                referenced_agents.add(agent)
            elif isinstance(agent, dict):
                _collect_agent_refs_from_expr(agent, referenced_agents, agent_names)

    elif expr_type == "DAGMergeExpression":
        for agent in expr.get("agents", []):
            if isinstance(agent, str) and agent in agent_names:
                referenced_agents.add(agent)
            elif isinstance(agent, dict):
                _collect_agent_refs_from_expr(agent, referenced_agents, agent_names)
        _collect_agent_refs_from_expr(expr.get("merger"), referenced_agents, agent_names)

    elif expr_type == "DAGBranchExpression":
        _collect_agent_refs_from_expr(expr.get("input"), referenced_agents, agent_names)
        _collect_agent_refs_from_expr(expr.get("true_branch"), referenced_agents, agent_names)
        _collect_agent_refs_from_expr(expr.get("false_branch"), referenced_agents, agent_names)

    elif expr_type == "MethodCallExpr" or expr_type == "method_call":
        # Agent.run(x) references the agent
        receiver = expr.get("object", expr.get("receiver", ""))
        if isinstance(receiver, str) and receiver in agent_names:
            referenced_agents.add(receiver)
        elif isinstance(receiver, dict):
            _collect_agent_refs_from_expr(receiver, referenced_agents, agent_names)

    elif expr_type == "FallbackExpr":
        _collect_agent_refs_from_expr(expr.get("primary"), referenced_agents, agent_names)
        _collect_agent_refs_from_expr(expr.get("backup"), referenced_agents, agent_names)

    # Check all dict values recursively for common keys
    for key in ["left", "right", "condition", "consequence", "alternative", "value"]:
        val = expr.get(key)
        if isinstance(val, dict):
            _collect_agent_refs_from_expr(val, referenced_agents, agent_names)
        elif isinstance(val, list):
            for item in val:
                _collect_agent_refs_from_expr(item, referenced_agents, agent_names)


def _collect_tool_refs_from_expr(expr: Any, referenced_tools: set, tool_names: set):
    """Collect tool name references from expressions (method calls on tools)."""
    if expr is None:
        return
    if isinstance(expr, str):
        if expr in tool_names:
            referenced_tools.add(expr)
        return
    if not isinstance(expr, dict):
        return

    expr_type = expr.get("type", "")

    if expr_type == "MethodCallExpr" or expr_type == "method_call":
        receiver = expr.get("object", expr.get("receiver", ""))
        if isinstance(receiver, str) and receiver in tool_names:
            referenced_tools.add(receiver)

    # std.xxx calls reference stdlib tools (not user-declared ones)
    if expr_type == "std_call":
        # std.xxx.yyy — this is a stdlib reference, not a user tool
        pass


# ===== Error Formatting =====

def _find_declaration_line(source_code: str, keyword: str, name: str) -> int:
    """Find the approximate line number of a declaration in source code."""
    lines = source_code.split('\n')
    for i, line in enumerate(lines):
        # Match: agent Name, tool Name, protocol Name, flow Name
        pattern = rf'{keyword}\s+{re.escape(name)}'
        if re.search(pattern, line):
            return i + 1
    return 0


def _parse_error_to_validation_error(
    exception: Exception,
    file_path: str,
    source_code: str
) -> Optional[ValidationError]:
    """
    Try to convert a Lark parse error into a structured ValidationError
    with line/column information and a fix_hint.
    """
    error_str = str(exception)

    # Lark UnexpectedToken / UnexpectedCharacters errors have structured format
    # Try to extract line and column
    line = _extract_line_from_error(exception)
    column = _extract_column_from_error(exception)

    # Generate fix_hint based on error type
    fix_hint = _generate_fix_hint(error_str)

    return ValidationError(
        file=file_path,
        line=line,
        column=column,
        error_type="ParseError",
        message=error_str,
        fix_hint=fix_hint,
        severity="error"
    )


def _extract_line_from_error(exception: Exception) -> int:
    """Extract line number from a Lark parse error."""
    error_str = str(exception)
    # Lark format: "at line X, col Y"
    match = re.search(r'at line (\d+)', error_str)
    if match:
        return int(match.group(1))
    # Alternative format: "line:X"
    match = re.search(r'line[:\s]*(\d+)', error_str)
    if match:
        return int(match.group(1))
    # Check for attribute on exception
    if hasattr(exception, 'line') and exception.line is not None:
        return int(exception.line)
    # Check for token with line info
    if hasattr(exception, 'token') and hasattr(exception.token, 'line'):
        return int(exception.token.line)
    return 0


def _extract_column_from_error(exception: Exception) -> int:
    """Extract column number from a Lark parse error."""
    error_str = str(exception)
    match = re.search(r'col(?:umn)?[:\s]*(\d+)', error_str)
    if match:
        return int(match.group(1))
    if hasattr(exception, 'column') and exception.column is not None:
        return int(exception.column)
    if hasattr(exception, 'token') and hasattr(exception.token, 'column'):
        return int(exception.token.column)
    return 0


def _generate_fix_hint(error_str: str) -> str:
    """Generate a contextual fix_hint based on the error message."""

    # Unexpected token patterns
    if "Unexpected token" in error_str:
        # Try to identify what was expected vs what was found
        if "requires" in error_str:
            return "Ensure 'requires' clause comes before the agent body block"
        if "ensures" in error_str:
            return "Ensure 'ensures' clause comes after 'requires' and before the agent body block"
        if ">>" in error_str:
            return "Check that pipeline expressions use proper syntax: expr >> Agent"
        if "|>>" in error_str:
            return "Check that fork expressions use proper syntax: expr |>> [Agent1, Agent2]"
        if "&>>" in error_str:
            return "Check that merge expressions use proper syntax: [Agent1, Agent2] &>> Merger"
        if "implements" in error_str:
            return "Check that 'implements' keyword is followed by a protocol name"
        if "uses" in error_str:
            return "Check that 'uses' keyword is followed by tool name(s)"
        return "Check syntax against Nexa language specification"

    if "UnexpectedCharacters" in error_str or "unexpected character" in error_str:
        return "Remove or escape the unexpected character"

    if "expecting" in error_str:
        return "Check that all required syntax elements are present"

    return "Check syntax against Nexa language specification"


def _build_result(
    errors: List[ValidationError],
    warnings: List[ValidationError],
    total_checks: int = 0,
) -> Dict[str, Any]:
    """Build the final validation result dictionary."""

    valid = len(errors) == 0

    if total_checks == 0:
        total_checks = 1 + len(_SEMANTIC_CHECK_NAMES)

    return {
        "valid": valid,
        "errors": [e.to_dict() for e in errors],
        "warnings": [w.to_dict() for w in warnings],
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "total_checks": total_checks,
        }
    }


# ===== Output Formatting =====

def format_error_json(result: Dict[str, Any]) -> str:
    """Format validation result as machine-readable JSON string."""
    return json.dumps(result, indent=2, ensure_ascii=False)


def format_error_human(result: Dict[str, Any], quiet: bool = False) -> str:
    """
    Format validation result as human-readable colored text.

    Uses ANSI escape codes:
    - Red (91) for errors
    - Yellow (93) for warnings
    - Green (92) for success
    - Bold (1) for headers

    Args:
        result: Validation result dictionary
        quiet: If True, only output errors/warnings (no success message)
    """
    lines = []

    valid = result.get("valid", False)
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])
    summary = result.get("summary", {})

    if not quiet:
        if valid and not warnings:
            lines.append(f"\033[92m✅ All checks passed!\033[0m")
        elif valid and warnings:
            lines.append(f"\033[92m✅ Syntax valid\033[0m, but with warnings:")
        else:
            lines.append(f"\033[91m❌ Validation failed\033[0m")

    # Format errors
    if errors:
        if not quiet:
            lines.append("")
            lines.append(f"\033[1m\033[91mErrors ({len(errors)}):\033[0m")
        for err in errors:
            line_str = f":{err['line']}" if err.get('line', 0) > 0 else ""
            col_str = f":{err['column']}" if err.get('column', 0) > 0 else ""
            loc = f"{err['file']}{line_str}{col_str}"
            lines.append(f"  \033[91m[{err.get('error_type', 'Error')}]\033[0m {loc}")
            lines.append(f"    {err.get('message', '')}")
            if err.get('fix_hint'):
                lines.append(f"    \033[2m💡 Fix: {err['fix_hint']}\033[0m")

    # Format warnings
    if warnings:
        if not quiet:
            lines.append("")
            lines.append(f"\033[1m\033[93mWarnings ({len(warnings)}):\033[0m")
        for warn in warnings:
            line_str = f":{warn['line']}" if warn.get('line', 0) > 0 else ""
            col_str = f":{warn['column']}" if warn.get('column', 0) > 0 else ""
            loc = f"{warn['file']}{line_str}{col_str}"
            lines.append(f"  \033[93m[{warn.get('error_type', 'Warning')}]\033[0m {loc}")
            lines.append(f"    {warn.get('message', '')}")
            if warn.get('fix_hint'):
                lines.append(f"    \033[2m💡 Fix: {warn['fix_hint']}\033[0m")

    if not quiet:
        lines.append("")
        lines.append(f"\033[2mSummary: {summary.get('errors', 0)} errors, {summary.get('warnings', 0)} warnings, {summary.get('total_checks', 0)} checks\033[0m")

    return "\n".join(lines)