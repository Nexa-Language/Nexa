"""
IAL Resolve — 递归术语重写引擎

IAL 的核心引擎：将自然语言断言递归解析为可执行测试。

重写流程:
    "they see success response"
        ↓ vocabulary lookup
    "component.success_response"
        ↓ component expansion  
    ["status 2xx", "body contains 'ok'"]
        ↓ standard term resolution
    [Check(InRange, "response.status", 200-299), Check(Contains, "response.body", "ok")]
        ↓ execution
    [✓, ✓]

设计原则：
- IAL引擎是固定的，新断言是词汇条目（不需要改代码）
- 递归深度限制防止无限循环
- 无法解析的术语视为 SemanticCheck（用 LLM 判断）
"""

import re
from typing import Any, List, Optional, Dict, Tuple

from src.ial.vocabulary import Vocabulary, TermEntry
from src.ial.primitives import (
    Check, CheckOp, AgentAssertion, ProtocolCheck, PipelineCheck,
    SemanticCheck, Http, Primitive
)


# 递归解析最大深度 — 防止无限循环
MAX_RECURSION_DEPTH = 10


def resolve(assertion_text: str, vocabulary: Vocabulary, 
            depth: int = 0, context: Dict[str, Any] = None) -> List[Primitive]:
    """
    递归解析断言文本为原语列表
    
    Args:
        assertion_text: 断言文本，如 "they see success response"
        vocabulary: 术语词汇表
        depth: 当前递归深度
        context: 解析上下文（包含 agent_name, protocol_name 等）
    
    Returns:
        原语列表 [Check, AgentAssertion, ...]
    
    Raises:
        RecursionError: 超过最大递归深度
    """
    if context is None:
        context = {}
    
    if depth > MAX_RECURSION_DEPTH:
        raise RecursionError(
            f"IAL resolve exceeded max depth ({MAX_RECURSION_DEPTH}) "
            f"while resolving: '{assertion_text}'. "
            f"Possible circular glossary definition."
        )
    
    assertion_text = assertion_text.strip()
    
    # 1. 尝试词汇查找
    lookup_result = vocabulary.lookup(assertion_text)
    
    if lookup_result is not None:
        entry, params = lookup_result
        
        if entry.entry_type == "primitive":
            # 直接映射到原语 — 返回原语实例
            primitive = _instantiate_primitive(entry.means, params, context)
            if primitive is not None:
                return [primitive]
            return []
        
        if entry.entry_type == "call":
            # 调用类型 — 执行函数获取原语
            if callable(entry.means):
                result = entry.means(params, context)
                if isinstance(result, list):
                    return result
                if result is not None:
                    return [result]
            return []
        
        if entry.entry_type in ("expansion", "composite"):
            # 展开为多个术语字符串 — 递归解析每个
            expanded_terms = vocabulary.expand_with_params(entry, params)
            primitives = []
            for term in expanded_terms:
                if isinstance(term, str):
                    resolved = resolve(term, vocabulary, depth + 1, context)
                    primitives.extend(resolved)
                elif isinstance(term, (Check, AgentAssertion, ProtocolCheck, 
                                      PipelineCheck, SemanticCheck, Http)):
                    primitives.append(term)
            return primitives
    
    # 2. 词汇未匹配 — 尝试标准断言解析
    standard_primitives = _parse_standard_assertion(assertion_text, context)
    if standard_primitives:
        return standard_primitives
    
    # 3. 无法解析 — 生成语义检查（用 LLM 判断）
    return [SemanticCheck(actual="", intent=assertion_text, context=str(context))]


def _instantiate_primitive(means: Any, params: Dict[str, str], 
                           context: Dict[str, Any]) -> Optional[Primitive]:
    """
    从术语条目的 means 和提取的参数实例化原语
    
    Args:
        means: 术语条目的 means（可以是原语实例/原语工厂函数/字典）
        params: 提取的参数值
        context: 解析上下文
    
    Returns:
        原语实例或 None
    """
    if isinstance(means, (Check, AgentAssertion, ProtocolCheck, 
                          PipelineCheck, SemanticCheck, Http)):
        # 已经是原语实例 — 直接返回
        return means
    
    if callable(means):
        # 原语工厂函数 — 调用生成原语
        try:
            return means(params, context)
        except Exception:
            return None
    
    if isinstance(means, dict):
        # 字字典描述 — 构造原语
        return _dict_to_primitive(means, params, context)
    
    return None


