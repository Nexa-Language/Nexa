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
Nexa Design by Contract (契约式编程) 运行时引擎

核心概念：
- requires: 前置条件（函数调用前必须满足）
- ensures: 后置条件（函数返回后必须满足）
- invariant: 不变式（对象生命周期中始终满足）

Nexa 特色：
- 确定性契约：传统逻辑条件（如 amount > 0）
- 语义契约：自然语言条件（如 "input contains financial data"），用 LLM 在运行时判断
- 与 semantic_if 融合：语义契约复用 nexa_semantic_eval() 机制
- 与 @retry/@fallback 融合：ensures 失败时自动触发 retry 或 fallback
- 与 protocol 互补：protocol 约束结构，requires 约束输入，ensures 约束行为
"""

from typing import Any, Dict, List, Optional, Callable
from .evaluator import nexa_semantic_eval


class ContractViolation(Exception):
    """契约违反异常
    
    Attributes:
        clause_type: 'requires' 或 'ensures'
        clause: 违反的契约条款
        context: 评估时的上下文信息
        is_semantic: 是否为语义契约
    """
    def __init__(self, message: str, clause_type: str = "requires",
                 clause: Optional['ContractClause'] = None,
                 context: Optional[Dict] = None,
                 is_semantic: bool = False):
        super().__init__(message)
        self.clause_type = clause_type
        self.clause = clause
        self.context = context or {}
        self.is_semantic = is_semantic

    def __repr__(self):
        tag = "semantic" if self.is_semantic else "deterministic"
        return f"ContractViolation({self.clause_type}:{tag}, message={self.args[0]})"


class ContractClause:
    """单个契约条款
    
    Attributes:
        expression: 确定性表达式字符串（如 'amount > 0'）或 None
        condition_text: 语义条件的自然语言文本（如 'input contains financial data'）或 None
        is_semantic: 是否为语义契约（自然语言条件）
        message: 附加说明/错误消息
    """
    def __init__(self, expression: Optional[str] = None,
                 condition_text: Optional[str] = None,
                 is_semantic: bool = False,
                 message: str = ""):
        self.expression = expression
        self.condition_text = condition_text
        self.is_semantic = is_semantic
        self.message = message

    def __repr__(self):
        if self.is_semantic:
            return f"ContractClause(semantic: \"{self.condition_text}\")"
        return f"ContractClause(deterministic: \"{self.expression}\")"

    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "expression": self.expression,
            "condition_text": self.condition_text,
            "is_semantic": self.is_semantic,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ContractClause':
        """从字典反序列化"""
        return cls(
            expression=data.get("expression"),
            condition_text=data.get("condition_text"),
            is_semantic=data.get("is_semantic", False),
            message=data.get("message", ""),
        )


class OldValues:
    """捕获函数入口时的表达式值，用于后置条件中的 old(expr) 比较
    
    Attributes:
        values: {表达式文本: 入口时的值}
    """
    def __init__(self, values: Optional[Dict[str, Any]] = None):
        self.values = values or {}

    def get(self, expr: str) -> Any:
        """获取 old(expr) 的值"""
        return self.values.get(expr)

    def __repr__(self):
        return f"OldValues({self.values})"


class ContractSpec:
    """契约规格：包含 requires/ensures/invariant 列表
    
    Attributes:
        requires: 前置条件列表
        ensures: 后置条件列表
        invariants: 不变式列表
    """
    def __init__(self, requires: Optional[List[ContractClause]] = None,
                 ensures: Optional[List[ContractClause]] = None,
                 invariants: Optional[List[ContractClause]] = None):
        self.requires = requires or []
        self.ensures = ensures or []
        self.invariants = invariants or []

    def __repr__(self):
        req = ", ".join(repr(r) for r in self.requires)
        ens = ", ".join(repr(e) for e in self.ensures)
        inv = ", ".join(repr(i) for i in self.invariants)
        return f"ContractSpec(requires=[{req}], ensures=[{ens}], invariants=[{inv}])"

    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "requires": [c.to_dict() for c in self.requires],
            "ensures": [c.to_dict() for c in self.ensures],
            "invariants": [c.to_dict() for c in self.invariants],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ContractSpec':
        """从字典反序列化"""
        return cls(
            requires=[ContractClause.from_dict(c) for c in data.get("requires", [])],
            ensures=[ContractClause.from_dict(c) for c in data.get("ensures", [])],
            invariants=[ContractClause.from_dict(c) for c in data.get("invariants", [])],
        )

    def has_requires(self) -> bool:
        return len(self.requires) > 0

    def has_ensures(self) -> bool:
        return len(self.ensures) > 0

    def has_invariants(self) -> bool:
        return len(self.invariants) > 0


def _extract_old_expressions(spec: ContractSpec) -> List[str]:
    """从 ensures 条款中提取所有 old(expr) 表达式
    
    返回需要捕获入口值的表达式文本列表。
    例如: ensures result > old(x) -> 提取 "x"
          ensures old(amount) > 0 -> 提取 "amount"
    """
    import re
    old_exprs = []
    for clause in spec.ensures:
        if not clause.is_semantic and clause.expression:
            # 匹配 old(expr) 模式
            matches = re.findall(r'old\(([^)]+)\)', clause.expression)
            for m in matches:
                old_exprs.append(m)
    return old_exprs


def capture_old_values(spec: ContractSpec, context: Dict[str, Any]) -> OldValues:
    """捕获函数入口时的值，用于后置条件中的 old(expr) 比较
    
    Args:
        spec: 契约规格
        context: 当前上下文（变量名到值的映射）
    
    Returns:
        OldValues 对象，包含所有 old(expr) 在入口时的值
    """
    old_exprs = _extract_old_expressions(spec)
    values = {}
    for expr in old_exprs:
        # 简单表达式：直接从 context 中获取变量值
        # 支持嵌套属性访问如 old(input.data)
        try:
            value = _evaluate_identifier_path(expr, context)
            values[expr] = value
        except Exception:
            # 如果无法获取值，跳过（在 ensures 检查时会报错）
            pass
    return OldValues(values)


def _evaluate_identifier_path(path: str, context: Dict[str, Any]) -> Any:
    """评估点号分隔的标识符路径，如 'input.data.amount'
    
    Args:
        path: 标识符路径
        context: 上下文变量
    
    Returns:
        路径对应的值
    """
    parts = path.strip().split('.')
    value = context.get(parts[0])
    for part in parts[1:]:
        if isinstance(value, dict):
            value = value.get(part)
        elif hasattr(value, part):
            value = getattr(value, part)
        else:
            raise KeyError(f"Cannot resolve path '{path}' in context")
    return value


def _evaluate_deterministic_expression(expression: str, context: Dict[str, Any],
                                        result: Any = None, old_values: Optional[OldValues] = None) -> bool:
    """评估确定性契约表达式
    
    支持特殊语法：
    - result: 引用函数返回值
    - old(expr): 引用函数入口时的值
    
    Args:
        expression: 表达式字符串（如 'amount > 0' 或 'result >= old(x)'）
        context: 上下文变量
        result: 函数返回值（ensures 中使用）
        old_values: 入口时捕获的值
    
    Returns:
        表达式是否满足
    """
    import re
    
    # 构建评估环境
    eval_context = dict(context)
    
    # 替换 old(expr) 为实际捕获的值
    if old_values:
        for expr_text, old_val in old_values.values.items():
            # 将 old(expr) 替换为值
            # 使用 repr() 确保类型安全
            expression = expression.replace(f'old({expr_text})', repr(old_val))
    
    # 替换 result 为函数返回值
    if result is not None:
        eval_context['result'] = result
    
    # 安全评估：使用受限的 eval
    # 只允许基本比较和数学运算
    try:
        # 首先尝试直接 eval（受限于 eval_context）
        allowed_names = set(eval_context.keys())
        # 添加内置函数
        safe_builtins = {
            'True': True, 'False': False, 'None': None,
            'len': len, 'str': str, 'int': int, 'float': float,
            'abs': abs, 'min': min, 'max': max,
            'isinstance': isinstance, 'type': type,
            'list': list, 'dict': dict, 'bool': bool,
        }
        eval_globals = {"__builtins__": safe_builtins}
        eval_locals = {k: v for k, v in eval_context.items() if k in allowed_names}
        
        return bool(eval(expression, eval_globals, eval_locals))
    except Exception as e:
        print(f"[Contract] Failed to evaluate expression '{expression}': {e}")
        return False


def _evaluate_semantic_clause(clause: ContractClause, target_text: str) -> bool:
    """评估语义契约条款（自然语言条件）
    
    使用 nexa_semantic_eval() 机制判断自然语言条件是否满足。
    
    Args:
        clause: 语义契约条款
        target_text: 待判断的文本（输入或输出）
    
    Returns:
        条件是否满足
    """
    if not clause.is_semantic or not clause.condition_text:
        return False
    
    try:
        matched = nexa_semantic_eval(clause.condition_text, target_text)
        print(f"[Contract Semantic] '{clause.condition_text}' against '{target_text[:100]}...' -> {matched}")
        return matched
    except Exception as e:
        print(f"[Contract] Semantic evaluation failed: {e}. Defaulting to False.")
        return False


def check_requires(spec: ContractSpec, context: Dict[str, Any]) -> Optional[ContractViolation]:
    """检查前置条件
    
    Args:
        spec: 契约规格
        context: 当前上下文（变量名到值的映射）
    
    Returns:
        None 如果所有条件满足，ContractViolation 如果有条件违反
    """
    for clause in spec.requires:
        if clause.is_semantic:
            # 语义契约：用 LLM 判断自然语言条件
            # 对于 requires，需要将输入文本作为目标
            input_text = str(context)
            satisfied = _evaluate_semantic_clause(clause, input_text)
        else:
            # 确定性契约：用逻辑表达式判断
            satisfied = _evaluate_deterministic_expression(clause.expression, context)
        
        if not satisfied:
            message = clause.message or (
                f"Requires clause violated: {clause.condition_text if clause.is_semantic else clause.expression}"
            )
            return ContractViolation(
                message=message,
                clause_type="requires",
                clause=clause,
                context=context,
                is_semantic=clause.is_semantic,
            )
    
    return None


def check_ensures(spec: ContractSpec, context: Dict[str, Any],
                   result: Any, old_values: Optional[OldValues] = None) -> Optional[ContractViolation]:
    """检查后置条件
    
    Args:
        spec: 契约规格
        context: 当前上下文
        result: 函数/agent 的返回值
        old_values: 入口时捕获的值（用于 old(expr) 比较）
    
    Returns:
        None 如果所有条件满足，ContractViolation 如果有条件违反
    """
    for clause in spec.ensures:
        if clause.is_semantic:
            # 语义契约：用 LLM 判断自然语言条件
            # 对于 ensures，需要将输出文本作为目标
            result_text = str(result) if result is not None else ""
            satisfied = _evaluate_semantic_clause(clause, result_text)
        else:
            # 确定性契约：用逻辑表达式判断
            # 支持 result 和 old(expr) 特殊语法
            satisfied = _evaluate_deterministic_expression(
                clause.expression, context, result=result, old_values=old_values
            )
        
        if not satisfied:
            message = clause.message or (
                f"Ensures clause violated: {clause.condition_text if clause.is_semantic else clause.expression}"
            )
            return ContractViolation(
                message=message,
                clause_type="ensures",
                clause=clause,
                context=context,
                is_semantic=clause.is_semantic,
            )
    
    return None


def check_invariants(spec: ContractSpec, context: Dict[str, Any]) -> Optional[ContractViolation]:
    """检查不变式
    
    Args:
        spec: 契约规格
        context: 当前上下文
    
    Returns:
        None 如果所有不变式满足，ContractViolation 如果有不变式违反
    """
    for clause in spec.invariants:
        if clause.is_semantic:
            state_text = str(context)
            satisfied = _evaluate_semantic_clause(clause, state_text)
        else:
            satisfied = _evaluate_deterministic_expression(clause.expression, context)
        
        if not satisfied:
            message = clause.message or (
                f"Invariant violated: {clause.condition_text if clause.is_semantic else clause.expression}"
            )
            return ContractViolation(
                message=message,
                clause_type="invariant",
                clause=clause,
                context=context,
                is_semantic=clause.is_semantic,
            )
    
    return None