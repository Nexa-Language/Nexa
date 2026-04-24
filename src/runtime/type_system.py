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
Nexa Gradual Type System (渐进式类型系统) 运行时引擎

双轴类型安全模式:
- NEXA_TYPE_MODE (运行时轴): strict / warn / forgiving
- NEXA_LINT_MODE (lint轴): default / warn / strict

核心原则:
- 渐进式是核心: 不是"全有或全无"，从无类型开始逐步添加
- Agent 优先: 类型系统首先为 Agent 输入输出设计
- Protocol 升级: 从字符串标注 → 完整类型表达式，保持向后兼容
- 不阻塞执行: 类型检查作为 lint pass，即使有类型错误程序也能运行(warn模式)
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union, get_args, get_origin
from enum import Enum

logger = logging.getLogger("nexa.type_system")


# ============================================================
# 双轴类型安全模式
# ============================================================

class TypeMode(Enum):
    """运行时类型检查模式 (NEXA_TYPE_MODE)
    
    - strict:    类型不匹配=运行时错误，程序终止（适合认证/支付等关键场景）
    - warn:      类型不匹配=日志警告并继续（默认）
    - forgiving: 类型不匹配=静默忽略
    """
    STRICT = "strict"
    WARN = "warn"
    FORGIVING = "forgiving"


class LintMode(Enum):
    """Lint 时类型检查模式 (NEXA_LINT_MODE)
    
    - default: 只检查有类型标注的代码（默认）
    - warn:    对缺失类型标注发出警告
    - strict:  缺失类型标注=lint错误（非零退出码）
    """
    DEFAULT = "default"
    WARN = "warn"
    STRICT = "strict"


def get_type_mode(cli_override: Optional[str] = None) -> TypeMode:
    """获取运行时类型检查模式
    
    优先级: CLI flag > 环境变量 > nexa.toml > 默认值(warn)
    
    Args:
        cli_override: CLI 参数覆盖值
    
    Returns:
        TypeMode 枚举值
    """
    from .config import load_nexa_config
    
    # 1. CLI flag (最高优先级)
    if cli_override:
        try:
            return TypeMode(cli_override.lower())
        except ValueError:
            logger.warning(f"Invalid NEXA_TYPE_MODE from CLI: {cli_override}, using default")
    
    # 2. 环境变量
    env_val = os.environ.get("NEXA_TYPE_MODE")
    if env_val:
        try:
            return TypeMode(env_val.lower())
        except ValueError:
            logger.warning(f"Invalid NEXA_TYPE_MODE from env: {env_val}, using default")
    
    # 3. nexa.toml 配置文件
    config = load_nexa_config()
    config_val = config.get("type", {}).get("mode")
    if config_val:
        try:
            return TypeMode(config_val.lower())
        except ValueError:
            logger.warning(f"Invalid NEXA_TYPE_MODE from config: {config_val}, using default")
    
    # 4. 默认值
    return TypeMode.WARN


def get_lint_mode(cli_override: Optional[str] = None) -> LintMode:
    """获取 lint 类型检查模式
    
    优先级: CLI flag > 环境变量 > nexa.toml > 默认值(default)
    
    Args:
        cli_override: CLI 参数覆盖值
    
    Returns:
        LintMode 枚举值
    """
    from .config import load_nexa_config
    
    # 1. CLI flag (最高优先级)
    if cli_override:
        try:
            return LintMode(cli_override.lower())
        except ValueError:
            logger.warning(f"Invalid NEXA_LINT_MODE from CLI: {cli_override}, using default")
    
    # 2. 环境变量
    env_val = os.environ.get("NEXA_LINT_MODE")
    if env_val:
        try:
            return LintMode(env_val.lower())
        except ValueError:
            logger.warning(f"Invalid NEXA_LINT_MODE from env: {env_val}, using default")
    
    # 3. nexa.toml 配置文件
    config = load_nexa_config()
    config_val = config.get("lint", {}).get("mode")
    if config_val:
        try:
            return LintMode(config_val.lower())
        except ValueError:
            logger.warning(f"Invalid NEXA_LINT_MODE from config: {config_val}, using default")
    
    # 4. 默认值
    return LintMode.DEFAULT


# ============================================================
# 类型表达式 (Type Expression) 表示
# ============================================================

class TypeExpr:
    """类型表达式基类 — 表示 Nexa 类型标注的内部结构
    
    子类:
    - PrimitiveTypeExpr: str, int, float, bool, unit
    - GenericTypeExpr: list[T], dict[K, V], Option[T], Result[T, E]
    - UnionTypeExpr: str | int | float
    - OptionTypeExpr: T? (简写为 Option[T])
    - ResultTypeExpr: Result[T, E]
    - AliasTypeExpr: 自定义类型别名引用
    - FuncTypeExpr: (T1, T2) -> T3
    - SemanticTypeExpr: str @ "constraint" (已有语义类型)
    """
    
    def is_compatible_with(self, value: Any) -> bool:
        """检查值是否与此类型兼容"""
        return TypeInferrer.infer_type(value).is_subtype_of(self)
    
    def to_python_type(self) -> type:
        """将 Nexa 类型表达式转换为 Python 类型"""
        return Any  # 基类默认
    
    def to_type_str(self) -> str:
        """将类型表达式转换为字符串表示"""
        return "Any"


