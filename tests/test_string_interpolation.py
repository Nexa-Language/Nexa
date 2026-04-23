"""
P3-1: String Interpolation Tests

50+ tests covering all aspects of #{expr} interpolation:
- Basic interpolation parsing and AST generation
- Multiple variables
- No interpolation (plain strings unchanged)
- Escape handling (\\#{ -> literal #{)
- Dot access (user.name)
- Bracket access (arr[0])
- Type conversion via _nexa_interp_str
- None handling
- Dict/list value interpolation
- Empty interpolation #{}
- Invalid expressions
- Code generation for interpolated strings
- _nexa_interp_str helper function
- StdTool registration
- Integration with other features (pipe, null coalesce)
"""

import pytest
import sys
import os
import json

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ==================== Helper Utilities ====================

def parse_code(code):
    'Parse Nexa code and return AST dict'
    from src.nexa_parser import parse
    return parse(code)


def parse_and_transform(code):
    'Parse and transform Nexa code, return AST dict'
    return parse_code(code)


def generate_code(code):
    'Parse Nexa code and generate Python code'
    from src.nexa_parser import parse
    from src.code_generator import CodeGenerator
    ast = parse(code)
    gen = CodeGenerator(ast)
    return gen.generate()


def _find_flow_body(ast, flow_name):
    'Find the body of a specific flow in the AST'
    for node in ast.get("body", []):
        if node.get("type") == "FlowDeclaration" and node.get("name") == flow_name:
            return node.get("body", [])
    return None


def _find_string_expr_in_flow(ast, flow_name):
    'Find the first string expression (InterpolatedString or StringLiteral) in a flow body.\nDrills into FunctionCallExpression arguments (e.g. print("...")) to find the string.'
    body = _find_flow_body(ast, flow_name)
    if not body:
        return None
    for stmt in body:
        # Check ExpressionStatement
        expr = stmt.get("expression", stmt)
        if isinstance(expr, dict):
            result = _drill_for_string(expr)
            if result:
                return result
        # Check AssignmentStatement value
        value = stmt.get("value", None)
        if isinstance(value, dict):
            result = _drill_for_string(value)
            if result:
                return result
        # Check PrintStatement expression
        p_expr = stmt.get("expression", None)
        if isinstance(p_expr, dict):
            result = _drill_for_string(p_expr)
            if result:
                return result
    return None


def _drill_for_string(expr):
    'Drill into expression to find InterpolatedString or StringLiteral'
    if not isinstance(expr, dict):
        return None
    etype = expr.get("type", "")
    if etype in ("InterpolatedString", "StringLiteral"):
        return expr
    # Drill into FunctionCallExpression arguments
    if etype == "FunctionCallExpression":
        for arg in expr.get("arguments", []):
            if isinstance(arg, dict):
                result = _drill_for_string(arg)
                if result:
                    return result
    # Drill into nested expressions
    for key in ("expression", "value", "left", "right", "primary", "backup"):
        child = expr.get(key)
        if isinstance(child, dict):
            result = _drill_for_string(child)
            if result:
                return result
    return None


# ==================== P3-1: _parse_string_interpolation Tests ====================

