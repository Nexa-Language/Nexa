"""
Nexa Template System (P2-4) Comprehensive Tests
"""

import pytest
import sys
import os
import time
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.runtime.template import (
    NexaTemplateRenderer, TemplateContentParser,
    _nexa_tpl_escape, _nexa_tpl_join, _nexa_tpl_safe_str,
    FILTER_REGISTRY, apply_filter_chain,
    render_string, template, compile_template, render,
    agent_template_prompt, agent_template_slot_fill,
    agent_template_register, agent_template_list, agent_template_unregister,
    get_active_templates, CompiledTemplate,
    filter_upper, filter_uppercase, filter_lower, filter_lowercase,
    filter_capitalize, filter_trim, filter_truncate, filter_replace,
    filter_escape, filter_raw, filter_safe, filter_default,
    filter_length, filter_first, filter_last, filter_reverse,
    filter_join, filter_slice, filter_json, filter_number,
    filter_url_encode, filter_strip_tags, filter_word_count,
    filter_line_count, filter_indent, filter_date,
    filter_sort, filter_unique, filter_abs, filter_ceil, filter_floor,
)
from src.ast_transformer import NexaTemplateParser as ASTTemplateParser, TemplatePart, TemplateFilter
from src.runtime.contracts import ContractViolation


class TestHelperFunctions:
    def test_escape_html_tags(self):
        r = _nexa_tpl_escape("<script>alert(1)</script>")
        assert r == "&lt;script&gt;alert(1)&lt;/script&gt;"

    def test_escape_ampersand(self):
        assert _nexa_tpl_escape("a & b") == "a &amp; b"

    def test_escape_double_quotes(self):
        r = _nexa_tpl_escape(chr(34) + "hello" + chr(34))
        assert chr(38)+chr(113)+chr(117)+chr(111)+chr(116)+chr(59) in r

    def test_escape_single_quotes(self):
        assert _nexa_tpl_escape("'hello'") == "&#x27;hello&#x27;"

    def test_escape_empty_string(self):
        assert _nexa_tpl_escape("") == ""

    def test_escape_no_special_chars(self):
        assert _nexa_tpl_escape("Hello World") == "Hello World"

    def test_escape_lt_only(self):
        assert _nexa_tpl_escape("a<b") == "a&lt;b"

    def test_escape_gt_only(self):
        assert _nexa_tpl_escape("a>b") == "a&gt;b"

    def test_join_basic(self):
        assert _nexa_tpl_join(["a", "b", "c"]) == "abc"

    def test_join_empty_list(self):
        assert _nexa_tpl_join([]) == ""

    def test_join_with_none(self):
        assert _nexa_tpl_join(["a", None, "c"]) == "ac"

    def test_join_mixed_types(self):
        assert _nexa_tpl_join(["a", 1, True]) == "a1True"

    def test_join_single_item(self):
        assert _nexa_tpl_join(["x"]) == "x"

    def test_safe_str_string(self):
        assert _nexa_tpl_safe_str("hello") == "hello"

    def test_safe_str_none(self):
        assert _nexa_tpl_safe_str(None) == ""

    def test_safe_str_number(self):
        assert _nexa_tpl_safe_str(42) == "42"

    def test_safe_str_bool_true(self):
        assert _nexa_tpl_safe_str(True) == "true"

    def test_safe_str_bool_false(self):
        assert _nexa_tpl_safe_str(False) == "false"

    def test_safe_str_list(self):
        assert _nexa_tpl_safe_str([1, 2]) == "[1, 2]"

    def test_safe_str_zero(self):
        assert _nexa_tpl_safe_str(0) == "0"

    def test_safe_str_empty_string(self):
        assert _nexa_tpl_safe_str("") == ""

    def test_safe_str_float(self):
        assert _nexa_tpl_safe_str(3.14) == "3.14"