class PrimitiveTypeExpr(TypeExpr):
    """基本类型: str, int, float, bool, unit"""
    
    _PRIMITIVE_MAP = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "unit": type(None),
    }
    
    def __init__(self, name: str):
        self.name = name
        assert name in self._PRIMITIVE_MAP, f"Unknown primitive type: {name}"
    
    def to_python_type(self) -> type:
        return self._PRIMITIVE_MAP[self.name]
    
    def to_type_str(self) -> str:
        return self.name
    
    def __eq__(self, other):
        return isinstance(other, PrimitiveTypeExpr) and self.name == other.name
    
    def __hash__(self):
        return hash(self.name)
    
    def __repr__(self):
        return f"PrimitiveTypeExpr({self.name})"


class GenericTypeExpr(TypeExpr):
    """泛型类型: list[T], dict[K, V], Option[T], Result[T, E]"""
    
    _GENERIC_MAP = {
        "list": list,
        "dict": dict,
    }
    
    def __init__(self, name: str, type_params: List[TypeExpr]):
        self.name = name
        self.type_params = type_params
    
    def to_python_type(self) -> type:
        if self.name == "list":
            elem_type = self.type_params[0].to_python_type() if self.type_params else Any
            return List[elem_type]
        elif self.name == "dict":
            key_type = self.type_params[0].to_python_type() if self.type_params else Any
            val_type = self.type_params[1].to_python_type() if len(self.type_params) > 1 else Any
            return Dict[key_type, val_type]
        elif self.name == "Option":
            inner_type = self.type_params[0].to_python_type() if self.type_params else Any
            return Optional[inner_type]
        elif self.name == "Result":
            ok_type = self.type_params[0].to_python_type() if self.type_params else Any
            err_type = self.type_params[1].to_python_type() if len(self.type_params) > 1 else Any
            return Union[ok_type, err_type]
        return Any
    
    def to_type_str(self) -> str:
        params_str = ", ".join(p.to_type_str() for p in self.type_params)
        if self.name == "Option":
            return f"{self.type_params[0].to_type_str()}?" if self.type_params else "Option"
        return f"{self.name}[{params_str}]"
    
    def __eq__(self, other):
        return isinstance(other, GenericTypeExpr) and self.name == other.name and self.type_params == other.type_params
    
    def __hash__(self):
        return hash((self.name, tuple(hash(p) for p in self.type_params)))
    
    def __repr__(self):
        return f"GenericTypeExpr({self.name}, {self.type_params})"


class UnionTypeExpr(TypeExpr):
    """联合类型: str | int | float"""
    
    def __init__(self, types: List[TypeExpr]):
        self.types = types
    
    def to_python_type(self) -> type:
        py_types = tuple(t.to_python_type() for t in self.types)
        return Union[py_types]
    
    def to_type_str(self) -> str:
        return " | ".join(t.to_type_str() for t in self.types)
    
    def __eq__(self, other):
        return isinstance(other, UnionTypeExpr) and set(self.types) == set(other.types)
    
    def __hash__(self):
        return hash(tuple(sorted(hash(t) for t in self.types)))
    
    def __repr__(self):
        return f"UnionTypeExpr({self.types})"


class OptionTypeExpr(TypeExpr):
    """可选类型: T? = Option[T]"""
    
    def __init__(self, inner: TypeExpr):
        self.inner = inner
    
    def to_python_type(self) -> type:
        return Optional[self.inner.to_python_type()]
    
    def to_type_str(self) -> str:
        return f"{self.inner.to_type_str()}?"
    
    def __eq__(self, other):
        return isinstance(other, OptionTypeExpr) and self.inner == other.inner
    
    def __hash__(self):
        return hash(("Option", hash(self.inner)))
    
    def __repr__(self):
        return f"OptionTypeExpr({self.inner})"


class ResultTypeExpr(TypeExpr):
    """Result 类型: Result[T, E]"""
    
    def __init__(self, ok_type: TypeExpr, err_type: TypeExpr):
        self.ok_type = ok_type
        self.err_type = err_type
    
    def to_python_type(self) -> type:
        return Union[self.ok_type.to_python_type(), self.err_type.to_python_type()]
    
    def to_type_str(self) -> str:
        return f"Result[{self.ok_type.to_type_str()}, {self.err_type.to_type_str()}]"
    
    def __eq__(self, other):
        return isinstance(other, ResultTypeExpr) and self.ok_type == other.ok_type and self.err_type == other.err_type
    
    def __hash__(self):
        return hash(("Result", hash(self.ok_type), hash(self.err_type)))
    
    def __repr__(self):
        return f"ResultTypeExpr({self.ok_type}, {self.err_type})"


class AliasTypeExpr(TypeExpr):
    """类型别名引用: UserId (指向 type UserId = int)"""
    
    def __init__(self, name: str, resolved: Optional[TypeExpr] = None):
        self.name = name
        self.resolved = resolved  # 如果已解析，指向实际类型
    
    def to_python_type(self) -> type:
        if self.resolved:
            return self.resolved.to_python_type()
        return Any  # 未解析的别名
    
    def to_type_str(self) -> str:
        return self.name
    
    def __eq__(self, other):
        return isinstance(other, AliasTypeExpr) and self.name == other.name
    
    def __hash__(self):
        return hash(self.name)
    
    def __repr__(self):
        return f"AliasTypeExpr({self.name}, resolved={self.resolved})"


class FuncTypeExpr(TypeExpr):
    """函数类型: (T1, T2) -> T3"""
    
    def __init__(self, param_types: List[TypeExpr], return_type: TypeExpr):
        self.param_types = param_types
        self.return_type = return_type
    
    def to_python_type(self) -> type:
        return Callable  # 简化处理
    
    def to_type_str(self) -> str:
        params_str = ", ".join(p.to_type_str() for p in self.param_types)
        return f"({params_str}) -> {self.return_type.to_type_str()}"
    
    def __eq__(self, other):
        return isinstance(other, FuncTypeExpr) and self.param_types == other.param_types and self.return_type == other.return_type
    
    def __hash__(self):
        return hash((tuple(hash(p) for p in self.param_types), hash(self.return_type)))
    
    def __repr__(self):
        return f"FuncTypeExpr({self.param_types}, {self.return_type})"


