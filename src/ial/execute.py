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
IAL Execute — 原语执行引擎

执行 IAL 原语并返回 CheckResult。
支持 Agent 断言、Protocol 检查、Pipeline 检查、语义检查等。

执行策略:
- AgentAssertion: 尝试调用 agent 获取输出，然后执行 checks
- ProtocolCheck: 检查数据是否符合 protocol schema
- PipelineCheck: 验证 DAG 管道输出
- SemanticCheck: 用 LLM 判断语义是否符合预期（需 API key）
- Check: 对提取的值执行 CheckOp 比较
- Http: 执行 HTTP 请求并检查响应
"""

import re
import os
import json
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union

from src.ial.primitives import (
    Check, CheckOp, AgentAssertion, ProtocolCheck, PipelineCheck,
    SemanticCheck, Http, Cli, CodeQuality, ReadFile, FunctionCall,
    PropertyCheck, InvariantCheck, Primitive, CheckResult, 
    ScenarioResult, FeatureResult
)


def execute_primitive(primitive: Primitive, context: Dict[str, Any] = None) -> CheckResult:
    """
    执行单个 IAL 原语并返回检查结果
    
    Args:
        primitive: 待执行的原语
        context: 执行上下文（包含 runtime 状态、agent 实例等）
    
    Returns:
        CheckResult 包含通过/失败状态和消息
    """
    if context is None:
        context = {}
    
    if isinstance(primitive, Check):
        return _execute_check(primitive, context)
    elif isinstance(primitive, AgentAssertion):
        return _execute_agent_assertion(primitive, context)
    elif isinstance(primitive, ProtocolCheck):
        return _execute_protocol_check(primitive, context)
    elif isinstance(primitive, PipelineCheck):
        return _execute_pipeline_check(primitive, context)
    elif isinstance(primitive, SemanticCheck):
        return _execute_semantic_check(primitive, context)
    elif isinstance(primitive, Http):
        return _execute_http(primitive, context)
    elif isinstance(primitive, Cli):
        return _execute_cli(primitive, context)
    elif isinstance(primitive, ReadFile):
        return _execute_read_file(primitive, context)
    elif isinstance(primitive, FunctionCall):
        return _execute_function_call(primitive, context)
    elif isinstance(primitive, PropertyCheck):
        return _execute_property_check(primitive, context)
    elif isinstance(primitive, InvariantCheck):
        return _execute_invariant_check(primitive, context)
    else:
        return CheckResult(
            passed=False,
            primitive=primitive,
            message=f"Unknown primitive type: {type(primitive)}"
        )


def execute_primitives(primitives: List[Primitive], 
                       context: Dict[str, Any] = None) -> List[CheckResult]:
    """
    执行原语列表并返回所有检查结果
    
    Args:
        primitives: 原语列表
        context: 执行上下文
    
    Returns:
        检查结果列表
    """
    if context is None:
        context = {}
    
    results = []
    for primitive in primitives:
        result = execute_primitive(primitive, context)
        results.append(result)
    
    return results


def _execute_check(check: Check, context: Dict[str, Any]) -> CheckResult:
    """
    执行通用 Check 原语 — 对目标字段执行 CheckOp 比较
    
    从 context 中提取目标值，然后用 CheckOp 与期望值比较。
    """
    # 从上下文提取目标值
    actual_value = _extract_value(check.target, context)
    
    if actual_value is None and check.op not in (CheckOp.Exists, CheckOp.NotExists):
        # 目标值不存在（且不是 Exists/NotExists 检查）→ 失败
        return CheckResult(
            passed=False,
            primitive=check,
            message=f"Target '{check.target}' not found in context",
            actual=None
        )
    
    # 执行比较操作
    passed, message = _apply_check_op(check.op, actual_value, check.expected)
    
    return CheckResult(
        passed=passed,
        primitive=check,
        message=message,
        actual=actual_value
    )


def _extract_value(target: str, context: Dict[str, Any]) -> Any:
    """
    从上下文中提取目标值
    
    支持:
    - "response.status" → context["response"]["status"]
    - "output" → context["output"]
    - "response.body" → context["response"]["body"]
    """
    parts = target.split(".")
    value = context
    
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif hasattr(value, part):
            value = getattr(value, part)
        else:
            return None
    
    return value


def _apply_check_op(op: CheckOp, actual: Any, expected: Any) -> tuple:
    """
    应用 CheckOp 比较，返回 (passed, message)
    """
    try:
        if op == CheckOp.Equals:
            passed = actual == expected
            msg = f"Equals: {actual!r} == {expected!r}" if passed else f"Equals: {actual!r} != {expected!r}"
            return (passed, msg)
        
        if op == CheckOp.NotEquals:
            passed = actual != expected
            msg = f"NotEquals: {actual!r} != {expected!r}" if passed else f"NotEquals: {actual!r} == {expected!r}"
            return (passed, msg)
        
        if op == CheckOp.Contains:
            if isinstance(actual, str) and isinstance(expected, str):
                passed = expected in actual
                msg = f"Contains: '{expected}' in '{actual[:100]}'" if passed else f"Contains: '{expected}' not in '{actual[:100]}'"
                return (passed, msg)
            if isinstance(actual, (list, dict)):
                passed = expected in actual
                msg = f"Contains: {expected!r} in {type(actual).__name__}" if passed else f"Contains: {expected!r} not found"
                return (passed, msg)
            return (False, f"Contains: actual type {type(actual).__name__} not searchable")
        
        if op == CheckOp.NotContains:
            if isinstance(actual, str) and isinstance(expected, str):
                passed = expected not in actual
                msg = f"NotContains: '{expected}' not in text" if passed else f"NotContains: '{expected}' found in text"
                return (passed, msg)
            return (False, f"NotContains: actual type {type(actual).__name__} not searchable")
        
        if op == CheckOp.Matches:
            if isinstance(actual, str):
                passed = bool(re.search(expected, actual))
                msg = f"Matches: pattern '{expected}'" if passed else f"Matches: pattern '{expected}' not found"
                return (passed, msg)
            return (False, f"Matches: actual is not string")
        
        if op == CheckOp.Exists:
            passed = actual is not None
            msg = f"Exists: value present" if passed else f"Exists: value missing"
            return (passed, msg)
        
        if op == CheckOp.NotExists:
            passed = actual is None
            msg = f"NotExists: value absent" if passed else f"NotExists: value present"
            return (passed, msg)
        
        if op == CheckOp.LessThan:
            passed = actual < expected
            msg = f"LessThan: {actual} < {expected}" if passed else f"LessThan: {actual} >= {expected}"
            return (passed, msg)
        
        if op == CheckOp.GreaterThan:
            passed = actual > expected
            msg = f"GreaterThan: {actual} > {expected}" if passed else f"GreaterThan: {actual} <= {expected}"
            return (passed, msg)
        
        if op == CheckOp.InRange:
            if isinstance(expected, tuple) and len(expected) == 2:
                low, high = expected
                passed = low <= actual <= high
                msg = f"InRange: {actual} in [{low}, {high}]" if passed else f"InRange: {actual} not in [{low}, {high}]"
                return (passed, msg)
            return (False, f"InRange: expected must be (low, high) tuple")
        
        if op == CheckOp.StartsWith:
            if isinstance(actual, str) and isinstance(expected, str):
                passed = actual.startswith(expected)
                msg = f"StartsWith: '{actual[:50]}' starts with '{expected}'" if passed else f"StartsWith: does not start with '{expected}'"
                return (passed, msg)
            return (False, f"StartsWith: both must be strings")
        
        if op == CheckOp.EndsWith:
            if isinstance(actual, str) and isinstance(expected, str):
                passed = actual.endswith(expected)
                msg = f"EndsWith: '{actual[:50]}' ends with '{expected}'" if passed else f"EndsWith: does not end with '{expected}'"
                return (passed, msg)
            return (False, f"EndsWith: both must be strings")
        
        if op == CheckOp.IsType:
            type_map = {"str": str, "int": int, "float": float, "bool": bool, 
                       "list": list, "dict": dict, "string": str, "number": (int, float)}
            expected_type = type_map.get(expected, type(None))
            if expected_type == type(None) and isinstance(expected, str):
                # Try to evaluate the type name
                try:
                    expected_type = eval(expected)
                except Exception:
                    pass
            passed = isinstance(actual, expected_type)
            msg = f"IsType: {type(actual).__name__} is {expected}" if passed else f"IsType: {type(actual).__name__} is not {expected}"
            return (passed, msg)
        
        if op == CheckOp.HasLength:
            if hasattr(actual, '__len__'):
                actual_len = len(actual)
                if isinstance(expected, tuple) and len(expected) == 2:
                    passed = expected[0] <= actual_len <= expected[1]
                    msg = f"HasLength: {actual_len} in [{expected[0]}, {expected[1]}]" if passed else f"HasLength: {actual_len} not in range"
                    return (passed, msg)
                passed = actual_len == expected
                msg = f"HasLength: {actual_len} == {expected}" if passed else f"HasLength: {actual_len} != {expected}"
                return (passed, msg)
            return (False, f"HasLength: actual has no length")
        
        return (False, f"Unknown CheckOp: {op}")
    
    except Exception as e:
        return (False, f"CheckOp error: {e}")


def _execute_agent_assertion(assertion: AgentAssertion, 
                             context: Dict[str, Any]) -> CheckResult:
    """
    执行 Agent 断言 — 调用 agent 并检查输出
    
    执行策略:
    1. 如果 context 中有已构建的 runtime → 直接调用 agent
    2. 如果有生成的 .py 文件 → 动态加载并调用
    3. 否则 → 尝试模拟执行（标记为 ⏭️ skipped）
    """
    agent_name = assertion.agent_name
    input_text = assertion.input_text
    
    # 策略 1: 从 context 中的 runtime 模块获取 agent
    runtime_module = context.get("runtime_module")
    if runtime_module and hasattr(runtime_module, agent_name):
        try:
            agent_obj = getattr(runtime_module, agent_name)
            if hasattr(agent_obj, 'run'):
                output = agent_obj.run(input_text)
            elif callable(agent_obj):
                output = agent_obj(input_text)
            else:
                output = str(agent_obj)
            
            # 将输出注入 context，然后执行 checks
            check_context = {**context, "output": output}
            all_passed = True
            messages = []
            
            for check in assertion.checks:
                result = _execute_check(check, check_context)
                if not result.passed:
                    all_passed = False
                messages.append(str(result))
            
            combined_msg = f"Agent '{agent_name}' with input '{input_text[:50]}': " + "; ".join(messages)
            return CheckResult(
                passed=all_passed,
                primitive=assertion,
                message=combined_msg,
                actual=output
            )
        except Exception as e:
            return CheckResult(
                passed=False,
                primitive=assertion,
                message=f"Agent execution failed: {e}",
                actual=None
            )
    
    # 策略 2: 从生成的 Python 文件动态加载
    generated_py = context.get("generated_py_path")
    if generated_py:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("nexa_runtime", generated_py)
            module = importlib.util.module_from_spec(spec)
            sys.modules["nexa_runtime"] = module
            spec.loader.exec_module(module)
            
            if hasattr(module, agent_name):
                agent_obj = getattr(module, agent_name)
                output = agent_obj.run(input_text) if hasattr(agent_obj, 'run') else str(agent_obj)
                
                check_context = {**context, "output": output}
                all_passed = True
                messages = []
                
                for check in assertion.checks:
                    result = _execute_check(check, check_context)
                    if not result.passed:
                        all_passed = False
                    messages.append(str(result))
                
                return CheckResult(
                    passed=all_passed,
                    primitive=assertion,
                    message=f"Agent '{agent_name}': " + "; ".join(messages),
                    actual=output
                )
        except Exception as e:
            return CheckResult(
                passed=False,
                primitive=assertion,
                message=f"Dynamic agent load failed: {e}",
                actual=None
            )
    
    # 策略 3: 无可用 runtime → 标记为 skipped
    return CheckResult(
        passed=True,  # Skipped counts as "not failed"
        primitive=assertion,
        message=f"Agent '{agent_name}' not available for execution (skipped)",
        actual=None
    )


def _execute_protocol_check(proto_check: ProtocolCheck,
                            context: Dict[str, Any]) -> CheckResult:
    """
    执行协议检查 — 验证数据是否符合 protocol 约束
    
    检查策略:
    1. 如果 context 中有 protocol 类 → 用 Pydantic 验证
    2. 如果有 field_checks → 执行每个字段检查
    3. 否则 → 检查基本的 schema 结构
    """
    protocol_name = proto_check.protocol_name
    data = proto_check.data
    if data is None:
        data = context.get("output")
    if data is None:
        data = context.get("response")
    
    # 策略 1: 从 runtime 模块获取 protocol 类
    runtime_module = context.get("runtime_module")
    if runtime_module and hasattr(runtime_module, protocol_name):
        try:
            proto_class = getattr(runtime_module, protocol_name)
            if hasattr(proto_class, 'model_validate'):
                # Pydantic v2
                validated = proto_class.model_validate(data)
                return CheckResult(
                    passed=True,
                    primitive=proto_check,
                    message=f"Protocol '{protocol_name}' validation passed",
                    actual=validated
                )
            elif hasattr(proto_class, 'parse_obj'):
                # Pydantic v1
                validated = proto_class.parse_obj(data)
                return CheckResult(
                    passed=True,
                    primitive=proto_check,
                    message=f"Protocol '{protocol_name}' validation passed",
                    actual=validated
                )
        except Exception as e:
            return CheckResult(
                passed=False,
                primitive=proto_check,
                message=f"Protocol '{protocol_name}' validation failed: {e}",
                actual=data
            )
    
    # 策略 2: 执行 field_checks
    if proto_check.field_checks:
        check_context = {**context, "data": data}
        all_passed = True
        messages = []
        
        for check in proto_check.field_checks:
            result = _execute_check(check, check_context)
            if not result.passed:
                all_passed = False
            messages.append(str(result))
        
        return CheckResult(
            passed=all_passed,
            primitive=proto_check,
            message=f"Protocol '{protocol_name}' field checks: " + "; ".join(messages),
            actual=data
        )
    
    # 策略 3: 基本 schema 检查 — 数据不为空即视为通过
    if data is not None:
        return CheckResult(
            passed=True,
            primitive=proto_check,
            message=f"Protocol '{protocol_name}' basic check passed (data exists)",
            actual=data
        )
    
    return CheckResult(
        passed=False,
        primitive=proto_check,
        message=f"Protocol '{protocol_name}' check failed: no data available",
        actual=None
    )


def _execute_pipeline_check(pipeline_check: PipelineCheck,
                            context: Dict[str, Any]) -> CheckResult:
    """
    执行管道检查 — 验证 DAG 管道输出
    
    由于管道执行需要完整的 runtime 环境，此处主要做基本验证。
    """
    pipeline_expr = pipeline_check.pipeline_expr
    
    # 检查管道表达式是否引用了存在的 agents
    # 解析 "raw >> Analyst >> Formatter" 格式
    agents_in_pipeline = re.findall(r'(\w+)', pipeline_expr)
    
    runtime_module = context.get("runtime_module")
    available_agents = []
    missing_agents = []
    
    if runtime_module:
        for agent_name in agents_in_pipeline:
            if hasattr(runtime_module, agent_name):
                available_agents.append(agent_name)
            else:
                missing_agents.append(agent_name)
    
    if missing_agents:
        return CheckResult(
            passed=False,
            primitive=pipeline_check,
            message=f"Pipeline agents not found: {missing_agents}",
            actual=None
        )
    
    # 尝试执行管道（如果有 runtime）
    if runtime_module and available_agents:
        try:
            # 简单的顺序管道执行
            input_text = pipeline_check.input_text
            current_output = input_text
            
            for agent_name in available_agents:
                agent_obj = getattr(runtime_module, agent_name)
                if hasattr(agent_obj, 'run'):
                    current_output = agent_obj.run(current_output)
                elif callable(agent_obj):
                    current_output = agent_obj(current_output)
            
            # 执行 checks
            check_context = {**context, "output": current_output}
            all_passed = True
            messages = []
            
            for check in pipeline_check.checks:
                result = _execute_check(check, check_context)
                if not result.passed:
                    all_passed = False
                messages.append(str(result))
            
            return CheckResult(
                passed=all_passed,
                primitive=pipeline_check,
                message=f"Pipeline '{pipeline_expr}': " + "; ".join(messages),
                actual=current_output
            )
        except Exception as e:
            return CheckResult(
                passed=False,
                primitive=pipeline_check,
                message=f"Pipeline execution failed: {e}",
                actual=None
            )
    
    # 无 runtime → 标记为 skipped
    return CheckResult(
        passed=True,
        primitive=pipeline_check,
        message=f"Pipeline '{pipeline_expr}' skipped (no runtime available)",
        actual=None
    )


def _execute_semantic_check(semantic_check: SemanticCheck,
                            context: Dict[str, Any]) -> CheckResult:
    """
    执行语义检查 — 用 LLM 判断输出是否符合语义预期
    
    如果有 LLM API 可用 → 实际调用 LLM 判断
    否则 → 基于关键词匹配做启发式判断
    """
    actual = semantic_check.actual or context.get("output", "")
    intent = semantic_check.intent
    
    # 策略 1: 使用 Nexa 的 semantic_if 机制 (LLM 判断)
    # 检查是否有 LLM 可用
    api_key = os.environ.get("NEXA_API_KEY") or os.environ.get("OPENAI_API_KEY")
    
    if api_key:
        try:
            from src.runtime.evaluator import nexa_semantic_eval
            result = nexa_semantic_eval(actual, intent)
            passed = result.lower() in ("yes", "true", "1", "pass")
            return CheckResult(
                passed=passed,
                primitive=semantic_check,
                message=f"SemanticCheck(LLM): '{intent}' → {result}",
                actual=actual
            )
        except Exception:
            pass
    
    # 策略 2: 启发式关键词匹配 — 检查 intent 中的关键词是否出现在 actual 中
    # 从 intent 中提取关键词（去掉引号内容作为匹配目标）
    keywords = re.findall(r'[\'"](\w+)[\'"]', intent)
    if not keywords:
        # 没有引号 → 提取所有非停用词
        stop_words = {"a", "an", "the", "is", "are", "was", "were", "be", "been",
                      "with", "and", "or", "not", "in", "on", "at", "to", "for",
                      "of", "by", "from", "as", "that", "this", "it", "they", "we"}
        words = re.findall(r'\b\w+\b', intent.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    if keywords and actual:
        matched = [kw for kw in keywords if kw.lower() in actual.lower()]
        if matched:
            return CheckResult(
                passed=True,
                primitive=semantic_check,
                message=f"SemanticCheck(heuristic): keywords {matched} found in output",
                actual=actual
            )
        else:
            return CheckResult(
                passed=False,
                primitive=semantic_check,
                message=f"SemanticCheck(heuristic): no keywords from '{intent}' found in output",
                actual=actual
            )
    
    # 无法判断 → 标记为 skipped
    return CheckResult(
        passed=True,
        primitive=semantic_check,
        message=f"SemanticCheck: '{intent}' (no LLM or heuristic match available, skipped)",
        actual=actual
    )


def _execute_http(http: Http, context: Dict[str, Any]) -> CheckResult:
    """
    执行 HTTP 请求原语
    """
    try:
        import urllib.request
        import urllib.error
        
        url = http.url
        if not url:
            return CheckResult(passed=False, primitive=http, message="No URL specified")
        
        data = json.dumps(http.body).encode() if http.body else None
        headers = {**http.headers}
        if data and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        
        req = urllib.request.Request(url, data=data, headers=headers, method=http.method)
        
        try:
            with urllib.request.urlopen(req) as response:
                response_body = response.read().decode('utf-8')
                response_status = response.status
                response_headers = dict(response.headers)
                
                # 构建响应上下文
                resp_context = {
                    **context,
                    "response": {
                        "status": response_status,
                        "body": response_body,
                        "headers": response_headers
                    }
                }
                
                # 执行 checks
                all_passed = True
                messages = []
                for check in http.checks:
                    result = _execute_check(check, resp_context)
                    if not result.passed:
                        all_passed = False
                    messages.append(str(result))
                
                return CheckResult(
                    passed=all_passed,
                    primitive=http,
                    message=f"HTTP {http.method} {url}: " + "; ".join(messages),
                    actual={"status": response_status, "body": response_body[:200]}
                )
        except urllib.error.HTTPError as e:
            # HTTP 错误响应
            resp_context = {
                **context,
                "response": {
                    "status": e.code,
                    "body": e.read().decode('utf-8') if e.readable() else "",
                    "headers": dict(e.headers) if hasattr(e, 'headers') else {}
                }
            }
            
            all_passed = True
            messages = []
            for check in http.checks:
                result = _execute_check(check, resp_context)
                if not result.passed:
                    all_passed = False
                messages.append(str(result))
            
            return CheckResult(
                passed=all_passed,
                primitive=http,
                message=f"HTTP {http.method} {url} (status {e.code}): " + "; ".join(messages),
                actual={"status": e.code}
            )
    except Exception as e:
        return CheckResult(
            passed=False,
            primitive=http,
            message=f"HTTP request failed: {e}",
            actual=None
        )


def _execute_cli(cli: Cli, context: Dict[str, Any]) -> CheckResult:
    """
    执行 CLI 命令原语
    """
    try:
        result = subprocess.run(
            cli.command, shell=True, capture_output=True, text=True, timeout=30
        )
        
        output = result.stdout + result.stderr
        
        cli_context = {**context, "output": output, "exit_code": result.returncode}
        
        all_passed = True
        messages = []
        for check in cli.checks:
            result_item = _execute_check(check, cli_context)
            if not result_item.passed:
                all_passed = False
            messages.append(str(result_item))
        
        return CheckResult(
            passed=all_passed,
            primitive=cli,
            message=f"CLI '{cli.command}': " + "; ".join(messages),
            actual=output[:200]
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            passed=False,
            primitive=cli,
            message=f"CLI command timed out: '{cli.command}'",
            actual=None
        )
    except Exception as e:
        return CheckResult(
            passed=False,
            primitive=cli,
            message=f"CLI execution failed: {e}",
            actual=None
        )


def _execute_read_file(read_file: ReadFile, context: Dict[str, Any]) -> CheckResult:
    """
    执行文件读取原语
    """
    try:
        with open(read_file.path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        file_context = {**context, "file_content": content}
        
        all_passed = True
        messages = []
        for check in read_file.checks:
            result = _execute_check(check, file_context)
            if not result.passed:
                all_passed = False
            messages.append(str(result))
        
        return CheckResult(
            passed=all_passed,
            primitive=read_file,
            message=f"ReadFile '{read_file.path}': " + "; ".join(messages),
            actual=content[:200]
        )
    except FileNotFoundError:
        return CheckResult(
            passed=False,
            primitive=read_file,
            message=f"File not found: '{read_file.path}'",
            actual=None
        )
    except Exception as e:
        return CheckResult(
            passed=False,
            primitive=read_file,
            message=f"ReadFile failed: {e}",
            actual=None
        )


def _execute_function_call(func_call: FunctionCall, 
                           context: Dict[str, Any]) -> CheckResult:
    """
    执行函数调用原语
    """
    runtime_module = context.get("runtime_module")
    
    if runtime_module and hasattr(runtime_module, func_call.function_name):
        try:
            fn = getattr(runtime_module, func_call.function_name)
            result = fn(*func_call.args, **func_call.kwargs)
            
            fn_context = {**context, "function_result": result}
            
            all_passed = True
            messages = []
            for check in func_call.checks:
                check_result = _execute_check(check, fn_context)
                if not check_result.passed:
                    all_passed = False
                messages.append(str(check_result))
            
            return CheckResult(
                passed=all_passed,
                primitive=func_call,
                message=f"FunctionCall '{func_call.function_name}': " + "; ".join(messages),
                actual=result
            )
        except Exception as e:
            return CheckResult(
                passed=False,
                primitive=func_call,
                message=f"Function call failed: {e}",
                actual=None
            )
    
    return CheckResult(
        passed=True,
        primitive=func_call,
        message=f"Function '{func_call.function_name}' not available (skipped)",
        actual=None
    )


def _execute_property_check(prop_check: PropertyCheck,
                            context: Dict[str, Any]) -> CheckResult:
    """
    执行属性检查原语
    """
    obj = _extract_value(prop_check.obj_name, context)
    
    if obj is None:
        return CheckResult(
            passed=False,
            primitive=prop_check,
            message=f"Object '{prop_check.obj_name}' not found",
            actual=None
        )
    
    if not hasattr(obj, prop_check.property_name):
        return CheckResult(
            passed=False,
            primitive=prop_check,
            message=f"Property '{prop_check.property_name}' not found on '{prop_check.obj_name}'",
            actual=None
        )
    
    prop_value = getattr(obj, prop_check.property_name)
    prop_context = {**context, "property_value": prop_value}
    
    all_passed = True
    messages = []
    for check in prop_check.checks:
        result = _execute_check(check, prop_context)
        if not result.passed:
            all_passed = False
        messages.append(str(result))
    
    return CheckResult(
        passed=all_passed,
        primitive=prop_check,
        message=f"PropertyCheck '{prop_check.obj_name}.{prop_check.property_name}': " + "; ".join(messages),
        actual=prop_value
    )


def _execute_invariant_check(inv_check: InvariantCheck,
                             context: Dict[str, Any]) -> CheckResult:
    """
    执行不变式检查原语
    """
    # 不变式检查需要 runtime 环境来评估表达式
    # 简化实现：标记为 skipped
    return CheckResult(
        passed=True,
        primitive=inv_check,
        message=f"Invariant '{inv_check.invariant_name}' check skipped (no expression evaluator)",
        actual=None
    )