def _dict_to_primitive(desc: Dict[str, Any], params: Dict[str, str],
                       context: Dict[str, Any]) -> Optional[Primitive]:
    """
    从字典描述构造原语实例
    
    字典格式示例:
        {"type": "AgentAssertion", "agent": "WeatherBot", "input": "{question}", 
         "checks": [{"op": "Contains", "target": "output", "expected": "{text}"}]}
    """
    ptype = desc.get("type", "")
    
    # 替换参数值
    def replace_params(value):
        if isinstance(value, str):
            for k, v in params.items():
                value = value.replace(f'{{{k}}}', v)
            return value
        return value
    
    if ptype == "Check":
        op_str = desc.get("op", "Equals")
        try:
            op = CheckOp(op_str.lower())
        except ValueError:
            op = CheckOp.Equals
        target = replace_params(desc.get("target", ""))
        expected = replace_params(desc.get("expected", ""))
        return Check(op=op, target=target, expected=expected)
    
    if ptype == "AgentAssertion":
        agent_name = replace_params(desc.get("agent", context.get("agent_name", "")))
        input_text = replace_params(desc.get("input", ""))
        checks = _parse_checks_list(desc.get("checks", []), params)
        return AgentAssertion(agent_name=agent_name, input_text=input_text, checks=checks)
    
    if ptype == "ProtocolCheck":
        protocol_name = replace_params(desc.get("protocol", context.get("protocol_name", "")))
        checks = _parse_checks_list(desc.get("checks", []), params)
        return ProtocolCheck(protocol_name=protocol_name, field_checks=checks)
    
    if ptype == "PipelineCheck":
        pipeline_expr = replace_params(desc.get("pipeline", ""))
        input_text = replace_params(desc.get("input", ""))
        checks = _parse_checks_list(desc.get("checks", []), params)
        return PipelineCheck(pipeline_expr=pipeline_expr, input_text=input_text, checks=checks)
    
    if ptype == "SemanticCheck":
        intent = replace_params(desc.get("intent", ""))
        actual = replace_params(desc.get("actual", ""))
        return SemanticCheck(actual=actual, intent=intent)
    
    return None


def _parse_checks_list(checks_desc: List[Dict], params: Dict[str, str]) -> List[Check]:
    """
    从字典列表构造 Check 对象列表
    """
    checks = []
    for check_desc in checks_desc:
        op_str = check_desc.get("op", "Equals")
        try:
            op = CheckOp(op_str.lower())
        except ValueError:
            op = CheckOp.Equals
        
        target = check_desc.get("target", "")
        expected = check_desc.get("expected", "")
        
        # 替换参数
        for k, v in params.items():
            target = target.replace(f'{{{k}}}', v)
            expected = expected.replace(f'{{{k}}}', v)
        
        # 处理 InRange 的范围值
        if op == CheckOp.InRange and isinstance(expected, str):
            # 解析 "200-299" 格式
            range_match = re.match(r'(\d+)-(\d+)', expected)
            if range_match:
                expected = (int(range_match.group(1)), int(range_match.group(2)))
        
        # 处理数值型期望值
        if op in (CheckOp.LessThan, CheckOp.GreaterThan) and isinstance(expected, str):
            try:
                expected = int(expected)
            except ValueError:
                try:
                    expected = float(expected)
                except ValueError:
                    pass
        
        checks.append(Check(op=op, target=target, expected=expected))
    
    return checks