class SemanticTypeExpr(TypeExpr):
    """语义类型: str @ "constraint" (兼容已有的 type 语义声明)"""
    
    def __init__(self, base: TypeExpr, constraint: str):
        self.base = base
        self.constraint = constraint
    
    def to_python_type(self) -> type:
        return self.base.to_python_type()
    
    def to_type_str(self) -> str:
        return f"{self.base.to_type_str()} @ \"{self.constraint}\""
    
    def __eq__(self, other):
        return isinstance(other, SemanticTypeExpr) and self.base == other.base and self.constraint == other.constraint
    
    def __hash__(self):
        return hash((hash(self.base), self.constraint))
    
    def __repr__(self):
        return f"SemanticTypeExpr({self.base}, \"{self.constraint}\")"


# ============================================================
# 类型推断器 (Type Inferrer)
# ============================================================

class InferredType(TypeExpr):
    """推断出的类型 — 局部变量自动推断的结果
    
    let x = 5  → InferredType(PrimitiveTypeExpr("int"), source="literal")
    let name = "Alice" → InferredType(PrimitiveTypeExpr("str"), source="literal")
    """
    
    def __init__(self, actual_type: TypeExpr, source: str = "inferred"):
        self.actual_type = actual_type
        self.source = source  # "literal", "expression", "return", etc.
    
    def to_python_type(self) -> type:
        return self.actual_type.to_python_type()
    
    def to_type_str(self) -> str:
        return self.actual_type.to_type_str()
    
    def __repr__(self):
        return f"InferredType({self.actual_type}, source={self.source})"


class TypeInferrer:
    """类型推断器 — 从值推断 Nexa 类型
    
    用法:
    >>> TypeInferrer.infer_type(5)
    PrimitiveTypeExpr("int")
    >>> TypeInferrer.infer_type([1, 2, 3])
    GenericTypeExpr("list", [PrimitiveTypeExpr("int")])
    >>> TypeInferrer.infer_type(None)
    OptionTypeExpr(PrimitiveTypeExpr("unit"))
    """
    
    @staticmethod
    def infer_type(value: Any) -> TypeExpr:
        """从 Python 值推断 Nexa 类型表达式"""
        if value is None:
            return OptionTypeExpr(PrimitiveTypeExpr("unit"))
        
        # 基本类型
        if isinstance(value, bool):  # bool 必须在 int 前检查，因为 bool 是 int 的子类
            return PrimitiveTypeExpr("bool")
        if isinstance(value, int):
            return PrimitiveTypeExpr("int")
        if isinstance(value, float):
            return PrimitiveTypeExpr("float")
        if isinstance(value, str):
            return PrimitiveTypeExpr("str")
        
        # 复合类型
        if isinstance(value, list):
            if len(value) == 0:
                return GenericTypeExpr("list", [AliasTypeExpr("Any")])
            # 推断元素类型 — 取所有元素的共同类型
            elem_types = [TypeInferrer.infer_type(elem) for elem in value]
            unified = TypeInferrer._unify_types(elem_types)
            return GenericTypeExpr("list", [unified])
        
        if isinstance(value, dict):
            if len(value) == 0:
                return GenericTypeExpr("dict", [AliasTypeExpr("Any"), AliasTypeExpr("Any")])
            key_types = [TypeInferrer.infer_type(k) for k in value.keys()]
            val_types = [TypeInferrer.infer_type(v) for v in value.values()]
            return GenericTypeExpr("dict", [
                TypeInferrer._unify_types(key_types),
                TypeInferrer._unify_types(val_types)
            ])
        
        # Pydantic 模型或其他自定义类型
        if hasattr(value, '__class__') and value.__class__.__name__ != 'type':
            return AliasTypeExpr(value.__class__.__name__)
        
        return AliasTypeExpr("Any")
    
    @staticmethod
    def infer_from_expression(expr_ast: dict) -> TypeExpr:
        """从 AST 表达式节点推断类型（用于局部变量推断）
        
        Args:
            expr_ast: 表达式 AST 字典
        
        Returns:
            推断的 TypeExpr
        """
        expr_type = expr_ast.get("type", "")
        
        if expr_type == "IntLiteral":
            return PrimitiveTypeExpr("int")
        elif expr_type == "FloatLiteral":
            return PrimitiveTypeExpr("float")
        elif expr_type == "StringLiteral" or expr_type == "InterpolatedString":
            return PrimitiveTypeExpr("str")
        elif expr_type == "BooleanLiteral":
            return PrimitiveTypeExpr("bool")
        elif expr_type == "Identifier":
            # 需要符号表才能推断 — 返回 Any
            return AliasTypeExpr("Any")
        elif expr_type == "ListExpression":
            return GenericTypeExpr("list", [AliasTypeExpr("Any")])
        elif expr_type == "DictExpression":
            return GenericTypeExpr("dict", [AliasTypeExpr("Any"), AliasTypeExpr("Any")])
        elif expr_type == "PipelineExpression":
            # 管道表达式返回最后一个 agent 的输出类型
            return AliasTypeExpr("Any")
        elif expr_type == "AgentCallExpression":
            # Agent 调用 — 返回其 protocol 类型或 Any
            return AliasTypeExpr("Any")
        elif expr_type == "BinaryExpression":
            # 二元运算: 数值运算返回数值类型
            op = expr_ast.get("operator", "")
            if op in ("+", "-", "*", "/", "%"):
                return AliasTypeExpr("Any")  # 简化：需要更多上下文
            return AliasTypeExpr("Any")
        
        return AliasTypeExpr("Any")
    
    @staticmethod
    def _unify_types(types: List[TypeExpr]) -> TypeExpr:
        """统一多个类型 — 如果都相同则返回该类型，否则返回联合类型"""
        if not types:
            return AliasTypeExpr("Any")
        
        unique_types = list(set(types))
        if len(unique_types) == 1:
            return unique_types[0]
        
        return UnionTypeExpr(unique_types)


