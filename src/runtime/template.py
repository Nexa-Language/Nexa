'''
Nexa Template System -- Agent-Native template rendering engine

Core concepts:
- NexaTemplateRenderer: Template rendering engine with 30+ filters
- template/compile/render: External template file API (mtime-based cache)
- Agent-Native extensions: agent_template_prompt, agent_template_slot_fill, agent_template_register
- Handle-as-dict pattern: {"_nexa_template_id": int} for compiled templates
- Thread-safe registry: _registry_lock + ID counter
- ContractViolation integration: requires/ensures for template operations

Nexa differentiation (vs NTNT):
- Agent Prompt template: auto-inject agent context into template variables
- Multi-source Slot Fill: priority-based variable resolution (explicit > auth > kv > memory > agent_attrs)
- Agent Template Registry: per-agent template registration and listing

No new external dependencies: html + json + os + threading + time (all Python stdlib)
'''

import html
import json
import os
import threading
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

from .contracts import ContractViolation


# ==================== Global Registry ====================

_template_registry: Dict[int, 'CompiledTemplate'] = {}
_template_id_counter: int = 0
_registry_lock = threading.Lock()

# Agent template registry (name -> template_str)
_agent_template_registry: Dict[str, Dict] = {}
_agent_template_lock = threading.Lock()


def _next_template_id() -> int:
    'Generate next template ID (thread-safe)'
    global _template_id_counter
    with _registry_lock:
        _template_id_counter += 1
        return _template_id_counter


def _register_template(tid: int, compiled: 'CompiledTemplate') -> None:
    'Register compiled template to global registry'
    with _registry_lock:
        _template_registry[tid] = compiled


def _unregister_template(tid: int) -> None:
    'Remove compiled template from global registry'
    with _registry_lock:
        _template_registry.pop(tid, None)


def _get_template(tid: int) -> Optional['CompiledTemplate']:
    'Get compiled template from global registry'
    with _registry_lock:
        return _template_registry.get(tid)


def get_active_templates() -> Dict[int, str]:
    'Get all active template handles (for debugging)'
    with _registry_lock:
        return {tid: ct.path for tid, ct in _template_registry.items()}


# ==================== CompiledTemplate ====================

class CompiledTemplate:
    'Compiled template with mtime-based cache auto-reload'

    def __init__(self, path: str, parts: List, mtime: float):
        self.path = path
        self.parts = parts
        self.mtime = mtime  # Last modification time for cache invalidation

    def is_stale(self) -> bool:
        'Check if template file has been modified since compilation'
        if not self.path or not os.path.exists(self.path):
            return False
        try:
            current_mtime = os.path.getmtime(self.path)
            return current_mtime > self.mtime
        except OSError:
            return False

    def to_dict(self) -> Dict:
        'Convert to handle-as-dict format'
        return {
            '_nexa_template_id': self.id if hasattr(self, 'id') else 0,
            'path': self.path
        }


# ==================== HTML Escape Helper ====================

def _nexa_tpl_escape(value: Any) -> str:
    'HTML auto-escape -- {{expr}} calls this by default'
    return html.escape(str(value))


def _nexa_tpl_join(parts: List) -> str:
    'Join template rendering result parts'
    return ''.join(str(p) if p is not None else '' for p in parts)


def _nexa_tpl_safe_str(value: Any) -> str:
    'Safe string conversion: undefined -> empty string'
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


# ==================== 30+ Filter Functions ====================

def filter_upper(value: Any) -> str:
    'Uppercase filter'
    return _nexa_tpl_safe_str(value).upper()


def filter_uppercase(value: Any) -> str:
    'Uppercase filter (alias)'
    return filter_upper(value)


def filter_lower(value: Any) -> str:
    'Lowercase filter'
    return _nexa_tpl_safe_str(value).lower()


def filter_lowercase(value: Any) -> str:
    'Lowercase filter (alias)'
    return filter_lower(value)


def filter_capitalize(value: Any) -> str:
    'Capitalize first letter filter'
    return _nexa_tpl_safe_str(value).capitalize()


def filter_trim(value: Any) -> str:
    'Trim whitespace filter'
    return _nexa_tpl_safe_str(value).strip()


def filter_truncate(value: Any, length: int = 100) -> str:
    'Truncate to length filter'
    s = _nexa_tpl_safe_str(value)
    if len(s) <= length:
        return s
    return s[:length] + '...'


def filter_replace(value: Any, from_str: str = '', to_str: str = '') -> str:
    'Replace substring filter'
    return _nexa_tpl_safe_str(value).replace(from_str, to_str)


def filter_escape(value: Any) -> str:
    'HTML escape filter (explicit)'
    return html.escape(_nexa_tpl_safe_str(value))


def filter_raw(value: Any) -> str:
    'No-escape filter (mark as safe)'
    return _nexa_tpl_safe_str(value)


def filter_safe(value: Any) -> str:
    'No-escape filter (alias for raw)'
    return filter_raw(value)


def filter_default(value: Any, default_value: Any = '') -> str:
    'Default value filter -- undefined/empty -> default'
    if value is None or value == '' or value == []:
        return _nexa_tpl_safe_str(default_value)
    return _nexa_tpl_safe_str(value)


def filter_length(value: Any) -> str:
    'Length filter -- returns length of string/list/dict'
    if isinstance(value, (str, list, dict)):
        return str(len(value))
    return '0'


def filter_first(value: Any) -> str:
    'First element filter'
    if isinstance(value, list) and len(value) > 0:
        return _nexa_tpl_safe_str(value[0])
    if isinstance(value, str) and len(value) > 0:
        return value[0]
    return ''


def filter_last(value: Any) -> str:
    'Last element filter'
    if isinstance(value, list) and len(value) > 0:
        return _nexa_tpl_safe_str(value[-1])
    if isinstance(value, str) and len(value) > 0:
        return value[-1]
    return ''


