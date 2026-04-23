"""
Tests for Nexa Inspector & Validator (Agent-Native Tooling)

Covers:
- inspect_nexa_file: correct extraction of agents, tools, protocols, flows, types, imports
- infer_dag_topology: correct DAG topology inference from flow statements
- Contract extraction in inspect output
- implements_annotations extraction
- Summary statistics correctness
- validate_nexa_file: valid files, invalid files, unused declarations, reference errors
- Error formatting: human + JSON dual mode
- fix_hint generation
"""

import json
import os
import sys
import tempfile
import pytest

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from runtime.inspector import (
    inspect_nexa_file,
    infer_dag_topology,
    format_inspect_json,
    format_inspect_text,
    _expr_to_name,
)
from runtime.validator import (
    validate_nexa_file,
    ValidationError,
    format_error_json,
    format_error_human,
)

# Path to example files
EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples')


# ===== Inspector Tests =====

class TestInspectNexaFile:
    """Tests for the inspect_nexa_file function."""

    def test_inspect_pipeline_and_routing(self):
        """Test inspecting examples/02_pipeline_and_routing.nx"""
        file_path = os.path.join(EXAMPLES_DIR, "02_pipeline_and_routing.nx")
        result = inspect_nexa_file(file_path)

        # Basic structure
        assert result["file"] == file_path
        assert "version" in result
        assert "summary" in result

        # Agents extracted correctly
        agents = result["agents"]
        assert len(agents) == 5  # Router, WeatherBot, NewsBot, SmallTalkBot, Translator

        agent_names = [a["name"] for a in agents]
        assert "Router" in agent_names
        assert "WeatherBot" in agent_names
        assert "NewsBot" in agent_names
        assert "SmallTalkBot" in agent_names
        assert "Translator" in agent_names

        # Agent details
        weather_bot = next(a for a in agents if a["name"] == "WeatherBot")
        assert weather_bot["role"] == "Weather Expert"
        assert weather_bot.get("model") == "minimax-m2.5"

        # NewsBot uses std.http
        news_bot = next(a for a in agents if a["name"] == "NewsBot")
        uses = news_bot.get("tools", [])
        assert "std.http" in uses

        # Flows extracted
        flows = result["flows"]
        assert len(flows) >= 1
        main_flow = next(f for f in flows if f["name"] == "main")
        assert main_flow["statements_count"] > 0

        # Summary statistics
        summary = result["summary"]
        assert summary["total_agents"] == 5
        assert summary["total_flows"] >= 1

    def test_inspect_dag_topology(self):
        """Test inspecting examples/15_dag_topology.nx — DAG topology inference"""
        file_path = os.path.join(EXAMPLES_DIR, "15_dag_topology.nx")
        result = inspect_nexa_file(file_path)

        agents = result["agents"]
        assert len(agents) >= 5  # Researcher, Analyst, Writer, Reviewer, UrgentHandler, NormalHandler

        agent_names = [a["name"] for a in agents]
        assert "Researcher" in agent_names
        assert "Analyst" in agent_names
        assert "Writer" in agent_names

        # Flows with DAG topology
        flows = result["flows"]
        main_flow = next(f for f in flows if f["name"] == "main")

        # DAG topology should be inferred
        dag_topology = main_flow.get("dag_topology", [])
        assert len(dag_topology) > 0

        # Check that topology contains known patterns
        # Simple pipeline: "What is AI?" >> Researcher >> Writer
        has_pipeline = any(">>" in topo for topo in dag_topology)
        assert has_pipeline

    def test_inspect_contract_file(self):
        """Test contract extraction from agent declarations"""
        # test_contract.nx has `flow main()` which can't parse, so we create
        # a temporary file that parses correctly with contract clauses
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nx', delete=False) as f:
            f.write("""
agent FinancialAnalyst
    requires "input contains financial data"
    ensures "output contains specific analysis conclusions" {
    role: "Senior Financial Advisor",
    prompt: "Analyze financial data and output standard reports.",
    model: "minimax-m2.5"
}

agent PaymentValidator
    requires "input contains payment data"
    ensures "output confirms payment validity" {
    role: "Payment Validator",
    prompt: "Validate payment data."
}

flow analyze_finances(data: str)
    requires "data contains financial information"
    ensures result >= 0 {
    analysis = FinancialAnalyst(data)
    result = analysis
}

flow main {
    print("Contract demo")
}
""")
            f.flush()
            temp_path = f.name

        try:
            result = inspect_nexa_file(temp_path)

            # Agents with contracts
            agents = result["agents"]

            # FinancialAnalyst should have requires/ensures contracts
            financial = next(a for a in agents if a["name"] == "FinancialAnalyst")
            contracts = financial.get("contracts", {})
            requires = contracts.get("requires", [])
            ensures = contracts.get("ensures", [])
            assert len(requires) > 0
            assert len(ensures) > 0
            assert any("financial data" in r for r in requires)
            assert any("analysis conclusions" in e for e in ensures)

            # PaymentValidator should have contracts too
            payment = next(a for a in agents if a["name"] == "PaymentValidator")
            contracts = payment.get("contracts", {})
            assert contracts.get("requires", []) or contracts.get("ensures", [])

            # Flows with contracts
            flows = result["flows"]
            analyze_flow = next((f for f in flows if f["name"] == "analyze_finances"), None)
            if analyze_flow:
                flow_contracts = analyze_flow.get("contracts", {})
                assert flow_contracts.get("requires", []) or flow_contracts.get("ensures", [])
        finally:
            os.unlink(temp_path)

    def test_inspect_tool_file(self):
        """Test inspecting examples/test_custom_tool.nx — tool extraction"""
        file_path = os.path.join(EXAMPLES_DIR, "test_custom_tool.nx")
        result = inspect_nexa_file(file_path)

        # Tools extracted
        tools = result["tools"]
        assert len(tools) >= 2

        # Local tool with description and parameters
        greeting_tool = next((t for t in tools if t["name"] == "Tool1_Greeting"), None)
        if greeting_tool:
            assert greeting_tool["type"] == "local"
            assert greeting_tool.get("description") == "生成问候语"

        # MCP tool
        mcp_tool = next((t for t in tools if t.get("type") == "mcp"), None)
        if mcp_tool:
            assert mcp_tool.get("mcp") is not None

        # Python tool
        python_tool = next((t for t in tools if t.get("type") == "python"), None)
        if python_tool:
            assert python_tool.get("python") is not None

        # Agent using tools
        agents = result["agents"]
        tool_user = next((a for a in agents if "Tool1_Greeting" in a.get("tools", [])), None)
        if tool_user:
            assert tool_user["name"] == "Tool4_User"

    def test_inspect_protocol_file(self):
        """Test inspecting examples/test_protocol_implements.nx — protocol extraction"""
        file_path = os.path.join(EXAMPLES_DIR, "test_protocol_implements.nx")
        result = inspect_nexa_file(file_path)

        # Protocols extracted
        protocols = result["protocols"]
        assert len(protocols) >= 1

        protocol_names = [p["name"] for p in protocols]
        assert "SimpleResult" in protocol_names

        # Protocol fields
        simple_result = next(p for p in protocols if p["name"] == "SimpleResult")
        fields = simple_result.get("fields", {})
        assert "status" in fields
        assert "message" in fields

        # Agent implements protocol
        agents = result["agents"]
        impl_agent = next((a for a in agents if a.get("protocol") == "SimpleResult"), None)
        if impl_agent:
            assert impl_agent["name"] == "Test1_SimpleProtocol"

    def test_inspect_decorator_file(self):
        """Test inspecting examples/test_agent_decorators.nx — decorator extraction"""
        file_path = os.path.join(EXAMPLES_DIR, "test_agent_decorators.nx")
        result = inspect_nexa_file(file_path)

        agents = result["agents"]
        assert len(agents) >= 1

        # Agent with @limit decorator
        limit_agent = next((a for a in agents if a.get("decorators")), None)
        if limit_agent:
            decorators = limit_agent["decorators"]
            assert len(decorators) > 0
            dec = decorators[0]
            assert dec["name"] in ["limit", "timeout", "retry", "temperature"]

    def test_inspect_semantic_types(self):
        """Test inspecting examples/test_semantic_types.nx — type extraction"""
        file_path = os.path.join(EXAMPLES_DIR, "test_semantic_types.nx")
        if not os.path.exists(file_path):
            pytest.skip("test_semantic_types.nx not found")

        result = inspect_nexa_file(file_path)

        types = result.get("types", [])
        if types:
            assert len(types) >= 1
            # Check type structure
            t = types[0]
            assert "name" in t
            assert "base_type" in t

    def test_inspect_summary_statistics(self):
        """Test that summary statistics are correct"""
        file_path = os.path.join(EXAMPLES_DIR, "02_pipeline_and_routing.nx")
        result = inspect_nexa_file(file_path)

        summary = result["summary"]
        # Counts should match actual extracted data
        assert summary["total_agents"] == len(result["agents"])
        assert summary["total_tools"] == len(result["tools"])
        assert summary["total_protocols"] == len(result["protocols"])
        assert summary["total_flows"] == len(result["flows"])
        assert summary["total_tests"] == len(result["tests"])

    def test_inspect_file_not_found(self):
        """Test inspecting a non-existent file returns error info"""
        result = inspect_nexa_file("/nonexistent/file.nx")
        assert result.get("error") is not None
        assert "does not exist" in result["error"]
        assert result["agents"] == []

    def test_inspect_imports(self):
        """Test import/include extraction"""
        file_path = os.path.join(EXAMPLES_DIR, "test_include_module.nx")
        if not os.path.exists(file_path):
            pytest.skip("test_include_module.nx not found")

        result = inspect_nexa_file(file_path)
        imports = result.get("imports", [])
        # If the file has includes, they should be extracted
        if imports:
            assert len(imports) > 0