# ============================================================
# 类型检查结果
# ============================================================

class TypeCheckResult:
    """类型检查结果
    
    Attributes:
        passed: 是否通过类型检查
        violations: 类型违反列表
        warnings: 类型警告列表
    """
    
    def __init__(self, passed: bool = True, violations: List['TypeViolation'] = None,
                 warnings: List['TypeWarning'] = None):
        self.passed = passed
        self.violations = violations or []
        self.warnings = warnings or []
    
    def add_violation(self, violation: 'TypeViolation'):
        self.violations.append(violation)
        self.passed = False
    
    def add_warning(self, warning: 'TypeWarning'):
        self.warnings.append(warning)
    
    def __repr__(self):
        if self.passed:
            return "TypeCheckResult(passed=True)"
        return f"TypeCheckResult(passed=False, violations={len(self.violations)}, warnings={len(self.warnings)})"
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [w.to_dict() for w in self.warnings],
        }


class TypeViolation(Exception):
    """类型违反异常 — 与 ContractViolation 区分
    
    NEXA_TYPE_MODE=strict 时抛出此异常终止程序。
    
    Attributes:
        expected_type: 期望的类型表达式
        actual_type: 实际的类型表达式
        value: 实际值
        context: 上下文信息（函数名、字段名等）
    """
    
    def __init__(self, message: str, expected_type: Optional[TypeExpr] = None,
                 actual_type: Optional[TypeExpr] = None, value: Any = None,
                 context: Optional[Dict] = None):
        super().__init__(message)
        self.expected_type = expected_type
        self.actual_type = actual_type
        self.value = value
        self.context = context or {}
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "type": "TypeViolation",
            "message": str(self),
            "expected_type": self.expected_type.to_type_str() if self.expected_type else "Unknown",
            "actual_type": self.actual_type.to_type_str() if self.actual_type else "Unknown",
            "context": self.context,
        }
    
    def __repr__(self):
        expected = self.expected_type.to_type_str() if self.expected_type else "Unknown"
        actual = self.actual_type.to_type_str() if self.actual_type else "Unknown"
        return f"TypeViolation(expected={expected}, actual={actual}, context={self.context})"


class TypeWarning:
    """类型警告 — NEXA_TYPE_MODE=warn 时使用
    
    Attributes:
        message: 警告消息
        expected_type: 期望的类型表达式
        actual_type: 实际的类型表达式
        context: 上下文信息
    """
    
    def __init__(self, message: str, expected_type: Optional[TypeExpr] = None,
                 actual_type: Optional[TypeExpr] = None, context: Optional[Dict] = None):
        self.message = message
        self.expected_type = expected_type
        self.actual_type = actual_type
        self.context = context or {}
    
    def to_dict(self) -> Dict:
        return {
            "type": "TypeWarning",
            "message": self.message,
            "expected_type": self.expected_type.to_type_str() if self.expected_type else "Unknown",
            "actual_type": self.actual_type.to_type_str() if self.actual_type else "Unknown",
            "context": self.context,
        }
    
    def __repr__(self):
        expected = self.expected_type.to_type_str() if self.expected_type else "Unknown"
        actual = self.actual_type.to_type_str() if self.actual_type else "Unknown"
        return f"TypeWarning(expected={expected}, actual={actual}, context={self.context})"


# ============================================================
# 类型检查器 (Type Checker)
# ============================================================