def filter_reverse(value: Any) -> str:
    'Reverse filter -- reverses string or list'
    if isinstance(value, list):
        return json.dumps(value[::-1])
    if isinstance(value, str):
        return value[::-1]
    return _nexa_tpl_safe_str(value)


def filter_join(value: Any, separator: str = ',') -> str:
    'Join filter -- join list with separator'
    if isinstance(value, list):
        return separator.join([_nexa_tpl_safe_str(v) for v in value])
    return _nexa_tpl_safe_str(value)


def filter_slice(value: Any, start: int = 0, end: int = None) -> str:
    'Slice filter -- slice string or list'
    if isinstance(value, list):
        sliced = value[start:end]
        return json.dumps(sliced)
    if isinstance(value, str):
        return value[start:end]
    return _nexa_tpl_safe_str(value)


def filter_json(value: Any) -> str:
    'JSON serialize filter'
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return _nexa_tpl_safe_str(value)


def filter_number(value: Any, decimals: int = 2) -> str:
    'Number format filter -- format number with decimal places'
    try:
        num = float(value)
        return f'{num:.{decimals}f}'
    except (TypeError, ValueError):
        return _nexa_tpl_safe_str(value)


def filter_url_encode(value: Any) -> str:
    'URL encode filter'
    return urllib.parse.quote(_nexa_tpl_safe_str(value))


def filter_strip_tags(value: Any) -> str:
    'Strip HTML tags filter'
    import re
    return re.sub(r'<[^>]+>', '', _nexa_tpl_safe_str(value))


def filter_word_count(value: Any) -> str:
    'Word count filter'
    return str(len(_nexa_tpl_safe_str(value).split()))


def filter_line_count(value: Any) -> str:
    'Line count filter'
    return str(len(_nexa_tpl_safe_str(value).splitlines()))


def filter_indent(value: Any, indent_size: int = 2) -> str:
    'Indent filter -- indent each line'
    lines = _nexa_tpl_safe_str(value).splitlines()
    indent_str = ' ' * indent_size
    return '\n'.join([indent_str + line for line in lines])


def filter_date(value: Any, fmt: str = '%Y-%m-%d') -> str:
    'Date format filter -- format timestamp or date string'
    try:
        if isinstance(value, (int, float)):
            return time.strftime(fmt, time.localtime(value))
        return _nexa_tpl_safe_str(value)
    except (TypeError, ValueError):
        return _nexa_tpl_safe_str(value)


def filter_sort(value: Any) -> str:
    'Sort filter -- sort list'
    if isinstance(value, list):
        try:
            return json.dumps(sorted(value))
        except TypeError:
            return json.dumps(value)
    return _nexa_tpl_safe_str(value)


def filter_unique(value: Any) -> str:
    'Unique filter -- deduplicate list'
    if isinstance(value, list):
        try:
            return json.dumps(list(set(value)))
        except TypeError:
            return json.dumps(value)
    return _nexa_tpl_safe_str(value)


def filter_abs(value: Any) -> str:
    'Absolute value filter'
    try:
        return str(abs(float(value)))
    except (TypeError, ValueError):
        return '0'


def filter_ceil(value: Any) -> str:
    'Ceiling filter'
    try:
        import math
        return str(math.ceil(float(value)))
    except (TypeError, ValueError):
        return '0'


def filter_floor(value: Any) -> str:
    'Floor filter'
    try:
        import math
        return str(math.floor(float(value)))
    except (TypeError, ValueError):
        return '0'


# ==================== Filter Registry ====================

FILTER_REGISTRY: Dict[str, Any] = {
    'upper': filter_upper,
    'uppercase': filter_uppercase,
    'lower': filter_lower,
    'lowercase': filter_lowercase,
    'capitalize': filter_capitalize,
    'trim': filter_trim,
    'truncate': filter_truncate,
    'replace': filter_replace,
    'escape': filter_escape,
    'raw': filter_raw,
    'safe': filter_safe,
    'default': filter_default,
    'length': filter_length,
    'first': filter_first,
    'last': filter_last,
    'reverse': filter_reverse,
    'join': filter_join,
    'slice': filter_slice,
    'json': filter_json,
    'number': filter_number,
    'url_encode': filter_url_encode,
    'strip_tags': filter_strip_tags,
    'word_count': filter_word_count,
    'line_count': filter_line_count,
    'indent': filter_indent,
    'date': filter_date,
    'sort': filter_sort,
    'unique': filter_unique,
    'abs': filter_abs,
    'ceil': filter_ceil,
    'floor': filter_floor,
}


def apply_filter_chain(value: Any, filters: List[Dict]) -> str:
    'Apply a chain of filters to a value'

    result = value
    for f in filters:
        fname = f.get('name', '')
        fargs = f.get('args', [])

        filter_fn = FILTER_REGISTRY.get(fname)
        if filter_fn is None:
            # Unknown filter: pass through (error boundary)
            continue

        try:
            if fargs:
                result = filter_fn(result, *fargs)
            else:
                result = filter_fn(result)
        except (TypeError, ValueError) as e:
            # Filter error: pass through (error boundary)
            continue

    return _nexa_tpl_safe_str(result)


# ==================== NexaTemplateRenderer ====================

