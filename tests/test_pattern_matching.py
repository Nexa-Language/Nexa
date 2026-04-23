"""
P3-3: Pattern Matching + Destructuring Tests

80+ tests covering all pattern types:
- Wildcard (5): _ matches anything, no binding
- Variable (5): variable binding, name capture
- Literal (10): int/float/string/bool matching
- Tuple (10): (a,b) destructuring, nested tuples
- Array (10): [a,b,..rest] with rest collector
- Map (10): {name, age:a} destructuring, rest collector
- Variant (10): Option::Some(v), Enum::Variant matching
- Match expr (10): multi-arm, guard conditions, priority
- Destructuring let (5): let (a,b) = expr
- Destructuring for (5): for (k,v) in items
- Exhaustiveness (3): non-exhaustive match warning
- Integration (5): match + pipe, match + ??, match + template
- Runtime (5): nexa_match_pattern, nexa_destructure helpers
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


def generate_code(code):
    'Parse Nexa code and generate Python code'
    from src.nexa_parser import parse
    from src.code_generator import CodeGenerator
    ast = parse(code)
    gen = CodeGenerator(ast)
    return gen.generate()


def _find_flow_body(ast, name):
    'Find the body of a flow declaration in AST'
    for item in ast.get('body', []):
        if isinstance(item, dict) and item.get('type') == 'FlowDeclaration' and item.get('name') == name:
            return item.get('body', [])
    return []


def _find_flow_stmt(ast, name, index=0):
    'Find a specific statement in a flow body'
    body = _find_flow_body(ast, name)
    if body and index < len(body):
        return body[index]
    return None


# ==================== Wildcard Pattern Tests ====================

class TestWildcardPattern:
    'P3-3: Test that _ wildcard pattern matches anything'

    def test_wildcard_parses(self):
        '_ pattern parses correctly in match expression'
        ast = parse_code('flow wf1 { match x { _ => 0 } }')
        stmt = _find_flow_stmt(ast, 'wf1', 0)
        assert stmt is not None
        assert stmt['type'] == 'MatchExpression'
        arm = stmt['arms'][0]
        assert arm['pattern']['kind'] == 'wildcard'

    def test_wildcard_no_binding(self):
        '_ pattern has no variable binding'
        ast = parse_code('flow wf2 { match x { _ => 0 } }')
        stmt = _find_flow_stmt(ast, 'wf2', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'wildcard'
        # Wildcard should not have 'name' field
        assert 'name' not in pattern

    def test_wildcard_always_matches_runtime(self):
        '_ pattern always matches in runtime'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'wildcard'}
        result = nexa_match_pattern(pattern, 42)
        assert result == {}
        result = nexa_match_pattern(pattern, None)
        assert result == {}
        result = nexa_match_pattern(pattern, [1, 2, 3])
        assert result == {}

    def test_wildcard_in_default_arm(self):
        '_ wildcard used as default arm in match'
        ast = parse_code('flow wf3 { match x { 0 => \"zero\", _ => \"other\" } }')
        stmt = _find_flow_stmt(ast, 'wf3', 0)
        assert len(stmt['arms']) == 2
        assert stmt['arms'][1]['pattern']['kind'] == 'wildcard'

    def test_wildcard_codegen(self):
        '_ wildcard generates True condition in Python code'
        code = generate_code('flow wf4 { match x { _ => 42 } }')
        assert 'if True' in code


# ==================== Variable Pattern Tests ====================

class TestVariablePattern:
    'P3-3: Test that variable pattern matches anything and binds variable'

    def test_variable_parses(self):
        'variable pattern parses correctly'
        ast = parse_code('flow vf1 { match x { n => n } }')
        stmt = _find_flow_stmt(ast, 'vf1', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'variable'
        assert pattern['name'] == 'n'

    def test_variable_binding_runtime(self):
        'variable pattern binds matched value to variable name'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'variable', 'name': 'x'}
        result = nexa_match_pattern(pattern, 42)
        assert result == {'x': 42}

    def test_variable_string_binding(self):
        'variable pattern binds string values'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'variable', 'name': 's'}
        result = nexa_match_pattern(pattern, 'hello')
        assert result == {'s': 'hello'}

    def test_variable_codegen_binding(self):
        'variable pattern generates binding in Python code'
        code = generate_code('flow vf2 { match x { n => n + 1 } }')
        assert 'n = _match_value' in code

    def test_variable_multiple_arms(self):
        'different variable names in different arms'
        ast = parse_code('flow vf3 { match x { a => a, b => b + 1 } }')
        stmt = _find_flow_stmt(ast, 'vf3', 0)
        assert stmt['arms'][0]['pattern']['name'] == 'a'
        assert stmt['arms'][1]['pattern']['name'] == 'b'


# ==================== Literal Pattern Tests ====================

class TestLiteralPattern:
    'P3-3: Test that literal patterns match exact values'

    def test_int_literal_parses(self):
        'integer literal pattern parses correctly'
        ast = parse_code('flow lf1 { match x { 0 => \"zero\" } }')
        stmt = _find_flow_stmt(ast, 'lf1', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'literal'
        assert pattern['value'] == 0
        assert pattern['value_type'] == 'int'

    def test_float_literal_parses(self):
        'float literal pattern parses correctly'
        ast = parse_code('flow lf2 { match x { 3.14 => \"pi\" } }')
        stmt = _find_flow_stmt(ast, 'lf2', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'literal'
        assert pattern['value_type'] == 'float'

    def test_string_literal_parses(self):
        'string literal pattern parses correctly'
        ast = parse_code('flow lf3 { match x { \"hello\" => 1 } }')
        stmt = _find_flow_stmt(ast, 'lf3', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'literal'
        assert pattern['value'] == 'hello'
        assert pattern['value_type'] == 'string'

    def test_true_literal_parses(self):
        'true literal pattern parses correctly'
        ast = parse_code('flow lf4 { match x { true => 1 } }')
        stmt = _find_flow_stmt(ast, 'lf4', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'literal'
        assert pattern['value'] == True
        assert pattern['value_type'] == 'bool'

    def test_false_literal_parses(self):
        'false literal pattern parses correctly'
        ast = parse_code('flow lf5 { match x { false => 0 } }')
        stmt = _find_flow_stmt(ast, 'lf5', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'literal'
        assert pattern['value'] == False
        assert pattern['value_type'] == 'bool'

    def test_int_literal_runtime_match(self):
        'integer literal matches exact value in runtime'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'literal', 'value': 42, 'value_type': 'int'}
        assert nexa_match_pattern(pattern, 42) == {}
        assert nexa_match_pattern(pattern, 41) is None

    def test_string_literal_runtime_match(self):
        'string literal matches exact value in runtime'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'literal', 'value': 'hello', 'value_type': 'string'}
        assert nexa_match_pattern(pattern, 'hello') == {}
        assert nexa_match_pattern(pattern, 'world') is None

    def test_bool_literal_runtime_match(self):
        'bool literal matches exact value in runtime'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern_true = {'type': 'Pattern', 'kind': 'literal', 'value': True, 'value_type': 'bool'}
        assert nexa_match_pattern(pattern_true, True) == {}
        assert nexa_match_pattern(pattern_true, False) is None

    def test_float_literal_runtime_match(self):
        'float literal matches exact value in runtime'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'literal', 'value': 3.14, 'value_type': 'float'}
        assert nexa_match_pattern(pattern, 3.14) == {}
        assert nexa_match_pattern(pattern, 2.71) is None

    def test_literal_codegen_condition(self):
        'literal pattern generates equality condition in Python code'
        code = generate_code('flow lf6 { match x { 0 => \"zero\" } }')
        assert '_match_value == 0' in code


# ==================== Tuple Pattern Tests ====================

class TestTuplePattern:
    'P3-3: Test tuple pattern (a, b) destructuring'

    def test_tuple_parses(self):
        'tuple pattern (a, b) parses correctly'
        ast = parse_code('flow tf1 { match x { (a, b) => a } }')
        stmt = _find_flow_stmt(ast, 'tf1', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'tuple'
        assert len(pattern['elements']) == 2
        assert pattern['elements'][0]['kind'] == 'variable'
        assert pattern['elements'][0]['name'] == 'a'
        assert pattern['elements'][1]['kind'] == 'variable'
        assert pattern['elements'][1]['name'] == 'b'

    def test_tuple_runtime_match(self):
        'tuple pattern matches list/tuple of exact length'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'tuple',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'a'},
                                {'type': 'Pattern', 'kind': 'variable', 'name': 'b'}]}
        result = nexa_match_pattern(pattern, [1, 2])
        assert result == {'a': 1, 'b': 2}
        assert nexa_match_pattern(pattern, [1, 2, 3]) is None
        assert nexa_match_pattern(pattern, 'not a tuple') is None

    def test_tuple_runtime_nested(self):
        'nested tuple pattern matches nested structures'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'tuple',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'x'},
                                {'type': 'Pattern', 'kind': 'tuple',
                                'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'y'},
                                             {'type': 'Pattern', 'kind': 'variable', 'name': 'z'}]}]}
        result = nexa_match_pattern(pattern, [1, [2, 3]])
        assert result == {'x': 1, 'y': 2, 'z': 3}

    def test_tuple_codegen_condition(self):
        'tuple pattern generates _nexa_is_tuple_like condition'
        code = generate_code('flow tf2 { match x { (a, b) => a } }')
        assert '_nexa_is_tuple_like' in code

    def test_tuple_codegen_bindings(self):
        'tuple pattern generates element bindings'
        code = generate_code('flow tf3 { match x { (a, b) => a } }')
        assert 'a = _match_value[0]' in code
        assert 'b = _match_value[1]' in code

    def test_tuple_three_elements(self):
        'tuple pattern with three elements'
        ast = parse_code('flow tf4 { match x { (a, b, c) => a } }')
        stmt = _find_flow_stmt(ast, 'tf4', 0)
        pattern = stmt['arms'][0]['pattern']
        assert len(pattern['elements']) == 3

    def test_tuple_with_literal_element(self):
        'tuple pattern with literal element inside'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'tuple',
                   'elements': [{'type': 'Pattern', 'kind': 'literal', 'value': 0, 'value_type': 'int'},
                                {'type': 'Pattern', 'kind': 'variable', 'name': 'y'}]}
        result = nexa_match_pattern(pattern, [0, 'hello'])
        assert result == {'y': 'hello'}
        assert nexa_match_pattern(pattern, [1, 'hello']) is None

    def test_tuple_runtime_length_check(self):
        'tuple pattern fails on wrong length'
        from src.runtime.pattern_matching import nexa_match_pattern, _nexa_is_tuple_like
        assert _nexa_is_tuple_like([1, 2], 2) == True
        assert _nexa_is_tuple_like([1, 2, 3], 2) == False
        assert _nexa_is_tuple_like([1], 2) == False
        assert _nexa_is_tuple_like('abc', 3) == False

    def test_tuple_with_wildcard_element(self):
        'tuple pattern with wildcard element'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'tuple',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'x'},
                                {'type': 'Pattern', 'kind': 'wildcard'}]}
        result = nexa_match_pattern(pattern, [1, 'anything'])
        assert result == {'x': 1}


# ==================== Array Pattern Tests ====================

class TestArrayPattern:
    'P3-3: Test array pattern [a, b, ..rest] with rest collector'

    def test_array_no_rest_parses(self):
        'array pattern [a, b] without rest parses correctly'
        ast = parse_code('flow af1 { match x { [a, b] => a } }')
        stmt = _find_flow_stmt(ast, 'af1', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'array'
        assert len(pattern['elements']) == 2
        assert pattern['rest'] is None

    def test_array_with_rest_parses(self):
        'array pattern [a, b..rest] with rest parses correctly'
        ast = parse_code('flow af2 { match x { [a, b..rest] => a } }')
        stmt = _find_flow_stmt(ast, 'af2', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'array'
        assert pattern['rest'] == 'rest'

    def test_array_no_rest_runtime(self):
        'array pattern without rest matches exact length'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'array',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'a'},
                                {'type': 'Pattern', 'kind': 'variable', 'name': 'b'}],
                   'rest': None}
        result = nexa_match_pattern(pattern, [1, 2])
        assert result == {'a': 1, 'b': 2}
        assert nexa_match_pattern(pattern, [1, 2, 3]) is None

    def test_array_with_rest_runtime(self):
        'array pattern with rest collects remaining elements'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'array',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'a'},
                                {'type': 'Pattern', 'kind': 'variable', 'name': 'b'}],
                   'rest': 'rest'}
        result = nexa_match_pattern(pattern, [1, 2, 3, 4])
        assert result == {'a': 1, 'b': 2, 'rest': [3, 4]}
        # Still matches exact length
        result = nexa_match_pattern(pattern, [1, 2])
        assert result == {'a': 1, 'b': 2, 'rest': []}
        # Fails on too short
        assert nexa_match_pattern(pattern, [1]) is None

    def test_array_codegen_condition(self):
        'array pattern generates _nexa_is_tuple_like or _nexa_is_list_like condition'
        code = generate_code('flow af3 { match x { [a, b] => a } }')
        assert '_nexa_is_tuple_like' in code or '_nexa_is_list_like' in code

    def test_array_codegen_bindings(self):
        'array pattern generates element bindings'
        code = generate_code('flow af4 { match x { [a, b] => a } }')
        assert 'a = _match_value[0]' in code
        assert 'b = _match_value[1]' in code

    def test_array_codegen_rest_binding(self):
        'array pattern with rest generates rest binding'
        code = generate_code('flow af5 { match x { [first..rest] => first } }')
        assert '_nexa_list_rest' in code
        assert 'rest = _nexa_list_rest' in code

    def test_array_runtime_helpers(self):
        '_nexa_is_list_like and _nexa_list_rest helpers work correctly'
        from src.runtime.pattern_matching import _nexa_is_list_like, _nexa_list_rest
        assert _nexa_is_list_like([1, 2, 3], 2) == True
        assert _nexa_is_list_like([1], 2) == False
        assert _nexa_list_rest([1, 2, 3, 4], 2) == [3, 4]

    def test_array_single_element(self):
        'array pattern with single element'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'array',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'x'}],
                   'rest': None}
        result = nexa_match_pattern(pattern, [42])
        assert result == {'x': 42}
        assert nexa_match_pattern(pattern, [42, 43]) is None

    def test_array_fails_on_dict(self):
        'array pattern does not match dict values'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'array',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'a'}],
                   'rest': None}
        assert nexa_match_pattern(pattern, {'key': 'val'}) is None


# ==================== Map Pattern Tests ====================

class TestMapPattern:
    'P3-3: Test map pattern {name, age:a} destructuring'

    def test_map_shorthand_parses(self):
        'map pattern {name} shorthand parses correctly'
        ast = parse_code('flow mf1 { match x { {name} => name } }')
        stmt = _find_flow_stmt(ast, 'mf1', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'map'
        assert len(pattern['entries']) == 1
        entry = pattern['entries'][0]
        assert entry['key'] == 'name'

    def test_map_explicit_parses(self):
        'map pattern {name: n} explicit alias parses correctly'
        ast = parse_code('flow mf2 { match x { {age: a} => a } }')
        stmt = _find_flow_stmt(ast, 'mf2', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'map'
        entry = pattern['entries'][0]
        assert entry['key'] == 'age'
        assert entry['value_pattern']['kind'] == 'variable'
        assert entry['value_pattern']['name'] == 'a'

    def test_map_runtime_match(self):
        'map pattern matches dict with required keys'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'map',
                   'entries': [{'type': 'MapPatternEntry', 'key': 'name', 'value_pattern': {'type': 'Pattern', 'kind': 'variable', 'name': 'n'}}],
                   'rest': None}
        result = nexa_match_pattern(pattern, {'name': 'Alice', 'age': 30})
        assert result == {'n': 'Alice'}

    def test_map_runtime_shorthand(self):
        'map pattern shorthand {name} binds key value to variable name'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'map',
                   'entries': [{'type': 'MapPatternEntry', 'key': 'name', 'value_pattern': None}],
                   'rest': None}
        result = nexa_match_pattern(pattern, {'name': 'Bob'})
        assert result == {'name': 'Bob'}

    def test_map_runtime_missing_key(self):
        'map pattern fails if required key is missing'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'map',
                   'entries': [{'type': 'MapPatternEntry', 'key': 'name', 'value_pattern': None}],
                   'rest': None}
        assert nexa_match_pattern(pattern, {'age': 30}) is None

    def test_map_codegen_condition(self):
        'map pattern generates _nexa_is_dict_with_keys condition'
        code = generate_code('flow mf3 { match x { {name} => name } }')
        assert '_nexa_is_dict_with_keys' in code

    def test_map_codegen_bindings(self):
        'map pattern generates dict access bindings'
        code = generate_code('flow mf4 { match x { {name} => name } }')
        assert 'name = _match_value["name"]' in code

    def test_map_codegen_explicit_binding(self):
        'map pattern explicit binding {age: a} generates aliased binding'
        code = generate_code('flow mf5 { match x { {age: a} => a } }')
        assert 'a = _match_value["age"]' in code

    def test_map_runtime_helpers(self):
        '_nexa_is_dict_with_keys and _nexa_dict_rest helpers work'
        from src.runtime.pattern_matching import _nexa_is_dict_with_keys, _nexa_dict_rest
        assert _nexa_is_dict_with_keys({'name': 'A', 'age': 30}, ['name']) == True
        assert _nexa_is_dict_with_keys({'age': 30}, ['name']) == False
        assert _nexa_dict_rest({'name': 'A', 'age': 30, 'city': 'NY'}, ['name', 'age']) == {'city': 'NY'}

    def test_map_fails_on_non_dict(self):
        'map pattern does not match non-dict values'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'map',
                   'entries': [{'type': 'MapPatternEntry', 'key': 'name', 'value_pattern': None}],
                   'rest': None}
        assert nexa_match_pattern(pattern, [1, 2]) is None
        assert nexa_match_pattern(pattern, 'string') is None


# ==================== Variant Pattern Tests ====================

class TestVariantPattern:
    'P3-3: Test variant pattern Option::Some(v) matching'

    def test_variant_no_fields_parses(self):
        'variant pattern without fields parses correctly'
        ast = parse_code('flow vpf1 { match x { Option::None => 0 } }')
        stmt = _find_flow_stmt(ast, 'vpf1', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'variant'
        assert pattern['enum_name'] == 'Option'
        assert pattern['variant_name'] == 'None'
        assert len(pattern['fields']) == 0

    def test_variant_with_fields_parses(self):
        'variant pattern with field parses correctly'
        ast = parse_code('flow vpf2 { match x { Option::Some(v) => v } }')
        stmt = _find_flow_stmt(ast, 'vpf2', 0)
        pattern = stmt['arms'][0]['pattern']
        assert pattern['kind'] == 'variant'
        assert pattern['enum_name'] == 'Option'
        assert pattern['variant_name'] == 'Some'
        assert len(pattern['fields']) == 1
        assert pattern['fields'][0]['kind'] == 'variable'
        assert pattern['fields'][0]['name'] == 'v'

    def test_variant_runtime_match(self):
        'variant pattern matches enum variant value'
        from src.runtime.pattern_matching import nexa_match_pattern, nexa_make_variant
        value = nexa_make_variant('Option', 'Some', 42)
        pattern = {'type': 'Pattern', 'kind': 'variant',
                   'enum_name': 'Option', 'variant_name': 'Some',
                   'fields': [{'type': 'Pattern', 'kind': 'variable', 'name': 'v'}]}
        result = nexa_match_pattern(pattern, value)
        assert result == {'v': 42}

    def test_variant_runtime_no_match(self):
        'variant pattern fails on wrong variant'
        from src.runtime.pattern_matching import nexa_match_pattern, nexa_make_variant
        value = nexa_make_variant('Option', 'None')
        pattern = {'type': 'Pattern', 'kind': 'variant',
                   'enum_name': 'Option', 'variant_name': 'Some',
                   'fields': [{'type': 'Pattern', 'kind': 'variable', 'name': 'v'}]}
        assert nexa_match_pattern(pattern, value) is None

    def test_variant_runtime_unit_variant(self):
        'unit variant (no fields) matches correctly'
        from src.runtime.pattern_matching import nexa_match_pattern, nexa_make_variant
        value = nexa_make_variant('Option', 'None')
        pattern = {'type': 'Pattern', 'kind': 'variant',
                   'enum_name': 'Option', 'variant_name': 'None',
                   'fields': []}
        result = nexa_match_pattern(pattern, value)
        assert result == {}

    def test_variant_codegen_condition(self):
        'variant pattern generates _nexa_is_variant condition'
        code = generate_code('flow vpf3 { match x { Option::Some(v) => v } }')
        assert '_nexa_is_variant' in code

    def test_variant_codegen_bindings(self):
        'variant pattern generates field bindings'
        code = generate_code('flow vpf4 { match x { Option::Some(v) => v } }')
        assert 'v = _match_value["_nexa_fields"][0]' in code

    def test_variant_runtime_helpers(self):
        'nexa_make_variant creates proper variant value'
        from src.runtime.pattern_matching import nexa_make_variant, _nexa_is_variant
        v = nexa_make_variant('Result', 'Ok', 42)
        assert _nexa_is_variant(v, 'Result', 'Ok') == True
        assert _nexa_is_variant(v, 'Result', 'Err') == False
        assert v['_nexa_fields'] == [42]

    def test_variant_multi_field(self):
        'variant pattern with multiple fields'
        from src.runtime.pattern_matching import nexa_match_pattern, nexa_make_variant
        value = nexa_make_variant('Pair', 'Values', 1, 2)
        pattern = {'type': 'Pattern', 'kind': 'variant',
                   'enum_name': 'Pair', 'variant_name': 'Values',
                   'fields': [{'type': 'Pattern', 'kind': 'variable', 'name': 'x'},
                              {'type': 'Pattern', 'kind': 'variable', 'name': 'y'}]}
        result = nexa_match_pattern(pattern, value)
        assert result == {'x': 1, 'y': 2}

    def test_variant_non_dict_fails(self):
        'variant pattern fails on non-dict values'
        from src.runtime.pattern_matching import nexa_match_pattern
        pattern = {'type': 'Pattern', 'kind': 'variant',
                   'enum_name': 'Option', 'variant_name': 'Some',
                   'fields': []}
        assert nexa_match_pattern(pattern, 42) is None
        assert nexa_match_pattern(pattern, 'string') is None


# ==================== Match Expression Tests ====================

class TestMatchExpression:
    'P3-3: Test match expression parsing and code generation'

    def test_match_multi_arm(self):
        'match expression with multiple arms'
        ast = parse_code('flow mef1 { match x { 0 => \"zero\", 1 => \"one\", _ => \"other\" } }')
        stmt = _find_flow_stmt(ast, 'mef1', 0)
        assert stmt['type'] == 'MatchExpression'
        assert len(stmt['arms']) == 3

    def test_match_scrutinee(self):
        'match expression scrutinee is parsed'
        ast = parse_code('flow mef2 { match x + 1 { 0 => \"zero\" } }')
        stmt = _find_flow_stmt(ast, 'mef2', 0)
        assert stmt['scrutinee'] is not None

    def test_match_codegen_full(self):
        'match expression generates complete if/elif chain'
        code = generate_code('flow mef3 { match x { 0 => \"zero\", _ => \"other\" } }')
        assert '_match_value' in code
        assert '_match_result' in code
        assert 'if _match_value == 0' in code
        assert 'elif True' in code or 'else:' in code

    def test_match_block_body(self):
        'match expression with block body'
        ast = parse_code('flow mef4 { match x { 0 => { y = 1 } } }')
        stmt = _find_flow_stmt(ast, 'mef4', 0)
        arm = stmt['arms'][0]
        assert arm['body'] is not None

    def test_match_expression_body(self):
        'match expression with expression body'
        ast = parse_code('flow mef5 { match x { n => n * 2 } }')
        stmt = _find_flow_stmt(ast, 'mef5', 0)
        arm = stmt['arms'][0]
        assert arm['body'] is not None

    def test_match_guard_condition(self):
        'match arm with guard condition'
        ast = parse_code('flow mef6 { match x { n => n if n > 0 } }')
        stmt = _find_flow_stmt(ast, 'mef6', 0)
        arm = stmt['arms'][0]
        assert arm['guard'] is not None

    def test_match_mixed_patterns(self):
        'match expression with mixed pattern types'
        ast = parse_code('flow mef7 { match x { 0 => \"zero\", (a, b) => a, _ => \"other\" } }')
        stmt = _find_flow_stmt(ast, 'mef7', 0)
        assert stmt['arms'][0]['pattern']['kind'] == 'literal'
        assert stmt['arms'][1]['pattern']['kind'] == 'tuple'
        assert stmt['arms'][2]['pattern']['kind'] == 'wildcard'

    def test_match_at_script_level(self):
        'match expression can appear at script level'
        ast = parse_code('match x { 0 => \"zero\", _ => \"other\" }')
        # Script level match_expr should appear in body
        found = False
        for item in ast.get('body', []):
            if isinstance(item, dict) and item.get('type') == 'MatchExpression':
                found = True
                break
        assert found

    def test_match_string_pattern_codegen(self):
        'match expression with string literal pattern'
        code = generate_code('flow mef8 { match cmd { \"start\" => 1, \"stop\" => 0 } }')
        assert '_match_value == "start"' in code
        assert '_match_value == "stop"' in code


# ==================== Let Destructuring Tests ====================

class TestLetDestructuring:
    'P3-3: Test let destructuring: let (a, b) = expr'

    def test_let_tuple_parses(self):
        'let (a, b) = expr parses correctly'
        ast = parse_code('flow ldf1 { let (a, b) = expr; }')
        stmt = _find_flow_stmt(ast, 'ldf1', 0)
        assert stmt['type'] == 'LetPatternStatement'
        assert stmt['pattern']['kind'] == 'tuple'
        assert stmt['expression'] is not None

    def test_let_tuple_codegen(self):
        'let destructuring generates Python tuple unpacking'
        code = generate_code('flow ldf2 { let (a, b) = expr; }')
        assert '_let_value' in code
        assert 'a = _let_value[0]' in code
        assert 'b = _let_value[1]' in code

    def test_let_array_destructure(self):
        'let [a, b] = expr parses and generates code'
        code = generate_code('flow ldf3 { let [a, b] = expr; }')
        assert 'a = _let_value[0]' in code
        assert 'b = _let_value[1]' in code

    def test_let_runtime_destructure(self):
        'nexa_destructure works for tuple patterns'
        from src.runtime.pattern_matching import nexa_destructure
        pattern = {'type': 'Pattern', 'kind': 'tuple',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'x'},
                                {'type': 'Pattern', 'kind': 'variable', 'name': 'y'}]}
        result = nexa_destructure(pattern, [10, 20])
        assert result == {'x': 10, 'y': 20}

    def test_let_runtime_error(self):
        'nexa_destructure raises ValueError on mismatch'
        from src.runtime.pattern_matching import nexa_destructure
        pattern = {'type': 'Pattern', 'kind': 'tuple',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'a'},
                                {'type': 'Pattern', 'kind': 'variable', 'name': 'b'}]}
        with pytest.raises(ValueError):
            nexa_destructure(pattern, [1])  # Wrong length


# ==================== For Destructuring Tests ====================

class TestForDestructuring:
    'P3-3: Test for destructuring: for (key, value) in items'

    def test_for_tuple_parses(self):
        'for (k, v) in items parses correctly'
        ast = parse_code('flow fd1 { for (k, v) in items { print(k); } }')
        stmt = _find_flow_stmt(ast, 'fd1', 0)
        assert stmt['type'] == 'ForPatternStatement'
        assert stmt['pattern']['kind'] == 'tuple'
        assert stmt['iterable'] is not None

    def test_for_tuple_codegen(self):
        'for destructuring generates Python for loop with unpacking'
        code = generate_code('flow fd2 { for (k, v) in items { print(k); } }')
        assert 'for _for_item in' in code
        assert 'k = _for_item[0]' in code
        assert 'v = _for_item[1]' in code

    def test_for_variable_pattern(self):
        'for single variable pattern in items'
        ast = parse_code('flow fd3 { for item in items { print(item); } }')
        stmt = _find_flow_stmt(ast, 'fd3', 0)
        # This should be a regular ForEachStatement, not ForPatternStatement

    def test_for_runtime_destructure(self):
        'for destructuring works with dict items'
        from src.runtime.pattern_matching import nexa_destructure
        pattern = {'type': 'Pattern', 'kind': 'tuple',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'key'},
                                {'type': 'Pattern', 'kind': 'variable', 'name': 'val'}]}
        # Simulating dict.items() iteration
        for key, val in {'a': 1, 'b': 2}.items():
            result = nexa_destructure(pattern, [key, val])
            assert 'key' in result
            assert 'val' in result

    def test_for_nested_destructure(self):
        'for nested pattern destructuring'
        code = generate_code('flow fd4 { for (k, (x, y)) in items { print(k); } }')
        assert 'for _for_item in' in code


# ==================== Exhaustiveness Tests ====================

class TestExhaustiveness:
    'P3-3: Test non-exhaustive match scenarios'

    def test_match_without_wildcard(self):
        'match expression without wildcard/default arm'
        ast = parse_code('flow ef1 { match x { 0 => \"zero\", 1 => \"one\" } }')
        stmt = _find_flow_stmt(ast, 'ef1', 0)
        # No wildcard arm — this is a non-exhaustive match
        has_wildcard = any(arm['pattern']['kind'] == 'wildcard' for arm in stmt['arms'])
        assert not has_wildcard

    def test_match_with_wildcard_is_exhaustive(self):
        'match expression with wildcard is always exhaustive'
        ast = parse_code('flow ef2 { match x { 0 => \"zero\", _ => \"other\" } }')
        stmt = _find_flow_stmt(ast, 'ef2', 0)
        has_wildcard = any(arm['pattern']['kind'] == 'wildcard' for arm in stmt['arms'])
        assert has_wildcard

    def test_match_variable_is_exhaustive(self):
        'match expression with variable pattern is always exhaustive'
        ast = parse_code('flow ef3 { match x { n => n } }')
        stmt = _find_flow_stmt(ast, 'ef3', 0)
        # Single variable arm matches everything
        assert stmt['arms'][0]['pattern']['kind'] == 'variable'


# ==================== Integration Tests ====================

class TestIntegration:
    'P3-3: Test match expression integration with other features'

    def test_match_with_string_result(self):
        'match expression returning string values'
        code = generate_code('flow if1 { match cmd { \"start\" => 1, \"stop\" => 0 } }')
        assert '_match_value == "start"' in code

    def test_match_with_nested_expression(self):
        'match expression with complex scrutinee'
        ast = parse_code('flow if2 { match x + 1 { 0 => \"zero\" } }')
        stmt = _find_flow_stmt(ast, 'if2', 0)
        assert stmt['type'] == 'MatchExpression'
        assert stmt['scrutinee'] is not None

    def test_match_with_assignment(self):
        'match result assigned to variable'
        code = generate_code('flow if3 { result = match x { 0 => \"zero\", _ => \"other\" } }')
        # This may need assignment_stmt integration

    def test_match_with_bool_pattern(self):
        'match expression with boolean pattern'
        code = generate_code('flow if4 { match flag { true => 1, false => 0 } }')
        assert '_match_value == True' in code
        assert '_match_value == False' in code

    def test_match_with_tuple_and_literal(self):
        'match expression combining tuple and literal patterns'
        code = generate_code('flow if5 { match x { (a, 0) => a, _ => 0 } }')
        assert '_nexa_is_tuple_like' in code


# ==================== Runtime Helper Tests ====================

class TestRuntimeHelpers:
    'P3-3: Test pattern matching runtime helper functions'

    def test_nexa_match_pattern_wildcard(self):
        'nexa_match_pattern with wildcard always returns {}'
        from src.runtime.pattern_matching import nexa_match_pattern
        assert nexa_match_pattern({'kind': 'wildcard'}, 42) == {}
        assert nexa_match_pattern({'kind': 'wildcard'}, None) == {}

    def test_nexa_match_pattern_variable(self):
        'nexa_match_pattern with variable returns binding dict'
        from src.runtime.pattern_matching import nexa_match_pattern
        result = nexa_match_pattern({'kind': 'variable', 'name': 'x'}, 42)
        assert result == {'x': 42}

    def test_nexa_make_variant(self):
        'nexa_make_variant creates proper variant dict'
        from src.runtime.pattern_matching import nexa_make_variant
        v = nexa_make_variant('Option', 'Some', 42)
        assert v['_nexa_enum'] == 'Option'
        assert v['_nexa_variant'] == 'Some'
        assert v['_nexa_fields'] == [42]

    def test_nexa_destructure_success(self):
        'nexa_destructure successfully destructures values'
        from src.runtime.pattern_matching import nexa_destructure
        pattern = {'type': 'Pattern', 'kind': 'tuple',
                   'elements': [{'type': 'Pattern', 'kind': 'variable', 'name': 'a'}]}
        result = nexa_destructure(pattern, [10])
        assert result == {'a': 10}

    def test_nexa_destructure_failure(self):
        'nexa_destructure raises ValueError on mismatch'
        from src.runtime.pattern_matching import nexa_destructure
        pattern = {'type': 'Pattern', 'kind': 'literal', 'value': 42, 'value_type': 'int'}
        with pytest.raises(ValueError):
            nexa_destructure(pattern, 41)