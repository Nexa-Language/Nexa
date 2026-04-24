# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================

"""
Nexa Inspector — Agent-Native Tooling for Code Structure Analysis

Provides `inspect_nexa_file()` to produce a complete JSON description of a .nx program,
enabling AI Agents to understand the entire codebase in a single call.

Key capabilities:
- Extract all agents (with contracts, decorators, implements_annotations)
- Extract all tools (with description, parameters, type)
- Extract all protocols (with fields)
- Extract all flows (with parameters, statements, inferred DAG topology)
- Extract all tests (with assertions)
- Extract all types (with base_type, constraint)
- Extract imports
- Generate summary statistics
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def inspect_nexa_file(file_path: str) -> Dict[str, Any]:
    """
    Inspect a .nx file and return a complete JSON structure description.

    This is the core function that lets an Agent understand an entire Nexa program
    in a single call — no need to read source files individually.

    Args:
        file_path: Path to the .nx file to inspect

    Returns:
        Dict containing the complete structural description of the program,
        including agents, tools, protocols, flows, tests, types, imports,
        and summary statistics.
    """
    input_path = Path(file_path)
    if not input_path.exists():
        return {
            "file": file_path,
            "error": f"File '{file_path}' does not exist",
            "agents": [],
            "tools": [],
            "protocols": [],
            "flows": [],
            "tests": [],
            "types": [],
            "imports": [],
            "summary": {}
        }

    # Read source code
    with open(input_path, 'r', encoding='utf-8') as f:
        source_code = f.read()

    # Parse the file
    try:
        from nexa_parser import parse
        ast = parse(source_code)
    except Exception as e:
        # If parsing fails, still return partial info from regex-based extraction
        return _inspect_from_source(file_path, source_code, parse_error=str(e))

    # Build structured description from AST
    result = _inspect_from_ast(file_path, ast, source_code)
    return result


def _inspect_from_ast(file_path: str, ast: Dict[str, Any], source_code: str) -> Dict[str, Any]:
    """Build the inspection result from a parsed AST."""

    agents = []
    tools = []
    protocols = []
    flows = []
    tests = []
    types_list = []
    imports = []
    implements_annotations = []

    # Extract implements annotations from source (comments-based)
    from nexa_parser import extract_implements_annotations
    annotations = extract_implements_annotations(source_code)
    if annotations:
        implements_annotations = annotations

    # Process AST body
    body = ast.get("body", [])
    includes = ast.get("includes", [])

    # Collect imports
    for inc in includes:
        if isinstance(inc, dict) and inc.get("type") == "IncludeStatement":
            imports.append(inc.get("path", ""))

    # Collect all declared names for reference checking
    agent_names = set()
    tool_names = set()
    protocol_names = set()

    for item in body:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type", "")

        if item_type == "AgentDeclaration":
            agent_info = _extract_agent_info(item, implements_annotations)
            agents.append(agent_info)
            agent_names.add(item.get("name", ""))

        elif item_type == "ToolDeclaration":
            tool_info = _extract_tool_info(item)
            tools.append(tool_info)
            tool_names.add(item.get("name", ""))

        elif item_type == "ProtocolDeclaration":
            protocol_info = _extract_protocol_info(item)
            protocols.append(protocol_info)
            protocol_names.add(item.get("name", ""))

        elif item_type == "FlowDeclaration":
            flow_info = _extract_flow_info(item)
            flows.append(flow_info)

        elif item_type == "TestDeclaration":
            test_info = _extract_test_info(item)
            tests.append(test_info)

        elif item_type == "TypeDeclaration":
            type_info = _extract_type_info(item)
            types_list.append(type_info)

    # Build summary
    summary = {
        "total_agents": len(agents),
        "total_tools": len(tools),
        "total_protocols": len(protocols),
        "total_flows": len(flows),
        "total_tests": len(tests),
        "total_types": len(types_list),
        "total_imports": len(imports),
    }

    result = {
        "file": file_path,
        "version": _detect_version(source_code),
        "agents": agents,
        "tools": tools,
        "protocols": protocols,
        "flows": flows,
        "tests": tests,
        "types": types_list,
        "imports": imports,
        "implements_annotations": _format_implements_annotations(implements_annotations),
        "summary": summary,
    }

    return result


def _inspect_from_source(file_path: str, source_code: str, parse_error: str) -> Dict[str, Any]:
    """
    Fallback: extract structural info from source code using regex
    when the parser fails. Provides partial but useful information.
    """
    agents = []
    tools = []
    protocols = []
    flows = []
    imports = []

    # Regex-based extraction for basic info
    # Agents
    for match in re.finditer(r'(@[\w()=,.]+\s*\n\s*)*agent\s+(\w+)', source_code):
        agent_name = match.group(2)
        # Extract role
        role_match = re.search(rf'agent\s+{agent_name}\s*[^\{{]*\{{[^}}]*role:\s*"([^"]*)"', source_code)
        role = role_match.group(1) if role_match else ""
        agents.append({"name": agent_name, "role": role})

    # Tools
    for match in re.finditer(r'tool\s+(\w+)\s*\{', source_code):
        tool_name = match.group(1)
        # Check for MCP or Python tool
        mcp_match = re.search(rf'tool\s+{tool_name}\s*\{{[^}}]*mcp:\s*"([^"]*)"', source_code)
        python_match = re.search(rf'tool\s+{tool_name}\s*\{{[^}}]*python:\s*"([^"]*)"', source_code)
        desc_match = re.search(rf'tool\s+{tool_name}\s*\{{[^}}]*description:\s*"([^"]*)"', source_code)

        if mcp_match:
            tools.append({"name": tool_name, "type": "mcp", "mcp": mcp_match.group(1)})
        elif python_match:
            tools.append({"name": tool_name, "type": "python", "python": python_match.group(1)})
        else:
            desc = desc_match.group(1) if desc_match else ""
            tools.append({"name": tool_name, "description": desc, "type": "local"})

    # Protocols
    for match in re.finditer(r'protocol\s+(\w+)\s*\{', source_code):
        protocol_name = match.group(1)
        protocols.append({"name": protocol_name, "fields": {}})

    # Flows
    for match in re.finditer(r'flow\s+(\w+)', source_code):
        flow_name = match.group(1)
        flows.append({"name": flow_name, "parameters": [], "dag_topology": []})

    # Imports
    for match in re.finditer(r'include\s+"([^"]*)"\s*;', source_code):
        imports.append(match.group(1))

    return {
        "file": file_path,
        "version": _detect_version(source_code),
        "parse_error": parse_error,
        "agents": agents,
        "tools": tools,
        "protocols": protocols,
        "flows": flows,
        "tests": [],
        "types": [],
        "imports": imports,
        "implements_annotations": [],
        "summary": {
            "total_agents": len(agents),
            "total_tools": len(tools),
            "total_protocols": len(protocols),
            "total_flows": len(flows),
            "total_tests": 0,
            "total_types": 0,
            "total_imports": len(imports),
            "note": "Partial extraction due to parse error"
        }
    }


def _detect_version(source_code: str) -> str:
    """Detect Nexa version from source code comments."""
    version_match = re.search(r'//\s*Nexa\s+v?([\d.]+)', source_code)
    if version_match:
        return version_match.group(1)
    # Default version based on syntax features detected
    if 'requires' in source_code or 'ensures' in source_code:
        return "1.1"
    if '|>>' in source_code or '&>>' in source_code:
        return "1.0"
    if 'semantic_if' in source_code:
        return "0.9"
    return "1.0"


def _extract_agent_info(agent_decl: Dict[str, Any], annotations: List[Dict]) -> Dict[str, Any]:
    """Extract detailed agent information from an AgentDeclaration AST node."""

    name = agent_decl.get("name", "")
    properties = agent_decl.get("properties", {})
    uses = agent_decl.get("uses", []) or []
    implements = agent_decl.get("implements")

    # Decorators — infer name from params if empty (Lark transformer issue)
    decorators = []
    for dec in agent_decl.get("decorators", []):
        dec_name = dec.get("name", "")
        dec_params = dec.get("params", {})
        if not dec_name:
            if "max_tokens" in dec_params:
                dec_name = "limit"
            elif "seconds" in dec_params:
                dec_name = "timeout"
            elif "max_attempts" in dec_params:
                dec_name = "retry"
            elif "value" in dec_params:
                dec_name = "temperature"
        dec_info = {
            "name": dec_name,
            "params": dec_params
        }
        decorators.append(dec_info)

    # Contracts (requires/ensures)
    requires_list = []
    for req in agent_decl.get("requires", []):
        if isinstance(req, dict):
            if req.get("is_semantic"):
                requires_list.append(req.get("condition_text", ""))
            else:
                requires_list.append(req.get("expression", ""))

    ensures_list = []
    for ens in agent_decl.get("ensures", []):
        if isinstance(ens, dict):
            if ens.get("is_semantic"):
                ensures_list.append(ens.get("condition_text", ""))
            else:
                ensures_list.append(ens.get("expression", ""))

    # Implements annotations from comments (@implements: feature.id)
    impl_annotations = []
    for ann in annotations:
        if isinstance(ann, dict) and ann.get("agent_name") == name:
            impl_annotations.append(ann.get("feature_id", ann.get("constraint_id", "")))

    # Format uses list — check both AST uses field and properties dict
    uses_formatted = []
    for u in uses:
        if isinstance(u, str):
            uses_formatted.append(u)
        elif isinstance(u, dict):
            uses_formatted.append(str(u))
    # Also check properties for uses (some .nx files put uses as a property)
    prop_uses = properties.get("uses")
    if prop_uses and prop_uses not in uses_formatted:
        if isinstance(prop_uses, str):
            uses_formatted.append(prop_uses)
        elif isinstance(prop_uses, list):
            for u in prop_uses:
                if u not in uses_formatted:
                    uses_formatted.append(u)

    agent_info = {
        "name": name,
        "role": properties.get("role", ""),
        "model": properties.get("model", ""),
        "prompt": agent_decl.get("prompt", ""),
        "protocol": implements or "",
        "tools": uses_formatted,
        "decorators": decorators,
        "contracts": {
            "requires": requires_list,
            "ensures": ensures_list,
        },
        "implements_annotations": impl_annotations,
        "properties": properties,
    }

    # Clean up empty values for cleaner JSON
    if not agent_info["model"]:
        del agent_info["model"]
    if not agent_info["prompt"]:
        del agent_info["prompt"]
    if not agent_info["protocol"]:
        del agent_info["protocol"]
    if not agent_info["tools"]:
        del agent_info["tools"]
    if not agent_info["decorators"]:
        del agent_info["decorators"]
    if not agent_info["contracts"]["requires"] and not agent_info["contracts"]["ensures"]:
        del agent_info["contracts"]
    if not agent_info["implements_annotations"]:
        del agent_info["implements_annotations"]
    if not agent_info["properties"]:
        del agent_info["properties"]

    return agent_info


def _extract_tool_info(tool_decl: Dict[str, Any]) -> Dict[str, Any]:
    """Extract detailed tool information from a ToolDeclaration AST node."""

    name = tool_decl.get("name", "")

    # Determine tool type
    if "mcp" in tool_decl:
        return {
            "name": name,
            "mcp": tool_decl.get("mcp", ""),
            "type": "mcp"
        }
    elif "python" in tool_decl:
        return {
            "name": name,
            "python": tool_decl.get("python", ""),
            "type": "python"
        }
    else:
        description = tool_decl.get("description", "")
        parameters = tool_decl.get("parameters", {})
        # Simplify parameters for readability
        if isinstance(parameters, dict):
            params_simplified = parameters
        else:
            params_simplified = {}

        result = {
            "name": name,
            "description": description,
            "parameters": params_simplified,
            "type": "local"
        }
        if not description:
            del result["description"]
        if not params_simplified:
            del result["parameters"]
        return result


def _extract_protocol_info(protocol_decl: Dict[str, Any]) -> Dict[str, Any]:
    """Extract protocol information from a ProtocolDeclaration AST node."""
    return {
        "name": protocol_decl.get("name", ""),
        "fields": protocol_decl.get("fields", {})
    }


def _extract_flow_info(flow_decl: Dict[str, Any]) -> Dict[str, Any]:
    """Extract flow information including inferred DAG topology."""

    name = flow_decl.get("name", "")
    params = flow_decl.get("params", []) or []
    body = flow_decl.get("body", []) or []

    # Format parameters
    parameters = []
    for p in params:
        if isinstance(p, dict) and "name" in p:
            parameters.append({"name": p.get("name", ""), "type": p.get("type", "")})
        elif isinstance(p, dict):
            parameters.append(p)

    # Contracts
    requires_list = []
    for req in flow_decl.get("requires", []):
        if isinstance(req, dict):
            if req.get("is_semantic"):
                requires_list.append(req.get("condition_text", ""))
            else:
                requires_list.append(req.get("expression", ""))

    ensures_list = []
    for ens in flow_decl.get("ensures", []):
        if isinstance(ens, dict):
            if ens.get("is_semantic"):
                ensures_list.append(ens.get("condition_text", ""))
            else:
                ensures_list.append(ens.get("expression", ""))

    contracts = {}
    if requires_list:
        contracts["requires"] = requires_list
    if ensures_list:
        contracts["ensures"] = ensures_list

    # Infer DAG topology from flow body
    dag_topology = infer_dag_topology(body)

    # Count statements
    statements_count = len(body)

    flow_info = {
        "name": name,
        "parameters": parameters,
        "statements_count": statements_count,
        "dag_topology": dag_topology,
    }

    if contracts:
        flow_info["contracts"] = contracts

    return flow_info


def _extract_test_info(test_decl: Dict[str, Any]) -> Dict[str, Any]:
    """Extract test information from a TestDeclaration AST node."""
    body = test_decl.get("body", []) or []
    # Count assertions in the test body
    assertions_count = 0
    for stmt in body:
        if isinstance(stmt, dict):
            if stmt.get("type") == "AssertStatement":
                assertions_count += 1

    return {
        "name": test_decl.get("name", ""),
        "assertions_count": assertions_count
    }


def _extract_type_info(type_decl: Dict[str, Any]) -> Dict[str, Any]:
    """Extract semantic type information from a TypeDeclaration AST node."""
    name = type_decl.get("name", "")
    definition = type_decl.get("definition")

    if isinstance(definition, dict):
        if definition.get("type") == "SemanticType":
            return {
                "name": name,
                "base_type": _format_base_type(definition.get("base_type")),
                "constraint": definition.get("constraint", "")
            }
        elif definition.get("type") == "BaseType":
            return {
                "name": name,
                "base_type": definition.get("name", ""),
                "constraint": ""
            }
        elif definition.get("type") == "CustomType":
            return {
                "name": name,
                "base_type": definition.get("name", ""),
                "constraint": ""
            }
        elif definition.get("type") == "GenericType":
            return {
                "name": name,
                "base_type": f"{definition.get('name', '')}[{','.join(_format_base_type(p) for p in definition.get('type_params', []))}]",
                "constraint": ""
            }

    # definition might be a simple string (simple_type)
    if isinstance(definition, str):
        return {
            "name": name,
            "base_type": definition,
            "constraint": ""
        }

    return {
        "name": name,
        "base_type": "unknown",
        "constraint": ""
    }


def _format_base_type(base_type: Any) -> str:
    """Format a base_type AST node into a readable string."""
    if isinstance(base_type, str):
        return base_type
    if isinstance(base_type, dict):
        if base_type.get("type") == "BaseType":
            return base_type.get("name", "")
        elif base_type.get("type") == "CustomType":
            return base_type.get("name", "")
        elif base_type.get("type") == "GenericType":
            name = base_type.get("name", "")
            params = ",".join(_format_base_type(p) for p in base_type.get("type_params", []))
            return f"{name}[{params}]"
        elif base_type.get("type") == "SemanticType":
            bt = _format_base_type(base_type.get("base_type"))
            constraint = base_type.get("constraint", "")
            return f"{bt}@\"{constraint}\""
    return str(base_type)


def _format_implements_annotations(annotations: List[Dict]) -> List[str]:
    """Format implements annotations into simple feature ID strings."""
    result = []
    for ann in annotations:
        if isinstance(ann, dict):
            feature_id = ann.get("feature_id", ann.get("constraint_id", ""))
            if feature_id:
                result.append(feature_id)
    return result


# ===== DAG Topology Inference =====

def infer_dag_topology(flow_body: List[Any]) -> List[str]:
    """
    Infer DAG topology strings from flow body statements.

    Analyzes pipeline expressions (>>), fork expressions (|>>),
    merge expressions (&>>), and branch expressions (??) to
    produce human-readable topology strings like:
    - "Input >> AgentA >> AgentB" (simple pipeline)
    - "Input |>> [AgentA, AgentB]" (parallel fork)
    - "[AgentA, AgentB] &>> Merger" (merge)
    - "Input ?? TrueAgent : FalseAgent" (conditional branch)

    Args:
        flow_body: List of statement AST nodes from a flow declaration

    Returns:
        List of topology description strings
    """
    topologies = []

    for stmt in flow_body:
        if not isinstance(stmt, dict):
            continue

        # Check assignment statements — value may contain DAG expressions
        if stmt.get("type") == "AssignmentStatement":
            topo = _infer_topology_from_expr(stmt.get("value"))
            if topo:
                target = stmt.get("target", "")
                topologies.append(f"{target} = {topo}")

        # Check expression statements
        elif stmt.get("type") == "ExpressionStatement":
            topo = _infer_topology_from_expr(stmt.get("expression"))
            if topo:
                topologies.append(topo)

        # Check match statements — they contain routing topology
        elif stmt.get("type") == "MatchIntentStatement":
            match_topo = _infer_topology_from_match(stmt)
            if match_topo:
                topologies.append(match_topo)

    return topologies


def _expr_to_name_flat(expr: Any) -> str:
    """Convert an expression AST node to a short name WITHOUT recursion into DAG types.
    
    This is the safe version used inside _infer_topology_from_expr to prevent
    mutual recursion. It only handles simple leaf types (Identifier, StringLiteral, etc.)
    and returns a generic representation for complex types.
    """
    if expr is None:
        return "?"
    if isinstance(expr, str):
        return expr
    if isinstance(expr, dict):
        expr_type = expr.get("type", "")
        if expr_type == "Identifier" or expr_type == "id_expr":
            return expr.get("value", expr.get("name", ""))
        if expr_type == "InterpolatedString":
            # P3-1: Interpolated string — reconstruct from parts
            parts = expr.get('parts', [])
            result = ''
            for p in parts:
                if p.get('kind') == 'literal':
                    result += p.get('value', '')
                elif p.get('kind') == 'expr':
                    result += '#{' + p.get('value', '') + '}'
            return f'"{result}"'
        if expr_type == "InterpolatedString":
            parts = expr.get('parts', [])
            result = ''
            for p in parts:
                if p.get('kind') == 'literal':
                    result += p.get('value', '')
                elif p.get('kind') == 'expr':
                    result += '#{' + p.get('value', '') + '}'
            return f'"{result}"'
        if expr_type == "StringLiteral" or expr_type == "string_expr":
            return f'"{expr.get("value", "")}"'
        if expr_type == "IntLiteral" or expr_type == "int_expr":
            return str(expr.get("value", 0))
        if expr_type == "FloatLiteral" or expr_type == "float_expr":
            return str(expr.get("value", 0.0))
        if expr_type == "BooleanLiteral" or expr_type in ("true_expr", "false_expr"):
            return expr.get("value", expr_type == "true_expr")
        if expr_type == "MethodCallExpr" or expr_type == "method_call" or expr_type == "FunctionCallExpression":
            obj = _expr_to_name_flat(expr.get("object", expr.get("receiver", "")))
            method = expr.get("method", expr.get("function", ""))
            return f"{obj}.{method}"
        if expr_type == "PropertyAccess":
            base = _expr_to_name_flat(expr.get("base", expr.get("object", "")))
            prop = expr.get("property", "")
            return f"{base}.{prop}"
        # For DAG/Pipeline types, delegate to topology inference (no mutual recursion risk
        # since _infer_topology_from_expr uses _expr_to_name_flat, not _expr_to_name)
        if expr_type in ("PipelineExpression", "DAGForkExpression", "DAGMergeExpression",
                         "DAGBranchExpression", "FallbackExpr"):
            result = _infer_topology_from_expr(expr)
            return result if result else "?"
        # Fallback: try to get a name from the dict
        if "name" in expr:
            return str(expr["name"])
        if "value" in expr:
            return str(expr["value"])
    return str(expr)


def _infer_topology_from_expr(expr: Any) -> Optional[str]:
    """Infer a topology string from an expression AST node.
    
    Uses _expr_to_name_flat for leaf values to prevent mutual recursion with _expr_to_name.
    """

    if expr is None:
        return None

    if isinstance(expr, str):
        return expr

    if not isinstance(expr, dict):
        return None

    expr_type = expr.get("type", "")

    if expr_type == "PipelineExpression":
        # Simple pipeline: A >> B >> C
        stages = expr.get("stages", [])
        stage_strs = [_expr_to_name_flat(s) for s in stages]
        return " >> ".join(stage_strs)

    elif expr_type == "DAGForkExpression":
        # Parallel fork: Input |>> [AgentA, AgentB]
        input_str = _expr_to_name_flat(expr.get("input"))
        agents = expr.get("agents", [])
        agent_strs = [_expr_to_name_flat(a) if isinstance(a, dict) else str(a) for a in agents] if isinstance(agents, list) else [str(agents)]
        op = expr.get("operator", "|>>")
        return f"{input_str} {op} [{', '.join(agent_strs)}]"

    elif expr_type == "DAGMergeExpression":
        # Merge: [AgentA, AgentB] &>> Merger
        agents = expr.get("agents", [])
        agent_strs = [_expr_to_name_flat(a) if isinstance(a, dict) else str(a) for a in agents] if isinstance(agents, list) else [str(agents)]
        merger_str = _expr_to_name_flat(expr.get("merger"))
        op = expr.get("operator", "&>>")
        return f"[{', '.join(agent_strs)}] {op} {merger_str}"

    elif expr_type == "DAGBranchExpression":
        # Conditional branch: Input ?? TrueAgent : FalseAgent
        input_str = _expr_to_name_flat(expr.get("input"))
        # AST uses both true_agent/false_agent and true_branch/false_branch keys
        true_val = expr.get("true_agent", expr.get("true_branch"))
        false_val = expr.get("false_agent", expr.get("false_branch"))
        if true_val is not None and false_val is not None:
            true_str = _expr_to_name_flat(true_val)
            false_str = _expr_to_name_flat(false_val)
            return f"{input_str} ?? {true_str} : {false_str}"
        elif "cases" in expr:
            cases = expr.get("cases", [])
            case_strs = []
            for c in cases:
                if isinstance(c, dict):
                    case_strs.append(f'"{c.get("condition", "")}" => {_expr_to_name_flat(c.get("action", ""))}')
            return f"{input_str} ?? {{{', '.join(case_strs)}}}"

    elif expr_type == "FallbackExpr":
        primary = _expr_to_name_flat(expr.get("primary"))
        backup = _expr_to_name_flat(expr.get("backup"))
        return f"{primary} fallback {backup}"

    elif expr_type == "MethodCallExpr" or expr_type == "FunctionCallExpression":
        # Agent.run(input) or print(result)
        method = expr.get("method", expr.get("function", ""))
        obj = _expr_to_name_flat(expr.get("object"))
        return f"{obj}.{method}(...)"

    elif expr_type == "InterpolatedString":
        parts = expr.get('parts', [])
        result = ''
        for p in parts:
            if p.get('kind') == 'literal':
                result += p.get('value', '')
            elif p.get('kind') == 'expr':
                result += '#{' + p.get('value', '') + '}'
        return f'"{result}"'
    elif expr_type == "StringLiteral" or expr_type == "string_expr":
        return f'"{expr.get("value", "")}"'

    elif expr_type == "Identifier" or expr_type == "id_expr":
        return expr.get("value", expr.get("name", ""))

    # For simple identifiers or string literals — use flat conversion (no recursion)
    return _expr_to_name_flat(expr)


def _expr_to_name(expr: Any) -> str:
    """Convert an expression AST node to a short readable name.
    
    This is the richer version that handles all expression types including
    DAG topology expressions. It delegates DAG types to _infer_topology_from_expr
    which uses _expr_to_name_flat internally to avoid mutual recursion.
    """
    if expr is None:
        return "?"
    if isinstance(expr, str):
        return expr
    if isinstance(expr, dict):
        expr_type = expr.get("type", "")
        if expr_type == "Identifier" or expr_type == "id_expr":
            return expr.get("value", expr.get("name", str(expr)))
        if expr_type == "InterpolatedString":
            parts = expr.get('parts', [])
            result = ''
            for p in parts:
                if p.get('kind') == 'literal':
                    result += p.get('value', '')
                elif p.get('kind') == 'expr':
                    result += '#{' + p.get('value', '') + '}'
            return f'"{result}"'
        if expr_type == "StringLiteral" or expr_type == "string_expr":
            return f'"{expr.get("value", "")}"'
        if expr_type == "IntLiteral" or expr_type == "int_expr":
            return str(expr.get("value", 0))
        if expr_type == "PipelineExpression":
            stages = expr.get("stages", [])
            return " >> ".join(_expr_to_name_flat(s) for s in stages)
        if expr_type in ("DAGForkExpression", "DAGMergeExpression", "DAGBranchExpression", "FallbackExpr"):
            result = _infer_topology_from_expr(expr)
            return result if result else "?"
        if expr_type == "MethodCallExpr" or expr_type == "method_call" or expr_type == "FunctionCallExpression":
            obj = _expr_to_name_flat(expr.get("object", expr.get("receiver", "")))
            method = expr.get("method", expr.get("function", expr.get("name", "")))
            return f"{obj}.{method}"
        if expr_type == "PropertyAccess":
            base = _expr_to_name_flat(expr.get("base", expr.get("object", "")))
            prop = expr.get("property", "")
            return f"{base}.{prop}"
        # Fallback: try to get a name from the dict
        if "name" in expr:
            return str(expr["name"])
        if "value" in expr:
            return str(expr["value"])
    return str(expr)


def _infer_topology_from_match(match_stmt: Dict[str, Any]) -> str:
    """Infer topology from a match/intent routing statement."""
    target = match_stmt.get("target", "")
    cases = match_stmt.get("cases", [])
    default = match_stmt.get("default")

    case_strs = []
    for c in cases:
        if isinstance(c, dict):
            intent = c.get("intent", "")
            action = _expr_to_name(c.get("expression", ""))
            case_strs.append(f'intent("{intent}") => {action}')

    default_str = ""
    if default and isinstance(default, dict):
        default_str = f'_ => {_expr_to_name(default.get("expression", ""))}'

    all_strs = case_strs
    if default_str:
        all_strs.append(default_str)

    return f"match {target} {{{', '.join(all_strs)}}}"


def format_inspect_json(result: Dict[str, Any]) -> str:
    """Format inspection result as JSON string."""
    return json.dumps(result, indent=2, ensure_ascii=False)


def format_inspect_text(result: Dict[str, Any]) -> str:
    """Format inspection result as human-readable text summary."""

    lines = []
    lines.append(f"📄 File: {result.get('file', '?')}")
    lines.append(f"   Version: {result.get('version', '?')}")

    if result.get("parse_error"):
        lines.append(f"   ⚠️ Parse Error: {result['parse_error']}")
        lines.append("   (Showing partial extraction from source)")

    summary = result.get("summary", {})
    lines.append("")
    lines.append("📊 Summary:")
    lines.append(f"   Agents:    {summary.get('total_agents', 0)}")
    lines.append(f"   Tools:     {summary.get('total_tools', 0)}")
    lines.append(f"   Protocols: {summary.get('total_protocols', 0)}")
    lines.append(f"   Flows:     {summary.get('total_flows', 0)}")
    lines.append(f"   Tests:     {summary.get('total_tests', 0)}")
    lines.append(f"   Types:     {summary.get('total_types', 0)}")
    lines.append(f"   Imports:   {summary.get('total_imports', 0)}")

    # Agents
    agents = result.get("agents", [])
    if agents:
        lines.append("")
        lines.append("🤖 Agents:")
        for agent in agents:
            role = agent.get("role", "")
            name = agent.get("name", "")
            lines.append(f"   • {name} — {role}")
            if agent.get("model"):
                lines.append(f"     Model: {agent['model']}")
            if agent.get("protocol"):
                lines.append(f"     Protocol: {agent['protocol']}")
            if agent.get("tools"):
                lines.append(f"     Tools: {', '.join(agent['tools'])}")
            if agent.get("decorators"):
                for dec in agent["decorators"]:
                    params_str = ", ".join(f"{k}={v}" for k, v in dec.get("params", {}).items())
                    lines.append(f"     @{dec['name']}({params_str})")
            contracts = agent.get("contracts", {})
            if contracts:
                if contracts.get("requires"):
                    lines.append(f"     Requires: {', '.join(contracts['requires'])}")
                if contracts.get("ensures"):
                    lines.append(f"     Ensures: {', '.join(contracts['ensures'])}")
            if agent.get("implements_annotations"):
                lines.append(f"     Implements: {', '.join(agent['implements_annotations'])}")

    # Tools
    tools = result.get("tools", [])
    if tools:
        lines.append("")
        lines.append("🔧 Tools:")
        for tool in tools:
            name = tool.get("name", "")
            tool_type = tool.get("type", "local")
            lines.append(f"   • {name} ({tool_type})")
            if tool.get("description"):
                lines.append(f"     Description: {tool['description']}")
            if tool.get("mcp"):
                lines.append(f"     MCP: {tool['mcp']}")
            if tool.get("python"):
                lines.append(f"     Python: {tool['python']}")
            if tool.get("parameters"):
                params = tool["parameters"]
                if isinstance(params, dict):
                    for k, v in params.items():
                        lines.append(f"     Param: {k}: {v}")

    # Protocols
    protocols = result.get("protocols", [])
    if protocols:
        lines.append("")
        lines.append("📋 Protocols:")
        for proto in protocols:
            name = proto.get("name", "")
            fields = proto.get("fields", {})
            lines.append(f"   • {name}")
            for field_name, field_type in fields.items():
                lines.append(f"     {field_name}: {field_type}")

    # Flows
    flows = result.get("flows", [])
    if flows:
        lines.append("")
        lines.append("🔄 Flows:")
        for flow in flows:
            name = flow.get("name", "")
            params = flow.get("parameters", [])
            stmt_count = flow.get("statements_count", 0)
            param_str = ", ".join(f"{p.get('name', '')}: {p.get('type', '')}" for p in params) if params else ""
            lines.append(f"   • {name}({param_str}) — {stmt_count} statements")
            dag = flow.get("dag_topology", [])
            if dag:
                lines.append(f"     DAG Topology:")
                for topo in dag:
                    lines.append(f"       {topo}")
            contracts = flow.get("contracts", {})
            if contracts:
                if contracts.get("requires"):
                    lines.append(f"     Requires: {', '.join(contracts['requires'])}")
                if contracts.get("ensures"):
                    lines.append(f"     Ensures: {', '.join(contracts['ensures'])}")

    # Tests
    tests = result.get("tests", [])
    if tests:
        lines.append("")
        lines.append("🧪 Tests:")
        for test in tests:
            name = test.get("name", "")
            assertions = test.get("assertions_count", 0)
            lines.append(f"   • {name} — {assertions} assertions")

    # Types
    types_list = result.get("types", [])
    if types_list:
        lines.append("")
        lines.append("📐 Types:")
        for t in types_list:
            name = t.get("name", "")
            base = t.get("base_type", "")
            constraint = t.get("constraint", "")
            if constraint:
                lines.append(f"   • {name} = {base} @ \"{constraint}\"")
            else:
                lines.append(f"   • {name} = {base}")

    # Imports
    imports = result.get("imports", [])
    if imports:
        lines.append("")
        lines.append("📦 Imports:")
        for imp in imports:
            lines.append(f"   • {imp}")

    return "\n".join(lines)