class TestFilters:
    def test_upper(self):
        assert filter_upper("hello") == "HELLO"

    def test_uppercase(self):
        assert filter_uppercase("hello") == "HELLO"

    def test_lower(self):
        assert filter_lower("HELLO") == "hello"

    def test_lowercase(self):
        assert filter_lowercase("HELLO") == "hello"

    def test_capitalize(self):
        assert filter_capitalize("hello world") == "Hello world"

    def test_capitalize_already_cap(self):
        assert filter_capitalize("Hello") == "Hello"

    def test_capitalize_empty(self):
        assert filter_capitalize("") == ""

    def test_trim(self):
        assert filter_trim("  hello  ") == "hello"

    def test_trim_tabs(self):
        assert filter_trim("\thello\t") == "hello"

    def test_truncate_default(self):
        assert filter_truncate("Hello World") == "Hello World"

    def test_truncate_custom_length(self):
        assert filter_truncate("Hello World", 5) == "Hello..."

    def test_truncate_short_string(self):
        assert filter_truncate("Hi", 10) == "Hi"

    def test_truncate_exact_length(self):
        assert filter_truncate("Hello", 5) == "Hello"

    def test_replace_basic(self):
        assert filter_replace("hello world", "world", "earth") == "hello earth"

    def test_replace_multiple(self):
        assert filter_replace("aaa", "a", "b") == "bbb"

    def test_escape_explicit(self):
        r = filter_escape("<b>bold</b>")
        assert r == "&lt;b&gt;bold&lt;/b&gt;"

    def test_raw_no_escape(self):
        assert filter_raw("<b>bold</b>") == "<b>bold</b>"

    def test_safe_no_escape(self):
        assert filter_safe("<b>bold</b>") == "<b>bold</b>"

    def test_default_with_value(self):
        assert filter_default("hello", "fallback") == "hello"

    def test_default_with_none(self):
        assert filter_default(None, "fallback") == "fallback"

    def test_default_with_empty_string(self):
        assert filter_default("", "fallback") == "fallback"

    def test_default_with_zero(self):
        assert filter_default(0, "fallback") == "0"

    def test_length_string(self):
        assert filter_length("hello") == "5"

    def test_length_list(self):
        assert filter_length([1, 2, 3]) == "3"

    def test_length_dict(self):
        assert filter_length({"a": 1, "b": 2}) == "2"

    def test_length_empty(self):
        assert filter_length("") == "0"

    def test_first_list(self):
        assert filter_first([1, 2, 3]) == "1"

    def test_first_string(self):
        assert filter_first("hello") == "h"

    def test_first_empty(self):
        assert filter_first([]) == ""

    def test_last_list(self):
        assert filter_last([1, 2, 3]) == "3"

    def test_last_string(self):
        assert filter_last("hello") == "o"

    def test_last_empty(self):
        assert filter_last([]) == ""

    def test_reverse_string(self):
        assert filter_reverse("hello") == "olleh"

    def test_reverse_list(self):
        assert filter_reverse([1, 2, 3]) == "[3, 2, 1]"

    def test_reverse_empty_string(self):
        assert filter_reverse("") == ""

    def test_join_list_default(self):
        assert filter_join(["a", "b", "c"]) == "a,b,c"

    def test_join_with_separator(self):
        assert filter_join(["a", "b", "c"], ", ") == "a, b, c"

    def test_join_empty(self):
        assert filter_join([]) == ""

    def test_slice_string(self):
        assert filter_slice("hello", 1, 3) == "el"

    def test_slice_string_from_start(self):
        assert filter_slice("hello", 0, 2) == "he"

    def test_slice_list(self):
        assert filter_slice([1, 2, 3, 4], 1, 2) == "[2]"

    def test_json_basic(self):
        result = filter_json({"key": "value"})
        assert "key" in result and "value" in result

    def test_json_string(self):
        result = filter_json("hello")
        assert "hello" in result

    def test_number_basic(self):
        assert filter_number(3.14159, 2) == "3.14"

    def test_number_integer(self):
        assert filter_number(42, 0) == "42"

    def test_number_negative(self):
        assert filter_number(-3.14, 1) == "-3.1"

    def test_url_encode(self):
        assert filter_url_encode("hello world") == "hello%20world"

    def test_url_encode_special_chars(self):
        result = filter_url_encode("a=b&c=d")
        assert "a" in result and "%3D" in result

    def test_strip_tags(self):
        assert filter_strip_tags("<b>bold</b> text") == "bold text"

    def test_strip_tags_complex(self):
        assert filter_strip_tags("<div><p>hello</p></div>") == "hello"

    def test_strip_tags_no_tags(self):
        assert filter_strip_tags("plain text") == "plain text"

    def test_word_count(self):
        assert filter_word_count("hello world foo") == "3"

    def test_word_count_single(self):
        assert filter_word_count("hello") == "1"

    def test_word_count_empty(self):
        assert filter_word_count("") == "0"

    def test_line_count(self):
        assert filter_line_count("line1\nline2\nline3") == "3"

    def test_line_count_single(self):
        assert filter_line_count("single line") == "1"

    def test_line_count_empty(self):
        assert filter_line_count("") == "0"

    def test_indent(self):
        assert filter_indent("line1\nline2", 2) == "  line1\n  line2"

    def test_indent_default(self):
        result = filter_indent("line1\nline2")
        assert "line1" in result

    def test_indent_custom_spaces(self):
        assert filter_indent("a\nb", 4) == "    a\n    b"

    def test_date_basic(self):
        result = filter_date(0, "%Y-%m-%d")
        assert isinstance(result, str)

    def test_sort_list(self):
        assert filter_sort([3, 1, 2]) == "[1, 2, 3]"  # json.dumps format

    def test_sort_strings(self):
        assert filter_sort(["c", "a", "b"]) == '["a", "b", "c"]'

    def test_unique_list(self):
        assert filter_unique([1, 2, 2, 3, 3]) == "[1, 2, 3]"

    def test_unique_string_list(self):
        result = filter_unique(["a", "b", "a"])
        assert "a" in result and "b" in result

    def test_unique_already_unique(self):
        assert filter_unique([1, 2, 3]) == "[1, 2, 3]"

    def test_abs_negative(self):
        assert filter_abs(-5) == "5.0"

    def test_abs_positive(self):
        assert filter_abs(5) == "5.0"

    def test_abs_float(self):
        assert filter_abs(-3.14) == "3.14"

    def test_ceil(self):
        assert filter_ceil(3.2) == "4"

    def test_ceil_already_int(self):
        assert filter_ceil(4.0) == "4"

    def test_ceil_negative(self):
        assert filter_ceil(-3.2) == "-3"

    def test_floor(self):
        assert filter_floor(3.8) == "3"

    def test_floor_already_int(self):
        assert filter_floor(3.0) == "3"

    def test_floor_negative(self):
        assert filter_floor(-3.8) == "-4"