class NexaTemplateRenderer:
    'Template rendering engine with filter support and error boundaries'

    def __init__(self, type_mode: str = 'warn'):
        '''
        Args:
            type_mode: Error handling mode
                - strict: raise ContractViolation on errors
                - warn: log warning, return empty/default
                - silent: silently return empty/default
        '''
        self.type_mode = type_mode
        self.filters = FILTER_REGISTRY

    def render_parts(self, parts: List[Dict], data: Dict) -> str:
        'Render a list of TemplatePart dicts with data context'

        result = []
        for part in parts:
            rendered = self._render_part(part, data)
            result.append(rendered)

        return _nexa_tpl_join(result)

    def _render_part(self, part: Dict, data: Dict) -> str:
        'Render a single TemplatePart'

        kind = part.get('kind', 'literal')

        if kind == 'literal':
            return part.get('value', '')

        elif kind == 'expr':
            # {{expr}} -- auto HTML escape
            var_name = part.get('value', '')
            value = self._resolve_var(var_name, data)
            return _nexa_tpl_escape(_nexa_tpl_safe_str(value))

        elif kind == 'raw_expr':
            # {{{expr}}} -- no escape
            var_name = part.get('value', '')
            value = self._resolve_var(var_name, data)
            return _nexa_tpl_safe_str(value)

        elif kind == 'filtered_expr':
            # {{expr | filter1 | filter2(arg)}} -- escape after filters
            var_name = part.get('value', '')
            filters = part.get('filters', [])
            value = self._resolve_var(var_name, data)
            filtered = apply_filter_chain(value, filters)
            return _nexa_tpl_escape(filtered)

        elif kind == 'raw_filtered_expr':
            # {{{expr | filter}}} -- no escape after filters
            var_name = part.get('value', '')
            filters = part.get('filters', [])
            value = self._resolve_var(var_name, data)
            return apply_filter_chain(value, filters)

        elif kind == 'for_loop':
            return self._render_for_loop(part, data)

        elif kind == 'if_block':
            return self._render_if_block(part, data)

        elif kind == 'partial':
            return self._render_partial(part, data)

        # Unknown kind: error boundary
        return ''

    def _resolve_var(self, var_name: str, data: Dict) -> Any:
        'Resolve a variable name from data context (supports dot access)'

        if not var_name:
            return None

        # Handle @metadata variables (for-loop context)
        if var_name.startswith('@'):
            return data.get(var_name)

        # Handle dot-access: user.name -> data["user"]["name"]
        parts = var_name.split('.')
        current = data

        for p in parts:
            if isinstance(current, dict):
                current = current.get(p)
            elif isinstance(current, list):
                try:
                    current = current[int(p)]
                except (ValueError, IndexError):
                    return None
            else:
                return None

            if current is None:
                return None

        return current

    def _resolve_condition(self, condition: str, data: Dict) -> bool:
        'Resolve a condition expression to boolean'

        if not condition:
            return False

        # Try simple variable lookup
        value = self._resolve_var(condition, data)
        if value is not None:
            return bool(value)

        # Try comparison: var == 'val' or var != 'val'
        # Support: role == 'admin', count > 5, etc.
        import re

        # == comparison
        eq_match = re.match(r'(\w+(?:\.\w+)*)\s*==\s*["\']?([^"\']*)["\']?', condition)
        if eq_match:
            left_var = eq_match.group(1)
            right_val = eq_match.group(2)
            left_val = self._resolve_var(left_var, data)
            return _nexa_tpl_safe_str(left_val) == right_val

        # != comparison
        ne_match = re.match(r'(\w+(?:\.\w+)*)\s*!=\s*["\']?([^"\']*)["\']?', condition)
        if ne_match:
            left_var = ne_match.group(1)
            right_val = ne_match.group(2)
            left_val = self._resolve_var(left_var, data)
            return _nexa_tpl_safe_str(left_val) != right_val

        # > comparison (numeric)
        gt_match = re.match(r'(\w+(?:\.\w+)*)\s*>\s*(\d+)', condition)
        if gt_match:
            left_var = gt_match.group(1)
            right_val = float(gt_match.group(2))
            left_val = self._resolve_var(left_var, data)
            try:
                return float(left_val) > right_val
            except (TypeError, ValueError):
                return False

        # < comparison (numeric)
        lt_match = re.match(r'(\w+(?:\.\w+)*)\s*<\s*(\d+)', condition)
        if lt_match:
            left_var = lt_match.group(1)
            right_val = float(lt_match.group(2))
            left_val = self._resolve_var(left_var, data)
            try:
                return float(left_val) < right_val
            except (TypeError, ValueError):
                return False

        # Fallback: try as boolean
        try:
            return bool(value)
        except (TypeError, ValueError):
            if self.type_mode == 'strict':
                raise ContractViolation(
                    f'Template condition evaluation failed: {condition}',
                    clause_type='requires'
                )
            return False

    def _render_for_loop(self, part: Dict, data: Dict) -> str:
        'Render a for-loop TemplatePart'

        var_name = part.get('var', 'item')
        iterable_name = part.get('iterable', 'items')
        body_parts = part.get('body', [])
        empty_body = part.get('empty_body', [])

        iterable = self._resolve_var(iterable_name, data)

        # Error boundary: undefined/non-iterable -> empty_body or empty
        if iterable is None or not isinstance(iterable, (list, tuple)):
            if empty_body:
                return self.render_parts(empty_body, data)
            return ''

        if len(iterable) == 0:
            if empty_body:
                return self.render_parts(empty_body, data)
            return ''

        result = []
        length = len(iterable)

        for index, item in enumerate(iterable):
            # Create loop context with metadata
            loop_data = {**data}  # Copy parent context
            loop_data[var_name] = item
            loop_data['@index'] = index
            loop_data['@index1'] = index + 1
            loop_data['@first'] = index == 0
            loop_data['@last'] = index == length - 1
            loop_data['@length'] = length
            loop_data['@even'] = index % 2 == 0
            loop_data['@odd'] = index % 2 == 1

            rendered = self.render_parts(body_parts, loop_data)
            result.append(rendered)

        return _nexa_tpl_join(result)

    def _render_if_block(self, part: Dict, data: Dict) -> str:
        'Render an if-block TemplatePart'

        condition = part.get('condition', '')
        then_parts = part.get('body', [])
        elif_chains = part.get('elif_chains', [])
        else_parts = part.get('else_parts', [])

        # Evaluate primary condition
        if self._resolve_condition(condition, data):
            return self.render_parts(then_parts, data)

        # Evaluate elif chains
        for elif_chain in elif_chains:
            elif_cond = elif_chain.get('condition', '')
            elif_parts = elif_chain.get('parts', [])
            if self._resolve_condition(elif_cond, data):
                return self.render_parts(elif_parts, data)

        # Evaluate else
        if else_parts:
            return self.render_parts(else_parts, data)

        return ''

    def _render_partial(self, part: Dict, data: Dict) -> str:
        'Render a partial TemplatePart'

        partial_name = part.get('partial_name', '')
        data_expr = part.get('data_expr', '')

        # If data_expr is provided, resolve it as data context
        if data_expr:
            partial_data = self._resolve_var(data_expr, data)
            if isinstance(partial_data, dict):
                partial_data = {**data, **partial_data}
            else:
                partial_data = data
        else:
            partial_data = data

        # Try to load partial from agent template registry
        with _agent_template_lock:
            agent_tpl = _agent_template_registry.get(partial_name)

        if agent_tpl:
            # Parse and render agent-registered template
            from src.ast_transformer import NexaTemplateParser
            parser = NexaTemplateParser()
            parts = parser.parse_template_content(agent_tpl.get('template_str', ''))
            return self.render_parts(parts, partial_data)

        # Try to load partial from file
        partial_path = partial_name
        if not os.path.exists(partial_path):
            # Try common extensions
            for ext in ['.html', '.tpl', '.nx', '.txt']:
                if os.path.exists(partial_path + ext):
                    partial_path = partial_path + ext
                    break

        if os.path.exists(partial_path):
            compiled = compile_template(partial_path)
            if compiled:
                compiled_obj = _get_template(compiled['_nexa_template_id'])
                if compiled_obj:
                    return self.render_parts(compiled_obj.parts, partial_data)

        # Error boundary: partial not found -> empty string
        if self.type_mode == 'strict':
            raise ContractViolation(
                f'Template partial not found: {partial_name}',
                clause_type='requires'
            )
        return ''

    def render_string(self, template_str: str, data: Dict) -> str:
        'Render a template string directly (parse + render)'

        from src.ast_transformer import NexaTemplateParser
        parser = NexaTemplateParser()
        parts = parser.parse_template_content(template_str)
        # Convert TemplatePart dataclass objects to dicts
        dict_parts = [p.to_dict() if hasattr(p, 'to_dict') else p for p in parts]
        return self.render_parts(dict_parts, data)


