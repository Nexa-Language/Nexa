from __future__ import annotations
import lark
from lark import Transformer, v_args
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

# ===== P3-1: String Interpolation — interpolation expression validation pattern =====
_INTERP_EXPR_PATTERN = re.compile(
    r'^[a-zA-Z_][a-zA-Z0-9_]*'
    r'(\.[a-zA-Z_][a-zA-Z0-9_]*'
    r'|\[\d+\]'
    r'|\[[a-zA-Z_][a-zA-Z0-9_]*\]'
    r')*$'
)

# ===== P2-4: Template System Data Classes =====

@dataclass
class TemplateFilter:
    'Template filter definition: name + args'
    name: str
    args: List[Any] = field(default_factory=list)

@dataclass
class TemplatePart:
    'Template part definition: one of literal/expr/raw_expr/filtered_expr/raw_filtered_expr/for_loop/if_block/partial'
    kind: str = 'literal'
    value: str = ''
    filters: List[TemplateFilter] = field(default_factory=list)
    raw: bool = False
    var: str = ''
    iterable: str = ''
    body: List[TemplatePart] = field(default_factory=list)
    empty_body: List[TemplatePart] = field(default_factory=list)
    condition: str = ''
    elif_chains: List[Dict] = field(default_factory=list)
    else_parts: List[TemplatePart] = field(default_factory=list)
    partial_name: str = ''
    data_expr: str = ''

    @staticmethod
    def _part_to_dict(p) -> Dict:
        'Helper: convert TemplatePart or dict to dict'
        if hasattr(p, 'to_dict'):
            return p.to_dict()
        elif isinstance(p, dict):
            return p
        else:
            return {'kind': 'literal', 'value': str(p) if p is not None else '', 'raw': False}

    def to_dict(self) -> Dict:
        'Convert TemplatePart to dict for AST serialization'
        d = {'kind': self.kind, 'value': self.value, 'raw': self.raw}
        if self.filters:
            d['filters'] = [{'name': f.name, 'args': f.args} for f in self.filters]
        if self.var:
            d['var'] = self.var
        if self.iterable:
            d['iterable'] = self.iterable
        if self.body:
            d['body'] = [TemplatePart._part_to_dict(p) for p in self.body]
        if self.empty_body:
            d['empty_body'] = [TemplatePart._part_to_dict(p) for p in self.empty_body]
        if self.condition:
            d['condition'] = self.condition
        if self.elif_chains:
            d['elif_chains'] = [
                {'condition': c.get('condition', '') if isinstance(c, dict) else c.condition,
                 'parts': [TemplatePart._part_to_dict(p) for p in (c.get('parts', []) if isinstance(c, dict) else c.parts)]}
                for c in self.elif_chains
            ]
        if self.else_parts:
            d['else_parts'] = [TemplatePart._part_to_dict(p) for p in self.else_parts]
        if self.partial_name:
            d['partial_name'] = self.partial_name
        if self.data_expr:
            d['data_expr'] = self.data_expr
        return d


class NexaTemplateParser:
    'Parses template content string into TemplatePart list'

    def parse_template_content(self, content: str) -> List[TemplatePart]:
        'Parse template content into list of TemplatePart objects'
        parts, _ = self._parse_content(content, 0, len(content))
        return parts

    def _parse_content(self, content: str, start: int, end: int) -> Tuple[List[TemplatePart], int]:
        'Recursively parse content from start to end'
        parts = []
        pos = start
        literal_buf = []

        while pos < end:
            # Check for escaped braces
            if pos < end - 1 and content[pos] == '\\' and content[pos + 1] in ('{', '}'):
                literal_buf.append(content[pos + 1])
                pos += 2
                continue

            # Check for {{{ (raw expression)
            if pos < end - 2 and content[pos:pos + 3] == '{{{':
                if literal_buf:
                    parts.append(TemplatePart(kind='literal', value=''.join(literal_buf)))
                    literal_buf = []

                close_pos = self._find_closing_braces(content, pos + 3, '}}}')
                if close_pos == -1:
                    literal_buf.append(content[pos:pos + 3])
                    pos += 3
                    continue

                inner = content[pos + 3:close_pos].strip()
                if '|' in inner:
                    base_expr, filters = self._parse_filter_chain(inner)
                    parts.append(TemplatePart(kind='raw_filtered_expr', value=base_expr, filters=filters, raw=True))
                else:
                    parts.append(TemplatePart(kind='raw_expr', value=inner, raw=True))
                pos = close_pos + 3
                continue

            # Check for {{ (expression or control structure)
            if pos < end - 1 and content[pos:pos + 2] == '{{':
                if literal_buf:
                    parts.append(TemplatePart(kind='literal', value=''.join(literal_buf)))
                    literal_buf = []

                remaining = content[pos + 2:]

                if remaining.startswith('#for'):
                    close_pos = self._find_closing_braces(content, pos + 6, '}}')
                    if close_pos == -1:
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    for_header = content[pos + 6:close_pos].strip()
                    for_match = self._parse_for_header(for_header)
                    if for_match:
                        var_name, iterable_name = for_match
                        body_end = self._find_matching_end(content, close_pos + 2, '{{#for', '{{/for')
                        if body_end == -1:
                            pos = close_pos + 2
                            continue

                        body_start = close_pos + 2
                        body_content_end = body_end

                        # Check for {{#empty}} within body
                        empty_start = -1
                        search_pos = body_start
                        while search_pos < body_content_end:
                            emp_idx = content.find('{{#empty}}', search_pos, body_content_end)
                            if emp_idx == -1:
                                break
                            empty_start = emp_idx + 9
                            break

                        if empty_start != -1:
                            body_parts, _ = self._parse_content(content, body_start, empty_start - 9)
                            empty_parts, _ = self._parse_content(content, empty_start, body_content_end)
                        else:
                            body_parts, _ = self._parse_content(content, body_start, body_content_end)
                            empty_parts = []

                        parts.append(TemplatePart(
                            kind='for_loop', var=var_name, iterable=iterable_name,
                            body=body_parts, empty_body=empty_parts
                        ))

                        end_close = content.find('}}', body_end)
                        if end_close != -1:
                            pos = end_close + 2
                        else:
                            pos = body_content_end + 9
                        continue

                elif remaining.startswith('#if'):
                    close_pos = self._find_closing_braces(content, pos + 5, '}}')
                    if close_pos == -1:
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    condition = content[pos + 5:close_pos].strip()
                    result = self._parse_if_block_content(content, close_pos + 2)
                    if result:
                        then_parts, elif_chains, else_parts, end_pos = result
                        # Convert elif_chains dicts to proper format
                        elif_chain_parts = []
                        for ec in elif_chains:
                            elif_chain_parts.append({
                                'condition': ec.get('condition', ''),
                                'parts': ec.get('parts', [])
                            })
                        parts.append(TemplatePart(
                            kind='if_block', condition=condition,
                            body=then_parts, elif_chains=elif_chain_parts, else_parts=else_parts
                        ))
                        pos = end_pos
                        continue
                    else:
                        pos = close_pos + 2
                        continue

                elif remaining.startswith('#elif') or remaining.startswith('#else') or remaining.startswith('/for') or remaining.startswith('/if'):
                    if literal_buf:
                        parts.append(TemplatePart(kind='literal', value=''.join(literal_buf)))
                        literal_buf = []
                    return parts, pos

                elif remaining.startswith('>'):
                    close_pos = self._find_closing_braces(content, pos + 4, '}}')
                    if close_pos == -1:
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    inner = content[pos + 4:close_pos].strip()
                    partial_name, data_expr = self._parse_partial(inner)
                    parts.append(TemplatePart(kind='partial', partial_name=partial_name, data_expr=data_expr))
                    pos = close_pos + 2
                    continue

                else:
                    close_pos = self._find_closing_braces(content, pos + 2, '}}')
                    if close_pos == -1:
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    if close_pos < end and content[close_pos] == '{':
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    inner = content[pos + 2:close_pos].strip()
                    if '|' in inner:
                        base_expr, filters = self._parse_filter_chain(inner)
                        parts.append(TemplatePart(kind='filtered_expr', value=base_expr, filters=filters))
                    else:
                        parts.append(TemplatePart(kind='expr', value=inner))
                    pos = close_pos + 2
                    continue

            literal_buf.append(content[pos])
            pos += 1

        if literal_buf:
            parts.append(TemplatePart(kind='literal', value=''.join(literal_buf)))

        return parts, pos

    def _find_closing_braces(self, content: str, start: int, closing: str) -> int:
        'Find closing braces position from start'
        pos = start
        while pos < len(content):
            idx = content.find(closing, pos)
            if idx == -1:
                return -1
            if closing == '}}' and idx > 0 and content[idx - 1] == '{':
                pos = idx + 2
                continue
            return idx
        return -1

    def _find_matching_end(self, content: str, start: int, open_tag: str, close_tag: str) -> int:
        'Find matching close tag accounting for nesting'
        depth = 1
        pos = start

        while pos < len(content) and depth > 0:
            next_brace = content.find('{{', pos)
            if next_brace == -1:
                return -1

            after = content[next_brace + 2:]

            if after.startswith('#for') or after.startswith('#if'):
                depth += 1
                pos = next_brace + 2
                close_idx = content.find('}}', pos)
                if close_idx == -1:
                    return -1
                pos = close_idx + 2
                continue

            elif after.startswith('/for') and close_tag == '{{/for':
                depth -= 1
                if depth == 0:
                    return next_brace
                pos = next_brace + 7
                close_idx = content.find('}}', pos)
                if close_idx == -1:
                    return -1
                pos = close_idx + 2
                continue

            elif after.startswith('/if') and close_tag == '{{/if':
                depth -= 1
                if depth == 0:
                    return next_brace
                pos = next_brace + 5
                close_idx = content.find('}}', pos)
                if close_idx == -1:
                    return -1
                pos = close_idx + 2
                continue

            else:
                close_idx = content.find('}}', next_brace + 2)
                if close_idx == -1:
                    return -1
                pos = close_idx + 2
                continue

        return -1

    def _parse_if_block_content(self, content: str, start: int) -> Optional[Tuple]:
        'Parse if block content including elif chains and else'
        from src.runtime.template import TemplateContentParser
        # Delegate to the standalone parser's if-block logic
        standalone = TemplateContentParser()
        return standalone._parse_if_block_content(content, start)

    def _parse_for_header(self, header: str) -> Optional[Tuple[str, str]]:
        'Parse for-loop header: var in iterable'
        parts = header.split(' in ')
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return None

    def _parse_filter_chain(self, expr_str: str) -> Tuple[str, List[TemplateFilter]]:
        'Parse filter chain: expr | filter1 | filter2(arg)'
        parts = expr_str.split('|')
        base_expr = parts[0].strip()
        filters = []

        for f_part in parts[1:]:
            f_str = f_part.strip()
            arg_match = re.match(r'(\w+)\(([^)]*)\)', f_str)
            if arg_match:
                fname = arg_match.group(1)
                raw_args = arg_match.group(2)
                args = [a.strip().strip("'\"") for a in raw_args.split(',')]
                parsed_args = []
                for a in args:
                    try:
                        parsed_args.append(int(a))
                    except ValueError:
                        try:
                            parsed_args.append(float(a))
                        except ValueError:
                            parsed_args.append(a)
                filters.append(TemplateFilter(name=fname, args=parsed_args))
            else:
                filters.append(TemplateFilter(name=f_str))

        return base_expr, filters

    def _parse_partial(self, inner: str) -> Tuple[str, str]:
        'Parse partial reference: name or name data_expr'
        parts = inner.split(None, 1)
        if len(parts) == 1:
            return parts[0], ''
        return parts[0], parts[1]