class TestFilterRegistry:
    def test_registry_has_30_plus_entries(self):
        assert len(FILTER_REGISTRY) >= 30

    def test_registry_contains_all_required(self):
        required = [
            "upper", "uppercase", "lower", "lowercase", "capitalize",
            "trim", "truncate", "replace", "escape", "raw", "safe",
            "default", "length", "first", "last", "reverse", "join",
            "slice", "json", "number", "url_encode", "strip_tags",
            "word_count", "line_count", "indent", "date",
            "sort", "unique", "abs", "ceil", "floor",
        ]
        for name in required:
            assert name in FILTER_REGISTRY, f"Missing filter: {name}"

    def test_registry_values_callable(self):
        for name, fn in FILTER_REGISTRY.items():
            assert callable(fn), f"Filter {name} is not callable"


class TestApplyFilterChain:
    def test_single_filter(self):
        result = apply_filter_chain("hello", [{"name": "upper", "args": []}])
        assert result == "HELLO"

    def test_chain_two_filters(self):
        result = apply_filter_chain("  hello  ", [
            {"name": "trim", "args": []},
            {"name": "upper", "args": []}
        ])
        assert result == "HELLO"

    def test_chain_with_args(self):
        result = apply_filter_chain("hello world", [{"name": "truncate", "args": [5]}])
        assert result == "hello..."

    def test_chain_default_then_upper(self):
        result = apply_filter_chain(None, [
            {"name": "default", "args": ["fallback"]},
            {"name": "upper", "args": []}
        ])
        assert result == "FALLBACK"

    def test_empty_chain(self):
        result = apply_filter_chain("hello", [])
        assert result == "hello"

    def test_unknown_filter_skipped(self):
        # Unknown filters are silently skipped (error boundary)
        result = apply_filter_chain("hello", [{"name": "nonexistent", "args": []}])
        assert result == "hello"