# ==================== Default Renderer ====================

_default_renderer = NexaTemplateRenderer(type_mode='warn')


# ==================== External Template API ====================

def template(path: str, data: Dict = None) -> str:
    '''Load template file + render with data (similar to NTNT template(path,data))

    Args:
        path: Template file path (.html, .tpl, .nx, .txt)
        data: Data context dict for rendering

    Returns:
        Rendered string

    Raises:
        ContractViolation: If path is invalid (strict mode)
    '''
    if data is None:
        data = {}

    # Validate path
    if not path or not os.path.exists(path):
        # Try common extensions
        found = False
        for ext in ['.html', '.tpl', '.nx', '.txt']:
            if os.path.exists(path + ext):
                path = path + ext
                found = True
                break
        if not found:
            raise ContractViolation(
                f'Template file not found: {path}',
                clause_type='requires'
            )

    # Compile (with cache)
    compiled = compile_template(path)

    # Render
    return render(compiled, data)


def compile_template(path: str) -> Dict:
    '''Compile template file (mtime cache + auto-reload)

    Args:
        path: Template file path

    Returns:
        Handle-as-dict: {"_nexa_template_id": int, "path": str}

    Note:
        Uses mtime-based cache: if file unchanged, returns cached compiled template.
        If file modified, re-compiles and updates cache.
    '''
    if not os.path.exists(path):
        raise ContractViolation(
            f'Template file not found: {path}',
            clause_type='requires'
        )

    mtime = os.path.getmtime(path)

    # Check cache for existing compiled template with same path
    with _registry_lock:
        for tid, ct in _template_registry.items():
            if ct.path == path:
                if not ct.is_stale():
                    return {'_nexa_template_id': tid, 'path': path}
                # Stale: re-compile below
                break

    # Load and parse template content
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    from src.ast_transformer import NexaTemplateParser
    parser = NexaTemplateParser()
    parts = parser.parse_template_content(content)

    # Create CompiledTemplate
    tid = _next_template_id()
    compiled = CompiledTemplate(path=path, parts=parts, mtime=mtime)
    compiled.id = tid
    _register_template(tid, compiled)

    return {'_nexa_template_id': tid, 'path': path}


def render(compiled: Dict, data: Dict = None) -> str:
    '''Render a compiled template handle with data

    Args:
        compiled: Handle-as-dict {"_nexa_template_id": int, "path": str}
        data: Data context dict for rendering

    Returns:
        Rendered string
    '''
    if data is None:
        data = {}

    if not isinstance(compiled, dict) or '_nexa_template_id' not in compiled:
        raise ContractViolation(
            'Invalid compiled template handle: missing _nexa_template_id',
            clause_type='requires'
        )

    tid = compiled['_nexa_template_id']
    compiled_obj = _get_template(tid)

    if compiled_obj is None:
        raise ContractViolation(
            f'Compiled template not found in registry: id={tid}',
            clause_type='requires'
        )

    # Check for stale cache (auto-reload)
    if compiled_obj.is_stale():
        # Re-compile and update
        new_mtime = os.path.getmtime(compiled_obj.path)
        with open(compiled_obj.path, 'r', encoding='utf-8') as f:
            content = f.read()

        from src.ast_transformer import NexaTemplateParser
        parser = NexaTemplateParser()
        new_parts = parser.parse_template_content(content)
        compiled_obj.parts = new_parts
        compiled_obj.mtime = new_mtime

    # Convert TemplatePart objects to dicts if needed
    dict_parts = [p.to_dict() if hasattr(p, 'to_dict') else p for p in compiled_obj.parts]
    return _default_renderer.render_parts(dict_parts, data)