def _parse_standard_assertion(assertion_text: str, 
                              context: Dict[str, Any]) -> List[Primitive]:
    """
    解析标准断言格式 — 无需词汇表也能理解常见模式
    
    支持的标准格式:
    - "status 2xx" → Check(InRange, "response.status", (200, 299))
    - "body contains 'ok'" → Check(Contains, "response.body", "ok")
    - "output equals 'hello'" → Check(Equals, "output", "hello")
    - "output contains 'weather'" → Check(Contains, "output", "weather")
    - "response matches /^success/" → Check(Matches, "response", "^success")
    - "field exists 'title'" → Check(Exists, "field.title", "title")
    """
    primitives = []
    
    # Pattern: "status 2xx" — HTTP status class (2xx = 200-299)
    match = re.match(r'^status\s+(\d)xx$', assertion_text, re.IGNORECASE)
    if match:
        prefix = int(match.group(1))
        lower = prefix * 100
        upper = lower + 99
        primitives.append(Check(op=CheckOp.InRange, target="response.status", 
                                expected=(lower, upper)))
        return primitives
    
    # Pattern: "status NNN" (exact status code)
    match = re.match(r'^status\s+(\d{3})$', assertion_text, re.IGNORECASE)
    if match:
        code = int(match.group(1))
        primitives.append(Check(op=CheckOp.Equals, target="response.status", expected=code))
        return primitives
    
    # Pattern: "{target} contains '{value}'"
    match = re.match(r'^(\w+(?:\.\w+)*)\s+contains\s+[\'"](.+?)[\'"]$', assertion_text, re.IGNORECASE)
    if match:
        target = match.group(1)
        value = match.group(2)
        primitives.append(Check(op=CheckOp.Contains, target=target, expected=value))
        return primitives
    
    # Pattern: "{target} equals '{value}'"
    match = re.match(r'^(\w+(?:\.\w+)*)\s+equals\s+[\'"](.+?)[\'"]$', assertion_text, re.IGNORECASE)
    if match:
        target = match.group(1)
        value = match.group(2)
        primitives.append(Check(op=CheckOp.Equals, target=target, expected=value))
        return primitives
    
    # Pattern: "{target} matches '{pattern}'"
    match = re.match(r'^(\w+(?:\.\w+)*)\s+matches\s+[\'"](.+?)[\'"]$', assertion_text, re.IGNORECASE)
    if match:
        target = match.group(1)
        pattern = match.group(2)
        primitives.append(Check(op=CheckOp.Matches, target=target, expected=pattern))
        return primitives
    
    # Pattern: "{target} exists"
    match = re.match(r'^(\w+(?:\.\w+)*)\s+exists$', assertion_text, re.IGNORECASE)
    if match:
        target = match.group(1)
        primitives.append(Check(op=CheckOp.Exists, target=target, expected=None))
        return primitives
    
    # Pattern: "{target} not exists"
    match = re.match(r'^(\w+(?:\.\w+)*)\s+not\s+exists$', assertion_text, re.IGNORECASE)
    if match:
        target = match.group(1)
        primitives.append(Check(op=CheckOp.NotExists, target=target, expected=None))
        return primitives
    
    # Pattern: "body contains 'value'" (short-hand for response.body)
    match = re.match(r'^body\s+contains\s+[\'"](.+?)[\'"]$', assertion_text, re.IGNORECASE)
    if match:
        value = match.group(1)
        primitives.append(Check(op=CheckOp.Contains, target="response.body", expected=value))
        return primitives
    
    # Pattern: "output contains 'value'" (short-hand for agent output)
    match = re.match(r'^output\s+contains\s+[\'"](.+?)[\'"]$', assertion_text, re.IGNORECASE)
    if match:
        value = match.group(1)
        primitives.append(Check(op=CheckOp.Contains, target="output", expected=value))
        return primitives
    
    # Pattern: "output equals 'value'"
    match = re.match(r'^output\s+equals\s+[\'"](.+?)[\'"]$', assertion_text, re.IGNORECASE)
    if match:
        value = match.group(1)
        primitives.append(Check(op=CheckOp.Equals, target="output", expected=value))
        return primitives
    
    # Pattern: "response is valid" → ProtocolCheck
    match = re.match(r'^response\s+is\s+valid$', assertion_text, re.IGNORECASE)
    if match:
        protocol_name = context.get("protocol_name", "unknown")
        primitives.append(ProtocolCheck(protocol_name=protocol_name))
        return primitives
    
    # Pattern: "protocol check passes" → ProtocolCheck
    match = re.match(r'^protocol\s+check\s+passes$', assertion_text, re.IGNORECASE)
    if match:
        protocol_name = context.get("protocol_name", "unknown")
        primitives.append(ProtocolCheck(protocol_name=protocol_name))
        return primitives
    
    return primitives


def resolve_scenario_assertions(assertions: List[str], vocabulary: Vocabulary,
                                context: Dict[str, Any] = None) -> List[Primitive]:
    """
    解析 Scenario 的所有断言为原语列表
    
    Args:
        assertions: 断言文本列表，如 ["the agent responds with 'weather'", "the response is valid"]
        vocabulary: 术语词汇表
        context: 解析上下文
    
    Returns:
        原语列表
    """
    if context is None:
        context = {}
    
    all_primitives = []
    for assertion_text in assertions:
        primitives = resolve(assertion_text, vocabulary, depth=0, context=context)
        all_primitives.extend(primitives)
    
    return all_primitives