class TestNexaTemplateParser:
    def setup_method(self):
        self.parser = ASTTemplateParser()

    def test_parse_literal_only(self):
        parts = self.parser.parse_template_content("Hello World")
        assert len(parts) == 1
        assert parts[0].kind == "literal"
        assert parts[0].value == "Hello World"

    def test_parse_simple_expr(self):
        parts = self.parser.parse_template_content("Hello {{name}}!")
        assert len(parts) == 3
        assert parts[0].kind == "literal"
        assert parts[1].kind == "expr"
        assert parts[1].value == "name"
        assert parts[2].kind == "literal"

    def test_parse_raw_expr(self):
        parts = self.parser.parse_template_content("{{{html}}}")
        assert len(parts) == 1
        assert parts[0].kind == "raw_expr"
        assert parts[0].value == "html"
        assert parts[0].raw == True

    def test_parse_filtered_expr(self):
        parts = self.parser.parse_template_content("{{name | upper}}")
        assert len(parts) == 1
        assert parts[0].kind == "filtered_expr"
        assert parts[0].value == "name"
        assert len(parts[0].filters) == 1
        assert parts[0].filters[0].name == "upper"

    def test_parse_raw_filtered_expr(self):
        parts = self.parser.parse_template_content("{{{name | upper}}}")
        assert len(parts) == 1
        assert parts[0].kind == "raw_filtered_expr"
        assert parts[0].raw == True

    def test_parse_filter_chain_multiple(self):
        parts = self.parser.parse_template_content("{{name | trim | upper}}")
        assert len(parts) == 1
        assert len(parts[0].filters) == 2

    def test_parse_filter_with_args(self):
        parts = self.parser.parse_template_content("{{text | truncate(20)}}")
        assert parts[0].filters[0].name == "truncate"

    def test_parse_for_loop(self):
        parts = self.parser.parse_template_content("{{#for item in items}}{{item}}{{/for}}")
        for_loops = [p for p in parts if p.kind == "for_loop"]
        assert len(for_loops) >= 1
        assert for_loops[0].var == "item"
        assert for_loops[0].iterable == "items"

    def test_parse_if_block(self):
        parts = self.parser.parse_template_content("{{#if x > 0}}positive{{/if}}")
        if_blocks = [p for p in parts if p.kind == "if_block"]
        assert len(if_blocks) >= 1

    def test_parse_if_elif_else(self):
        content = "{{#if role == 'admin'}}A{{#elif role == 'mod'}}M{{#else}}U{{/if}}"
        parts = self.parser.parse_template_content(content)
        if_blocks = [p for p in parts if p.kind == "if_block"]
        assert len(if_blocks) >= 1
        assert len(if_blocks[0].elif_chains) >= 1

    def test_parse_partial(self):
        parts = self.parser.parse_template_content("{{> header}}")
        partials = [p for p in parts if p.kind == "partial"]
        assert len(partials) >= 1
        assert partials[0].partial_name == "header"

    def test_parse_partial_with_data(self):
        parts = self.parser.parse_template_content("{{> card user}}")
        partials = [p for p in parts if p.kind == "partial"]
        assert partials[0].partial_name == "card"
        assert partials[0].data_expr == "user"

    def test_parse_empty_string(self):
        parts = self.parser.parse_template_content("")
        assert len(parts) == 0

    def test_parse_multiple_exprs(self):
        parts = self.parser.parse_template_content("{{a}} and {{b}}")
        exprs = [p for p in parts if p.kind in ("expr", "filtered_expr")]
        assert len(exprs) == 2