def render_string(template_str: str, data: Dict = None) -> str:
    '''Render a template string directly (parse + render in one call)

    Args:
        template_str: Template content string
        data: Data context dict

    Returns:
        Rendered string
    '''
    if data is None:
        data = {}
    return _default_renderer.render_string(template_str, data)


# ==================== Agent-Native Extensions ====================

def agent_template_prompt(agent: Any, template_str: str, context: Dict = None) -> str:
    '''Auto-inject agent context into template variables

    Automatically injects:
    - agent_name: agent.name
    - agent_desc: agent.description
    - agent_tools: list of tool names

    Args:
        agent: NexaAgent instance
        template_str: Template content string
        context: Additional data context (merged with agent context)

    Returns:
        Rendered string with agent context injected
    '''
    # Build agent context
    agent_context = {}

    if hasattr(agent, 'name'):
        agent_context['agent_name'] = agent.name
    elif isinstance(agent, dict):
        agent_context['agent_name'] = agent.get('name', '')

    if hasattr(agent, 'role'):
        agent_context['agent_desc'] = agent.role
    elif hasattr(agent, 'description'):
        agent_context['agent_desc'] = agent.description
    elif isinstance(agent, dict):
        agent_context['agent_desc'] = agent.get('role', agent.get('description', ''))

    # Tool names
    if hasattr(agent, 'tools'):
        tools = agent.tools
        if isinstance(tools, list):
            agent_context['agent_tools'] = [
                t.get('name', str(t)) if isinstance(t, dict) else str(t)
                for t in tools
            ]
    elif isinstance(agent, dict):
        tools = agent.get('tools', [])
        agent_context['agent_tools'] = [
            t.get('name', str(t)) if isinstance(t, dict) else str(t)
            for t in tools
        ]

    # Merge with user-provided context (user context takes priority)
    merged = {**agent_context}
    if context:
        merged.update(context)

    return render_string(template_str, merged)


def agent_template_slot_fill(agent: Any, template_str: str, slot_sources: Dict = None) -> str:
    '''Multi-source slot filling with priority resolution

    Priority order (highest to lowest):
    1. explicit_data -- explicitly passed data
    2. auth_context -- agent auth context (P2-1)
    3. kv_data -- agent KV store data (P2-3)
    4. memory -- agent long-term memory
    5. agent_attrs -- agent attributes (name, description, tools)

    Args:
        agent: NexaAgent instance
        template_str: Template content string
        slot_sources: Dict of additional source data with priority keys

    Returns:
        Rendered string with all sources merged by priority
    '''
    # Layer 5 (lowest priority): agent attributes
    agent_attrs = {}
    if hasattr(agent, 'name'):
        agent_attrs['agent_name'] = agent.name
    elif isinstance(agent, dict):
        agent_attrs['agent_name'] = agent.get('name', '')

    if hasattr(agent, 'role'):
        agent_attrs['agent_desc'] = agent.role
    elif hasattr(agent, 'description'):
        agent_attrs['agent_desc'] = agent.description
    elif isinstance(agent, dict):
        agent_attrs['agent_desc'] = agent.get('role', agent.get('description', ''))

    if hasattr(agent, 'tools'):
        tools = agent.tools
        if isinstance(tools, list):
            agent_attrs['agent_tools'] = [
                t.get('name', str(t)) if isinstance(t, dict) else str(t)
                for t in tools
            ]
    elif isinstance(agent, dict):
        agent_attrs['agent_tools'] = [
            t.get('name', str(t)) if isinstance(t, dict) else str(t)
            for t in agent.get('tools', [])
        ]

    # Layer 4: memory (long-term memory)
    memory_data = {}
    if hasattr(agent, 'memory'):
        try:
            mem = agent.memory
            if hasattr(mem, 'query'):
                # Try to get recent memories
                recent = mem.query('recent context')
                if isinstance(recent, list):
                    memory_data['recent_memories'] = recent
        except Exception:
            pass
    elif isinstance(agent, dict):
        mem = agent.get('memory', None)
        if mem and isinstance(mem, dict):
            memory_data['recent_memories'] = mem.get('recent', [])

    # Layer 3: kv_data (KV store)
    kv_data = {}
    try:
        from .kv_store import agent_kv_context
        kv_data = agent_kv_context(agent)
    except (ImportError, Exception):
        pass

    # Layer 2: auth_context (P2-1)
    auth_data = {}
    try:
        from .auth import agent_auth_context
        auth_data = agent_auth_context(agent)
    except (ImportError, Exception):
        pass

    # Layer 1 (highest priority): explicit_data
    explicit_data = {}
    if slot_sources:
        explicit_data = slot_sources.get('explicit_data', slot_sources)

    # Merge by priority (highest priority overwrites lower)
    merged = {}
    merged.update(agent_attrs)      # Layer 5
    merged.update(memory_data)      # Layer 4
    merged.update(kv_data)          # Layer 3
    merged.update(auth_data)        # Layer 2
    merged.update(explicit_data)    # Layer 1 (highest)

    return render_string(template_str, merged)


