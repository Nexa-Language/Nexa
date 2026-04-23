"""
IAL — Intent Assertion Language 公共 API

IAL 引擎让需求文档变成可执行测试，形成"需求→实现→验证"的闭环。

核心架构:
    "they see success response"
        ↓ vocabulary lookup
    "component.success_response"
        ↓ component expansion  
    ["status 2xx", "body contains 'ok'"]
        ↓ standard term resolution
    [Check(InRange, "response.status", 200-299), Check(Contains, "response.body", "ok")]
        ↓ execution
    [✓, ✓]

公共 API:
    resolve() — 递归术语重写（断言文本 → 原语列表）
    execute() — 原语执行（原语 → CheckResult）
    create_vocabulary() — 创建标准词汇表
"""

from src.ial.primitives import (
    CheckOp, Check, AgentAssertion, ProtocolCheck, PipelineCheck,
    SemanticCheck, Http, Cli, CodeQuality, ReadFile, FunctionCall,
    PropertyCheck, InvariantCheck, Primitive,
    CheckResult, ScenarioResult, FeatureResult
)
from src.ial.vocabulary import Vocabulary, TermEntry
from src.ial.resolve import resolve, resolve_scenario_assertions, MAX_RECURSION_DEPTH
from src.ial.execute import execute_primitive, execute_primitives
from src.ial.standard import create_standard_vocabulary


def create_vocabulary() -> Vocabulary:
    """创建包含标准术语的词汇表（便捷入口）"""
    return create_standard_vocabulary()


__all__ = [
    # 原语类型
    'CheckOp', 'Check', 'AgentAssertion', 'ProtocolCheck', 'PipelineCheck',
    'SemanticCheck', 'Http', 'Cli', 'CodeQuality', 'ReadFile', 'FunctionCall',
    'PropertyCheck', 'InvariantCheck', 'Primitive',
    # 结果类型
    'CheckResult', 'ScenarioResult', 'FeatureResult',
    # 词汇表
    'Vocabulary', 'TermEntry',
    # 核心函数
    'resolve', 'resolve_scenario_assertions', 'MAX_RECURSION_DEPTH',
    'execute_primitive', 'execute_primitives',
    'create_vocabulary', 'create_standard_vocabulary',
]