class TestBasicRendering:
    def test_simple_literal(self):
        assert render_string("Hello World", {}) == "Hello World"

    def test_simple_expr(self):
        assert render_string("Hello {{name}}!", {"name": "World"}) == "Hello World!"

    def test_multiple_exprs(self):
        assert render_string("{{a}} and {{b}}", {"a": "foo", "b": "bar"}) == "foo and bar"

    def test_expr_with_dot_access(self):
        assert render_string("Hello {{user.name}}", {"user": {"name": "Alice"}}) == "Hello Alice"

    def test_expr_missing_var(self):
        assert render_string("Hello {{name}}!", {}) == "Hello !"

    def test_expr_none_var(self):
        assert render_string("Hello {{name}}!", {"name": None}) == "Hello !"

    def test_expr_number(self):
        assert render_string("Age: {{age}}", {"age": 25}) == "Age: 25"

    def test_expr_boolean(self):
        assert render_string("Active: {{active}}", {"active": True}) == "Active: true"

    def test_empty_template(self):
        assert render_string("", {}) == ""

    def test_only_expr(self):
        assert render_string("{{name}}", {"name": "World"}) == "World"

    def test_expr_list(self):
        result = render_string("{{items}}", {"items": [1, 2, 3]})
        assert "[1, 2, 3]" in result


class TestAutoEscape:
    def test_escape_script_tag(self):
        result = render_string("{{content}}", {"content": "<script>alert(1)</script>"})
        assert "&lt;script&gt;" in result

    def test_escape_ampersand(self):
        result = render_string("{{text}}", {"text": "a & b"})
        assert "&" in result

    def test_escape_double_quotes(self):
        result = render_string("{{text}}", {"text": '"hello"'})
        assert chr(38)+chr(113)+chr(117)+chr(111)+chr(116)+chr(59) in result

    def test_escape_angle_brackets(self):
        result = render_string("{{text}}", {"text": "<b>bold</b>"})
        assert "&lt;" in result and "&gt;" in result

    def test_no_escape_for_safe_text(self):
        assert render_string("{{text}}", {"text": "Hello World"}) == "Hello World"

    def test_escape_mixed(self):
        result = render_string("{{text}}", {"text": "<a href='x'>link</a>"})
        assert "&lt;" in result


class TestRawExpr:
    def test_raw_html(self):
        assert render_string("{{{html}}}", {"html": "<b>bold</b>"}) == "<b>bold</b>"

    def test_raw_script(self):
        result = render_string("{{{content}}}", {"content": "<script>alert(1)</script>"})
        assert "<script>" in result

    def test_raw_mixed_with_escaped(self):
        result = render_string("Escaped: {{html}}, Raw: {{{html}}}", {"html": "<b>bold</b>"})
        assert "<" in result and "<b>bold</b>" in result

    def test_raw_number(self):
        assert render_string("{{{num}}}", {"num": 42}) == "42"

    def test_raw_none(self):
        assert render_string("{{{val}}}", {"val": None}) == ""