class TypeChecker:
    """渐进式类型检查器
    
    核心方法:
    - check_function_call: 函数调用边界类型检查
    - check_return_type: 返回类型验证
    - check_protocol_compliance: Protocol 合规性检查
    - check_union_type: 联合类型兼容性检查
    - check_option_type: Option[T] 类型处理
    - check_result_type: Result[T, E] 类型处理
    """
    
    def __init__(self, type_mode: Optional[TypeMode] = None, lint_mode: Optional[LintMode] = None):
        self.type_mode = type_mode or get_type_mode()
        self.lint_mode = lint_mode or get_lint_mode()
        self._type_registry: Dict[str, TypeExpr] = {}  # 类型别名注册表
        self._protocol_registry: Dict[str, Dict[str, TypeExpr]] = {}  # Protocol 注册表
    
    def register_type_alias(self, name: str, type_expr: TypeExpr):
        """注册类型别名"""
        self._type_registry[name] = type_expr
    
    def register_protocol(self, name: str, fields: Dict[str, TypeExpr]):
        """注册 Protocol 类型信息"""
        self._protocol_registry[name] = fields
    
    def register_protocol_field(self, protocol_name: str, field_name: str, field_type: TypeExpr):
        """注册 Protocol 单个字段类型（增量注册）
        
        Args:
            protocol_name: Protocol 名称
            field_name: 字段名
            field_type: 字段类型表达式
        """
        if protocol_name not in self._protocol_registry:
            self._protocol_registry[protocol_name] = {}
        self._protocol_registry[protocol_name][field_name] = field_type
    
    def resolve_type(self, type_expr: TypeExpr) -> TypeExpr:
        """解析类型别名到实际类型"""
        if isinstance(type_expr, AliasTypeExpr):
            resolved = self._type_registry.get(type_expr.name)
            if resolved:
                type_expr.resolved = resolved
                return self.resolve_type(resolved)  # 递归解析
            return type_expr
        elif isinstance(type_expr, GenericTypeExpr):
            # 解析泛型参数中的别名
            type_expr.type_params = [self.resolve_type(p) for p in type_expr.type_params]
            return type_expr
        elif isinstance(type_expr, UnionTypeExpr):
            type_expr.types = [self.resolve_type(t) for t in type_expr.types]
            return type_expr
        elif isinstance(type_expr, OptionTypeExpr):
            type_expr.inner = self.resolve_type(type_expr.inner)
            return type_expr
        elif isinstance(type_expr, ResultTypeExpr):
            type_expr.ok_type = self.resolve_type(type_expr.ok_type)
            type_expr.err_type = self.resolve_type(type_expr.err_type)
            return type_expr
        return type_expr
    
    def check_type_match(self, value: Any, expected_type: TypeExpr,
                         context: Optional[Dict] = None) -> TypeCheckResult:
        """检查值是否匹配期望类型
        
        Args:
            value: 实际值
            expected_type: 期望的类型表达式
            context: 上下文信息（函数名、字段名等）
        
        Returns:
            TypeCheckResult
        """
        result = TypeCheckResult()
        
        # 解析类型别名
        expected_type = self.resolve_type(expected_type)
        
        # 推断实际类型
        actual_type = TypeInferrer.infer_type(value)
        
        # 检查兼容性
        if not self._is_type_compatible(actual_type, expected_type, value):
            violation = TypeViolation(
                message=f"Type mismatch: expected {expected_type.to_type_str()}, got {actual_type.to_type_str()}",
                expected_type=expected_type,
                actual_type=actual_type,
                value=value,
                context=context or {}
            )
            
            if self.type_mode == TypeMode.STRICT:
                result.add_violation(violation)
            elif self.type_mode == TypeMode.WARN:
                result.add_warning(TypeWarning(
                    message=str(violation),
                    expected_type=expected_type,
                    actual_type=actual_type,
                    context=context or {}
                ))
                # warn 模式不阻止通过，但记录警告
            # forgiving 模式完全忽略
        
        return result
    
    def check_function_call(self, func_name: str, arg_values: List[Any],
                            param_types: List[TypeExpr]) -> TypeCheckResult:
        """函数调用边界类型检查
        
        Args:
            func_name: 函数名
            arg_values: 实际参数值列表
            param_types: 参数声明类型列表
        
        Returns:
            TypeCheckResult
        """
        result = TypeCheckResult()
        
        # 参数数量检查
        if len(arg_values) != len(param_types):
            violation = TypeViolation(
                message=f"Function '{func_name}' expects {len(param_types)} arguments, got {len(arg_values)}",
                context={"function": func_name, "expected_count": len(param_types), "actual_count": len(arg_values)}
            )
            if self.type_mode == TypeMode.STRICT:
                result.add_violation(violation)
            elif self.type_mode == TypeMode.WARN:
                result.add_warning(TypeWarning(message=str(violation), context=violation.context))
            return result
        
        #逐参数类型检查
        for i, (arg_val, param_type) in enumerate(zip(arg_values, param_types)):
            param_result = self.check_type_match(
                arg_val, param_type,
                context={"function": func_name, "param_index": i}
            )
            result.violations.extend(param_result.violations)
            result.warnings.extend(param_result.warnings)
        
        if result.violations:
            result.passed = False
        
        return result
    
    def check_return_type(self, func_name: str, return_value: Any,
                          declared_return: TypeExpr) -> TypeCheckResult:
        """返回类型验证
        
        Args:
            func_name: 函数名
            return_value: 实际返回值
            declared_return: 声明的返回类型
        
        Returns:
            TypeCheckResult
        """
        return self.check_type_match(
            return_value, declared_return,
            context={"function": func_name, "check": "return_type"}
        )
    
    def check_protocol_compliance(self, data: Dict[str, Any],
                                  protocol_name: str) -> TypeCheckResult:
        """Protocol 合规性检查
        
        Args:
            data: 实际数据字典
            protocol_name: Protocol 名称
        
        Returns:
            TypeCheckResult
        """
        result = TypeCheckResult()
        
        protocol_fields = self._protocol_registry.get(protocol_name)
        if not protocol_fields:
            # 未注册的 Protocol — 无法检查
            logger.debug(f"Protocol '{protocol_name}' not registered in type checker")
            return result
        
        # 检查每个字段
        for field_name, field_type in protocol_fields.items():
            if field_name not in data:
                # 缺失字段
                violation = TypeViolation(
                    message=f"Protocol '{protocol_name}' missing field '{field_name}'",
                    expected_type=field_type,
                    actual_type=None,
                    value=None,
                    context={"protocol": protocol_name, "field": field_name, "check": "missing_field"}
                )
                if self.type_mode == TypeMode.STRICT:
                    result.add_violation(violation)
                elif self.type_mode == TypeMode.WARN:
                    result.add_warning(TypeWarning(
                        message=str(violation),
                        expected_type=field_type,
                        context=violation.context
                    ))
                continue
            
            # 检查字段值类型
            field_result = self.check_type_match(
                data[field_name], field_type,
                context={"protocol": protocol_name, "field": field_name}
            )
            result.violations.extend(field_result.violations)
            result.warnings.extend(field_result.warnings)
        
        # 检查多余字段
        for field_name in data:
            if field_name not in protocol_fields:
                warning_msg = f"Protocol '{protocol_name}' has extra field '{field_name}'"
                if self.type_mode == TypeMode.WARN:
                    result.add_warning(TypeWarning(
                        message=warning_msg,
                        context={"protocol": protocol_name, "field": field_name, "check": "extra_field"}
                    ))
        
        if result.violations:
            result.passed = False
        
        return result
    
    def check_union_type(self, value: Any, union_type: UnionTypeExpr,
                         context: Optional[Dict] = None) -> TypeCheckResult:
        """联合类型兼容性检查
        
        Args:
            value: 实际值
            union_type: 联合类型表达式
            context: 上下文信息
        
        Returns:
            TypeCheckResult
        """
        actual_type = TypeInferrer.infer_type(value)
        
        # 检查值类型是否在联合类型的成员中
        for member_type in union_type.types:
            resolved_member = self.resolve_type(member_type)
            if self._is_type_compatible(actual_type, resolved_member, value):
                return TypeCheckResult(passed=True)
        
        # 都不匹配
        violation = TypeViolation(
            message=f"Value type {actual_type.to_type_str()} not compatible with union type {union_type.to_type_str()}",
            expected_type=union_type,
            actual_type=actual_type,
            value=value,
            context=context or {}
        )
        
        result = TypeCheckResult()
        if self.type_mode == TypeMode.STRICT:
            result.add_violation(violation)
        elif self.type_mode == TypeMode.WARN:
            result.add_warning(TypeWarning(
                message=str(violation),
                expected_type=union_type,
                actual_type=actual_type,
                context=context or {}
            ))
        
        return result
    
    def check_option_type(self, value: Any, option_type: OptionTypeExpr,
                          context: Optional[Dict] = None) -> TypeCheckResult:
        """Option[T] 类型处理
        
        None 值是合法的 Option 类型值。
        非 None 值必须匹配内部类型 T。
        """
        if value is None:
            # None 是合法的 Option 值
            return TypeCheckResult(passed=True)
        
        # 非 None 值检查内部类型
        return self.check_type_match(value, option_type.inner, context=context)
    
    def check_result_type(self, value: Any, result_type: ResultTypeExpr,
                          context: Optional[Dict] = None) -> TypeCheckResult:
        """Result[T, E] 类型处理
        
        值可以是 Ok(T) 或 Err(E) 类型。
        """
        # 简化处理: 检查值是否兼容 Ok 类型或 Err 类型
        ok_result = self.check_type_match(value, result_type.ok_type, context=context)
        if ok_result.passed:
            return ok_result
        
        err_result = self.check_type_match(value, result_type.err_type, context=context)
        if err_result.passed:
            return err_result
        
        # 都不匹配
        violation = TypeViolation(
            message=f"Value not compatible with Result[{result_type.ok_type.to_type_str()}, {result_type.err_type.to_type_str()}]",
            expected_type=result_type,
            actual_type=TypeInferrer.infer_type(value),
            value=value,
            context=context or {}
        )
        
        result = TypeCheckResult()
        if self.type_mode == TypeMode.STRICT:
            result.add_violation(violation)
        elif self.type_mode == TypeMode.WARN:
            result.add_warning(TypeWarning(
                message=str(violation),
                expected_type=result_type,
                actual_type=TypeInferrer.infer_type(value),
                context=context or {}
            ))
        
        return result
    
    def handle_violation(self, result: TypeCheckResult) -> None:
        """根据 TypeMode 处理类型检查结果
        
        - STRICT: 抛出 TypeViolation 异常
        - WARN: 记录日志警告
        - FORGIVING: 静默忽略
        """
        if self.type_mode == TypeMode.STRICT and result.violations:
            # 抛出第一个违反异常
            raise result.violations[0]
        
        elif self.type_mode == TypeMode.WARN:
            for warning in result.warnings:
                logger.warning(f"⚠️ Type warning: {warning.message}")
            for violation in result.violations:
                logger.warning(f"⚠️ Type violation (would be error in strict mode): {violation}")
        
        # FORGIVING 模式静默忽略
    
    # ============================================================
    # Lint 类型检查
    # ============================================================
    
    def lint_check_annotations(self, ast: Dict) -> TypeCheckResult:
        """Lint: 检查类型标注完整性
        
        根据 LintMode:
        - DEFAULT: 只检查有标注的代码
        - WARN: 对缺失标注发出警告
        - STRICT: 缺失标注=lint错误
        """
        result = TypeCheckResult()
        
        if self.lint_mode == LintMode.DEFAULT:
            # 只检查有标注的部分
            return result
        
        body = ast.get("body", [])
        
        for node in body:
            node_type = node.get("type", "")
            
            if node_type == "FlowDeclaration":
                # 检查 flow 参数是否有类型标注
                params = node.get("params", [])
                for param in params:
                    if isinstance(param, dict):
                        param_type = param.get("type_annotation") or param.get("type")
                        if param_type is None or param_type == "Any" or param_type == "":
                            msg = f"Flow '{node.get('name')}' parameter '{param.get('name')}' lacks type annotation"
                            if self.lint_mode == LintMode.STRICT:
                                result.add_violation(TypeViolation(
                                    message=msg,
                                    context={"flow": node.get("name"), "param": param.get("name"), "check": "missing_annotation"}
                                ))
                            else:
                                result.add_warning(TypeWarning(
                                    message=msg,
                                    context={"flow": node.get("name"), "param": param.get("name"), "check": "missing_annotation"}
                                ))
                
                # 检查返回类型标注
                return_type = node.get("return_type")
                if return_type is None:
                    msg = f"Flow '{node.get('name')}' lacks return type annotation"
                    if self.lint_mode == LintMode.STRICT:
                        result.add_violation(TypeViolation(
                            message=msg,
                            context={"flow": node.get("name"), "check": "missing_return_type"}
                        ))
                    else:
                        result.add_warning(TypeWarning(
                            message=msg,
                            context={"flow": node.get("name"), "check": "missing_return_type"}
                        ))
            
            elif node_type == "AgentDeclaration":
                # Agent 的 protocol 提供隐式类型标注
                if node.get("implements") is None:
                    msg = f"Agent '{node.get('name')}' lacks protocol implementation (no output type)"
                    if self.lint_mode == LintMode.STRICT:
                        result.add_violation(TypeViolation(
                            message=msg,
                            context={"agent": node.get("name"), "check": "missing_protocol"}
                        ))
                    else:
                        result.add_warning(TypeWarning(
                            message=msg,
                            context={"agent": node.get("name"), "check": "missing_protocol"}
                        ))
        
        return result
    
    # ============================================================
    # 内部辅助方法
    # ============================================================
    
    def _is_type_compatible(self, actual_type: TypeExpr, expected_type: TypeExpr,
                            value: Any = None) -> bool:
        """检查 actual_type 是否与 expected_type 兼容
        
        兼容规则:
        1. 相同基本类型 → 兼容
        2. AliasTypeExpr("Any") → 与任何类型兼容
        3. 联合类型 → actual 是 union 成员之一即可
        4. Option[T] → None 兼容，非 None 需兼容 T
        5. int 兼容 float (数值 widening)
        6. 子类型关系 (简化: 只检查名义类型)
        """
        # Any 与任何类型兼容
        if isinstance(expected_type, AliasTypeExpr) and expected_type.name == "Any":
            return True
        if isinstance(actual_type, AliasTypeExpr) and actual_type.name == "Any":
            return True
        
        # 相同类型
        if actual_type == expected_type:
            return True
        
        # 数值 widening: int → float
        if isinstance(actual_type, PrimitiveTypeExpr) and isinstance(expected_type, PrimitiveTypeExpr):
            if actual_type.name == "int" and expected_type.name == "float":
                return True
        
        # Union 类型: actual 是 union 成员之一
        if isinstance(expected_type, UnionTypeExpr):
            for member in expected_type.types:
                if self._is_type_compatible(actual_type, member, value):
                    return True
        
        # Option 类型: None 兼容 Option[T]
        if isinstance(expected_type, OptionTypeExpr):
            if value is None:
                return True
            return self._is_type_compatible(actual_type, expected_type.inner, value)
        
        # Generic 类型: list[T] / dict[K,V]
        if isinstance(expected_type, GenericTypeExpr) and isinstance(actual_type, GenericTypeExpr):
            if expected_type.name != actual_type.name:
                return False
            # 检查泛型参数兼容性
            if expected_type.name == "list":
                if not actual_type.type_params:
                    return True  # 未知元素类型的列表兼容
                return self._is_type_compatible(actual_type.type_params[0], expected_type.type_params[0])
            elif expected_type.name == "dict":
                if not actual_type.type_params or len(actual_type.type_params) < 2:
                    return True
                key_compat = self._is_type_compatible(actual_type.type_params[0], expected_type.type_params[0])
                val_compat = self._is_type_compatible(actual_type.type_params[1], expected_type.type_params[1])
                return key_compat and val_compat
        
        # Alias 类型: 解析后比较
        if isinstance(expected_type, AliasTypeExpr) and expected_type.resolved:
            return self._is_type_compatible(actual_type, expected_type.resolved, value)
        if isinstance(actual_type, AliasTypeExpr) and actual_type.resolved:
            return self._is_type_compatible(actual_type.resolved, expected_type, value)
        
        # 基本类型兼容性检查（使用 Python isinstance）
        if isinstance(expected_type, PrimitiveTypeExpr) and value is not None:
            expected_py_type = expected_type.to_python_type()
            # 特殊处理: bool 不兼容 int（尽管 Python 中 bool 是 int 子类）
            if expected_type.name == "int" and isinstance(value, bool):
                return False
            if expected_type.name == "bool" and not isinstance(value, bool):
                return False
            return isinstance(value, expected_py_type)
        
        return False