class NexaTransformer(Transformer):
    """
    负责将 Lark 解析后生成的树结构（Tree）转化为
    Nexa 原生的轻量级 JSON / Dict 抽象语法树（AST）
    """
    
    # Nexa keywords that must never be parsed as identifiers
    _NEXA_KEYWORDS = frozenset({
        'defer', 'if', 'else', 'for', 'each', 'in', 'while', 'break', 'continue',
        'agent', 'tool', 'flow', 'protocol', 'test', 'match', 'loop', 'until',
        'print', 'try', 'catch', 'assert', 'true', 'false', 'join', 'std', 'img',
        'requires', 'ensures', 'invariant', 'type', 'unit',
        'otherwise', 'job', 'on', 'perform', 'on_failure', 'server', 'group',
        'route', 'serve', 'static', 'cors', 'semantic',
        'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS',
        'db', 'connect', 'query', 'execute',
        'auth', 'require_auth', 'enable_auth', 'oauth',
        'kv', 'open',
        'spawn', 'parallel', 'race', 'channel', 'after', 'schedule', 'await',
        'select', 'recv', 'send', 'close', 'sleep_ms',
        'template', 'let',
        'struct', 'enum', 'trait', 'impl', 'fn',
    })

    @staticmethod
    def _score_ast_node(node):
        'Score an AST node for _ambig resolution. Higher score = preferred alternative.'
        if not isinstance(node, dict):
            return 0
        node_type = node.get('type', '')

        # Heavy penalty: keyword misparsed as identifier
        if node_type == 'Identifier' and node.get('value', '') in NexaTransformer._NEXA_KEYWORDS:
            return -1000

        # Recurse into wrapper statement types to find inner expression score
        if node_type == 'ExpressionStatement':
            return NexaTransformer._score_ast_node(node.get('expression', {}))
        if node_type == 'AssignmentStatement':
            return NexaTransformer._score_ast_node(node.get('value', {})) + 5
        if node_type == 'DeferStatement':
            return 100

        # Penalty: keyword used as function name (e.g., defer(x) parsed instead of defer_stmt)
        if node_type == 'FunctionCallExpression':
            func = node.get('function', '')
            if isinstance(func, str) and func in NexaTransformer._NEXA_KEYWORDS:
                return -500
            args = node.get('arguments', [])
            has_nested = any(
                isinstance(a, dict) and a.get('type') in ('FunctionCallExpression', 'MethodCallExpression', 'StdCallExpression')
                for a in args
            )
            base = 50 if has_nested else 5
            return base + sum(NexaTransformer._score_ast_node(a) for a in args if isinstance(a, dict))

        if node_type == 'NullCoalesceExpression':
            parts = node.get('parts', [])
            flat_count = sum(1 for p in parts if isinstance(p, dict) and p.get('type') != 'NullCoalesceExpression')
            return 20 + flat_count * 5 + sum(NexaTransformer._score_ast_node(p) for p in parts if isinstance(p, dict))

        if node_type == 'FallbackExpr':
            return 30  # Prefer FallbackExpr over MethodCallExpression in ambiguous parses

        # P3-3: Pattern matching preference — MatchExpression > MatchIntentStatement
        if node_type == 'MatchExpression':
            return 50
        if node_type == 'MatchArm':
            return 45
        if node_type == 'Pattern':
            kind = node.get('kind', '')
            if kind == 'wildcard':
                return 40
            elif kind == 'literal':
                return 38  # Literal > variable so true/false resolve as literal, not variable
            elif kind == 'variable':
                return 35
            elif kind == 'tuple':
                return 25
            elif kind == 'array':
                return 25
            elif kind == 'map':
                return 25
            elif kind == 'variant':
                return 25
            return 20

        # Penalize MatchIntentStatement when MatchExpression is available
        if node_type == 'MatchIntentStatement':
            return -50  # Prefer MatchExpression over old intent matching

        if node_type == 'LetPatternStatement':
            return 50
        if node_type == 'ForPatternStatement':
            return 50

        # P3-4: ADT declarations — high score so struct/enum/trait/impl are preferred over generic expressions
        if node_type == 'StructDeclaration':
            return 60
        if node_type == 'EnumDeclaration':
            return 60
        if node_type == 'TraitDeclaration':
            return 60
        if node_type == 'ImplDeclaration':
            return 60
        if node_type == 'VariantCallExpression':
            return 55  # Variant call > generic identifier/function call
        if node_type == 'FieldInitExpression':
            return 45

        return 1

    def _ambig(self, args):
        'Handle ambiguous parse trees - intelligently select the best alternative'
        # 1. Check for builtin type preferences (existing logic)
        builtin_types = ['str_type', 'int_type', 'float_type', 'bool_type', 'list_type', 'dict_type']
        for child in args:
            if hasattr(child, 'data') and child.data in builtin_types:
                return getattr(self, child.data)(child.children)

        # 2. For already-transformed alternatives (dicts/lists), use scoring
        if all(not hasattr(a, 'data') for a in args):
            scores = []
            for alt in args:
                if isinstance(alt, list):
                    scores.append(sum(NexaTransformer._score_ast_node(item) for item in alt))
                elif isinstance(alt, dict):
                    scores.append(NexaTransformer._score_ast_node(alt))
                else:
                    scores.append(0)
            best_idx = max(range(len(scores)), key=lambda i: scores[i])
            return args[best_idx]

        # 3. For Lark Tree alternatives, prefer specific keyword rules over generic ones
        # Order matters: literal_true_pat/literal_false_pat must come before variable_pat
        # so that 'true'/'false' resolve as literal patterns, not variable patterns
        preferred_rules = ['defer_stmt', 'pipe_chain_expr', 'null_coalesce_expr',
                           'traditional_if_stmt', 'foreach_stmt', 'while_stmt',
                           'try_catch_stmt', 'assignment_stmt',
                           'match_expr', 'wildcard_pat',
                           'literal_true_pat', 'literal_false_pat',
                           'literal_int_pat', 'literal_float_pat', 'literal_str_pat',
                           'variable_pat',
                           'tuple_pat', 'array_pat', 'array_pat_rest', 'map_pat', 'map_pat_rest', 'variant_pat',
                           'let_pattern_stmt', 'for_pattern_stmt']
        for child in args:
            if hasattr(child, 'data') and child.data in preferred_rules:
                return getattr(self, child.data)(child.children)

        # 4. Default: first alternative
        first = args[0]
        if hasattr(first, 'data'):
            return getattr(self, first.data)(first.children)
        return first
    
    @v_args(inline=False)
    def import_stmt(self, args):
        return {"type": "IncludeStatement", "path": str(args[0]).strip('"')}

    @v_args(inline=False)
    def fallback_expr(self, args):
        primary = args[0]
        backup = args[1]
        
        if hasattr(primary, 'data'):
            primary = getattr(self, primary.data)(primary.children)
            
        if hasattr(backup, 'data'):
            backup = getattr(self, backup.data)(backup.children)

        return {"type": "FallbackExpr", "primary": primary, "backup": backup}
            
    @v_args(inline=False)
    def img_call(self, args):
        return {"type": "ImgCall", "path": args[0].value.strip('"')}

    @v_args(inline=False)
    def program(self, args):
        includes = []
        body = []
        for arg in args:
            if isinstance(arg, dict) and arg.get("type") == "IncludeStatement":
                includes.append(arg)
            else:
                body.append(arg)
        return {"type": "Program", "includes": includes, "body": body}

    @v_args(inline=False)
    def tool_decl(self, args):
        name = str(args[0])
        body_args = args[1]
        # Handle different tool body types
        if isinstance(body_args, dict):
            if body_args.get("type") == "mcp":
                return {
                    "type": "ToolDeclaration",
                    "name": name,
                    "mcp": body_args.get("mcp")
                }
            elif body_args.get("type") == "python":
                return {
                    "type": "ToolDeclaration",
                    "name": name,
                    "python": body_args.get("python")
                }
            else:
                return {
                    "type": "ToolDeclaration",
                    "name": name,
                    "description": body_args.get("description", ""),
                    "parameters": body_args.get("parameters", {})
                }
        return {
            "type": "ToolDeclaration",
            "name": name,
            "description": body_args.get("description", ""),
            "parameters": body_args.get("parameters", {})
        }

    @v_args(inline=False)
    def tool_body(self, args):
        # Handle different tool_body types - this is a passthrough
        if args and isinstance(args[0], dict):
            return args[0]
        # Legacy format
        if len(args) >= 2:
            return {
                "description": str(args[0]).strip('"'),
                "parameters": args[1]
            }
        return {"description": "", "parameters": {}}

    @v_args(inline=False)
    def tool_body_standard(self, args):
        return {
            "description": str(args[0]).strip('"'),
            "parameters": args[1]
        }

    @v_args(inline=False)
    def tool_body_mcp(self, args):
        return {
            "type": "mcp",
            "mcp": str(args[0]).strip('"')
        }

    @v_args(inline=False)
    def tool_body_python(self, args):
        return {
            "type": "python",
            "python": str(args[0]).strip('"')
        }

    
    # ===== v1.0.2: Semantic Types =====
    
    @v_args(inline=False)
    def type_decl(self, args):
        """语义类型声明 - v1.0.2"""
        name = str(args[0])
        type_def = args[1] if len(args) > 1 else None
        return {
            "type": "TypeDeclaration",
            "name": name,
            "definition": type_def
        }
    
    @v_args(inline=False)
    def constrained_type(self, args):
        """带约束的语义类型: base_type @ "constraint" """
        base_type = args[0]
        constraint = str(args[1]).strip('"') if len(args) > 1 else ""
        return {
            "type": "SemanticType",
            "base_type": base_type,
            "constraint": constraint
        }
    
    @v_args(inline=False)
    def simple_type(self, args):
        """简单类型（无约束）"""
        return args[0] if args else None
    
    @v_args(inline=False)
    def str_type(self, args):
        return {"type": "BaseType", "name": "str"}
    
    @v_args(inline=False)
    def int_type(self, args):
        return {"type": "BaseType", "name": "int"}
    
    @v_args(inline=False)
    def float_type(self, args):
        return {"type": "BaseType", "name": "float"}
    
    @v_args(inline=False)
    def bool_type(self, args):
        return {"type": "BaseType", "name": "bool"}
    
    # ===== v1.1: 渐进式类型系统 - Type Expression Handlers =====
    
    @v_args(inline=False)
    def type_str_expr(self, args):
        """类型表达式: str"""
        return {"type": "BaseType", "name": "str"}
    
    @v_args(inline=False)
    def type_int_expr(self, args):
        """类型表达式: int"""
        return {"type": "BaseType", "name": "int"}
    
    @v_args(inline=False)
    def type_float_expr(self, args):
        """类型表达式: float"""
        return {"type": "BaseType", "name": "float"}
    
    @v_args(inline=False)
    def type_bool_expr(self, args):
        """类型表达式: bool"""
        return {"type": "BaseType", "name": "bool"}
    
    @v_args(inline=False)
    def type_unit_expr(self, args):
        """类型表达式: unit"""
        return {"type": "BaseType", "name": "unit"}
    
    @v_args(inline=False)
    def type_list_expr(self, args):
        """类型表达式: list[T]"""
        element_type = args[0] if args else {"type": "BaseType", "name": "str"}
        return {
            "type": "GenericType",
            "name": "list",
            "type_params": [element_type]
        }
    
    @v_args(inline=False)
    def type_dict_expr(self, args):
        """类型表达式: dict[K, V]"""
        key_type = args[0] if len(args) > 0 else {"type": "BaseType", "name": "str"}
        value_type = args[1] if len(args) > 1 else {"type": "BaseType", "name": "str"}
        return {
            "type": "GenericType",
            "name": "dict",
            "type_params": [key_type, value_type]
        }
    
    @v_args(inline=False)
    def type_option_generic_expr(self, args):
        """类型表达式: Option[T]"""
        inner = args[0] if args else {"type": "BaseType", "name": "str"}
        return {
            "type": "OptionTypeExpr",
            "inner": inner
        }
    
    @v_args(inline=False)
    def type_option_expr(self, args):
        """类型表达式: T? (简写)"""
        inner = args[0] if args else {"type": "BaseType", "name": "str"}
        return {
            "type": "OptionTypeExpr",
            "inner": inner
        }
    
    @v_args(inline=False)
    def type_result_expr(self, args):
        """类型表达式: Result[T, E]"""
        ok_type = args[0] if args else {"type": "BaseType", "name": "str"}
        err_type = args[1] if len(args) > 1 else {"type": "BaseType", "name": "str"}
        return {
            "type": "ResultTypeExpr",
            "ok_type": ok_type,
            "err_type": err_type
        }
    
    @v_args(inline=False)
    def type_union_expr(self, args):
        """类型表达式: T1 | T2 | T3"""
        types = [arg for arg in args if isinstance(arg, dict)]
        return {
            "type": "UnionTypeExpr",
            "types": types
        }
    
    @v_args(inline=True)
    def type_alias_expr(self, name):
        """类型表达式: 自定义类型别名"""
        return {"type": "CustomType", "name": str(name)}
    
    @v_args(inline=False)
    def list_type(self, args):
        """列表类型: list[Type]"""
        element_type = args[0] if args else {"type": "BaseType", "name": "str"}
        return {
            "type": "GenericType",
            "name": "list",
            "type_params": [element_type]
        }
    
    @v_args(inline=False)
    def dict_type(self, args):
        """字典类型: dict[KeyType, ValueType]"""
        key_type = args[0] if len(args) > 0 else {"type": "BaseType", "name": "str"}
        value_type = args[1] if len(args) > 1 else {"type": "BaseType", "name": "str"}
        return {
            "type": "GenericType",
            "name": "dict",
            "type_params": [key_type, value_type]
        }
    
    @v_args(inline=True)
    def custom_type(self, name):
        """自定义类型引用 - 从 IDENTIFIER 解析"""
        return {"type": "CustomType", "name": str(name)}

    @v_args(inline=False)
    def protocol_decl(self, args):
        name = str(args[0])
        fields = {}
        field_types = {}  # v1.1: 类型表达式信息
        for arg in args[1:]:
            if isinstance(arg, dict) and arg.get("type") == "ProtocolBody":
                fields[arg["key"]] = arg["value"]
                # v1.1: 如果有类型表达式，保存到 field_types
                if "type_expr" in arg:
                    field_types[arg["key"]] = arg["type_expr"]
        return {
            "type": "ProtocolDeclaration",
            "name": name,
            "fields": fields,
            "field_types": field_types  # v1.1: 渐进式类型系统
        }

    @v_args(inline=False)
    def protocol_body_string(self, args):
        """v1.1: 旧格式 protocol body — 字符串标注 (向后兼容)"""
        key = str(args[0])
        value = str(args[1]).strip('"')
        return {
            "type": "ProtocolBody",
            "key": key,
            "value": value
        }

    @v_args(inline=False)
    def protocol_body_typed(self, args):
        """v1.1: 新格式 protocol body — 类型表达式"""
        key = str(args[0])
        type_expr = args[1]  # 已经是 TypeExpr dict
        # 旧格式兼容：value 字段保存类型字符串
        value = type_expr.get("name", type_expr.get("value", "")) if isinstance(type_expr, dict) else str(type_expr)
        if isinstance(type_expr, dict):
            if type_expr.get("type") == "GenericType":
                value = type_expr.get("name", "")
            elif type_expr.get("type") == "BaseType":
                value = type_expr.get("name", "")
            elif type_expr.get("type") == "CustomType":
                value = type_expr.get("name", "")
            elif type_expr.get("type") == "UnionTypeExpr":
                value = " | ".join(t.get("name", t.get("value", "?")) for t in type_expr.get("types", []))
            elif type_expr.get("type") == "OptionTypeExpr":
                value = type_expr.get("inner", {}).get("name", "?") + "?"
            elif type_expr.get("type") == "ResultTypeExpr":
                ok = type_expr.get("ok_type", {}).get("name", "?")
                err = type_expr.get("err_type", {}).get("name", "?")
                value = f"Result[{ok}, {err}]"
        return {
            "type": "ProtocolBody",
            "key": key,
            "value": value,
            "type_expr": type_expr  # v1.1: 完整类型表达式
        }

    @v_args(inline=False)
    def json_object(self, args):
        obj = {}
        for pair in args:
            obj[pair[0]] = pair[1]
        return obj

    @v_args(inline=True)
    def json_pair(self, k, v):
        return (str(k).strip('"'), str(v).strip('"'))

    # ===== P1-3: Background Job System (后台任务系统) =====

    @v_args(inline=False)
    def job_decl(self, args):
        """Job 声明: job SendEmail on emails { perform(user_id) { ... } }"""
        name = str(args[0])
        queue = str(args[1]).strip('"')

        # Parse optional inline options: (retry: 2, timeout: 120)
        inline_options = {}
        for arg in args:
            if isinstance(arg, dict) and arg.get("type") == "JobOptions":
                inline_options = arg.get("options", {})

        # Parse body: config items + perform + optional on_failure
        config_items = {}
        perform_decl = None
        on_failure_decl = None

        for arg in args:
            if isinstance(arg, dict):
                if arg.get("type") == "JobBody":
                    config_items = arg.get("config", {})
                    perform_decl = arg.get("perform")
                    on_failure_decl = arg.get("on_failure")
                elif arg.get("type") == "JobOptions":
                    inline_options = arg.get("options", {})

        # Merge inline options into config
        for key, value in inline_options.items():
            config_items[key] = value

        return {
            "type": "JobDeclaration",
            "name": name,
            "queue": queue,
            "options": inline_options,
            "config": config_items,
            "perform": perform_decl,
            "on_failure": on_failure_decl,
        }

    @v_args(inline=False)
    def job_options(self, args):
        """Job inline options: (retry: 2, timeout: 120, priority: critical)"""
        options = {}
        for arg in args:
            if isinstance(arg, dict) and arg.get("type") == "JobOption":
                options[arg["key"]] = arg["value"]
        return {"type": "JobOptions", "options": options}

    @v_args(inline=False)
    def job_option(self, args):
        """Single job option: retry=2"""
        key = str(args[0])
        value = args[1]
        if isinstance(value, dict):
            value = value.get("value", value.get("name", str(value)))
        return {"type": "JobOption", "key": key, "value": value}

    @v_args(inline=True)
    def job_option_int(self, value):
        return {"type": "JobOptionValue", "value_type": "int", "value": int(value)}

    @v_args(inline=True)
    def job_option_float(self, value):
        return {"type": "JobOptionValue", "value_type": "float", "value": float(value)}

    @v_args(inline=True)
    def job_option_string(self, value):
        return {"type": "JobOptionValue", "value_type": "string", "value": str(value).strip('"')}

    @v_args(inline=True)
    def job_option_id(self, value):
        return {"type": "JobOptionValue", "value_type": "id", "value": str(value), "name": str(value)}

    @v_args(inline=False)
    def job_body(self, args):
        """Job body: config* perform [on_failure]"""
        config = {}
        perform = None
        on_failure = None

        for arg in args:
            if isinstance(arg, dict):
                if arg.get("type") == "JobConfig":
                    config[arg["key"]] = arg["value"]
                elif arg.get("type") == "PerformDecl":
                    perform = arg
                elif arg.get("type") == "OnFailureDecl":
                    on_failure = arg

        return {
            "type": "JobBody",
            "config": config,
            "perform": perform,
            "on_failure": on_failure,
        }

    @v_args(inline=False)
    def job_config(self, args):
        """Job config item: retry: 5"""
        key = str(args[0])
        value = args[1]
        if isinstance(value, dict):
            value = value.get("value", value.get("name", str(value)))
        return {"type": "JobConfig", "key": key, "value": value}

    @v_args(inline=True)
    def job_config_int_value(self, value):
        return {"type": "JobConfigValue", "value_type": "int", "value": int(value)}

    @v_args(inline=True)
    def job_config_float_value(self, value):
        return {"type": "JobConfigValue", "value_type": "float", "value": float(value)}

    @v_args(inline=True)
    def job_config_string_value(self, value):
        return {"type": "JobConfigValue", "value_type": "string", "value": str(value).strip('"')}

    @v_args(inline=True)
    def job_config_id_value(self, value):
        return {"type": "JobConfigValue", "value_type": "id", "value": str(value), "name": str(value)}

    @v_args(inline=False)
    def perform_decl(self, args):
        """Perform declaration: perform(user_id) { ... }"""
        # args may contain param_list and block
        params = []
        body = []

        for arg in args:
            if isinstance(arg, dict):
                if arg.get("type") == "JobParamList":
                    params = arg.get("params", [])
                elif arg.get("type") == "Block":
                    body = arg.get("statements", [])
                elif arg.get("type") == "FlowStmt":
                    body.append(arg)
            elif isinstance(arg, list):
                #可能是语句列表
                body.extend(arg)

        return {
            "type": "PerformDecl",
            "params": params,
            "body": body,
        }

    @v_args(inline=False)
    def job_param_list(self, args):
        """Job parameter list: user_id, amount"""
        params = [str(arg) for arg in args]
        return {"type": "JobParamList", "params": params}

    @v_args(inline=False)
    def on_failure_decl(self, args):
        """On failure declaration: on_failure(error, attempt) { ... }"""
        error_param = str(args[0])
        attempt_param = str(args[1])
        body = []

        for arg in args[2:]:
            if isinstance(arg, dict):
                if arg.get("type") == "Block":
                    body = arg.get("statements", [])
                elif arg.get("type") == "FlowStmt":
                    body.append(arg)
            elif isinstance(arg, list):
                body.extend(arg)

        return {
            "type": "OnFailureDecl",
            "error_param": error_param,
            "attempt_param": attempt_param,
            "body": body,
        }

    # ===== P1-4: Built-In HTTP Server (内置 HTTP 服务器) =====

    @v_args(inline=False)
    def server_decl(self, args):
        """Server 声明: server 8080 { ... }"""
        port = int(args[0])
        
        directives = []
        routes = []
        groups = []
        
        # server_body 包含 directives, routes, groups
        for arg in args[1:]:
            if isinstance(arg, dict):
                if arg.get("type") == "ServerBody":
                    directives = arg.get("directives", [])
                    routes = arg.get("routes", [])
                    groups = arg.get("groups", [])
                elif arg.get("type") == "ServerStatic":
                    directives.append(arg)
                elif arg.get("type") == "ServerCors":
                    directives.append(arg)
                elif arg.get("type") == "ServerMiddleware":
                    directives.append(arg)
                elif arg.get("type") == "RouteDeclaration":
                    routes.append(arg)
                elif arg.get("type") == "SemanticRouteDeclaration":
                    routes.append(arg)
                elif arg.get("type") == "ServerGroup":
                    groups.append(arg)
            elif isinstance(arg, list):
                # server_body returns a list
                for item in arg:
                    if isinstance(item, dict):
                        if item.get("type") == "ServerStatic":
                            directives.append(item)
                        elif item.get("type") == "ServerCors":
                            directives.append(item)
                        elif item.get("type") == "ServerMiddleware":
                            directives.append(item)
                        elif item.get("type") == "RouteDeclaration":
                            routes.append(item)
                        elif item.get("type") == "SemanticRouteDeclaration":
                            routes.append(item)
                        elif item.get("type") == "ServerGroup":
                            groups.append(item)
        
        return {
            "type": "ServerDeclaration",
            "port": port,
            "directives": directives,
            "routes": routes,
            "groups": groups,
        }

    # ===== P1-5: Database Integration (内置数据库集成) =====

    @v_args(inline=False)
    def db_decl(self, args):
        """Database declaration: db app_db = connect('sqlite://:memory:')"""
        name = str(args[0])
        # Grammar: "db" IDENTIFIER "=" "connect" "(" STRING_LITERAL ")"
        # Anonymous terminals are filtered, so args = [IDENTIFIER, STRING_LITERAL]
        connection_string = str(args[1]).strip('"')

        return {
            "type": "DatabaseDeclaration",
            "name": name,
            "connection_string": connection_string,
        }

    # ===== P2-1: Built-In Auth & OAuth (内置认证与 OAuth) =====

    @v_args(inline=False)
    def auth_decl(self, args):
        '''Auth declaration: auth myAuth = enable_auth("providers_json")

        P2-1: Agent-Native 三层认证模型声明
        '''
        name = str(args[0])
        # Grammar: "auth" IDENTIFIER "=" "enable_auth" "(" STRING_LITERAL ")"
        # Anonymous terminals filtered, args = [IDENTIFIER, STRING_LITERAL]
        providers_json = str(args[1]).strip('"')

        # 尝试解析 providers JSON
        try:
            providers = json.loads(providers_json)
        except (json.JSONDecodeError, TypeError):
            providers = [{"name": providers_json}]

        return {
            "type": "AuthDeclaration",
            "name": name,
            "providers": providers,
            "options": {},
        }

    # ===== P2-3: KV Store (内置键值存储) =====

    @v_args(inline=False)
    def kv_decl(self, args):
        '''KV declaration: kv myCache = open("cache.db")

        P2-3: Agent-Native 统一键值存储声明
        '''
        name = str(args[0])
        # Grammar: "kv" IDENTIFIER "=" "open" "(" STRING_LITERAL ")"
        # Anonymous terminals filtered, args = [IDENTIFIER, STRING_LITERAL]
        path = str(args[1]).strip('"')

        return {
            "type": "KVDeclaration",
            "name": name,
            "path": path,
        }

    # ===== P2-2: Structured Concurrency (结构化并发) =====

    @v_args(inline=False)
    def spawn_expr(self, args):
        '''spawn expression: spawn(handler)

        P2-2: 后台任务派生, handler 可为 callable 或 NexaAgent
        '''
        handler = args[0] if args else None
        return {
            'type': 'SpawnExpression',
            'handler': handler,
        }

    @v_args(inline=False)
    def parallel_expr(self, args):
        '''parallel expression: parallel(handlers)

        P2-2: 并行执行所有 handler, 返回结果列表
        '''
        handlers = args[0] if args else None
        return {
            'type': 'ParallelExpression',
            'handlers': handlers,
        }

    @v_args(inline=False)
    def race_expr(self, args):
        '''race expression: race(handlers)

        P2-2: 第一个成功结果, 取消其余
        '''
        handlers = args[0] if args else None
        return {
            'type': 'RaceExpression',
            'handlers': handlers,
        }

    @v_args(inline=False)
    def channel_expr(self, args):
        '''channel expression: channel()

        P2-2: 创建通道对 [tx, rx]
        '''
        return {
            'type': 'ChannelDeclaration',
        }

    @v_args(inline=False)
    def after_expr(self, args):
        '''after expression: after(delay, handler)

        P2-2: 延迟执行
        '''
        delay = args[0] if len(args) > 0 else None
        handler = args[1] if len(args) > 1 else None
        return {
            'type': 'AfterExpression',
            'delay': delay,
            'handler': handler,
        }

    @v_args(inline=False)
    def schedule_expr(self, args):
        '''schedule expression: schedule(interval, handler)

        P2-2: 周期执行
        '''
        interval = args[0] if len(args) > 0 else None
        handler = args[1] if len(args) > 1 else None
        return {
            'type': 'ScheduleExpression',
            'interval': interval,
            'handler': handler,
        }

    @v_args(inline=False)
    def select_expr(self, args):
        '''select expression: select(channels, timeout?)

        P2-2: 多路复用通道
        '''
        channels = args[0] if len(args) > 0 else None
        timeout = args[1] if len(args) > 1 else None
        return {
            'type': 'SelectExpression',
            'channels': channels,
            'timeout': timeout,
        }

    @v_args(inline=False)
    def concurrent_decl(self, args):
        '''concurrent declaration wrapper — delegates to inner expression'''
        if args:
            return args[0]
        return {'type': 'ConcurrentDeclaration'}

    @v_args(inline=False)
    def require_auth_decl(self, args):
        '''RequireAuth directive: require_auth "/dashboard"

        P2-1: 在 server body 内声明受保护路径
        '''
        path_pattern = str(args[0]).strip('"')

        return {
            "type": "RequireAuth",
            "path": path_pattern,
        }

    @v_args(inline=False)
    def server_body(self, args):
        """Server body: directive* route* group*"""
        directives = []
        routes = []
        groups = []
        
        for arg in args:
            if isinstance(arg, dict):
                t = arg.get("type", "")
                if t in ("ServerStatic", "ServerCors", "ServerMiddleware", "RequireAuth"):
                    directives.append(arg)
                elif t in ("RouteDeclaration", "SemanticRouteDeclaration"):
                    routes.append(arg)
                elif t == "ServerGroup":
                    groups.append(arg)
            elif isinstance(arg, list):
                for item in arg:
                    if isinstance(item, dict):
                        t = item.get("type", "")
                        if t in ("ServerStatic", "ServerCors", "ServerMiddleware", "RequireAuth"):
                            directives.append(item)
                        elif t in ("RouteDeclaration", "SemanticRouteDeclaration"):
                            routes.append(item)
                        elif t == "ServerGroup":
                            groups.append(item)
        
        return {
            "type": "ServerBody",
            "directives": directives,
            "routes": routes,
            "groups": groups,
        }

    @v_args(inline=False)
    def server_static(self, args):
        """Static directive: static '/assets' from './public'"""
        url_prefix = str(args[0]).strip('"')
        filesystem_path = str(args[1]).strip('"')
        return {
            "type": "ServerStatic",
            "url_prefix": url_prefix,
            "filesystem_path": filesystem_path,
        }

    @v_args(inline=False)
    def server_cors(self, args):
        """CORS directive: cors { origins: ["*"], methods: ["GET", "POST"] }"""
        # args[0] is the dict_literal
        config = args[0] if isinstance(args[0], dict) else {}
        return {
            "type": "ServerCors",
            "config": config,
        }

    @v_args(inline=False)
    def server_middleware(self, args):
        """Middleware directive: middleware [mw1, mw2]"""
        middleware_names = []
        for arg in args:
            if isinstance(arg, str):
                middleware_names.append(arg)
            elif isinstance(arg, list):
                middleware_names.extend(arg)
        return {
            "type": "ServerMiddleware",
            "middleware_names": middleware_names,
        }

    @v_args(inline=False)
    def route_decl_standard(self, args):
        """Route 声明: route GET "/path" => HandlerName"""
        method = str(args[0])
        pattern = str(args[1]).strip('"')
        handler = args[2] if isinstance(args[2], dict) else {"type": "RouteHandlerFn", "name": str(args[2])}
        
        # Determine handler type
        handler_type = handler.get("handler_type", "fn")
        handler_name = handler.get("name", "")
        dag_chain = handler.get("dag_chain", [])
        
        return {
            "type": "RouteDeclaration",
            "method": method,
            "pattern": pattern,
            "handler": handler_name,
            "handler_type": handler_type,
            "dag_chain": dag_chain,
        }

    @v_args(inline=False)
    def semantic_route_decl(self, args):
        """Semantic route 声明: semantic route "/path" => AgentName"""
        pattern = str(args[0]).strip('"')
        handler = args[1] if isinstance(args[1], dict) else {"type": "RouteHandlerFn", "name": str(args[1])}
        
        handler_name = handler.get("name", str(args[1]) if not isinstance(args[1], dict) else "")
        
        return {
            "type": "SemanticRouteDeclaration",
            "method": "SEMANTIC",
            "pattern": pattern,
            "handler": handler_name,
            "handler_type": "semantic",
        }

    @v_args(inline=False)
    def route_handler_fn(self, args):
        """Route handler function name"""
        return {"type": "RouteHandlerFn", "name": str(args[0]), "handler_type": "fn"}

    @v_args(inline=False)
    def route_handler_dag(self, args):
        """Route handler DAG chain: Agent1 |>> Agent2 |>> Agent3"""
        chain = [str(arg) for arg in args]
        first = chain[0]
        return {
            "type": "RouteHandlerDag",
            "name": first,
            "handler_type": "dag",
            "dag_chain": chain,
        }

    @v_args(inline=False)
    def server_group(self, args):
        """Server group: group "/admin" { ... }"""
        prefix = str(args[0]).strip('"')
        
        directives = []
        routes = []
        
        for arg in args[1:]:
            if isinstance(arg, dict):
                t = arg.get("type", "")
                if t in ("ServerStatic", "ServerCors", "ServerMiddleware"):
                    directives.append(arg)
                elif t in ("RouteDeclaration", "SemanticRouteDeclaration"):
                    routes.append(arg)
            elif isinstance(arg, list):
                for item in arg:
                    if isinstance(item, dict):
                        t = item.get("type", "")
                        if t in ("ServerStatic", "ServerCors", "ServerMiddleware"):
                            directives.append(item)
                        elif t in ("RouteDeclaration", "SemanticRouteDeclaration"):
                            routes.append(item)
        
        return {
            "type": "ServerGroup",
            "prefix": prefix,
            "directives": directives,
            "routes": routes,
        }

    @v_args(inline=False)
    def agent_decl(self, args):
        # Handle decorators (multiple @limit, @timeout, etc.)
        decorators = []
        requires_clauses = []
        ensures_clauses = []
        idx = 0
        while idx < len(args):
            arg = args[idx]
            if isinstance(arg, dict) and arg.get("type") == "agent_decorator":
                decorators.append(arg)
                idx += 1
            else:
                break
        
        # Skip decorators to find name
        name = str(args[idx]) if idx < len(args) else ""
        idx += 1
        
        return_type = "str"
        if idx < len(args) and args[idx] is not None:
            if isinstance(args[idx], dict) and "value" in args[idx]:
                return_type = args[idx]["value"]
            idx += 1
        else:
            idx += 1
            
        uses = []
        if idx < len(args) and args[idx] is not None:
            uses = args[idx]
            idx += 1
        else:
            idx += 1
            
        implements = None
        if idx < len(args) and args[idx] is not None:
            implements = str(args[idx])
            idx += 1
        else:
            idx += 1
            
        # Collect requires and ensures contract clauses
        # They appear between implements and the property block
        properties = {}
        for arg in args[idx:]:
            if isinstance(arg, dict):
                if arg.get("type") == "ContractClause":
                    if arg.get("clause_type") == "requires":
                        requires_clauses.append(arg)
                    elif arg.get("clause_type") == "ensures":
                        ensures_clauses.append(arg)
                    else:
                        # unknown clause type, skip
                        pass
                elif "key" in arg:
                    properties[arg["key"]] = arg["value"]
        
        # Extract decorator values
        max_tokens = None
        timeout = None
        retry = None
        temperature = None
        for dec in decorators:
            dec_name = dec.get("name", "")
            dec_params = dec.get("params", {})
            if dec_name == "limit":
                max_tokens = dec_params.get("max_tokens")
            elif dec_name == "timeout":
                timeout = dec_params.get("seconds")
            elif dec_name == "retry":
                retry = dec_params.get("max_attempts")
            elif dec_name == "temperature":
                temperature = dec_params.get("value")
                
        return {
            "type": "AgentDeclaration",
            "name": name,
            "decorators": decorators,
            "max_tokens": max_tokens,
            "timeout": timeout,
            "retry": retry,
            "temperature": temperature,
            "return_type": return_type,
            "uses": uses,
            "implements": implements,
            "properties": properties,
            "prompt": properties.get("prompt", ""),
            "requires": requires_clauses,
            "ensures": ensures_clauses,
        }

    @v_args(inline=False)
    def agent_decorator(self, args):
        name = str(args[0]) if args else ""
        params = {}
        for arg in args[1:]:
            if isinstance(arg, dict):
                params.update(arg)
        return {"type": "agent_decorator", "name": name, "params": params}

    @v_args(inline=False)
    def agent_decorator_name(self, args):
        return str(args[0]) if args else ""

    @v_args(inline=False)
    def agent_decorator_params(self, args):
        params = {}
        for arg in args:
            if isinstance(arg, dict):
                params.update(arg)
        return params

    @v_args(inline=False)
    def agent_decorator_param(self, args):
        key = str(args[0])
        value = args[1]
        if hasattr(value, 'value'):
            value = value.value
        try:
            value = int(value)
        except (ValueError, TypeError):
            try:
                value = float(value)
            except (ValueError, TypeError):
                pass
        return {key: value}

    @v_args(inline=False)
    def return_type(self, args):
        val = "".join([str(a) for a in args])
        return {"type": "return_type", "value": val}

    @v_args(inline=False)
    def agent_property(self, args):
        key = str(args[0])
        value = args[1]
        return {"key": key, "value": value}

    @v_args(inline=True)
    def string_val(self, s):
        return str(s).strip('"')

    @v_args(inline=True)
    def multiline_string_val(self, s):
        """处理多行字符串，移除三引号并保留内部换行"""
        s = str(s)
        # 移除开头和结尾的三引号
        if s.startswith('"""') and s.endswith('"""'):
            return s[3:-3]
        return s

    @v_args(inline=True)
    def id_val(self, i):
        return str(i)

    @v_args(inline=True)
    def list_val(self, i):
        return i

    @v_args(inline=True)
    def int_val(self, i):
        return int(i)

    @v_args(inline=True)
    def true_val(self):
        return True

    @v_args(inline=True)
    def false_val(self):
        return False

    @v_args(inline=False)
    def fallback_list_val(self, args):
        """处理 fallback_list_val 节点"""
        return args[0]  # 返回 fallback_list

    @v_args(inline=False)
    def fallback_list(self, args):
        """处理 fallback_list，返回带 fallback 标记的列表"""
        result = []
        for item in args:
            if isinstance(item, dict):
                result.append(item)
            else:
                result.append({"value": str(item).strip('"'), "is_fallback": False})
        return {"type": "fallback_list", "models": result}

    @v_args(inline=True)
    def primary_model(self, item):
        """处理主模型"""
        from lark import Token
        if isinstance(item, Token):
            value = str(item).strip('"')
            return {"value": value, "is_fallback": False}
        return {"value": str(item).strip('"'), "is_fallback": False}

    @v_args(inline=True)
    def fallback_model(self, item):
        """处理 fallback 模型"""
        from lark import Token
        if isinstance(item, Token):
            value = str(item).strip('"')
            return {"value": value, "is_fallback": True}
        return {"value": str(item).strip('"'), "is_fallback": True}

    @v_args(inline=False)
    def if_stmt(self, args):
        """if 语句"""
        condition = args[0]
        then_block = args[1]
        else_block = args[2] if len(args) > 2 else []
        return {
            "type": "IfStatement",
            "condition": condition,
            "then_block": then_block,
            "else_block": else_block
        }

    @v_args(inline=False)
    def condition(self, args):
        """条件表达式 - v1.0.1-beta 使用 CMP_OP 终端"""
        from lark import Token
        op = args[1]
        if isinstance(op, Token):
            op = str(op)
        return {
            "type": "ConditionExpression",
            "left": args[0],
            "operator": op,
            "right": args[2]
        }

    @v_args(inline=False)
    def comparison_expr(self, args):
        """比较表达式 - v1.0.1-beta 使用 CMP_OP 终端"""
        if len(args) == 1:
            # 简单布尔判断 (只有表达式)
            return args[0]
        # args: [left, CMP_OP token, right]
        from lark import Token
        op = args[1]
        if isinstance(op, Token):
            op = str(op)
        return {
            "type": "ComparisonExpression",
            "left": args[0],
            "operator": op,
            "right": args[2]
        }

    @v_args(inline=False)
    def identifier_list(self, args):
        return [str(arg) for arg in args]

    def use_identifier_list(self, args):
        return [str(arg) for arg in args]

    def use_identifier(self, args):
        return str(args[0])

    def namespaced_id(self, args):
        return f"{args[0]}.{args[1]}"

    def string_use(self, args):
        return str(args[0])[1:-1]

    def mcp_use(self, args):
        return "mcp:" + str(args[0])[1:-1]

    @v_args(inline=False)
    def flow_decl(self, args):
        # flow_decl: "flow" IDENTIFIER ["(" param_list ")"] ["->" type_expr] requires_clause* ensures_clause* block
        # v1.1: 新增可选返回类型 ["->" type_expr]
        name = str(args[0])
        params = []
        return_type = None  # v1.1: 返回类型标注
        requires_clauses = []
        ensures_clauses = []
        body = []
        
        # Walk through remaining args to classify them
        for i in range(1, len(args)):
            arg = args[i]
            if arg is None:
                continue
            if isinstance(arg, dict):
                # v1.1: 检查返回类型表达式
                if arg.get("type") in ("BaseType", "GenericType", "CustomType",
                                       "OptionTypeExpr", "ResultTypeExpr", "UnionTypeExpr",
                                       "SemanticType", "FuncTypeExpr"):
                    # 如果还没有找到返回类型且已找到参数，这是返回类型
                    if return_type is None and params:
                        return_type = arg
                    elif return_type is None and not params:
                        # 可能是参数类型或返回类型，需要上下文判断
                        # 如果之前没有 ParamList，这可能是返回类型
                        return_type = arg
                    continue
                if arg.get("type") == "ContractClause":
                    if arg.get("clause_type") == "requires":
                        requires_clauses.append(arg)
                    elif arg.get("clause_type") == "ensures":
                        ensures_clauses.append(arg)
                elif arg.get("type") == "ParamList":
                    params = arg.get("params", [])
                elif "name" in arg and arg.get("type") not in ("ContractClause", "BaseType", "GenericType", "CustomType", "OptionTypeExpr", "ResultTypeExpr", "UnionTypeExpr", "SemanticType", "FuncTypeExpr"):
                    # This is a param dict (with "name" and "type_annotation" or "type")
                    params.append(arg)
            elif isinstance(arg, list):
                # Check if it's a param list or a body block
                if len(arg) > 0 and isinstance(arg[0], dict) and 'name' in arg[0] and arg[0].get("type") != "ContractClause":
                    params = arg
                else:
                    body = arg
        
        return {
            "type": "FlowDeclaration",
            "name": name,
            "params": params,
            "return_type": return_type,  # v1.1: 渐进式类型系统
            "requires": requires_clauses,
            "ensures": ensures_clauses,
            "body": body
        }
    
    # ===== Design by Contract (契约式编程) - v1.1 =====
    
    @v_args(inline=False)
    def requires_semantic_clause(self, args):
        """语义前置条件: requires 自然语言字符串"""
        condition_text = str(args[0]).strip('"')
        return {
            "type": "ContractClause",
            "clause_type": "requires",
            "is_semantic": True,
            "condition_text": condition_text,
            "expression": None,
            "message": "",
        }
    
    @v_args(inline=False)
    def requires_deterministic_clause(self, args):
        """确定性前置条件: requires 比较表达式"""
        # args[0] 是 comparison_expr 的结果
        expr = args[0]
        expression_str = self._contract_expr_to_string(expr)
        return {
            "type": "ContractClause",
            "clause_type": "requires",
            "is_semantic": False,
            "condition_text": None,
            "expression": expression_str,
            "message": "",
        }
    
    @v_args(inline=False)
    def ensures_semantic_clause(self, args):
        """语义后置条件: ensures 自然语言字符串"""
        condition_text = str(args[0]).strip('"')
        return {
            "type": "ContractClause",
            "clause_type": "ensures",
            "is_semantic": True,
            "condition_text": condition_text,
            "expression": None,
            "message": "",
        }
    
    @v_args(inline=False)
    def ensures_deterministic_clause(self, args):
        """确定性后置条件: ensures 比较表达式"""
        expr = args[0]
        expression_str = self._contract_expr_to_string(expr)
        return {
            "type": "ContractClause",
            "clause_type": "ensures",
            "is_semantic": False,
            "condition_text": None,
            "expression": expression_str,
            "message": "",
        }
    
    def _contract_expr_to_string(self, expr) -> str:
        """将表达式 AST 节点转换为契约表达式字符串
        
        支持:
        - ComparisonExpression: amount > 0 -> "amount > 0"
        - LogicalExpression: a > 0 and b < 10 -> "a > 0 and b < 10"
        - 简单标识符/字面量
        - old(expr) 和 result 特殊语法
        """
        if isinstance(expr, str):
            return expr
        if isinstance(expr, dict):
            ex_type = expr.get("type")
            if ex_type == "ComparisonExpression":
                left = self._contract_expr_to_string(expr.get("left"))
                op = expr.get("operator")
                right = self._contract_expr_to_string(expr.get("right"))
                return f"{left} {op} {right}"
            elif ex_type == "LogicalExpression":
                left = self._contract_expr_to_string(expr.get("left"))
                op = expr.get("operator")
                right = self._contract_expr_to_string(expr.get("right"))
                return f"{left} {op} {right}"
            elif ex_type == "ConditionExpression":
                left = self._contract_expr_to_string(expr.get("left"))
                op = expr.get("operator")
                right = self._contract_expr_to_string(expr.get("right"))
                return f"{left} {op} {right}"
            elif ex_type == "Identifier":
                return expr.get("value", "")
            elif ex_type == "StringLiteral":
                return f'"{expr.get("value", "")}"'
            elif ex_type == "IntLiteral":
                return str(expr.get("value", 0))
            elif ex_type == "FloatLiteral":
                return str(expr.get("value", 0.0))
            elif ex_type == "BooleanLiteral":
                return "True" if expr.get("value") else "False"
            elif ex_type == "BinaryExpression":
                left = self._contract_expr_to_string(expr.get("left"))
                op = expr.get("operator")
                right = self._contract_expr_to_string(expr.get("right"))
                return f"{left} {op} {right}"
            elif ex_type == "PropertyAccess":
                base = self._contract_expr_to_string(expr.get("base"))
                prop = expr.get("property")
                return f"{base}.{prop}"
        return str(expr)
    
    @v_args(inline=False)
    def param_list(self, args):
        return [arg for arg in args if arg is not None]
    
    @v_args(inline=False)
    def param(self, args):
        """v1.1: 参数支持完整类型表达式 (param: IDENTIFIER ":" type_expr)"""
        name = str(args[0])
        type_annotation = args[1]
        # 从类型表达式提取简单类型名（用于兼容旧代码）
        if isinstance(type_annotation, dict):
            simple_type = type_annotation.get("name", type_annotation.get("value", ""))
            if type_annotation.get("type") == "GenericType":
                simple_type = type_annotation.get("name", "")
            elif type_annotation.get("type") == "OptionTypeExpr":
                inner_name = type_annotation.get("inner", {}).get("name", "?") if isinstance(type_annotation.get("inner"), dict) else "?"
                simple_type = inner_name
            elif type_annotation.get("type") == "UnionTypeExpr":
                simple_type = " | ".join(
                    t.get("name", t.get("value", "?")) for t in type_annotation.get("types", [])
                )
        else:
            simple_type = str(type_annotation)
        
        return {
            "name": name,
            "type": simple_type,  # 兼容旧代码
            "type_annotation": type_annotation  # v1.1: 完整类型表达式
        }

    @v_args(inline=False)
    def test_decl(self, args):
        return {
            "type": "TestDeclaration",
            "name": str(args[0]).strip('"'),
            "body": args[1]
        }

    @v_args(inline=False)
    def block(self, args):
        return args

    @v_args(inline=False)
    def assignment_stmt(self, args):
        val = args[1]
        if hasattr(val, 'data') and val.data == 'fallback_expr':
            val = self.fallback_expr(val.children)
            
        return {
            "type": "AssignmentStatement",
            "target": str(args[0]),
            "value": val
        }

    # ===== v1.2: Error Propagation (? 操作符 + otherwise 内联错误处理) =====

    @v_args(inline=False)
    def try_assignment_stmt(self, args):
        """v1.2: ? 操作符赋值语句 — x = expr?  →  错误传播
        
        语法: IDENTIFIER "=" expression "?" ";"?
        语义: 对 expression 的结果执行 unwrap()
        - NexaResult.ok → 返回值赋给 target
        - NexaResult.err → 抛出 ErrorPropagation (early-return)
        """
        target = str(args[0])
        expr = args[1] if len(args) > 1 else args[0]
        return {
            "type": "TryAssignmentStatement",
            "target": target,
            "expression": expr
        }

    @v_args(inline=False)
    def otherwise_assignment_stmt(self, args):
        """v1.2: otherwise 内联错误处理赋值语句 — x = expr otherwise handler
        
        语法: IDENTIFIER "=" expression "otherwise" otherwise_handler ";"?
        语义: 对 expression 的结果执行 unwrap_or_else()
        - NexaResult.ok → 返回值赋给 target
        - NexaResult.err → 执行 otherwise_handler 作为 fallback
        """
        target = str(args[0])
        expr = args[1] if len(args) > 1 else args[0]
        handler = args[2] if len(args) > 2 else args[1]
        return {
            "type": "OtherwiseAssignmentStatement",
            "target": target,
            "expression": expr,
            "otherwise_handler": handler
        }

    @v_args(inline=False)
    def try_expr_stmt(self, args):
        """v1.2: ? 操作符表达式语句 — expr?  →  错误传播（无赋值）
        
        语法: expression "?" ";"?
        语义: 对 expression 的结果执行 unwrap()
        - NexaResult.ok → 继续执行
        - NexaResult.err → 抛出 ErrorPropagation (early-return)
        """
        expr = args[0]
        return {
            "type": "TryExprStatement",
            "expression": expr
        }

    @v_args(inline=False)
    def otherwise_agent_handler(self, args):
        """v1.2: otherwise handler — Agent 调用作为 fallback
        
        这是 Nexa 独有的特性: otherwise 可以指定另一个 Agent 作为 fallback
        语义: 失败时调用 fallback Agent
        """
        handler = args[0]
        if isinstance(handler, dict):
            return {
                "type": "OtherwiseAgentHandler",
                "handler_type": "agent_call",
                "agent_call": handler
            }
        return {
            "type": "OtherwiseAgentHandler",
            "handler_type": "agent_call",
            "agent_call": handler
        }

    @v_args(inline=True)
    def otherwise_value_handler(self, value):
        """v1.2: otherwise handler — 值作为 fallback
        
        语义: 失败时返回此值作为默认值
        例如: result = SearchBot.run(query) otherwise "No results found"
        """
        return {
            "type": "OtherwiseValueHandler",
            "handler_type": "value",
            "value": str(value).strip('"')
        }

    @v_args(inline=True)
    def otherwise_var_handler(self, name):
        """v1.2: otherwise handler — 变量引用作为 fallback
        
        语义: 失败时使用此变量值作为默认值
        例如: result = WeatherBot.run("Beijing") otherwise fallback_result
        """
        return {
            "type": "OtherwiseVarHandler",
            "handler_type": "variable",
            "variable": str(name)
        }

    @v_args(inline=False)
    def otherwise_block_handler(self, args):
        """v1.2: otherwise handler — 代码块作为 fallback
        
        语义: 失败时执行代码块中的语句
        例如: result = DebugBot.run(input) otherwise { print("failed"); "fallback" }
        """
        statements = args[0] if args else []
        return {
            "type": "OtherwiseBlockHandler",
            "handler_type": "block",
            "statements": statements
        }

    @v_args(inline=False)
    def expr_stmt(self, args):
        return {
            "type": "ExpressionStatement",
            "expression": args[0]
        }

    @v_args(inline=False)
    def try_catch_stmt(self, args):
        return {
            "type": "TryCatchStatement",
            "block_try": args[0],
            "catch_err": str(args[1]),
            "block_catch": args[2]
        }

    @v_args(inline=False)
    def assert_stmt(self, args):
        return {
            "type": "AssertStatement",
            "expression": args[0]
        }

    @v_args(inline=False)
    def break_stmt(self, args):
        return {
            "type": "BreakStatement"
        }

    @v_args(inline=False)
    def continue_stmt(self, args):
        """continue 语句 - v1.0.1-beta"""
        return {
            "type": "ContinueStatement"
        }

    @v_args(inline=False)
    def traditional_if_stmt(self, args):
        """传统 if/else if/else 语句 - v1.0.1-beta
        处理各种形式的 if 语句：
        1. if (...) { } - 无 else
        2. if (...) { } else { } - 只有 else
        3. if (...) { } else if (...) { } else { } - else if 链
        """
        condition = args[0]
        then_block = args[1] if len(args) > 1 else []
        
        # 收集 else if 和 else 子句
        else_if_clauses = []
        else_block = []
        
        # 处理剩余参数
        i = 2
        while i < len(args):
            arg = args[i]
            
            # 检查是否是条件（来自 else if）
            if isinstance(arg, dict) and arg.get("type") in ["ComparisonExpression", "LogicalExpression", "Identifier"]:
                # 这是一个 else if 的条件
                if i + 1 < len(args):
                    block = args[i + 1]
                    if isinstance(block, list):
                        else_if_clauses.append({
                            "type": "ElseIfClause",
                            "condition": arg,
                            "block": block
                        })
                        i += 2
                        continue
            
            # 检查是否是 block（来自 else）
            elif isinstance(arg, list):
                # 这是 else 的 block
                else_block = arg
                i += 1
                continue
            
            i += 1
        
        return {
            "type": "TraditionalIfStatement",
            "condition": condition,
            "then_block": then_block,
            "else_if_clauses": else_if_clauses,
            "else_block": else_block
        }

    @v_args(inline=False)
    def traditional_condition(self, args):
        """传统条件表达式"""
        return args[0] if args else {"type": "BooleanLiteral", "value": True}

    @v_args(inline=False)
    def logical_expr(self, args):
        """逻辑表达式 - 支持 and/or"""
        if len(args) == 1:
            return args[0]
        
        # 构建逻辑表达式链
        result = args[0]
        i = 1
        while i < len(args):
            operator = str(args[i])
            right = args[i + 1]
            result = {
                "type": "LogicalExpression",
                "left": result,
                "operator": operator,
                "right": right
            }
            i += 2
        
        return result

    @v_args(inline=False)
    def foreach_stmt(self, args):
        """for each 循环 - v1.0.1-beta"""
        if len(args) == 3:
            # for each item in iterable { block }
            return {
                "type": "ForEachStatement",
                "iterator": str(args[0]),
                "index": None,
                "iterable": args[1],
                "body": args[2]
            }
        elif len(args) == 4:
            # for each item, index in iterable { block }
            return {
                "type": "ForEachStatement",
                "iterator": str(args[0]),
                "index": str(args[1]),
                "iterable": args[2],
                "body": args[3]
            }
        return {"type": "ForEachStatement", "iterator": "", "iterable": None, "body": []}

    @v_args(inline=False)
    def while_stmt(self, args):
        """while 循环 - v1.0.1-beta"""
        return {
            "type": "WhileStatement",
            "condition": args[0] if args else {"type": "BooleanLiteral", "value": True},
            "body": args[1] if len(args) > 1 else []
        }

    @v_args(inline=False)
    def python_escape_stmt(self, args):
        """Python 逃生舱 - v1.0.1-beta
        语法: python! \"\"\"code\"\"\"
        """
        # 提取 Python 代码块 - MULTILINE_STRING
        python_code = ""
        if args:
            raw = str(args[0])
            # 移除三引号
            if raw.startswith('"""') and raw.endswith('"""'):
                python_code = raw[3:-3]
            else:
                python_code = raw
        # 移除首尾空白但保留内部换行
        python_code = python_code.strip()
        
        return {
            "type": "PythonEscapeStatement",
            "code": python_code
        }

    @v_args(inline=False)
    def semantic_if_stmt(self, args):
        condition = str(args[0]).strip('"')
        fast_match = str(args[1]).strip('"') if args[1] else None
        target = str(args[2])
        consequence = args[3]
        alternative = args[4] if len(args) > 4 and args[4] else []
        
        return {
            "type": "SemanticIfStatement",
            "condition": condition,
            "fast_match": fast_match,
            "target_variable": target,
            "consequence": consequence,
            "alternative": alternative
        }

    @v_args(inline=False)
    def loop_stmt(self, args):
        return {
            "type": "LoopUntilStatement",
            "body": args[0],
            "condition": args[1]
        }


    # ===== P3-3: Pattern Matching + Destructuring (模式匹配 + 解构) =====

    @v_args(inline=False)
    def match_expr(self, args):
        'P3-3: match expression with pattern matching - match expr { pattern => body, ... }'
        # Filter out anonymous terminals ("match", "{", ",", "}")
        parts = [a for a in args if isinstance(a, dict)]
        scrutinee = parts[0] if parts else None
        arms = parts[1:] if len(parts) > 1 else []
        return {
            'type': 'MatchExpression',
            'scrutinee': scrutinee,
            'arms': arms
        }

    @v_args(inline=False)
    def match_arm(self, args):
        'P3-3: match arm - pattern => body [if guard]'
        # Filter out anonymous terminals ("=>", "if")
        parts = [a for a in args if isinstance(a, dict)]
        pattern = parts[0] if parts else None
        body = parts[1] if len(parts) > 1 else []
        guard = parts[2] if len(parts) > 2 else None
        return {
            'type': 'MatchArm',
            'pattern': pattern,
            'body': body,
            'guard': guard
        }

    @v_args(inline=False)
    def wildcard_pat(self, args):
        'P3-3: wildcard pattern _ - matches anything, no binding'
        return {'type': 'Pattern', 'kind': 'wildcard'}

    @v_args(inline=False)
    def literal_int_pat(self, args):
        'P3-3: integer literal pattern - matches exact int value'
        value = int(str(args[0]))
        return {'type': 'Pattern', 'kind': 'literal', 'value': value, 'value_type': 'int'}

    @v_args(inline=False)
    def literal_float_pat(self, args):
        'P3-3: float literal pattern - matches exact float value'
        value = float(str(args[0]))
        return {'type': 'Pattern', 'kind': 'literal', 'value': value, 'value_type': 'float'}

    @v_args(inline=False)
    def literal_str_pat(self, args):
        'P3-3: string literal pattern - matches exact string value'
        value = str(args[0]).strip('"')
        return {'type': 'Pattern', 'kind': 'literal', 'value': value, 'value_type': 'string'}

    @v_args(inline=False)
    def literal_true_pat(self, args):
        'P3-3: boolean true pattern - matches true'
        return {'type': 'Pattern', 'kind': 'literal', 'value': True, 'value_type': 'bool'}

    @v_args(inline=False)
    def literal_false_pat(self, args):
        'P3-3: boolean false pattern - matches false'
        return {'type': 'Pattern', 'kind': 'literal', 'value': False, 'value_type': 'bool'}

    @v_args(inline=True)
    def variable_pat(self, name):
        'P3-3: variable pattern - matches anything, binds variable'
        return {'type': 'Pattern', 'kind': 'variable', 'name': str(name)}

    @v_args(inline=False)
    def tuple_pat(self, args):
        'P3-3: tuple pattern (a, b, ...) - matches tuple/list of specific length'
        # Filter out anonymous terminals ("(", ",")")
        elements = [a for a in args if isinstance(a, dict)]
        return {'type': 'Pattern', 'kind': 'tuple', 'elements': elements}

    @v_args(inline=False)
    def array_pat(self, args):
        'P3-3: array pattern [a, b] - matches array, no rest'
        # Filter out anonymous terminals ("[", ",", "]")
        elements = [a for a in args if isinstance(a, dict)]
        return {'type': 'Pattern', 'kind': 'array', 'elements': elements, 'rest': None}

    @v_args(inline=False)
    def array_pat_rest(self, args):
        'P3-3: array pattern with rest collector [a, b..rest]'
        # Grammar: "[" pattern ("," pattern)+ ".." IDENTIFIER "]"
        # Anonymous terminals ("[", ",", "..", "]") are discarded by Lark
        # Remaining args: Pattern dicts + IDENTIFIER token for rest variable
        elements = []
        rest = None
        for a in args:
            if isinstance(a, dict):
                elements.append(a)
            else:
                # The IDENTIFIER token for the rest variable name
                # Could be a Token or str — take the last non-dict arg as rest
                rest = str(a)
        return {'type': 'Pattern', 'kind': 'array', 'elements': elements, 'rest': rest}

    @v_args(inline=False)
    def map_pat(self, args):
        'P3-3: map pattern { name, age: a } - matches dict, no rest'
        entries = []
        for a in args:
            if isinstance(a, dict) and a.get('type') == 'MapPatternEntry':
                entries.append(a)
        return {'type': 'Pattern', 'kind': 'map', 'entries': entries, 'rest': None}

    @v_args(inline=False)
    def map_pat_rest(self, args):
        'P3-3: map pattern with rest collector {name, age: a..other}'
        # Grammar: "{" map_pattern_entry ("," map_pattern_entry)+ ".." IDENTIFIER "}"
        # Anonymous terminals ("{", ",", "..", "}") are discarded by Lark
        entries = []
        rest = None
        for a in args:
            if isinstance(a, dict) and a.get('type') == 'MapPatternEntry':
                entries.append(a)
            else:
                # The IDENTIFIER token for the rest variable name
                rest = str(a)
        return {'type': 'Pattern', 'kind': 'map', 'entries': entries, 'rest': rest}

    @v_args(inline=False)
    def map_entry_pat(self, args):
        'P3-3: map pattern entry - IDENTIFIER [":" pattern]'
        key = str(args[0])
        value_pattern = None
        for a in args[1:]:
            if isinstance(a, dict):
                value_pattern = a
                break
        # If no explicit value pattern, use key as variable name (shorthand)
        if value_pattern is None:
            value_pattern = {'type': 'Pattern', 'kind': 'variable', 'name': key}
        return {
            'type': 'MapPatternEntry',
            'key': key,
            'value_pattern': value_pattern
        }

    @v_args(inline=False)
    def variant_pat(self, args):
        'P3-3: variant pattern Enum::Variant(field1, field2) - matches enum variant'
        # Filter out anonymous terminals ("::", ",", "(", ")")
        str_args = [str(a) for a in args]
        enum_name = str_args[0] if str_args else ''
        variant_name = str_args[1] if len(str_args) > 1 else ''
        fields = [a for a in args if isinstance(a, dict)]
        return {
            'type': 'Pattern',
            'kind': 'variant',
            'enum_name': enum_name,
            'variant_name': variant_name,
            'fields': fields
        }

    @v_args(inline=False)
    def let_pattern_stmt(self, args):
        'P3-3: let destructuring - let pattern = expr;'
        # Filter out anonymous terminals ("let", "=", ";")
        parts = [a for a in args if isinstance(a, dict)]
        pattern = parts[0] if parts else None
        expression = parts[1] if len(parts) > 1 else None
        return {
            'type': 'LetPatternStatement',
            'pattern': pattern,
            'expression': expression
        }

    @v_args(inline=False)
    def for_pattern_stmt(self, args):
        'P3-3: for destructuring - for pattern in expr block'
        # Filter out anonymous terminals ("for", "in")
        parts = [a for a in args if isinstance(a, dict)]
        pattern = parts[0] if parts else None
        iterable = parts[1] if len(parts) > 1 else None
        body = parts[2] if len(parts) > 2 else []
        return {
            'type': 'ForPatternStatement',
            'pattern': pattern,
            'iterable': iterable,
            'body': body
        }

    @v_args(inline=False)
    def match_stmt(self, args):
        target = str(args[0])
        cases = []
        default_case = None
        for arg in args[1:]:
            if arg["type"] == "MatchCase":
                cases.append(arg)
            elif arg["type"] == "DefaultCase":
                default_case = arg
        
        return {
            "type": "MatchIntentStatement",
            "target": target,
            "cases": cases,
            "default": default_case
        }

    @v_args(inline=False)
    def match_case(self, args):
        return {
            "type": "MatchCase",
            "intent": str(args[0]).strip('"'),
            "expression": args[1]
        }

    @v_args(inline=False)
    def default_case(self, args):
        return {
            "type": "DefaultCase",
            "expression": args[0]
        }

    @v_args(inline=False)
    def pipeline_expr(self, args):
        return {
            "type": "PipelineExpression",
            "stages": args
        }
    
    # ==================== DAG 表达式转换 ====================
    
    @v_args(inline=False)
    def dag_expr(self, args):
        """DAG表达式统一处理"""
        return args[0]  # 返回具体的dag_fork_expr, dag_merge_expr或dag_branch_expr
    
    @v_args(inline=False)
    def dag_fork_wait(self, args):
        """
        分叉表达式 (等待所有结果): expr |>> [Agent1, Agent2]
        """
        input_expr = args[0]
        agents = args[1] if len(args) > 1 else []
        if not isinstance(agents, list):
            agents = [str(agents)]
        
        return {
            "type": "DAGForkExpression",
            "input": input_expr,
            "agents": agents,
            "operator": "|>>",
            "wait_all": True
        }
    
    @v_args(inline=False)
    def dag_fork_fire_forget(self, args):
        """
        分叉表达式 (fire-and-forget): expr || [Agent1, Agent2]
        """
        input_expr = args[0]
        agents = args[1] if len(args) > 1 else []
        if not isinstance(agents, list):
            agents = [str(agents)]
        
        return {
            "type": "DAGForkExpression",
            "input": input_expr,
            "agents": agents,
            "operator": "||",
            "wait_all": False
        }
    
    @v_args(inline=False)
    def dag_merge_expr(self, args):
        """
        合流表达式: [Agent1, Agent2] &>> MergerAgent 或 [Agent1, Agent2] && MergerAgent
        &>> 表示顺序合流
        && 表示共识合流
        
        Lark 传递: args[0] = agent list (from identifier_list_as_expr)
                   args[1] = merger expression
        注意: 操作符 &>> 或 && 是 literal，不会作为单独节点传递
        """
        # agents 来自 identifier_list_as_expr
        agents = args[0] if isinstance(args[0], list) else []
        if not isinstance(agents, list):
            agents = [str(agents)]
            
        merger = args[1] if len(args) > 1 else None
        
        return {
            "type": "DAGMergeExpression",
            "agents": agents,
            "merger": merger,
            "operator": "&>>",
            "strategy": "concat"
        }
    
    @v_args(inline=False)
    def dag_branch_expr(self, args):
        """
        条件分支表达式:
        1. expr ?? TrueAgent : FalseAgent (三元形式)
        2. expr ?? { "case1" => action1 } (块形式)
        """
        input_expr = args[0]
        
        # 检查是否是块形式 (semantic_if_block 是列表)
        if len(args) == 2:
            # 块形式: args[1] 是 semantic_if_block (case 列表)
            cases = args[1]
            if isinstance(cases, list):
                return {
                    "type": "DAGBranchExpression",
                    "input": input_expr,
                    "cases": cases
                }
        
        # 三元形式
        true_agent = args[1] if len(args) > 1 else None
        false_agent = args[2] if len(args) > 2 else None
        
        return {
            "type": "DAGBranchExpression",
            "input": input_expr,
            "true_agent": true_agent,
            "false_agent": false_agent
        }
    
    @v_args(inline=False)
    def identifier_list_as_expr(self, args):
        """将方括号内的标识符列表转换为列表
        
        Lark 传递的 args 来自 identifier_list 规则
        需要将每个 Token 转换为字符串
        """
        result = []
        for arg in args:
            # identifier_list 可能包含多个 IDENTIFIER token
            if hasattr(arg, '__iter__') and not isinstance(arg, str):
                # 如果是可迭代对象但不是字符串，展开它
                for sub_arg in arg:
                    result.append(str(sub_arg))
            else:
                result.append(str(arg))
        return result

    @v_args(inline=False)
    def join_call(self, args):
        # join_call: "join" "(" identifier_list ")" [ "." IDENTIFIER "(" [argument_list] ")" ]
        agents = args[0]
        method = "run"
        arguments = []
        if len(args) > 1:
            method = str(args[1])
            if len(args) > 2:
                arguments = args[2]
        
        return {
            "type": "JoinCallExpression",
            "agents": agents,
            "method": method,
            "arguments": arguments
        }

    @v_args(inline=False)
    def method_call(self, args):
        args = [a for a in args if a is not None]
        arguments = []
        if len(args) > 0 and isinstance(args[-1], list):
            arguments = args.pop()
            
        if len(args) == 1:
            return {
                "type": "FunctionCallExpression",
                "function": str(args[0]),
                "arguments": arguments
            }
        elif len(args) >= 2:
            return {
                "type": "MethodCallExpression",
                "object": str(args[0]),
                "method": str(args[1]),
                "arguments": arguments
            }
        return {}

    @v_args(inline=False)
    def kwarg(self, args):
        return {
            "type": "KeywordArgument",
            "key": str(args[0]),
            "value": args[1]
        }

    @v_args(inline=False)
    def dict_access_expr(self, args):
        return {
            "type": "DictAccessExpression",
            "base": args[0],
            "key": args[1]
        }

    @v_args(inline=False)
    def property_access(self, args):
        if len(args) == 2:
            base_val = str(args[0]) if type(args[0]).__name__ == "Token" else args[0]
            return {
                "type": "PropertyAccess",
                "base": base_val,
                "property": str(args[1])
            }
        return {"type": "PropertyAccess", "base": args[0], "property": str(args[1])}

    @v_args(inline=False)
    def argument_list(self, args):
        return args

    # 新增 DAG 操作符 transformer 方法
    @v_args(inline=False)
    def dag_chain_expr(self, args):
        """链式 DAG 表达式: expr |>> [...] &>> Agent"""
        return {
            "type": "DAGChainExpression",
            "fork": args[0],
            "merge": args[1]
        }
    
    @v_args(inline=False)
    def dag_chain_tail(self, args):
        """处理 dag_chain_tail: (&>> | &&) base_expr
        args 可能包含: [操作符token, base_expr] 或更多元素
        返回合流 agent 的标识符
        """
        # 过滤掉操作符 token，只保留 base_expr
        # args 结构: [Token('&>>'), base_expr] 或 [Token('&&'), base_expr]
        for arg in args:
            if isinstance(arg, dict) and arg.get("type") == "Identifier":
                return arg
            elif type(arg).__name__ == "Token":
                continue
            else:
                # 可能是其他表达式类型
                return arg
        # 如果没找到，返回最后一个非 token 元素
        non_tokens = [a for a in args if type(a).__name__ != "Token"]
        return non_tokens[-1] if non_tokens else {"type": "Identifier", "value": "Unknown"}

    # ===== P3-1: String Interpolation (字符串插值) =====

    @staticmethod
    def _parse_string_interpolation(s: str) -> Optional[Dict]:
        'P3-1: Parse #{expr} interpolation patterns inside a string value.\n\nReturns None if no interpolation found (plain string).\nReturns {"type": "InterpolatedString", "parts": [...]} if interpolation found.\nEach part is {"kind": "literal", "value": "..."} or {"kind": "expr", "value": "..."}.\n\nEscape handling: \\#{ -> literal #{, \\} inside #{...} -> literal }\nExpression validation: identifiers, dot access (user.name), bracket access (arr[0])'
        # Check if string contains any #{ pattern (unescaped)
        # First, process escape sequences: \\#{ -> #{ literal
        # We need to find actual #{ that are not preceded by backslash
        parts = []
        pos = 0
        has_interp = False

        while pos < len(s):
            # Check for escaped \#{ -> literal #
            if pos < len(s) - 1 and s[pos] == '\\' and s[pos + 1] == '#':
                # Check if it's \#{ (escaped interpolation start)
                if pos + 2 < len(s) and s[pos + 2] == '{':
                    # \#{ -> literal #{, skip the backslash
                    # We'll collect this as a literal character
                    parts_append = None
                    # Add # and { as literal characters
                    # But first flush any pending literal
                    parts.append({'kind': 'literal', 'value': '#{'})
                    pos += 3  # skip \#{
                    continue
                else:
                    # Just \# -> literal #
                    parts.append({'kind': 'literal', 'value': '#'})
                    pos += 2
                    continue
            
            # Check for escaped \} -> literal } (only meaningful inside interpolation context)
            # Actually, \} outside of #{...} is just a regular backslash + }
            # We handle \} inside interpolation below in the inner loop
            
            # Check for #{ interpolation start
            if pos < len(s) - 1 and s[pos] == '#' and s[pos + 1] == '{':
                has_interp = True
                # Find matching } — scan forward, handle nested braces and escaped \}
                depth = 1
                expr_start = pos + 2
                expr_pos = expr_start
                expr_buf = []
                
                while expr_pos < len(s) and depth > 0:
                    if s[expr_pos] == '\\' and expr_pos + 1 < len(s) and s[expr_pos + 1] == '}':
                        # Escaped \} inside interpolation -> literal }
                        expr_buf.append('}')
                        expr_pos += 2
                        continue
                    if s[expr_pos] == '{':
                        depth += 1
                        expr_buf.append('{')
                        expr_pos += 1
                        continue
                    if s[expr_pos] == '}':
                        depth -= 1
                        if depth == 0:
                            break
                        expr_buf.append('}')
                        expr_pos += 1
                        continue
                    expr_buf.append(s[expr_pos])
                    expr_pos += 1
                
                if depth != 0:
                    # Unmatched #{ — treat the whole thing as literal
                    parts.append({'kind': 'literal', 'value': '#{' + ''.join(expr_buf)})
                    pos = expr_pos
                    continue
                
                expr_content = ''.join(expr_buf).strip()
                
                # Empty interpolation #{} -> empty string expression
                if not expr_content:
                    parts.append({'kind': 'expr', 'value': ''})
                    pos = expr_pos + 1  # skip closing }
                    continue
                
                # Validate expression: simple variable, dot access, bracket access
                if _INTERP_EXPR_PATTERN.match(expr_content):
                    parts.append({'kind': 'expr', 'value': expr_content})
                else:
                    # Invalid expression — treat as literal (preserve original text)
                    parts.append({'kind': 'literal', 'value': '#{' + expr_content + '}'})
                
                pos = expr_pos + 1  # skip closing }
                continue
            
            # Regular character — accumulate into current literal
            # Find next special character or end of string
            lit_start = pos
            while pos < len(s):
                if pos < len(s) - 1 and s[pos] == '\\' and s[pos + 1] == '#' and pos + 2 < len(s) and s[pos + 2] == '{':
                    break
                if pos < len(s) - 1 and s[pos] == '#' and s[pos + 1] == '{':
                    break
                pos += 1
            
            lit_value = s[lit_start:pos]
            if lit_value:
                parts.append({'kind': 'literal', 'value': lit_value})
        
        if not has_interp:
            return None
        
        # Merge adjacent literal parts
        merged = []
        for p in parts:
            if merged and merged[-1]['kind'] == 'literal' and p['kind'] == 'literal':
                merged[-1]['value'] += p['value']
            else:
                merged.append(p)
        
        # If all parts are literals (e.g. only escaped \#{), return None for plain string
        if all(p['kind'] == 'literal' for p in merged):
            # Reconstruct the full literal value
            full_value = ''.join(p['value'] for p in merged)
            return None
        
        return {"type": "InterpolatedString", "parts": merged}

    @v_args(inline=True)
    def string_expr(self, s):
        'P3-1: Enhanced string_expr — detects #{...} interpolation in string content.\nWithout interpolation: returns StringLiteral.\nWith interpolation: returns InterpolatedString with parts.'
        raw = str(s).strip('"')
        # Try to parse interpolation
        interp_result = self._parse_string_interpolation(raw)
        if interp_result is not None:
            return interp_result
        # No interpolation — plain string literal
        return {"type": "StringLiteral", "value": raw}

    @v_args(inline=True)
    def id_expr(self, i):
        return {"type": "Identifier", "value": str(i)}

    @v_args(inline=False)
    def binary_expr(self, args):
        """二元表达式：支持加减乘除 - v1.0.1-beta
        语法: binary_expr: base_expr BINARY_OP base_expr
        使用 BINARY_OP 终端确保操作符正确匹配
        """
        if len(args) == 1:
            return args[0]
        
        # args 是 [left, BINARY_OP token, right]
        from lark import Token
        if len(args) == 3:
            op = args[1]
            if isinstance(op, Token):
                op = str(op)
            return {
                "type": "BinaryExpression",
                "left": args[0],
                "operator": op,
                "right": args[2]
            }
        
        # 兼容旧语法: base_expr ("+" base_expr)+
        result = args[0]
        for i in range(1, len(args)):
            right = args[i]
            result = {
                "type": "BinaryExpression",
                "operator": "+",
                "left": result,
                "right": right
            }
        return result

    @v_args(inline=False)
    def binary_op(self, args):
        """二元运算符"""
        return str(args[0]) if args else "+"

    @v_args(inline=True)
    def int_expr(self, val):
        """整数字面量"""
        return {"type": "IntLiteral", "value": int(val)}

    @v_args(inline=True)
    def float_expr(self, val):
        """浮点数字面量"""
        return {"type": "FloatLiteral", "value": float(val)}

    @v_args(inline=False)
    def true_expr(self, args):
        """布尔 true"""
        return {"type": "BooleanLiteral", "value": True}

    @v_args(inline=False)
    def false_expr(self, args):
        """布尔 false"""
        return {"type": "BooleanLiteral", "value": False}

    @v_args(inline=True)
    def multiline_string_expr(self, val):
        """多行字符串表达式"""
        s = str(val)
        if s.startswith('"""') and s.endswith('"""'):
            return {"type": "StringLiteral", "value": s[3:-3]}
        return {"type": "StringLiteral", "value": s}

    # ===== P2-4: Template System (模板系统) =====

    @v_args(inline=False)
    def template_string_expr(self, args):
        '''P2-4: template"""...""" expression handler

        Strips the """ wrapper from TEMPLATE_STRING token,
        then calls NexaTemplateParser to parse template content
        into structured TemplatePart list.

        Returns AST node: {"type": "TemplateStringExpr", "parts": [...]}
        '''
        # args[0] is the TEMPLATE_STRING token value
        raw = str(args[0])

        # Strip the """ wrapper
        if raw.startswith('"""') and raw.endswith('"""'):
            content = raw[3:-3]
        else:
            content = raw

        # Parse template content into TemplatePart objects
        parser = NexaTemplateParser()
        template_parts = parser.parse_template_content(content)

        # Convert TemplatePart objects to dicts for AST serialization
        parts_dicts = [p.to_dict() for p in template_parts]

        return {
            "type": "TemplateStringExpr",
            "parts": parts_dicts,
            "raw_content": content,
        }

    @v_args(inline=False)
    def std_call(self, args):
        """标准库调用: std.ns.func(...)"""
        return {
            "type": "StdCallExpression",
            "namespace": str(args[0]),
            "function": str(args[1]),
            "arguments": args[2] if len(args) > 2 else []
        }

    @v_args(inline=False)
    def semantic_if_expr(self, args):
        """semantic_if 表达式形式: semantic_if (var, "condition") { ... }"""
        return {
            "type": "SemanticIfExpression",
            "variable": str(args[0]),
            "condition": str(args[1]).strip('"'),
            "cases": args[2]
        }

    @v_args(inline=False)
    def semantic_if_block(self, args):
        """semantic_if 块: { "case1" => action1 }"""
        return args

    @v_args(inline=False)
    def semantic_if_case(self, args):
        """semantic_if case: "case" => action"""
        return {
            "pattern": str(args[0]).strip('"'),
            "action": args[1]
        }

    @v_args(inline=True)
    def string_val(self, s):
        return str(s).strip('"')

    @v_args(inline=True)
    def int_val(self, i):
        return int(i)

    @v_args(inline=True)
    def true_val(self):
        return True

    @v_args(inline=True)
    def false_val(self):
        return False

    @v_args(inline=False)
    def fallback_list_val(self, args):
        """处理 fallback_list_val 节点"""
        return args[0]

    @v_args(inline=False)
    def fallback_list(self, args):
        """处理 fallback_list，返回带 fallback 标记的列表"""
        result = []
        for item in args:
            if isinstance(item, dict):
                result.append(item)
            else:
                result.append({"value": str(item).strip('"'), "is_fallback": False})
        return {"type": "fallback_list", "models": result}

    @v_args(inline=True)
    def primary_model(self, item):
        """处理主模型"""
        from lark import Token
        if isinstance(item, Token):
            value = str(item).strip('"')
            return {"value": value, "is_fallback": False}
        return {"value": str(item).strip('"'), "is_fallback": False}

    @v_args(inline=True)
    def fallback_model(self, item):
        """处理 fallback 模型"""
        from lark import Token
        if isinstance(item, Token):
            value = str(item).strip('"')
            return {"value": value, "is_fallback": True}
        return {"value": str(item).strip('"'), "is_fallback": True}

    @v_args(inline=False)
    def if_stmt(self, args):
        """if 语句"""
        condition = args[0]
        then_block = args[1]
        else_block = args[2] if len(args) > 2 else []
        return {
            "type": "IfStatement",
            "condition": condition,
            "then_block": then_block,
            "else_block": else_block
        }

    @v_args(inline=False)
    def condition(self, args):
        """条件表达式"""
        return {
            "type": "ConditionExpression",
            "left": args[0],
            "operator": str(args[1]),
            "right": args[2]
        }

    @v_args(inline=False)
    def comparison_op(self, args):
        """比较运算符"""
        return str(args[0]) if args else "=="

    @v_args(inline=False)
    def comparison_expr(self, args):
        """比较表达式"""
        if len(args) == 1:
            # 简单表达式（无比较运算符）
            return args[0]
        return {
            "type": "ComparisonExpression",
            "left": args[0],
            "operator": str(args[1]),
            "right": args[2]
        }

    @v_args(inline=True)
    def string_expr(self, s):
        'P3-1: Enhanced string_expr — detects #{...} interpolation in string content.\nWithout interpolation: returns StringLiteral.\nWith interpolation: returns InterpolatedString with parts.'
        raw = str(s).strip('"')
        interp_result = NexaTransformer._parse_string_interpolation(raw)
        if interp_result is not None:
            return interp_result
        return {"type": "StringLiteral", "value": raw}

    @v_args(inline=True)
    def id_expr(self, i):
        return {"type": "Identifier", "value": str(i)}

    # ===== P3-2: Pipe Operator (管道操作符) =====

    @v_args(inline=False)
    def pipe_chain_expr(self, args):
        '''P3-2: Pipe chain expression - desugars |> to nested function calls

        x |> f        => FunctionCallExpression{function: f, arguments: [x]}
        x |> f(a, b)  => FunctionCallExpression{function: f, arguments: [x, a, b]}
        x |> f |> g   => FunctionCallExpression{function: g, arguments: [FunctionCallExpression{...}]}
        '''
        # Filter out "|>" anonymous terminal tokens (keep only dict AST nodes)
        steps = [a for a in args if isinstance(a, dict)]
        if not steps:
            return {"type": "Identifier", "value": "None"}
        result = steps[0]  # leftmost expression
        for right in steps[1:]:
            result = self._desugar_pipe_step(result, right)
        return result

    def _desugar_pipe_step(self, left, right):
        '''Desugar a single pipe step: left |> right

        Insert left as the first argument of right's function call.
        If right is an Identifier, wrap it as a FunctionCallExpression.
        If right is already a call expression, prepend left to its arguments.
        '''
        if isinstance(right, dict):
            right_type = right.get('type', '')
            if right_type == 'FunctionCallExpression':
                # f(a, b) => f(left, a, b)
                new_args = [left] + right.get('arguments', [])
                return {
                    'type': 'FunctionCallExpression',
                    'function': right.get('function', ''),
                    'arguments': new_args
                }
            elif right_type == 'MethodCallExpression':
                # obj.method(a) => obj.method(left, a)
                new_args = [left] + right.get('arguments', [])
                return {
                    'type': 'MethodCallExpression',
                    'object': right.get('object', ''),
                    'method': right.get('method', ''),
                    'arguments': new_args
                }
            elif right_type == 'StdCallExpression':
                # std.ns.func(a) => std.ns.func(left, a)
                new_args = [left] + right.get('arguments', [])
                return {
                    'type': 'StdCallExpression',
                    'namespace': right.get('namespace', ''),
                    'function': right.get('function', ''),
                    'arguments': new_args
                }
            elif right_type == 'PropertyAccess':
                # obj.method => MethodCallExpression(left, obj=base, method=prop)
                # std.text.upper => StdCallExpression(left, namespace=mid, function=prop)
                base_val = right.get('base', '')
                prop_val = right.get('property', '')
                # Check if this is a std.xxx.yyy pattern
                if isinstance(base_val, dict) and base_val.get('type') == 'PropertyAccess':
                    # nested property: std.text.upper -> base=std.text, prop=upper
                    inner_base = base_val.get('base', '')
                    inner_prop = base_val.get('property', '')
                    if inner_base == 'std' or (isinstance(inner_base, dict) and inner_base.get('value') == 'std'):
                        return {
                            'type': 'StdCallExpression',
                            'namespace': inner_prop,
                            'function': prop_val,
                            'arguments': [left]
                        }
                # Single-level property: obj.method -> MethodCallExpression
                if isinstance(base_val, str):
                    obj_name = base_val
                elif isinstance(base_val, dict):
                    obj_name = base_val.get('value', base_val.get('name', str(base_val)))
                else:
                    obj_name = str(base_val)
                return {
                    'type': 'MethodCallExpression',
                    'object': obj_name,
                    'method': prop_val,
                    'arguments': [left]
                }
            elif right_type == 'Identifier':
                # f => f(left)
                return {
                    'type': 'FunctionCallExpression',
                    'function': right.get('value', ''),
                    'arguments': [left]
                }
            else:
                # Unknown type - treat as function name with left as arg
                func_name = right.get('value', right.get('name', str(right)))
                return {
                    'type': 'FunctionCallExpression',
                    'function': func_name,
                    'arguments': [left]
                }
        else:
            # String or other simple value - treat as function name
            return {
                'type': 'FunctionCallExpression',
                'function': str(right),
                'arguments': [left]
            }

    # ===== P3-5: Defer Statement (延迟执行) =====

    @v_args(inline=False)
    def defer_stmt(self, args):
        '''P3-5: defer statement - execute expression when scope exits (LIFO order)

        defer expression; - like Go's defer, executes on scope exit even if error occurs
        '''
        # Filter out "defer" and ";" anonymous terminal tokens (keep only dict AST nodes)
        expr_parts = [a for a in args if isinstance(a, dict)]
        expr = expr_parts[0] if expr_parts else None
        return {
            'type': 'DeferStatement',
            'expression': expr
        }

    # ===== P3-6: Null Coalescing (空值合并) =====

    @v_args(inline=False)
    def null_coalesce_expr(self, args):
        '''P3-6: Null coalescing expression - expr ?? fallback

        If left is None/Option::None/empty dict -> return right, otherwise return left.
        Chained: a ?? b ?? c => try a, then b, then c.
        Stores all parts for code generator to produce nested _nexa_null_coalesce calls.
        '''
        # Filter out "??" anonymous terminal tokens (keep only dict AST nodes)
        parts = [a for a in args if isinstance(a, dict)]
        # Flatten nested NullCoalesceExpression parts (from ambiguous parse alternatives)
        # e.g., NullCoalesceExpr(parts: [a, NullCoalesceExpr(parts: [b, c])])
        #     => NullCoalesceExpr(parts: [a, b, c])
        flat_parts = []
        for p in parts:
            if isinstance(p, dict) and p.get('type') == 'NullCoalesceExpression':
                flat_parts.extend(p.get('parts', []))
            else:
                flat_parts.append(p)
        return {
            'type': 'NullCoalesceExpression',
            'parts': flat_parts
        }

    # ===== P3-4: ADT — Struct/Enum/Trait/Impl =====

    @v_args(inline=False)
    def struct_decl(self, args):
        'P3-4: struct declaration - struct Name { field1: Type1, field2: Type2 }'
        # Filter out anonymous terminals ("struct", "{", "}", ",")
        str_args = [str(a) for a in args if not isinstance(a, dict)]
        dict_args = [a for a in args if isinstance(a, dict)]
        name = str_args[0] if str_args else ''
        fields = dict_args
        return {
            'type': 'StructDeclaration',
            'name': name,
            'fields': fields,
        }

    @v_args(inline=False)
    def struct_field(self, args):
        'P3-4: struct field - name [: Type]'
        field_name = str(args[0])
        field_type = None
        for a in args[1:]:
            if not isinstance(a, dict) and str(a) != ':' and str(a) != ',' and str(a) != '{' and str(a) != '}':
                field_type = str(a)
                break
            elif isinstance(a, dict) and a.get('type') == 'Identifier':
                field_type = a.get('value', '')
                break
        return {
            'type': 'StructField',
            'name': field_name,
            'field_type': field_type,
        }

    @v_args(inline=False)
    def enum_decl(self, args):
        'P3-4: enum declaration - enum Name { Variant1(field1), Variant2 }'
        # Filter out anonymous terminals ("enum", "{", "}", ",")
        str_args = [str(a) for a in args if not isinstance(a, dict)]
        dict_args = [a for a in args if isinstance(a, dict)]
        name = str_args[0] if str_args else ''
        variants = dict_args
        return {
            'type': 'EnumDeclaration',
            'name': name,
            'variants': variants,
        }

    @v_args(inline=False)
    def enum_variant(self, args):
        'P3-4: enum variant - VariantName [(field_types)]'
        # args: variant_name, optionally "(" field_type1 "," field_type2 ")"
        str_args = [str(a) for a in args]
        variant_name = str_args[0] if str_args else ''
        # Collect field type names (everything after variant_name that is not a punctuation terminal)
        field_types = []
        for a in args[1:]:
            s = str(a)
            # Skip punctuation: commas, parens from optional group
            if s in ('(', ')', ',', '::'):
                continue
            if isinstance(a, dict) and a.get('type') == 'Identifier':
                field_types.append(a.get('value', s))
            elif isinstance(a, lark.Token) and a not in ('(', ')', ',', '::'):
                field_types.append(s)
        return {
            'type': 'EnumVariant',
            'name': variant_name,
            'fields': field_types,
        }

    @v_args(inline=False)
    def trait_decl(self, args):
        'P3-4: trait declaration - trait Name { fn method(params) -> RetType, ... }'
        # Filter out anonymous terminals ("trait", "{", "}", ",")
        str_args = [str(a) for a in args if not isinstance(a, dict)]
        dict_args = [a for a in args if isinstance(a, dict)]
        name = str_args[0] if str_args else ''
        methods = dict_args
        return {
            'type': 'TraitDeclaration',
            'name': name,
            'methods': methods,
        }

    @v_args(inline=False)
    def trait_method(self, args):
        'P3-4: trait method signature - fn name(params) [: RetType]'
        # args: "fn", method_name, "(", params..., ")", [":"], [return_type]
        str_args = [str(a) for a in args if not isinstance(a, dict)]
        dict_args = [a for a in args if isinstance(a, dict)]
        method_name = ''
        for a in args:
            s = str(a)
            if s == 'fn' or s == '(' or s == ')' or s == ':' or s == ',':
                continue
            if isinstance(a, dict):
                continue
            if method_name == '':
                method_name = s
                break
        # If no method_name found from tokens, try dict_args
        if method_name == '' and dict_args:
            method_name = dict_args[0].get('value', '') if dict_args[0].get('type') == 'Identifier' else str(dict_args[0])

        # Collect params from dict_args (they may be Param nodes or Identifier nodes)
        params = []
        return_type = None
        for a in dict_args:
            if isinstance(a, dict):
                if a.get('type') == 'Param':
                    params.append(a)
                elif a.get('type') == 'Identifier':
                    # Could be a param or return type; check context
                    # If we have ":" before this identifier, it's a return type
                    # Simple heuristic: the last Identifier after all params is return type
                    params.append(a)
        # Detect return type: look for ":" followed by identifier at end
        has_ret_marker = ':' in str_args
        if has_ret_marker and dict_args:
            # The last identifier after the colon is the return type
            last_dict = dict_args[-1]
            if last_dict.get('type') == 'Identifier':
                return_type = last_dict.get('value', str(last_dict))
                # Remove it from params
                if last_dict in params:
                    params.remove(last_dict)

        return {
            'type': 'TraitMethod',
            'name': method_name,
            'params': params,
            'return_type': return_type,
        }

    @v_args(inline=False)
    def impl_decl(self, args):
        'P3-4: impl declaration - impl TraitName for TypeName { fn method(params) { body }, ... }'
        # args: "impl", trait_name, "for", type_name, "{", impl_methods..., "}"
        str_args = [str(a) for a in args if not isinstance(a, dict)]
        dict_args = [a for a in args if isinstance(a, dict)]
        # Extract trait_name and type_name from string args (skip "impl", "for", braces)
        trait_name = ''
        type_name = ''
        for a in args:
            s = str(a)
            if s == 'impl' or s == 'for' or s == '{' or s == '}' or s == ',':
                continue
            if isinstance(a, dict):
                continue
            if trait_name == '':
                trait_name = s
            elif type_name == '':
                type_name = s
        # If trait_name/type_name not found from string tokens, try dict_args
        if trait_name == '' and len(dict_args) >= 1:
            d = dict_args[0]
            if isinstance(d, dict) and d.get('type') == 'Identifier':
                trait_name = d.get('value', '')
        if type_name == '' and len(dict_args) >= 2:
            d = dict_args[1]
            if isinstance(d, dict) and d.get('type') == 'Identifier':
                type_name = d.get('value', '')

        # impl_methods are dict_args (skip first two if they were trait/type identifiers)
        impl_methods = [a for a in dict_args if isinstance(a, dict) and a.get('type') == 'ImplMethod']
        # If no ImplMethod dicts found, try all dict_args after first two
        if not impl_methods:
            impl_methods = dict_args[2:] if len(dict_args) > 2 else dict_args

        return {
            'type': 'ImplDeclaration',
            'trait_name': trait_name,
            'type_name': type_name,
            'methods': impl_methods,
        }

    @v_args(inline=False)
    def impl_method(self, args):
        'P3-4: impl method - fn method_name(params) { body }'
        # args: "fn", method_name, "(", params..., ")", block
        str_args = [str(a) for a in args if not isinstance(a, dict)]
        dict_args = [a for a in args if isinstance(a, dict)]
        method_name = ''
        for a in args:
            s = str(a)
            if s == 'fn' or s == '(' or s == ')' or s == ',' or s == ':':
                continue
            if isinstance(a, dict):
                continue
            if method_name == '':
                method_name = s
                break
        if method_name == '' and dict_args:
            d = dict_args[0]
            if isinstance(d, dict) and d.get('type') == 'Identifier':
                method_name = d.get('value', '')

        # Collect params and body from dict_args
        params = []
        body = []
        for a in dict_args:
            if isinstance(a, dict):
                if a.get('type') == 'Param':
                    params.append(a)
                elif a.get('type') == 'Identifier':
                    params.append(a)
                elif a.get('type') == 'Block':
                    body = a.get('statements', [])
                elif a.get('type') == 'ImplMethod':
                    # Nested impl_method — skip
                    pass

        return {
            'type': 'ImplMethod',
            'name': method_name,
            'params': params,
            'body': body,
        }

    @v_args(inline=False)
    def variant_call_expr(self, args):
        'P3-4: variant call expression — Enum::Variant(args) as an expression'
        # args: enum_name, "::", variant_name, optionally "(" arguments... ")"
        str_args = [str(a) for a in args if not isinstance(a, dict)]
        dict_args = [a for a in args if isinstance(a, dict)]
        enum_name = str_args[0] if len(str_args) >= 1 else ''
        variant_name = str_args[1] if len(str_args) >= 2 else ''
        # Arguments are dict_args (expressions)
        arguments = dict_args
        return {
            'type': 'VariantCallExpression',
            'enum_name': enum_name,
            'variant_name': variant_name,
            'arguments': arguments,
        }

    @v_args(inline=False)
    def field_init(self, args):
        'P3-4: field init expression — field_name: expression (for struct constructor calls like Point(x: 1, y: 2))'
        field_name = str(args[0])
        # Find the expression value (skip ":" terminal)
        value = None
        for a in args[1:]:
            if isinstance(a, dict):
                value = a
            elif str(a) != ':':
                # Could be a simple value (identifier, number, string)
                pass
        if value is None:
            # Try to construct from remaining args
            remaining = [a for a in args[1:] if str(a) != ':']
            if remaining:
                value = {"type": "Identifier", "value": str(remaining[0])}
        return {
            'type': 'FieldInitExpression',
            'key': field_name,
            'value': value,
        }


    @v_args(inline=False)
    def simple_param_list(self, args):
        'P3-4: simple parameter list for trait/impl methods - just identifiers, no types'
        params = []
        for a in args:
            if isinstance(a, dict) and a.get('type') == 'Identifier':
                params.append(a)
            elif isinstance(a, lark.Token):
                params.append({'type': 'Identifier', 'value': str(a)})
        return params


if __name__ == "__main__":
    from nexa_parser import parse
    import os
    
    import sys
    example_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '../examples/01_hello_world.nx')
    with open(example_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    print("\n" + "="*50)
    print("🛡️ [Nexa Transformer] Starting AST Generation...")
    print("="*50)
    
    tree = parse(code)
    transformer = NexaTransformer()
    ast = transformer.transform(tree)
    
    # 强制在终端输出美化后的结构
    print("\n🟢 AST Generated Successfully! Dump:\n")
    print(json.dumps(ast, indent=2, ensure_ascii=False))
    print("="*50)