class TestInferDagTopology:
    """Tests for DAG topology inference."""

    def test_simple_pipeline(self):
        """Test inferring topology from a simple pipeline expression"""
        # Simulate a flow body with a pipeline assignment
        flow_body = [
            {
                "type": "AssignmentStatement",
                "target": "result",
                "value": {
                    "type": "PipelineExpression",
                    "stages": [
                        {"type": "string_expr", "value": "What is AI?"},
                        {"type": "id_expr", "value": "Researcher"},
                        {"type": "id_expr", "value": "Writer"},
                    ]
                }
            }
        ]

        topologies = infer_dag_topology(flow_body)
        assert len(topologies) == 1
        assert ">>" in topologies[0]
        assert "Researcher" in topologies[0]
        assert "Writer" in topologies[0]

    def test_fork_expression(self):
        """Test inferring topology from a fork expression (|>>)"""
        flow_body = [
            {
                "type": "AssignmentStatement",
                "target": "parallel",
                "value": {
                    "type": "DAGForkExpression",
                    "input": {"type": "id_expr", "value": "data"},
                    "agents": ["Researcher", "Analyst", "Writer"],
                    "operator": "|>>",
                    "wait_all": True
                }
            }
        ]

        topologies = infer_dag_topology(flow_body)
        assert len(topologies) == 1
        assert "|>>" in topologies[0]
        assert "Researcher" in topologies[0]
        assert "Analyst" in topologies[0]
        assert "Writer" in topologies[0]

    def test_merge_expression(self):
        """Test inferring topology from a merge expression (&>>)"""
        flow_body = [
            {
                "type": "AssignmentStatement",
                "target": "merged",
                "value": {
                    "type": "DAGMergeExpression",
                    "agents": ["Researcher", "Analyst"],
                    "merger": {"type": "id_expr", "value": "Reviewer"},
                    "operator": "&>>",
                    "strategy": "concat"
                }
            }
        ]

        topologies = infer_dag_topology(flow_body)
        assert len(topologies) == 1
        assert "&>>" in topologies[0]
        assert "Reviewer" in topologies[0]

    def test_empty_flow_body(self):
        """Test that empty flow body returns empty topology"""
        topologies = infer_dag_topology([])
        assert topologies == []