# ============================================================
# AST TypeExpr 构建器 (从 AST 字典构建 TypeExpr 对象)
# ============================================================

def build_type_expr_from_ast(type_ast: Dict) -> TypeExpr:
    """从 AST 字典构建 TypeExpr 对象
    
    Args:
        type_ast: AST 类型节点字典，格式如:
            {"type": "BaseType", "name": "str"}
            {"type": "GenericType", "name": "list", "type_params": [...]}
            {"type": "CustomType", "name": "UserId"}
            {"type": "SemanticType", "base_type": ..., "constraint": "..."}
            {"type": "UnionTypeExpr", "types": [...]}
            {"type": "OptionTypeExpr", "inner": ...}
            {"type": "ResultTypeExpr", "ok_type": ..., "err_type": ...}
    
    Returns:
        TypeExpr 对象
    """
    if not isinstance(type_ast, dict):
        # 简单字符串类型名
        if isinstance(type_ast, str):
            if type_ast in ("str", "int", "float", "bool", "unit"):
                return PrimitiveTypeExpr(type_ast)
            return AliasTypeExpr(type_ast)
        return AliasTypeExpr("Any")
    
    node_type = type_ast.get("type", "")
    
    if node_type == "BaseType":
        name = type_ast.get("name", "str")
        return PrimitiveTypeExpr(name)
    
    elif node_type == "GenericType":
        name = type_ast.get("name", "list")
        params = [build_type_expr_from_ast(p) for p in type_ast.get("type_params", [])]
        if name == "Option":
            inner = params[0] if params else AliasTypeExpr("Any")
            return OptionTypeExpr(inner)
        elif name == "Result":
            ok_type = params[0] if params else AliasTypeExpr("Any")
            err_type = params[1] if len(params) > 1 else AliasTypeExpr("Any")
            return ResultTypeExpr(ok_type, err_type)
        return GenericTypeExpr(name, params)
    
    elif node_type == "CustomType":
        name = type_ast.get("name", "")
        return AliasTypeExpr(name)
    
    elif node_type == "SemanticType":
        base = build_type_expr_from_ast(type_ast.get("base_type", {}))
        constraint = type_ast.get("constraint", "")
        return SemanticTypeExpr(base, constraint)
    
    elif node_type == "UnionTypeExpr":
        types = [build_type_expr_from_ast(t) for t in type_ast.get("types", [])]
        return UnionTypeExpr(types)
    
    elif node_type == "OptionTypeExpr":
        inner = build_type_expr_from_ast(type_ast.get("inner", {}))
        return OptionTypeExpr(inner)
    
    elif node_type == "ResultTypeExpr":
        ok_type = build_type_expr_from_ast(type_ast.get("ok_type", {}))
        err_type = build_type_expr_from_ast(type_ast.get("err_type", {}))
        return ResultTypeExpr(ok_type, err_type)
    
    elif node_type == "FuncTypeExpr":
        param_types = [build_type_expr_from_ast(p) for p in type_ast.get("param_types", [])]
        return_type = build_type_expr_from_ast(type_ast.get("return_type", {}))
        return FuncTypeExpr(param_types, return_type)
    
    # 兜底：简单字符串值
    name = type_ast.get("name", type_ast.get("value", ""))
    if name in ("str", "int", "float", "bool", "unit"):
        return PrimitiveTypeExpr(name)
    if name:
        return AliasTypeExpr(name)
    
    return AliasTypeExpr("Any")