class TestFilterChainRendering:
    def test_single_filter_trim(self):
        assert render_string("{{name | trim}}", {"name": "  hello  "}) == "hello"

    def test_single_filter_upper(self):
        assert render_string("{{name | upper}}", {"name": "hello"}) == "HELLO"

    def test_chain_trim_upper(self):
        assert render_string("{{name | trim | upper}}", {"name": "  hello  "}) == "HELLO"

    def test_filter_default_with_arg(self):
        assert render_string("{{name | default(fallback)}}", {"name": None}) == "fallback"

    def test_filter_default_with_value(self):
        assert render_string("{{name | default(fallback)}}", {"name": "hello"}) == "hello"

    def test_filter_length(self):
        assert render_string("{{text | length}}", {"text": "hello"}) == "5"

    def test_raw_filtered_expr(self):
        assert render_string("{{{html | raw}}}", {"html": "<b>bold</b>"}) == "<b>bold</b>"

    def test_filter_lower(self):
        assert render_string("{{name | lower}}", {"name": "HELLO"}) == "hello"

    def test_filter_capitalize(self):
        assert render_string("{{name | capitalize}}", {"name": "hello world"}) == "Hello world"


class TestForLoop:
    def test_simple_for_loop(self):
        result = render_string("{{#for item in items}}{{item}}{{/for}}", {"items": ["a", "b", "c"]})
        assert "abc" in result.replace(",", "").replace(" ", "")

    def test_for_loop_empty_list(self):
        result = render_string("{{#for item in items}}{{item}}{{/for}}", {"items": []})
        assert result == ""

    def test_for_loop_none_list(self):
        result = render_string("{{#for item in items}}{{item}}{{/for}}", {"items": None})
        assert result == ""

    def test_for_loop_with_literal_text(self):
        result = render_string("{{#for x in nums}}Num:{{x}} {{/for}}", {"nums": [1, 2, 3]})
        assert "Num:" in result

    def test_for_loop_index_metadata(self):
        result = render_string("{{#for item in items}}{{@index}}{{/for}}", {"items": ["a", "b", "c"]})
        assert "0" in result and "1" in result and "2" in result

    def test_for_loop_index1_metadata(self):
        result = render_string("{{#for item in items}}{{@index1}}{{/for}}", {"items": ["a", "b", "c"]})
        assert "1" in result and "2" in result and "3" in result

    def test_for_loop_nested_expr(self):
        result = render_string("{{#for item in items}}{{item.name}}{{/for}}",
                               {"items": [{"name": "A"}, {"name": "B"}]})
        assert "AB" in result.replace(",", "").replace(" ", "")

    def test_for_loop_with_empty_body(self):
        result = render_string("{{#for item in items}}yes{{#empty}}no{{/for}}", {"items": []})
        assert "no" in result

    def test_for_loop_with_empty_body_nonempty(self):
        result = render_string("{{#for item in items}}yes{{#empty}}no{{/for}}", {"items": ["a"]})
        assert "yes" in result

    def test_for_loop_first_metadata(self):
        result = render_string("{{#for item in items}}{{@first}}{{/for}}", {"items": ["a", "b"]})
        assert "true" in result.lower() or "True" in result


class TestIfBlock:
    def test_simple_if_true(self):
        result = render_string("{{#if x > 0}}positive{{/if}}", {"x": 5})
        assert "positive" in result

    def test_simple_if_false(self):
        result = render_string("{{#if x > 0}}positive{{/if}}", {"x": -1})
        assert "positive" not in result or result.strip() == ""

    def test_if_else_true(self):
        result = render_string("{{#if x > 0}}pos{{#else}}neg{{/if}}", {"x": 5})
        assert "pos" in result

    def test_if_else_false(self):
        result = render_string("{{#if x > 0}}pos{{#else}}neg{{/if}}", {"x": -1})
        assert "neg" in result

    def test_if_elif_else_first_match(self):
        content = "{{#if role == 'admin'}}A{{#elif role == 'mod'}}M{{#else}}U{{/if}}"
        result = render_string(content, {"role": "admin"})
        assert "A" in result

    def test_if_elif_else_second_match(self):
        content = "{{#if role == 'admin'}}A{{#elif role == 'mod'}}M{{#else}}U{{/if}}"
        result = render_string(content, {"role": "mod"})
        assert "M" in result

    def test_if_elif_else_no_match(self):
        content = "{{#if role == 'admin'}}A{{#elif role == 'mod'}}M{{#else}}U{{/if}}"
        result = render_string(content, {"role": "user"})
        assert "U" in result

    def test_if_truthy_value(self):
        result = render_string("{{#if x}}exists{{/if}}", {"x": "hello"})
        assert "exists" in result