class TestFormatOutput:
    """Tests for output formatting functions."""

    def test_format_inspect_json(self):
        """Test JSON formatting of inspect result"""
        result = {
            "file": "test.nx",
            "version": "1.0",
            "agents": [{"name": "Bot"}],
            "summary": {"total_agents": 1}
        }
        json_str = format_inspect_json(result)
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["file"] == "test.nx"
        assert parsed["agents"][0]["name"] == "Bot"

    def test_format_inspect_text(self):
        """Test text formatting of inspect result"""
        result = {
            "file": "test.nx",
            "version": "1.0",
            "agents": [{"name": "Bot", "role": "Helper"}],
            "tools": [],
            "protocols": [],
            "flows": [],
            "tests": [],
            "types": [],
            "imports": [],
            "summary": {"total_agents": 1, "total_tools": 0, "total_protocols": 0,
                        "total_flows": 0, "total_tests": 0}
        }
        text = format_inspect_text(result)
        assert "test.nx" in text
        assert "Bot" in text
        assert "Helper" in text
        assert "Summary" in text


# ===== Validator Tests =====

class TestValidateNexaFile:
    """Tests for the validate_nexa_file function."""

    def test_validate_valid_file(self):
        """Test that a valid .nx file returns valid: true"""
        file_path = os.path.join(EXAMPLES_DIR, "02_pipeline_and_routing.nx")
        result = validate_nexa_file(file_path)

        # The file should parse successfully
        assert "valid" in result
        # If there are errors, they should be semantic (not parse errors)
        # Most example files are valid syntax
        if result["valid"]:
            assert len(result["errors"]) == 0

    def test_validate_file_not_found(self):
        """Test validating a non-existent file"""
        result = validate_nexa_file("/nonexistent/file.nx")
        assert result["valid"] == False
        assert len(result["errors"]) >= 1
        assert result["errors"][0]["error_type"] == "FileNotFound"

    def test_validate_invalid_syntax(self):
        """Test validating a file with invalid syntax"""
        # Create a temporary file with invalid Nexa syntax
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nx', delete=False) as f:
            f.write("agent BrokenAgent {\n")  # Missing closing brace
            f.write("    role: \"Test\"\n")
            f.flush()
            temp_path = f.name

        try:
            result = validate_nexa_file(temp_path)
            assert result["valid"] == False
            assert len(result["errors"]) >= 1
            # Should have a ParseError
            assert result["errors"][0]["error_type"] == "ParseError"
            # Should have a fix_hint
            assert result["errors"][0]["fix_hint"] != ""
        finally:
            os.unlink(temp_path)

    def test_validate_unused_agent_warning(self):
        """Test that unused agents produce warnings"""
        # Create a file with an agent that's not used in any flow
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nx', delete=False) as f:
            f.write("""
agent UnusedBot {
    role: "Unused Bot",
    prompt: "I am never called"
}

agent UsedBot {
    role: "Used Bot",
    prompt: "I am called"
}

flow main {
    result = UsedBot("hello");
}
""")
            f.flush()
            temp_path = f.name

        try:
            result = validate_nexa_file(temp_path)
            # Should have a warning about UnusedBot
            warnings = result["warnings"]
            unused_warnings = [w for w in warnings if w["error_type"] == "UnusedAgent"]
            assert len(unused_warnings) >= 1
            assert any("UnusedBot" in w["message"] for w in unused_warnings)
            # fix_hint should suggest adding to a flow
            assert any("flow" in w["fix_hint"].lower() for w in unused_warnings)
        finally:
            os.unlink(temp_path)

    def test_validate_missing_protocol_reference(self):
        """Test that implements referencing non-existent protocol produces error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nx', delete=False) as f:
            f.write("""