def build_protocol_fields_from_ast(protocol_ast: Dict) -> Dict[str, TypeExpr]:
    """从 Protocol AST 字典构建字段类型映射
    
    Args:
        protocol_ast: Protocol AST 节点
    
    Returns:
        Dict[str, TypeExpr]: 字段名 → 类型表达式
    """
    fields = protocol_ast.get("fields", {})
    result = {}
    
    for field_name, field_value in fields.items():
        if isinstance(field_value, dict) and "type_expr" in field_value:
            # 新格式: 有完整类型表达式
            result[field_name] = build_type_expr_from_ast(field_value["type_expr"])
        elif isinstance(field_value, dict):
            # AST 格式的类型标注
            result[field_name] = build_type_expr_from_ast(field_value)
        elif isinstance(field_value, str):
            # 旧格式: 字符串类型名
            if field_value in ("str", "int", "float", "bool"):
                result[field_name] = PrimitiveTypeExpr(field_value)
            else:
                result[field_name] = AliasTypeExpr(field_value)
        else:
            result[field_name] = AliasTypeExpr("Any")
    
    return result


# ============================================================
# 流敏感类型收窄 (Flow-Sensitive Type Narrowing)
# ============================================================

class TypeNarrower:
    """流敏感类型收窄
    
    在条件分支中根据条件收窄类型:
    - if x is not None: Option[T] → T
    - if isinstance(x, int): Union[str, int] → int
    - match 语句中根据 pattern 收窄
    """
    
    @staticmethod
    def narrow_after_none_check(var_type: TypeExpr) -> TypeExpr:
        """if x is not None 之后: Option[T] → T"""
        if isinstance(var_type, OptionTypeExpr):
            return var_type.inner
        return var_type
    
    @staticmethod
    def narrow_after_isinstance(var_type: TypeExpr, check_type: PrimitiveTypeExpr) -> TypeExpr:
        """if isinstance(x, T) 之后: Union[A, B, T] → T"""
        if isinstance(var_type, UnionTypeExpr):
            for member in var_type.types:
                if member == check_type:
                    return check_type
        if var_type == check_type:
            return check_type
        return var_type
    
    @staticmethod
    def narrow_after_match(var_type: TypeExpr, pattern_type: TypeExpr) -> TypeExpr:
        """match 分支后类型收窄"""
        if isinstance(var_type, UnionTypeExpr):
            if pattern_type in var_type.types:
                return pattern_type
        if isinstance(var_type, OptionTypeExpr):
            if pattern_type == var_type.inner:
                return pattern_type
        return var_type


# ============================================================
# 便捷函数
# ============================================================

def check_type(value: Any, expected: TypeExpr, context: Optional[Dict] = None) -> TypeCheckResult:
    """便捷函数: 检查值类型
    
    自动根据 NEXA_TYPE_MODE 环境变量决定行为。
    """
    checker = TypeChecker()
    result = checker.check_type_match(value, expected, context=context)
    checker.handle_violation(result)
    return result


def check_protocol(data: Dict[str, Any], protocol_name: str) -> TypeCheckResult:
    """便捷函数: 检查 Protocol 合规性"""
    checker = TypeChecker()
    result = checker.check_protocol_compliance(data, protocol_name)
    checker.handle_violation(result)
    return result