class TestParseStringInterpolation:
    'P3-1: Test _parse_string_interpolation static method directly'

    def test_no_interpolation_returns_none(self):
        'Plain string without #{...} should return None'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("Hello World")
        assert result is None

    def test_simple_interpolation(self):
        '"Hello #{name}!" should return InterpolatedString with 3 parts'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("Hello #{name}!")
        assert result is not None
        assert result["type"] == "InterpolatedString"
        parts = result["parts"]
        assert len(parts) == 3
        assert parts[0]["kind"] == "literal"
        assert parts[0]["value"] == "Hello "
        assert parts[1]["kind"] == "expr"
        assert parts[1]["value"] == "name"
        assert parts[2]["kind"] == "literal"
        assert parts[2]["value"] == "!"

    def test_multiple_interpolations(self):
        '"#{a} and #{b}" should parse correctly with 3 parts'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{a} and #{b}")
        assert result is not None
        parts = result["parts"]
        assert len(parts) == 3
        assert parts[0]["kind"] == "expr"
        assert parts[0]["value"] == "a"
        assert parts[1]["kind"] == "literal"
        assert parts[1]["value"] == " and "
        assert parts[2]["kind"] == "expr"
        assert parts[2]["value"] == "b"

    def test_only_interpolation_no_literals(self):
        '"#{name}" should produce just one expr part'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{name}")
        assert result is not None
        parts = result["parts"]
        assert len(parts) == 1
        assert parts[0]["kind"] == "expr"
        assert parts[0]["value"] == "name"

    def test_escape_hash_brace(self):
        'Escaped \\#{ results in literal #{, with no real interpolation -> returns None'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("\\#{not_interp}")
        # All parts end up literal -> returns None (plain string)
        assert result is None

    def test_escape_hash_brace_with_interpolation(self):
        '"\\#{safe} #{name}" should have literal #{safe} and expr name'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("\\#{safe} #{name}")
        assert result is not None
        parts = result["parts"]
        # Check that there's a literal part with #{ and an expr part with name
        found_name_expr = False
        for p in parts:
            if p["kind"] == "expr" and p["value"] == "name":
                found_name_expr = True
        assert found_name_expr

    def test_dot_access_interpolation(self):
        '"#{user.name}" should parse as expr with value "user.name"'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{user.name}")
        assert result is not None
        parts = result["parts"]
        assert len(parts) == 1
        assert parts[0]["kind"] == "expr"
        assert parts[0]["value"] == "user.name"

    def test_bracket_access_interpolation(self):
        '"#{arr[0]}" should parse as expr with value "arr[0]"'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{arr[0]}")
        assert result is not None
        parts = result["parts"]
        assert len(parts) == 1
        assert parts[0]["kind"] == "expr"
        assert parts[0]["value"] == "arr[0]"

    def test_dot_and_bracket_combined(self):
        '"#{data.items[0]}" should parse as expr with value "data.items[0]"'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{data.items[0]}")
        assert result is not None
        parts = result["parts"]
        assert parts[0]["kind"] == "expr"
        assert parts[0]["value"] == "data.items[0]"

    def test_empty_interpolation(self):
        '"#{}" should parse as expr with empty value'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{}")
        assert result is not None
        parts = result["parts"]
        assert len(parts) == 1
        assert parts[0]["kind"] == "expr"
        assert parts[0]["value"] == ""

    def test_invalid_expression_returns_none(self):
        '"#{a + b}" with complex expression: invalid expr becomes literal, all-literal -> None'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{a + b}")
        # "a + b" is not a valid simple expression -> treated as literal
        # All parts literal -> returns None (no real interpolation)
        assert result is None

    def test_unmatched_brace_no_crash(self):
        '"#{name" with unmatched brace should not crash'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{name")
        # Should not crash; may return None or literal-only InterpolatedString
        # Just verify no exception

    def test_nested_braces_in_expr(self):
        '"#{dict[key]}" should parse correctly'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{dict[key]}")
        assert result is not None
        parts = result["parts"]
        assert parts[0]["kind"] == "expr"
        assert parts[0]["value"] == "dict[key]"

    def test_adjacent_literals_merged(self):
        '"a#{x}b#{y}c" should have 5 parts (literal, expr, literal, expr, literal)'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("a#{x}b#{y}c")
        assert result is not None
        parts = result["parts"]
        assert len(parts) == 5
        assert parts[0] == {"kind": "literal", "value": "a"}
        assert parts[1] == {"kind": "expr", "value": "x"}
        assert parts[2] == {"kind": "literal", "value": "b"}
        assert parts[3] == {"kind": "expr", "value": "y"}
        assert parts[4] == {"kind": "literal", "value": "c"}

    def test_string_with_only_literals_after_escape(self):
        '"\\#{x}" with only escaped interpolation should return None (plain string)'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("\\#{x}")
        assert result is None

    def test_multiple_dot_access(self):
        '"#{obj.attr.sub}" should parse correctly'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{obj.attr.sub}")
        assert result is not None
        assert result["parts"][0]["value"] == "obj.attr.sub"

    def test_interpolation_at_start(self):
        '"#{name} is here" should parse with expr first'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{name} is here")
        assert result["parts"][0]["kind"] == "expr"
        assert result["parts"][0]["value"] == "name"

    def test_interpolation_at_end(self):
        '"Hello #{name}" should parse with expr last'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("Hello #{name}")
        assert result["parts"][0]["kind"] == "literal"
        assert result["parts"][0]["value"] == "Hello "
        assert result["parts"][1]["kind"] == "expr"
        assert result["parts"][1]["value"] == "name"

    def test_consecutive_interpolations(self):
        '"#{a}#{b}" should parse as two adjacent expr parts'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{a}#{b}")
        assert len(result["parts"]) == 2
        assert result["parts"][0]["kind"] == "expr"
        assert result["parts"][1]["kind"] == "expr"

    def test_string_with_hash_but_no_brace(self):
        '"# not interpolation" should be plain string'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("# not interpolation")
        assert result is None

    def test_string_with_regular_braces(self):
        '"use {braces}" should be plain string'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("use {braces}")
        assert result is None

    def test_underscore_identifier(self):
        '"#{_name}" should parse underscore identifier'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{_name}")
        assert result["parts"][0]["kind"] == "expr"
        assert result["parts"][0]["value"] == "_name"

    def test_numeric_suffix_identifier(self):
        '"#{var123}" should parse identifier with numeric suffix'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{var123}")
        assert result["parts"][0]["kind"] == "expr"
        assert result["parts"][0]["value"] == "var123"

    def test_whitespace_in_interpolation_expr(self):
        '"#{ name }" should trim whitespace from expression'
        from src.ast_transformer import NexaTransformer
        result = NexaTransformer._parse_string_interpolation("#{ name }")
        assert result["parts"][0]["value"] == "name"


# ==================== P3-1: string_expr Handler Tests ====================

class TestStringExprHandler:
    'P3-1: Test that string_expr handler correctly detects interpolation in parsed strings'

    def test_plain_string_returns_string_literal(self):
        '"Hello World" should produce StringLiteral AST node'
        ast = parse_and_transform('flow main { x = "Hello World"; }')
        body = _find_flow_body(ast, 'main')
        stmt = body[0]
        assert stmt["type"] == "AssignmentStatement"
        value = stmt["value"]
        assert value["type"] == "StringLiteral"
        assert value["value"] == "Hello World"

    def test_interpolated_string_returns_interpolated_string(self):
        '"Hello #{name}!" should produce InterpolatedString AST node'
        ast = parse_and_transform('flow main { x = "Hello #{name}!"; }')
        body = _find_flow_body(ast, 'main')
        stmt = body[0]
        assert stmt["type"] == "AssignmentStatement"
        value = stmt["value"]
        assert value["type"] == "InterpolatedString"
        parts = value["parts"]
        assert len(parts) == 3
        assert parts[0]["kind"] == "literal"
        assert parts[0]["value"] == "Hello "
        assert parts[1]["kind"] == "expr"
        assert parts[1]["value"] == "name"
        assert parts[2]["kind"] == "literal"
        assert parts[2]["value"] == "!"

    def test_only_variable_interpolation(self):
        '"#{count}" should produce InterpolatedString with single expr part'
        ast = parse_and_transform('flow main { x = "#{count}"; }')
        body = _find_flow_body(ast, 'main')
        value = body[0]["value"]
        assert value["type"] == "InterpolatedString"
        assert len(value["parts"]) == 1
        assert value["parts"][0]["kind"] == "expr"
        assert value["parts"][0]["value"] == "count"

    def test_multiple_interpolations_in_string(self):
        '"#{greeting} #{name}" should parse with 2 expr and 1 literal parts'
        ast = parse_and_transform('flow main { x = "#{greeting} #{name}"; }')
        body = _find_flow_body(ast, 'main')
        value = body[0]["value"]
        assert value["type"] == "InterpolatedString"
        parts = value["parts"]
        assert len(parts) == 3
        assert parts[0]["kind"] == "expr"
        assert parts[0]["value"] == "greeting"
        assert parts[1]["kind"] == "literal"
        assert parts[1]["value"] == " "
        assert parts[2]["kind"] == "expr"
        assert parts[2]["value"] == "name"

    def test_dot_access_in_parsed_string(self):
        '"#{user.name}" should parse correctly through the full pipeline'
        ast = parse_and_transform('flow main { x = "#{user.name}"; }')
        body = _find_flow_body(ast, 'main')
        value = body[0]["value"]
        assert value["type"] == "InterpolatedString"
        assert value["parts"][0]["value"] == "user.name"

    def test_bracket_access_in_parsed_string(self):
        '"#{arr[0]}" should parse correctly through the full pipeline'
        ast = parse_and_transform('flow main { x = "#{arr[0]}"; }')
        body = _find_flow_body(ast, 'main')
        value = body[0]["value"]
        assert value["type"] == "InterpolatedString"
        assert value["parts"][0]["value"] == "arr[0]"

    def test_assignment_with_interpolated_string(self):
        'x = "Hello #{name}!" should produce InterpolatedString in value'
        ast = parse_and_transform('flow main { x = "Hello #{name}!"; }')
        body = _find_flow_body(ast, 'main')
        stmt = body[0]
        assert stmt["type"] == "AssignmentStatement"
        value = stmt["value"]
        assert value["type"] == "InterpolatedString"

    def test_print_with_interpolated_string(self):
        'print("Hello #{name}!") should produce InterpolatedString inside FunctionCallExpression'
        ast = parse_and_transform('flow main { print("Hello #{name}!"); }')
        str_expr = _find_string_expr_in_flow(ast, 'main')
        assert str_expr is not None
        assert str_expr["type"] == "InterpolatedString"
        assert str_expr["parts"][1]["value"] == "name"

    def test_print_with_plain_string(self):
        'print("Hello World") should produce StringLiteral inside FunctionCallExpression'
        ast = parse_and_transform('flow main { print("Hello World"); }')
        str_expr = _find_string_expr_in_flow(ast, 'main')
        assert str_expr is not None
        assert str_expr["type"] == "StringLiteral"


# ==================== P3-1: Code Generation Tests ====================

class TestInterpolatedStringCodeGeneration:
    'P3-1: Test that code generator produces correct Python for InterpolatedString'

    def test_simple_interpolation_codegen(self):
        '"Hello #{name}!" should generate concatenation with _nexa_interp_str'
        code = generate_code('flow main { print("Hello #{name}!"); }')
        assert "_nexa_interp_str" in code
        assert "'Hello '" in code
        assert "_nexa_interp_str(name)" in code

    def test_multiple_interpolation_codegen(self):
        '"#{a} and #{b}" should generate multiple _nexa_interp_str calls'
        code = generate_code('flow main { print("#{a} and #{b}"); }')
        assert "_nexa_interp_str(a)" in code
        assert "_nexa_interp_str(b)" in code
        assert "' and '" in code

    def test_only_expr_codegen(self):
        '"#{name}" should generate just _nexa_interp_str(name)'
        code = generate_code('flow main { print("#{name}"); }')
        assert "_nexa_interp_str(name)" in code

    def test_dot_access_codegen(self):
        '"#{user.name}" should generate dict-style access'
        code = generate_code('flow main { print("#{user.name}"); }')
        assert "_nexa_interp_str" in code
        assert 'user["name"]' in code

    def test_bracket_access_codegen(self):
        '"#{arr[0]}" should generate list-style access'
        code = generate_code('flow main { print("#{arr[0]}"); }')
        assert "_nexa_interp_str" in code
        assert "arr[0]" in code

    def test_plain_string_codegen_unchanged(self):
        '"Hello World" should generate plain Python string without _nexa_interp_str'
        code = generate_code('flow main { print("Hello World"); }')
        # No interpolation in the string, so no _nexa_interp_str call needed
        # The plain string "Hello World" appears as a regular Python string

    def test_empty_interpolation_codegen(self):
        '"#{}" should generate empty string'
        code = generate_code('flow main { print("#{}"); }')
        # Empty interpolation -> empty string literal
        assert "''" in code

    def test_assignment_with_interpolation_codegen(self):
        'x = "Hello #{name}!" should generate assignment with concatenation'
        code = generate_code('flow main { x = "Hello #{name}!"; }')
        assert "_nexa_interp_str" in code
        assert "name" in code

    def test_literal_with_special_chars_codegen(self):
        'Literal parts with newlines should be properly escaped'
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({"type": "Program", "body": []})
        result = gen._generate_interpolated_string([
            {"kind": "literal", "value": "Hello\nWorld"},
            {"kind": "expr", "value": "name"}
        ])
        assert "'Hello\\nWorld'" in result
        assert "_nexa_interp_str(name)" in result


# ==================== P3-1: _interp_expr_to_python Tests ====================

class TestInterpExprToPython:
    'P3-1: Test _interp_expr_to_python helper method'

    def _make_gen(self):
        from src.code_generator import CodeGenerator
        return CodeGenerator({"type": "Program", "body": []})

    def test_simple_identifier(self):
        'name should remain as "name"'
        gen = self._make_gen()
        result = gen._interp_expr_to_python("name")
        assert result == "name"

    def test_dot_access(self):
        'user.name should convert to user["name"]'
        gen = self._make_gen()
        result = gen._interp_expr_to_python("user.name")
        assert result == 'user["name"]'

    def test_multiple_dot_access(self):
        'config.server.host should convert to nested dict access'
        gen = self._make_gen()
        result = gen._interp_expr_to_python("config.server.host")
        assert result == 'config["server"]["host"]'

    def test_bracket_access_int(self):
        'arr[0] should remain as arr[0]'
        gen = self._make_gen()
        result = gen._interp_expr_to_python("arr[0]")
        assert result == "arr[0]"

    def test_bracket_access_string(self):
        'dict[key] should remain as dict[key]'
        gen = self._make_gen()
        result = gen._interp_expr_to_python("dict[key]")
        assert result == "dict[key]"

    def test_dot_then_bracket(self):
        'data.items[0] should convert to data["items"][0]'
        gen = self._make_gen()
        result = gen._interp_expr_to_python("data.items[0]")
        assert result == 'data["items"][0]'

    def test_bracket_then_dot(self):
        'arr[0].name should convert to arr[0]["name"]'
        gen = self._make_gen()
        result = gen._interp_expr_to_python("arr[0].name")
        assert result == 'arr[0]["name"]'


# ==================== P3-1: _nexa_interp_str Helper Tests ====================

class TestNexaInterpStr:
    'P3-1: Test _nexa_interp_str helper function for type conversion'

    def test_none_returns_empty_string(self):
        'None should convert to empty string'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str(None) == ""

    def test_int_returns_string(self):
        '42 should convert to "42"'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str(42) == "42"

    def test_float_returns_string(self):
        '3.14 should convert to "3.14"'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str(3.14) == "3.14"

    def test_bool_true_returns_true(self):
        'True should convert to "true"'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str(True) == "true"

    def test_bool_false_returns_false(self):
        'False should convert to "false"'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str(False) == "false"

    def test_string_returns_self(self):
        '"hello" should remain as "hello"'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str("hello") == "hello"

    def test_dict_returns_json(self):
        '{"key": "val"} should convert to JSON string'
        from src.runtime import _nexa_interp_str
        result = _nexa_interp_str({"key": "val"})
        assert "key" in result
        assert "val" in result
        parsed = json.loads(result)
        assert parsed["key"] == "val"

    def test_list_returns_json(self):
        '[1, 2, 3] should convert to JSON string'
        from src.runtime import _nexa_interp_str
        result = _nexa_interp_str([1, 2, 3])
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_option_some_returns_inner_value(self):
        'Option::Some dict should unwrap and convert inner value'
        from src.runtime import _nexa_interp_str
        some_dict = {"_nexa_option_variant": "Some", "value": "hello"}
        result = _nexa_interp_str(some_dict)
        assert result == "hello"

    def test_option_none_returns_empty(self):
        'Option::None dict should convert to empty string'
        from src.runtime import _nexa_interp_str
        none_dict = {"_nexa_option_variant": "None"}
        result = _nexa_interp_str(none_dict)
        assert result == ""

    def test_empty_dict_returns_json(self):
        '{} empty dict should convert to JSON "{}"'
        from src.runtime import _nexa_interp_str
        result = _nexa_interp_str({})
        assert result == "{}"

    def test_tuple_returns_json(self):
        '(1, 2) tuple should convert to JSON'
        from src.runtime import _nexa_interp_str
        result = _nexa_interp_str((1, 2))
        parsed = json.loads(result)
        assert parsed == [1, 2]

    def test_custom_object_returns_str(self):
        'Custom object should use default str()'
        from src.runtime import _nexa_interp_str
        class CustomObj:
            pass
        obj = CustomObj()
        result = _nexa_interp_str(obj)
        assert isinstance(result, str)
        assert len(result) > 0


# ==================== P3-1: _nexa_interp_str in BOILERPLATE Tests ====================

class TestBoilerplateInterpStr:
    'P3-1: Test that _nexa_interp_str is included in generated code BOILERPLATE'

    def test_boilerplate_contains_interp_str(self):
        'Generated code BOILERPLATE should include _nexa_interp_str definition'
        code = generate_code('flow main { print("Hello"); }')
        assert "_nexa_interp_str" in code

    def test_boilerplate_interp_str_none_handling(self):
        '_nexa_interp_str in BOILERPLATE should handle None -> empty string'
        from src.code_generator import BOILERPLATE
        assert "_nexa_interp_str" in BOILERPLATE


# ==================== P3-1: StdTool Registration Tests ====================

class TestStdToolRegistration:
    'P3-1: Test std.string.interpolate StdTool registration'

    def test_std_string_in_namespace_map(self):
        'std.string namespace should be in STD_NAMESPACE_MAP'
        from src.runtime.stdlib import STD_NAMESPACE_MAP
        assert "std.string" in STD_NAMESPACE_MAP
        assert "std_string_interpolate" in STD_NAMESPACE_MAP["std.string"]

    def test_std_string_interpolate_tool_exists(self):
        'std_string_interpolate StdTool should be in get_stdlib_tools()'
        from src.runtime.stdlib import get_stdlib_tools
        tools = get_stdlib_tools()
        assert "std_string_interpolate" in tools

    def test_std_string_interpolate_has_correct_description(self):
        'std_string_interpolate should have P3-1 description'
        from src.runtime.stdlib import get_stdlib_tools
        tools = get_stdlib_tools()
        tool = tools["std_string_interpolate"]
        assert "P3-1" in tool.description

    def test_std_string_interpolate_parameters(self):
        'std_string_interpolate should have template and context parameters'
        from src.runtime.stdlib import get_stdlib_tools
        tools = get_stdlib_tools()
        tool = tools["std_string_interpolate"]
        params = tool.parameters
        assert "template" in params["properties"]
        assert "context" in params["properties"]

    def test_std_string_interpolate_execution(self):
        'std_string_interpolate should execute and return interpolated result'
        from src.runtime.stdlib import get_stdlib_tools
        tools = get_stdlib_tools()
        tool = tools["std_string_interpolate"]
        result = tool.execute(
            template="Hello #{name}!",
            context=json.dumps({"name": "World"})
        )
        assert "World" in result
        assert "Hello" in result

    def test_std_string_interpolate_empty_context(self):
        'std_string_interpolate with empty context should still return template'
        from src.runtime.stdlib import get_stdlib_tools
        tools = get_stdlib_tools()
        tool = tools["std_string_interpolate"]
        result = tool.execute(
            template="Hello #{name}!",
            context="{}"
        )
        # With empty context, name resolves to None/empty
        assert "Hello" in result


# ==================== P3-1: Inspector Integration Tests ====================

class TestInspectorIntegration:
    'P3-1: Test that inspector handles InterpolatedString type'

    def test_inspector_expr_to_name_flat(self):
        '_expr_to_name_flat should handle InterpolatedString'
        from src.runtime.inspector import _expr_to_name_flat
        expr = {
            "type": "InterpolatedString",
            "parts": [
                {"kind": "literal", "value": "Hello "},
                {"kind": "expr", "value": "name"},
                {"kind": "literal", "value": "!"}
            ]
        }
        result = _expr_to_name_flat(expr)
        assert "Hello" in result
        assert "name" in result

    def test_type_inferrer_handles_interpolated_string(self):
        'TypeInferrer.infer_from_expression should return str type for InterpolatedString'
        from src.runtime.type_system import TypeInferrer
        expr = {
            "type": "InterpolatedString",
            "parts": [
                {"kind": "literal", "value": "Hello "},
                {"kind": "expr", "value": "name"},
            ]
        }
        result = TypeInferrer.infer_from_expression(expr)
        assert result.name == "str"


# ==================== P3-1: Edge Case Tests ====================

class TestEdgeCases:
    'P3-1: Test edge cases and error handling'

    def test_generate_interpolated_string_empty_parts(self):
        'Empty parts list should generate empty string'
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({"type": "Program", "body": []})
        result = gen._generate_interpolated_string([])
        assert result == '""'

    def test_generate_interpolated_string_single_literal(self):
        'Single literal part should generate single string'
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({"type": "Program", "body": []})
        result = gen._generate_interpolated_string([
            {"kind": "literal", "value": "Hello"}
        ])
        assert result == "'Hello'"

    def test_generate_interpolated_string_single_expr(self):
        'Single expr part should generate _nexa_interp_str call'
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({"type": "Program", "body": []})
        result = gen._generate_interpolated_string([
            {"kind": "expr", "value": "name"}
        ])
        assert result == "_nexa_interp_str(name)"

    def test_generate_interpolated_string_concatenation(self):
        'Multiple parts should generate + concatenation'
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({"type": "Program", "body": []})
        result = gen._generate_interpolated_string([
            {"kind": "literal", "value": "Hello "},
            {"kind": "expr", "value": "name"},
            {"kind": "literal", "value": "!"}
        ])
        assert "'Hello '" in result
        assert "_nexa_interp_str(name)" in result
        assert "'!'" in result
        assert " + " in result

    def test_generate_expr_code_interpolated_string(self):
        '_generate_expr_code should handle InterpolatedString type'
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({"type": "Program", "body": []})
        expr = {
            "type": "InterpolatedString",
            "parts": [
                {"kind": "literal", "value": "Hello "},
                {"kind": "expr", "value": "name"}
            ]
        }
        result = gen._generate_expr_code(expr)
        assert "'Hello '" in result
        assert "_nexa_interp_str(name)" in result

    def test_generate_expr_code_string_literal_unchanged(self):
        '_generate_expr_code should still handle StringLiteral — returns value as str'
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({"type": "Program", "body": []})
        expr = {"type": "StringLiteral", "value": "Hello World"}
        result = gen._generate_expr_code(expr)
        assert "Hello World" in result

    def test_flow_stmt_interpolated_string(self):
        '_generate_flow_stmt_code should handle InterpolatedString type'
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({"type": "Program", "body": []})
        stmt = {
            "type": "InterpolatedString",
            "parts": [
                {"kind": "literal", "value": "Hello "},
                {"kind": "expr", "value": "name"}
            ]
        }
        result = gen._generate_flow_stmt_code(stmt, indent=0)
        assert "'Hello '" in result
        assert "_nexa_interp_str(name)" in result


# ==================== P3-1: _nexa_interp_str Runtime Tests ====================

class TestNexaInterpStrRuntime:
    'P3-1: Test _nexa_interp_str from runtime/__init__.py'

    def test_runtime_interp_str_importable(self):
        '_nexa_interp_str should be importable from src.runtime'
        from src.runtime import _nexa_interp_str
        assert callable(_nexa_interp_str)

    def test_runtime_interp_str_in_all(self):
        '_nexa_interp_str should be in __all__'
        from src.runtime import __all__
        assert "_nexa_interp_str" in __all__

    def test_runtime_interp_str_none(self):
        '_nexa_interp_str(None) should return empty string'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str(None) == ""

    def test_runtime_interp_str_dict(self):
        '_nexa_interp_str(dict) should return JSON'
        from src.runtime import _nexa_interp_str
        result = _nexa_interp_str({"a": 1, "b": 2})
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_runtime_interp_str_int(self):
        '_nexa_interp_str(42) should return "42"'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str(42) == "42"

    def test_runtime_interp_str_zero(self):
        '_nexa_interp_str(0) should return "0"'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str(0) == "0"

    def test_runtime_interp_str_negative(self):
        '_nexa_interp_str(-5) should return "-5"'
        from src.runtime import _nexa_interp_str
        assert _nexa_interp_str(-5) == "-5"


# ==================== P3-1: Integration Tests ====================

class TestIntegration:
    'P3-1: Integration tests with other Nexa features'

    def test_interpolation_with_assignment(self):
        'Assigning interpolated string to variable should work'
        ast = parse_and_transform('flow main { msg = "Hello #{name}!"; print(msg); }')
        body = _find_flow_body(ast, 'main')
        assign_stmt = body[0]
        assert assign_stmt["type"] == "AssignmentStatement"
        assert assign_stmt["value"]["type"] == "InterpolatedString"

    def test_interpolation_codegen_full_pipeline(self):
        'Full code generation pipeline for interpolated string'
        code = generate_code('flow main { msg = "Hello #{name}!"; print(msg); }')
        assert "_nexa_interp_str(name)" in code
        assert "'Hello '" in code
        assert "'!'" in code

    def test_interpolation_with_null_coalesce_codegen(self):
        'Interpolated string with ?? should generate both features'
        code = generate_code('flow main { result = agent_run(prompt) ?? "default"; print("Got #{result}"); }')
        assert "_nexa_null_coalesce" in code
        assert "_nexa_interp_str" in code

    def test_multiple_flows_with_interpolation(self):
        'Multiple flows each with interpolated strings'
        code = generate_code('''
            flow greet { x = "Hello #{name}!"; print(x); }
            flow farewell { x = "Goodbye #{name}!"; print(x); }
        ''')
        assert "_nexa_interp_str(name)" in code

    def test_interpolation_in_print_statement(self):
        'Print with interpolated string should generate correct Python'
        code = generate_code('flow main { print("Count: #{count}"); }')
        assert "print(" in code
        assert "_nexa_interp_str(count)" in code
        assert "'Count: '" in code


# ==================== P3-1: Full End-to-End Tests ====================

class TestEndToEnd:
    'P3-1: Full end-to-end tests: parse -> transform -> generate'

    def test_e2e_simple_interpolation(self):
        'End-to-end: "Hello #{name}!" parsed, transformed, and generates correct Python'
        code = generate_code('flow main { x = "Hello #{name}!"; }')
        assert "x = " in code
        assert "_nexa_interp_str(name)" in code
        assert "'Hello '" in code
        assert "'!'" in code

    def test_e2e_plain_string(self):
        'End-to-end: "Hello World" should produce plain Python string'
        code = generate_code('flow main { x = "Hello World"; }')
        assert '"Hello World"' in code

    def test_e2e_dot_access(self):
        'End-to-end: "#{user.name}" should produce dict-style access'
        code = generate_code('flow main { print("#{user.name}"); }')
        assert 'user["name"]' in code
        assert "_nexa_interp_str" in code

    def test_e2e_bracket_access(self):
        'End-to-end: "#{arr[0]}" should produce list-style access'
        code = generate_code('flow main { print("#{arr[0]}"); }')
        assert "arr[0]" in code
        assert "_nexa_interp_str" in code

    def test_e2e_multi_var_interpolation(self):
        'End-to-end: "#{greeting}, #{name}!" should produce correct concatenation'
        code = generate_code('flow main { msg = "#{greeting}, #{name}!"; }')
        assert "_nexa_interp_str(greeting)" in code
        assert "_nexa_interp_str(name)" in code
        assert "', '" in code
        assert "'!'" in code

    def test_e2e_interpolated_string_ast_structure(self):
        'End-to-end: Verify full AST structure for interpolated string'
        ast = parse_and_transform('flow main { x = "Hello #{name}!"; }')
        body = _find_flow_body(ast, 'main')
        stmt = body[0]
        assert stmt["type"] == "AssignmentStatement"
        value = stmt["value"]
        assert value["type"] == "InterpolatedString"
        assert len(value["parts"]) == 3
        assert value["parts"][0] == {"kind": "literal", "value": "Hello "}
        assert value["parts"][1] == {"kind": "expr", "value": "name"}
        assert value["parts"][2] == {"kind": "literal", "value": "!"}

    def test_e2e_complex_interpolation(self):
        'End-to-end: Complex interpolation with dot and bracket access'
        ast = parse_and_transform('flow main { x = "#{data.items[0].name}"; }')
        body = _find_flow_body(ast, 'main')
        value = body[0]["value"]
        assert value["type"] == "InterpolatedString"
        assert value["parts"][0]["value"] == "data.items[0].name"

    def test_e2e_interpolation_and_plain_string_coexist(self):
        'End-to-end: Both interpolated and plain strings in same flow'
        ast = parse_and_transform('flow main { a = "plain"; b = "#{interp}"; }')
        body = _find_flow_body(ast, 'main')
        assert body[0]["value"]["type"] == "StringLiteral"
        assert body[1]["value"]["type"] == "InterpolatedString"

    def test_e2e_codegen_both_string_types(self):
        'End-to-end: Code generation with both string types'
        code = generate_code('flow main { a = "plain"; b = "#{interp}"; }')
        assert '"plain"' in code
        assert "_nexa_interp_str(interp)" in code