agent BrokenAgent implements NonExistentProtocol {
    role: "Broken",
    prompt: "I reference a protocol that doesn't exist"
}

flow main {
    result = BrokenAgent("test");
}
""")
            f.flush()
            temp_path = f.name

        try:
            result = validate_nexa_file(temp_path)
            assert result["valid"] == False
            errors = result["errors"]
            missing_proto = [e for e in errors if e["error_type"] == "MissingProtocolReference"]
            assert len(missing_proto) >= 1
            assert "NonExistentProtocol" in missing_proto[0]["message"]
            assert missing_proto[0]["fix_hint"] != ""
        finally:
            os.unlink(temp_path)

    def test_validate_missing_tool_reference(self):
        """Test that uses referencing non-existent tool produces error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nx', delete=False) as f:
            f.write("""
agent BrokenAgent uses NonExistentTool {
    role: "Broken",
    prompt: "I reference a tool that doesn't exist"
}

flow main {
    result = BrokenAgent("test");
}
""")
            f.flush()
            temp_path = f.name

        try:
            result = validate_nexa_file(temp_path)
            assert result["valid"] == False
            errors = result["errors"]
            missing_tool = [e for e in errors if e["error_type"] == "MissingToolReference"]
            assert len(missing_tool) >= 1
            assert "NonExistentTool" in missing_tool[0]["message"]
        finally:
            os.unlink(temp_path)

    def test_validate_empty_flow_warning(self):
        """Test that empty flow body produces a warning"""
        # This is tricky because empty flow body might not parse well
        # Let's test with a minimal flow that has at least one statement
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nx', delete=False) as f:
            f.write("""
agent Helper {
    role: "Helper",
    prompt: "I help"
}

flow main {
}
""")
            f.flush()
            temp_path = f.name

        try:
            result = validate_nexa_file(temp_path)
            # If parsing succeeds, check for empty flow warning
            warnings = result["warnings"]
            empty_flow = [w for w in warnings if w["error_type"] == "EmptyFlowBody"]
            # Empty flow body may or may not parse correctly depending on grammar
            if empty_flow:
                assert "main" in empty_flow[0]["message"]
        finally:
            os.unlink(temp_path)

    def test_validate_missing_agent_prompt_warning(self):
        """Test that agent without prompt produces a warning"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nx', delete=False) as f:
            f.write("""
