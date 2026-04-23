"""
IAL Primitives — Intent Assertion Language 原语类型定义

定义了 IAL 引擎的所有原子检查操作和断言原语。
新断言应该是词汇条目而非新原语，保持引擎固定不变。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional, List, Union


class CheckOp(Enum):
    """IAL 检查操作枚举 — 原子比较操作"""
    Equals = "equals"
    NotEquals = "not_equals"
    Contains = "contains"
    NotContains = "not_contains"
    Matches = "matches"
    Exists = "exists"
    NotExists = "not_exists"
    LessThan = "less_than"
    GreaterThan = "greater_than"
    InRange = "in_range"
    StartsWith = "starts_with"
    EndsWith = "ends_with"
    IsType = "is_type"
    HasLength = "has_length"


class PrimitiveType(Enum):
    """IAL 原语类型枚举"""
    AgentAssertion = "agent_assertion"
    ProtocolCheck = "protocol_check"
    PipelineCheck = "pipeline_check"
    SemanticCheck = "semantic_check"
    Http = "http"
    Cli = "cli"
    CodeQuality = "code_quality"
    Sql = "sql"
    ReadFile = "read_file"
    FunctionCall = "function_call"
    PropertyCheck = "property_check"
    InvariantCheck = "invariant_check"
    Check = "check"


@dataclass
class Check:
    """
    通用检查原语 — 对目标字段执行 CheckOp 比较
    
    Examples:
        Check(CheckOp.Contains, "response.body", "ok")
        Check(CheckOp.InRange, "response.status", (200, 299))
        Check(CheckOp.Equals, "output", "hello world")
    """
    op: CheckOp
    target: str
    expected: Any
    
    def __repr__(self):
        return f"Check({self.op.value}, {self.target}, {self.expected})"


@dataclass
class AgentAssertion:
    """
    Agent 断言原语 — 直接调用 agent 并检查输出
    
    Args:
        agent_name: Nexa agent 名称
        input_text: 输入文本
        checks: 对 agent 输出执行的检查列表
    """
    agent_name: str
    input_text: str
    checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"AgentAssertion({self.agent_name}, input={self.input_text!r}, checks={self.checks})"


@dataclass
class ProtocolCheck:
    """
    协议检查原语 — 验证输出符合 protocol 约束
    
    Args:
        protocol_name: Nexa protocol 名称
        data: 待验证的数据（或从上下文获取）
        field_checks: 对各字段执行的检查列表
    """
    protocol_name: str
    data: Optional[Any] = None
    field_checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"ProtocolCheck({self.protocol_name}, checks={self.field_checks})"


@dataclass
class PipelineCheck:
    """
    管道检查原语 — 验证 DAG 管道输出
    
    Args:
        pipeline_expr: 管道表达式（如 "raw >> Analyst >> Formatter"）
        input_text: 输入文本
        checks: 对管道输出执行的检查列表
    """
    pipeline_expr: str
    input_text: str = ""
    checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"PipelineCheck({self.pipeline_expr}, checks={self.checks})"


@dataclass
class SemanticCheck:
    """
    语义检查原语 — 用 LLM 判断输出是否符合语义预期
    
    Args:
        actual: 实际输出文本
        intent: 期望的语义描述
        context: 上下文信息
    """
    actual: str
    intent: str
    context: str = ""
    
    def __repr__(self):
        return f"SemanticCheck(intent={self.intent!r})"


@dataclass
class Http:
    """
    HTTP 请求原语 — 执行 HTTP 请求并对响应执行检查
    
    Args:
        method: HTTP 方法 (GET, POST, etc.)
        url: 请求 URL
        headers: 请求头
        body: 请求体
        checks: 对响应执行的检查列表
    """
    method: str = "GET"
    url: str = ""
    headers: dict = field(default_factory=dict)
    body: Optional[Any] = None
    checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"Http({self.method} {self.url}, checks={self.checks})"


@dataclass
class Cli:
    """
    CLI 命令原语 — 执行命令行并对输出执行检查
    
    Args:
        command: 命令字符串
        checks: 对命令输出执行的检查列表
    """
    command: str
    checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"Cli({self.command!r}, checks={self.checks})"


@dataclass
class CodeQuality:
    """
    代码质量检查原语
    
    Args:
        file_path: 待检查的文件路径
        metric: 质量指标 (lint, complexity, etc.)
        checks: 检查列表
    """
    file_path: str
    metric: str = "lint"
    checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"CodeQuality({self.file_path}, metric={self.metric})"


@dataclass
class ReadFile:
    """
    文件读取原语 — 读取文件内容并执行检查
    
    Args:
        path: 文件路径
        checks: 对文件内容执行的检查列表
    """
    path: str
    checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"ReadFile({self.path}, checks={self.checks})"


@dataclass
class FunctionCall:
    """
    函数调用原语 — 调用指定函数并检查返回值
    
    Args:
        function_name: 函数名
        args: 函数参数
        checks: 对返回值执行的检查列表
    """
    function_name: str
    args: List[Any] = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"FunctionCall({self.function_name}, checks={self.checks})"


@dataclass
class PropertyCheck:
    """
    属性检查原语 — 检查对象的属性值
    
    Args:
        obj_name: 对象名称
        property_name: 属性名
        checks: 对属性值执行的检查列表
    """
    obj_name: str
    property_name: str
    checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"PropertyCheck({self.obj_name}.{self.property_name})"


@dataclass
class InvariantCheck:
    """
    不变式检查原语 — 验证系统不变式
    
    Args:
        invariant_name: 不变式名称
        expression: 不变式表达式
        checks: 检查列表
    """
    invariant_name: str
    expression: str = ""
    checks: List[Check] = field(default_factory=list)
    
    def __repr__(self):
        return f"InvariantCheck({self.invariant_name})"


# 统一的原语类型别名
Primitive = Union[
    AgentAssertion, ProtocolCheck, PipelineCheck, SemanticCheck,
    Http, Cli, CodeQuality, ReadFile, FunctionCall,
    PropertyCheck, InvariantCheck, Check
]


@dataclass
class CheckResult:
    """
    单个检查的结果
    
    Args:
        passed: 是否通过
        primitive: 执行的原语
        message: 结果消息
        actual: 实际值（用于调试）
    """
    passed: bool
    primitive: Primitive
    message: str = ""
    actual: Any = None
    
    def __repr__(self):
        symbol = "✓" if self.passed else "✗"
        return f"{symbol} {self.primitive}: {self.message}"


@dataclass
class ScenarioResult:
    """
    Scenario 执行结果
    
    Args:
        scenario_name: 场景名称
        feature_id: 所属 feature ID
        results: 各断言的检查结果
        passed: 是否全部通过
    """
    scenario_name: str
    feature_id: str
    results: List[CheckResult] = field(default_factory=list)
    passed: bool = True
    
    def __repr__(self):
        symbol = "✓" if self.passed else "✗"
        return f"{symbol} Scenario '{self.scenario_name}' ({len(self.results)} checks)"


@dataclass 
class FeatureResult:
    """
    Feature 执行结果
    
    Args:
        feature_id: feature ID
        feature_name: feature 名称
        scenario_results: 各场景的结果
        passed: 是否全部通过
    """
    feature_id: str
    feature_name: str
    scenario_results: List[ScenarioResult] = field(default_factory=list)
    passed: bool = True
    
    def __repr__(self):
        symbol = "✓" if self.passed else "✗"
        return f"{symbol} Feature '{self.feature_id}' ({len(self.scenario_results)} scenarios)"