class TestPartial:
    def test_partial_parsing(self):
        parser = ASTTemplateParser()
        parts = parser.parse_template_content("{{> header}}")
        partials = [p for p in parts if p.kind == "partial"]
        assert len(partials) >= 1
        assert partials[0].partial_name == "header"

    def test_partial_with_data_expr(self):
        parser = ASTTemplateParser()
        parts = parser.parse_template_content("{{> card user}}")
        partials = [p for p in parts if p.kind == "partial"]
        assert partials[0].partial_name == "card"
        assert partials[0].data_expr == "user"


class TestCompiledTemplate:
    def test_create(self):
        ct = CompiledTemplate(path="/tmp/test.html", parts=[], mtime=0)
        assert ct.path == "/tmp/test.html"
        assert ct.mtime == 0

    def test_to_dict(self):
        ct = CompiledTemplate(path="/tmp/test.html", parts=[], mtime=0)
        ct.id = 42
        d = ct.to_dict()
        assert d["_nexa_template_id"] == 42
        assert d["path"] == "/tmp/test.html"

    def test_is_stale_nonexistent(self):
        ct = CompiledTemplate(path="/nonexistent/file.html", parts=[], mtime=0)
        assert ct.is_stale() == False

    def test_is_stale_existing_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write("test")
            path = f.name
        mtime = os.path.getmtime(path)
        ct = CompiledTemplate(path=path, parts=[], mtime=mtime)
        assert ct.is_stale() == False
        time.sleep(0.1)
        with open(path, 'w') as f:
            f.write("modified")
        assert ct.is_stale() == True
        os.unlink(path)


class TestGlobalRegistry:
    def test_get_active_templates(self):
        result = get_active_templates()
        assert isinstance(result, dict)

    def test_register_and_get(self):
        from src.runtime.template import _register_template, _get_template
        ct = CompiledTemplate(path="/test/path.html", parts=[], mtime=0)
        ct.id = 7777
        _register_template(7777, ct)
        retrieved = _get_template(7777)
        assert retrieved is not None
        assert retrieved.path == "/test/path.html"

    def test_unregister(self):
        from src.runtime.template import _unregister_template, _get_template
        _unregister_template(7777)
        assert _get_template(7777) is None


class TestAgentNative:
    def test_agent_template_register(self):
        result = agent_template_register("test_bot_a", "greeting", "Hello {{name}}!")
        assert result is not None

    def test_agent_template_prompt(self):
        agent_info = {"name": "HelperBot", "description": "A helpful assistant"}
        result = agent_template_prompt(agent_info, "You are {{agent_name}}, {{agent_desc}}")
        assert "HelperBot" in result
        assert "helpful assistant" in result

    def test_agent_template_slot_fill(self):
        agent = {"name": "Alice", "role": "admin"}
        result = agent_template_slot_fill(agent, "Welcome {{agent_name}} as {{agent_desc}}")
        assert "Alice" in result
        assert "admin" in result


class TestContractViolation:
    def test_render_invalid_path(self):
        with pytest.raises(ContractViolation):
            template("/nonexistent/path.html", {})

    def test_compile_invalid_path(self):
        with pytest.raises(ContractViolation):
            compile_template("/nonexistent/path.html")

    def test_render_invalid_handle(self):
        with pytest.raises(ContractViolation):
            render({"invalid": True}, {})

    def test_render_with_valid_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write("Hello {{name}}!")
            path = f.name
        try:
            compiled = compile_template(path)
            result = render(compiled, {"name": "World"})
            assert "Hello" in result and "World" in result
        finally:
            os.unlink(path)