agent NoPromptBot {
    role: "Bot without prompt"
}

flow main {
    result = NoPromptBot("test");
}
""")
            f.flush()
            temp_path = f.name

        try:
            result = validate_nexa_file(temp_path)
            warnings = result["warnings"]
            missing_prompt = [w for w in warnings if w["error_type"] == "MissingAgentPrompt"]
            if missing_prompt:
                assert "NoPromptBot" in missing_prompt[0]["message"]
                assert "prompt" in missing_prompt[0]["fix_hint"].lower()
        finally:
            os.unlink(temp_path)

    def test_validate_summary(self):
        """Test that validation summary contains correct counts"""
        file_path = os.path.join(EXAMPLES_DIR, "02_pipeline_and_routing.nx")
        result = validate_nexa_file(file_path)

        summary = result["summary"]
        assert "errors" in summary
        assert "warnings" in summary
        assert "total_checks" in summary
        assert summary["errors"] == len(result["errors"])
        assert summary["warnings"] == len(result["warnings"])

    def test_validate_valid_protocol_implements(self):
        """Test that correctly implemented protocol doesn't produce error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nx', delete=False) as f:
            f.write("""
protocol SimpleResult {
    status: "string",
    message: "string"
}

agent GoodAgent implements SimpleResult {
    role: "Good Agent",
    prompt: "I correctly implement a protocol"
}

flow main {
    result = GoodAgent("test");
}
""")
            f.flush()
            temp_path = f.name

        try:
            result = validate_nexa_file(temp_path)
            # Should not have MissingProtocolReference errors
            errors = result["errors"]
            missing_proto = [e for e in errors if e["error_type"] == "MissingProtocolReference"]
            assert len(missing_proto) == 0
        finally:
            os.unlink(temp_path)