def agent_template_register(agent: Any, name: str, template_str: str) -> Dict:
    '''Register agent-specific template to global registry

    Args:
        agent: NexaAgent instance
        name: Template name (used in {{> name}} partial references)
        template_str: Template content string

    Returns:
        Registration handle dict
    '''
    agent_name = ''
    if hasattr(agent, 'name'):
        agent_name = agent.name
    elif isinstance(agent, dict):
        agent_name = agent.get('name', '')

    with _agent_template_lock:
        _agent_template_registry[name] = {
            'agent_name': agent_name,
            'template_str': template_str,
            'registered_at': time.time(),
        }

    return {
        'name': name,
        'agent_name': agent_name,
        'status': 'registered'
    }


def agent_template_list() -> List[Dict]:
    '''List all registered agent templates

    Returns:
        List of template registration info dicts
    '''
    with _agent_template_lock:
        result = []
        for name, info in _agent_template_registry.items():
            result.append({
                'name': name,
                'agent_name': info.get('agent_name', ''),
                'registered_at': info.get('registered_at', 0),
            })
        return result


def agent_template_unregister(name: str) -> bool:
    '''Unregister an agent template

    Args:
        name: Template name to unregister

    Returns:
        True if template was found and removed, False otherwise
    '''
    with _agent_template_lock:
        if name in _agent_template_registry:
            del _agent_template_registry[name]
            return True
        return False


# ==================== Template Syntax Parser (Standalone) ====================
# This is a standalone parser that can be used without the full NexaTransformer
# The full version in ast_transformer.py handles Lark tree nodes