class TestNexaTemplateRendererDirect:
    def setup_method(self):
        self.renderer = NexaTemplateRenderer()

    def test_render_parts_basic(self):
        parts = [
            {"kind": "literal", "value": "Hello ", "filters": [], "raw": False},
            {"kind": "expr", "value": "name", "filters": [], "raw": False},
        ]
        assert self.renderer.render_parts(parts, {"name": "World"}) == "Hello World"

    def test_render_parts_raw(self):
        parts = [{"kind": "raw_expr", "value": "html", "filters": [], "raw": True}]
        assert self.renderer.render_parts(parts, {"html": "<b>bold</b>"}) == "<b>bold</b>"

    def test_render_parts_with_filter(self):
        parts = [{"kind": "filtered_expr", "value": "name", "filters": [{"name": "upper", "args": []}], "raw": False}]
        assert self.renderer.render_parts(parts, {"name": "hello"}) == "HELLO"

    def test_render_parts_escaped(self):
        parts = [{"kind": "expr", "value": "html", "filters": [], "raw": False}]
        result = self.renderer.render_parts(parts, {"html": "<b>bold</b>"})
        assert "&lt;" in result

    def test_resolve_var_simple(self):
        assert self.renderer._resolve_var("name", {"name": "Alice"}) == "Alice"

    def test_resolve_var_dot_access(self):
        assert self.renderer._resolve_var("user.name", {"user": {"name": "Alice"}}) == "Alice"

    def test_resolve_var_missing(self):
        assert self.renderer._resolve_var("missing", {}) is None

    def test_resolve_var_nested_dict(self):
        assert self.renderer._resolve_var("config.db.host", {"config": {"db": {"host": "localhost"}}}) == "localhost"


class TestTemplatePartDataclass:
    def test_create_literal(self):
        part = TemplatePart(kind="literal", value="Hello")
        assert part.kind == "literal"
        assert part.value == "Hello"

    def test_create_expr(self):
        part = TemplatePart(kind="expr", value="name")
        assert part.kind == "expr"

    def test_to_dict_literal(self):
        d = TemplatePart(kind="literal", value="Hello").to_dict()
        assert d["kind"] == "literal"
        assert d["value"] == "Hello"

    def test_to_dict_with_filters(self):
        part = TemplatePart(kind="filtered_expr", value="name",
                           filters=[TemplateFilter(name="upper", args=[])])
        d = part.to_dict()
        assert d["kind"] == "filtered_expr"
        assert len(d["filters"]) == 1

    def test_default_values(self):
        part = TemplatePart()
        assert part.kind == "literal"
        assert part.raw == False


class TestTemplateFilterDataclass:
    def test_create_no_args(self):
        f = TemplateFilter(name="upper")
        assert f.name == "upper"
        assert f.args == []

    def test_create_with_args(self):
        f = TemplateFilter(name="truncate", args=["20"])
        assert f.name == "truncate"

    def test_default_factory(self):
        f1 = TemplateFilter(name="upper")
        f2 = TemplateFilter(name="lower")
        assert f1.args is not f2.args


class TestEdgeCases:
    def test_adjacent_exprs(self):
        assert render_string("{{a}}{{b}}", {"a": "foo", "b": "bar"}) == "foobar"

    def test_expr_at_start(self):
        assert render_string("{{name}} World", {"name": "Hello"}) == "Hello World"

    def test_expr_at_end(self):
        assert render_string("Hello {{name}}", {"name": "World"}) == "Hello World"

    def test_deep_dot_access(self):
        assert render_string("{{a.b.c}}", {"a": {"b": {"c": "deep"}}}) == "deep"

    def test_unicode_content(self):
        assert render_string("{{name}}", {"name": "你好世界"}) == "你好世界"

    def test_empty_data_dict(self):
        assert render_string("No vars here", {}) == "No vars here"

    def test_single_braces_not_interpreted(self):
        assert render_string("{not a template}", {}) == "{not a template}"

    def test_triple_braces_raw(self):
        assert render_string("{{{x}}}", {"x": "raw"}) == "raw"