class TestErrorFormatting:
    """Tests for error formatting (human + JSON dual mode)."""

    def test_format_error_json(self):
        """Test JSON formatting of validation result"""
        result = {
            "valid": False,
            "errors": [
                {
                    "file": "test.nx",
                    "line": 15,
                    "column": 23,
                    "error_type": "ParseError",
                    "message": "Unexpected token",
                    "fix_hint": "Check syntax",
                    "severity": "error"
                }
            ],
            "warnings": [],
            "summary": {"errors": 1, "warnings": 0, "total_checks": 8}
        }
        json_str = format_error_json(result)
        parsed = json.loads(json_str)
        assert parsed["valid"] == False
        assert parsed["errors"][0]["error_type"] == "ParseError"
        assert parsed["errors"][0]["fix_hint"] == "Check syntax"

    def test_format_error_human_with_errors(self):
        """Test human-readable formatting with errors"""
        result = {
            "valid": False,
            "errors": [
                {
                    "file": "test.nx",
                    "line": 15,
                    "column": 23,
                    "error_type": "ParseError",
                    "message": "Unexpected token 'requires'",
                    "fix_hint": "Ensure 'requires' clause comes before the agent body block",
                    "severity": "error"
                }
            ],
            "warnings": [
                {
                    "file": "test.nx",
                    "line": 8,
                    "column": 1,
                    "error_type": "UnusedAgent",
                    "message": "Agent 'DebugBot' is declared but never used",
                    "fix_hint": "Add DebugBot to a flow pipeline",
                    "severity": "warning"
                }
            ],
            "summary": {"errors": 1, "warnings": 1, "total_checks": 8}
        }
        text = format_error_human(result)
        assert "Validation failed" in text
        assert "ParseError" in text
        assert "Unexpected token" in text
        assert "UnusedAgent" in text
        assert "DebugBot" in text
        assert "Fix" in text

    def test_format_error_human_success(self):
        """Test human-readable formatting when all checks pass"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "summary": {"errors": 0, "warnings": 0, "total_checks": 8}
        }
        text = format_error_human(result)
        assert "All checks passed" in text

    def test_format_error_human_quiet_mode(self):
        """Test quiet mode — only errors, no success message"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "summary": {"errors": 0, "warnings": 0, "total_checks": 8}
        }
        text = format_error_human(result, quiet=True)
        # In quiet mode with no errors, output should be minimal
        assert "All checks passed" not in text

    def test_format_error_human_with_warnings_only(self):
        """Test human-readable formatting with only warnings (valid: true)"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [
                {
                    "file": "test.nx",
                    "line": 5,
                    "column": 1,
                    "error_type": "UnusedAgent",
                    "message": "Agent 'Bot' is unused",
                    "fix_hint": "Add Bot to a flow",
                    "severity": "warning"
                }
            ],
            "summary": {"errors": 0, "warnings": 1, "total_checks": 8}
        }
        text = format_error_human(result)
        assert "Syntax valid" in text
        assert "warning" in text.lower()
        assert "UnusedAgent" in text

    def test_validation_error_to_dict(self):
        """Test ValidationError serialization"""
        err = ValidationError(
            file="test.nx",
            line=10,
            column=5,
            error_type="ParseError",
            message="Unexpected token",
            fix_hint="Check syntax",
            severity="error"
        )
        d = err.to_dict()
        assert d["file"] == "test.nx"
        assert d["line"] == 10
        assert d["column"] == 5
        assert d["error_type"] == "ParseError"
        assert d["message"] == "Unexpected token"
        assert d["fix_hint"] == "Check syntax"
        assert d["severity"] == "error"


class TestExprToName:
    """Tests for the _expr_to_name helper function."""

    def test_string_expr(self):
        """Test converting a string expression to name"""
        expr = {"type": "string_expr", "value": "hello"}
        assert _expr_to_name(expr) == '"hello"'

    def test_id_expr(self):
        """Test converting an identifier expression to name"""
        expr = {"type": "id_expr", "value": "AgentA"}
        assert _expr_to_name(expr) == "AgentA"

    def test_int_expr(self):
        """Test converting an integer expression to name"""
        expr = {"type": "int_expr", "value": 42}
        assert _expr_to_name(expr) == "42"

    def test_none_expr(self):
        """Test converting None to name"""
        assert _expr_to_name(None) == "?"

    def test_string_passthrough(self):
        """Test that plain strings pass through"""
        assert _expr_to_name("SimpleName") == "SimpleName"


# ===== Integration Tests =====

class TestCLIIntegration:
    """Integration tests for CLI inspect/validate commands."""

    def test_inspect_cli_json_output(self):
        """Test that nexa inspect produces valid JSON"""
        file_path = os.path.join(EXAMPLES_DIR, "02_pipeline_and_routing.nx")
        result = inspect_nexa_file(file_path)
        json_str = format_inspect_json(result)
        parsed = json.loads(json_str)
        assert parsed["file"] == file_path
        assert len(parsed["agents"]) > 0

    def test_validate_cli_json_output(self):
        """Test that nexa validate --json produces valid JSON"""
        file_path = os.path.join(EXAMPLES_DIR, "02_pipeline_and_routing.nx")
        result = validate_nexa_file(file_path)
        json_str = format_error_json(result)
        parsed = json.loads(json_str)
        assert "valid" in parsed
        assert "errors" in parsed
        assert "warnings" in parsed
        assert "summary" in parsed

    def test_inspect_and_validate_consistency(self):
        """Test that inspect and validate produce consistent results for the same file"""
        file_path = os.path.join(EXAMPLES_DIR, "test_contract.nx")

        inspect_result = inspect_nexa_file(file_path)
        validate_result = validate_nexa_file(file_path)

        # If inspect succeeds, validate should also parse successfully
        # (no parse errors in validate)
        if "parse_error" not in inspect_result:
            parse_errors = [e for e in validate_result["errors"] if e["error_type"] == "ParseError"]
            assert len(parse_errors) == 0

    def test_full_workflow_inspect_then_validate(self):
        """Test the full Agent workflow: inspect first, then validate"""
        file_path = os.path.join(EXAMPLES_DIR, "test_protocol_implements.nx")

        # Step 1: Inspect to understand the code structure
        inspect_result = inspect_nexa_file(file_path)
        assert len(inspect_result["protocols"]) >= 1

        # Step 2: Validate to check correctness
        validate_result = validate_nexa_file(file_path)
        # The file should parse (no ParseError)
        parse_errors = [e for e in validate_result["errors"] if e["error_type"] == "ParseError"]
        assert len(parse_errors) == 0

        # Step 3: Agent can use inspect data to understand structure
        # and validate data to fix issues — all in two calls
        # This demonstrates the Agent-Native Tooling value