class TemplateContentParser:
    '''Standalone template content parser (used in compile_template and render_string)

    Parses template content string into TemplatePart dicts:
    - {{expr}} -> Expr (auto HTML escape)
    - {{{expr}}} -> RawExpr (no escape)
    - {{expr | filter1 | filter2(arg)}} -> FilteredExpr
    - {{{expr | filter}}} -> RawFilteredExpr
    - {{#for var in iterable}}...{{/for}} -> ForLoop
    - {{#if cond}}...{{#elif c2}}...{{#else}}...{{/if}} -> IfBlock
    - {{> partial_name}} or {{> name data_expr}} -> Partial
    - \{{ or \}} -> Escaped literal braces
    - Other -> Literal
    '''

    def parse(self, content: str) -> List[Dict]:
        'Parse template content into list of TemplatePart dicts'
        return self._parse_content(content, 0, len(content))[0]

    def _parse_content(self, content: str, start: int, end: int) -> Tuple[List[Dict], int]:
        'Recursively parse content from start to end'
        parts = []
        pos = start
        literal_buf = []

        while pos < end:
            # Check for escaped braces: \{{ or \}}
            if pos < end - 1 and content[pos] == '\\' and content[pos + 1] in ('{', '}'):
                # Escaped brace: add literal brace character
                literal_buf.append(content[pos + 1])
                pos += 2
                continue

            # Check for {{{ (raw expression)
            if pos < end - 2 and content[pos:pos + 3] == '{{{':
                # Flush literal buffer
                if literal_buf:
                    parts.append({'kind': 'literal', 'value': ''.join(literal_buf)})
                    literal_buf = []

                # Find closing }}}
                close_pos = self._find_closing_braces(content, pos + 3, '}}}')
                if close_pos == -1:
                    # No closing: treat as literal
                    literal_buf.append(content[pos:pos + 3])
                    pos += 3
                    continue

                inner = content[pos + 3:close_pos].strip()

                # Check for filter chain in raw expression
                if '|' in inner:
                    base_expr, filters = self._parse_filter_chain(inner)
                    parts.append({
                        'kind': 'raw_filtered_expr',
                        'value': base_expr,
                        'filters': filters,
                        'raw': True
                    })
                else:
                    parts.append({
                        'kind': 'raw_expr',
                        'value': inner,
                        'raw': True
                    })

                pos = close_pos + 3
                continue

            # Check for {{ (expression or control structure)
            if pos < end - 1 and content[pos:pos + 2] == '{{':
                # Flush literal buffer
                if literal_buf:
                    parts.append({'kind': 'literal', 'value': ''.join(literal_buf)})
                    literal_buf = []

                # Check for control structures: {{#for, {{#if, {{#elif, {{#else, {{/for, {{/if
                remaining = content[pos + 2:]

                if remaining.startswith('#for'):
                    # {{#for var in iterable}}
                    close_pos = self._find_closing_braces(content, pos + 6, '}}')
                    if close_pos == -1:
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    for_header = content[pos + 6:close_pos].strip()
                    # Parse: var in iterable
                    for_match = self._parse_for_header(for_header)
                    if for_match:
                        var_name, iterable_name = for_match
                        # Find matching {{/for}}
                        body_end = self._find_matching_end(content, close_pos + 2, '{{#for', '{{/for')
                        if body_end == -1:
                            # Error: no matching end
                            pos = close_pos + 2
                            continue

                        # Parse body between close_pos+2 and body_end
                        body_start = close_pos + 2
                        body_content_end = body_end

                        # Check for {{#empty}} within body
                        empty_start = -1
                        empty_end = -1
                        search_pos = body_start
                        while search_pos < body_content_end:
                            emp_idx = content.find('{{#empty}}', search_pos, body_content_end)
                            if emp_idx == -1:
                                break
                            empty_start = emp_idx + 9  # After {{#empty}}
                            empty_end = body_content_end
                            break

                        if empty_start != -1:
                            body_parts, _ = self._parse_content(content, body_start, empty_start - 9)
                            empty_parts, _ = self._parse_content(content, empty_start, body_content_end)
                        else:
                            body_parts, _ = self._parse_content(content, body_start, body_content_end)
                            empty_parts = []

                        parts.append({
                            'kind': 'for_loop',
                            'var': var_name,
                            'iterable': iterable_name,
                            'body': body_parts,
                            'empty_body': empty_parts
                        })

                        # Skip past {{/for}}
                        end_close = content.find('}}', body_end)
                        if end_close != -1:
                            pos = end_close + 2
                        else:
                            pos = body_content_end + 9
                        continue

                elif remaining.startswith('#if'):
                    # {{#if condition}}
                    close_pos = self._find_closing_braces(content, pos + 5, '}}')
                    if close_pos == -1:
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    condition = content[pos + 5:close_pos].strip()

                    # Find matching {{/if}} and parse elif/else
                    result = self._parse_if_block_content(content, close_pos + 2)
                    if result:
                        then_parts, elif_chains, else_parts, end_pos = result
                        parts.append({
                            'kind': 'if_block',
                            'condition': condition,
                            'body': then_parts,
                            'elif_chains': elif_chains,
                            'else_parts': else_parts
                        })
                        pos = end_pos
                        continue
                    else:
                        pos = close_pos + 2
                        continue

                elif remaining.startswith('#elif') or remaining.startswith('#else') or remaining.startswith('/for') or remaining.startswith('/if'):
                    # These should be handled by parent context (for/if block parsing)
                    # If we encounter them here, it's an error or we're at the boundary
                    # Return what we have and let the caller handle
                    if literal_buf:
                        parts.append({'kind': 'literal', 'value': ''.join(literal_buf)})
                        literal_buf = []
                    return parts, pos

                elif remaining.startswith('>'):
                    # {{> partial_name}} or {{> name data_expr}}
                    close_pos = self._find_closing_braces(content, pos + 4, '}}')
                    if close_pos == -1:
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    inner = content[pos + 4:close_pos].strip()
                    partial_name, data_expr = self._parse_partial(inner)
                    parts.append({
                        'kind': 'partial',
                        'partial_name': partial_name,
                        'data_expr': data_expr
                    })
                    pos = close_pos + 2
                    continue

                else:
                    # Regular expression: {{expr}} or {{expr | filter}}
                    close_pos = self._find_closing_braces(content, pos + 2, '}}')
                    if close_pos == -1:
                        # No closing brace: treat as literal
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    # Make sure this isn't {{{ (raw expression)
                    if close_pos < end and content[close_pos] == '{':
                        # This is actually {{{ -- skip
                        literal_buf.append(content[pos:pos + 2])
                        pos += 2
                        continue

                    inner = content[pos + 2:close_pos].strip()

                    # Check for filter chain
                    if '|' in inner:
                        base_expr, filters = self._parse_filter_chain(inner)
                        parts.append({
                            'kind': 'filtered_expr',
                            'value': base_expr,
                            'filters': filters,
                            'raw': False
                        })
                    else:
                        parts.append({
                            'kind': 'expr',
                            'value': inner
                        })

                    pos = close_pos + 2
                    continue

            # Regular character: accumulate into literal buffer
            literal_buf.append(content[pos])
            pos += 1

        # Flush remaining literal buffer
        if literal_buf:
            parts.append({'kind': 'literal', 'value': ''.join(literal_buf)})

        return parts, pos

    def _find_closing_braces(self, content: str, start: int, closing: str) -> int:
        'Find closing braces position from start'
        pos = start
        while pos < len(content):
            idx = content.find(closing, pos)
            if idx == -1:
                return -1
            # Check that it's not {{{ (for }} closing inside {{{expr}}})
            if closing == '}}' and idx > 0 and content[idx - 1] == '{':
                # This }} is part of }}}}, skip
                pos = idx + 2
                continue
            return idx
        return -1

    def _find_matching_end(self, content: str, start: int, open_tag: str, close_tag: str) -> int:
        'Find matching close tag accounting for nesting'

        # open_tag and close_tag are in template format: {{#for and {{/for
        depth = 1
        pos = start

        while pos < len(content) and depth > 0:
            # Look for next {{ occurrence
            next_brace = content.find('{{', pos)
            if next_brace == -1:
                return -1

            # Check what follows {{:
            after = content[next_brace + 2:]

            if after.startswith('#for') or after.startswith('#if'):
                depth += 1
                pos = next_brace + 2
                # Skip past this opening tag's closing }}
                close_idx = content.find('}}', pos)
                if close_idx == -1:
                    return -1
                pos = close_idx + 2
                continue

            elif after.startswith('/for') and close_tag == '{{/for':
                depth -= 1
                if depth == 0:
                    return next_brace  # Position of {{/for}}
                pos = next_brace + 7  # Skip {{/for}}
                close_idx = content.find('}}', pos)
                if close_idx == -1:
                    return -1
                pos = close_idx + 2
                continue

            elif after.startswith('/if') and close_tag == '{{/if':
                depth -= 1
                if depth == 0:
                    return next_brace  # Position of {{/if}}
                pos = next_brace + 5  # Skip {{/if}}
                close_idx = content.find('}}', pos)
                if close_idx == -1:
                    return -1
                pos = close_idx + 2
                continue

            else:
                # Some other {{ tag, skip past }}
                close_idx = content.find('}}', next_brace + 2)
                if close_idx == -1:
                    return -1
                pos = close_idx + 2
                continue

        return -1

    def _parse_if_block_content(self, content: str, start: int) -> Optional[Tuple]:
        '''Parse if block content including elif chains and else

        Returns: (then_parts, elif_chains, else_parts, end_pos) or None
        '''
        # Find the boundaries of then, elif, else, /if
        # We need to track nesting for nested {{#if}} blocks

        then_start = start
        then_end = start
        elif_chains = []
        else_parts = []
        else_start = start
        else_end = start
        if_end = start

        # Scan for {{#elif}}, {{#else}}, {{/if}}
        pos = start
        depth = 1  # We're already inside one {{#if}}

        while pos < len(content) and depth > 0:
            next_brace = content.find('{{', pos)
            if next_brace == -1:
                break

            after = content[next_brace + 2:]

            if after.startswith('#if'):
                depth += 1
                close_idx = content.find('}}', next_brace + 5)
                if close_idx == -1:
                    break
                pos = close_idx + 2
                continue

            elif after.startswith('#for'):
                # Skip nested for loops entirely
                depth_for = 1
                pos_for = next_brace + 6
                close_idx_for = content.find('}}', pos_for)
                if close_idx_for != -1:
                    pos_for = close_idx_for + 2
                    while pos_for < len(content) and depth_for > 0:
                        next_f = content.find('{{', pos_for)
                        if next_f == -1:
                            break
                        af = content[next_f + 2:]
                        if af.startswith('#for'):
                            depth_for += 1
                        elif af.startswith('/for'):
                            depth_for -= 1
                        close_f = content.find('}}', next_f + 2)
                        if close_f == -1:
                            break
                        pos_for = close_f + 2
                    pos = pos_for
                else:
                    pos = next_brace + 2
                continue

            elif after.startswith('/if'):
                depth -= 1
                if depth == 0:
                    # Found our matching {{/if}}
                    if_end = next_brace
                    close_idx = content.find('}}', next_brace + 5)
                    if close_idx == -1:
                        break
                    end_pos = close_idx + 2
                    break
                else:
                    close_idx = content.find('}}', next_brace + 5)
                    if close_idx == -1:
                        break
                    pos = close_idx + 2
                    continue

            elif after.startswith('#elif') and depth == 1:
                # Only process elif at our nesting level
                close_idx = content.find('}}', next_brace + 7)
                if close_idx == -1:
                    break

                elif_cond = content[next_brace + 7:close_idx].strip()

                # The then_parts end here
                if not elif_chains and not else_parts:
                    then_end = next_brace

                elif_start = close_idx + 2
                elif_chains.append({
                    'condition': elif_cond,
                    'start': elif_start,
                    'parts': []  # Will be filled later
                })

                pos = close_idx + 2
                continue

            elif after.startswith('#else') and depth == 1:
                # Only process else at our nesting level
                close_idx = content.find('}}', next_brace + 7)
                if close_idx == -1:
                    break

                # Previous elif or then ends here
                if elif_chains:
                    # Last elif's content ends here
                    elif_chains[-1]['end'] = next_brace
                elif not elif_chains:
                    then_end = next_brace

                else_start = close_idx + 2
                pos = close_idx + 2
                continue

            else:
                # Other {{ tag, skip
                close_idx = content.find('}}', next_brace + 2)
                if close_idx == -1:
                    break
                pos = close_idx + 2
                continue

        # Now we have boundaries, parse each section
        if then_end == start and elif_chains:
            then_end = elif_chains[0]['start'] - 7  # Before first {{#elif
        if then_end == start and else_start > start:
            then_end = else_start - 7  # Before {{#else

        # Default then_end to if_end if no elif/else found
        if then_end == start:
            then_end = if_end

        then_parts, _ = self._parse_content(content, then_start, then_end)

        # Parse elif chains
        parsed_elif_chains = []
        for i, elif_info in enumerate(elif_chains):
            elif_start = elif_info['start']
            if i + 1 < len(elif_chains):
                elif_end = elif_chains[i + 1]['start'] - 7  # Before next {{#elif
            elif else_start > elif_start:
                elif_end = else_start - 7  # Before {{#else
            else:
                elif_end = if_end  # Before {{/if

            elif_parts, _ = self._parse_content(content, elif_start, elif_end)
            parsed_elif_chains.append({
                'condition': elif_info['condition'],
                'parts': elif_parts
            })

        # Parse else parts
        else_parts = []
        if else_start > start and else_start < if_end:
            else_parts, _ = self._parse_content(content, else_start, if_end)

        return then_parts, parsed_elif_chains, else_parts, end_pos

    def _parse_for_header(self, header: str) -> Optional[Tuple[str, str]]:
        'Parse for-loop header: "var in iterable"'

        parts = header.split(' in ')
        if len(parts) == 2:
            var_name = parts[0].strip()
            iterable_name = parts[1].strip()
            return var_name, iterable_name
        return None

    def _parse_filter_chain(self, expr_str: str) -> Tuple[str, List[Dict]]:
        '''Parse filter chain: "expr | filter1 | filter2(arg1,arg2)"

        Returns: (base_expr, [filter_dicts])
        '''
        parts = expr_str.split('|')
        base_expr = parts[0].strip()
        filters = []

        for f_part in parts[1:]:
            f_str = f_part.strip()
            # Check for filter with args: filter_name(arg1, arg2)
            import re
            arg_match = re.match(r'(\w+)\(([^)]*)\)', f_str)
            if arg_match:
                fname = arg_match.group(1)
                raw_args = arg_match.group(2)
                args = [a.strip().strip("'\"") for a in raw_args.split(',')]
                # Try to convert numeric args
                parsed_args = []
                for a in args:
                    try:
                        parsed_args.append(int(a))
                    except ValueError:
                        try:
                            parsed_args.append(float(a))
                        except ValueError:
                            parsed_args.append(a)
                filters.append({'name': fname, 'args': parsed_args})
            else:
                filters.append({'name': f_str, 'args': []})

        return base_expr, filters

    def _parse_partial(self, inner: str) -> Tuple[str, str]:
        '''Parse partial reference: "partial_name" or "partial_name data_expr"

        Returns: (name, data_expr)
        '''
        parts = inner.split(None, 1)  # Split on first whitespace
        if len(parts) == 1:
            return parts[0], ''
        return parts[0], parts[1]