# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
#
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# ========================================================================
"""Restricted expression evaluation helpers for Nexa runtime internals."""

from __future__ import annotations

import ast
import json
import operator
import shlex
from typing import Any, Mapping


class UnsafeExpressionError(ValueError):
    """Raised when an expression uses syntax outside the Nexa safe subset."""


_SHELL_METACHARS = set("|&;<>$`\\\n")


def parse_safe_command(command: str) -> list[str]:
    """Parse a command into argv without invoking a shell.

    Plain strings are split with shlex and rejected if they contain shell
    metacharacters. For complex argument values, callers can pass a JSON array
    of strings, e.g. '["grep", "-rn", "pattern", "."]'.
    """
    text = command.strip()
    if not text:
        raise ValueError("empty command")
    if text.startswith("["):
        args = json.loads(text)
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError("JSON command must be a list of strings")
        if not args:
            raise ValueError("empty command")
        return args
    if any(char in _SHELL_METACHARS for char in text):
        raise ValueError("shell metacharacters are not allowed; pass a JSON argv list for complex commands")
    return shlex.split(text)


_ALLOWED_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_ALLOWED_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
}

_ALLOWED_FUNCS = {
    "abs": abs,
    "min": min,
    "max": max,
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "isinstance": isinstance,
    "round": round,
    "type": type,
}

_ALLOWED_TYPES = {
    "str": str,
    "string": str,
    "int": int,
    "integer": int,
    "float": float,
    "number": (int, float),
    "bool": bool,
    "boolean": bool,
    "list": list,
    "array": list,
    "dict": dict,
    "object": dict,
    "tuple": tuple,
    "none": type(None),
    "None": type(None),
    "NoneType": type(None),
}


def resolve_type_name(name: Any) -> Any:
    """Resolve a Nexa/Python type name through an explicit allowlist."""
    if isinstance(name, type) or isinstance(name, tuple):
        return name
    if not isinstance(name, str):
        return type(None)
    return _ALLOWED_TYPES.get(name, _ALLOWED_TYPES.get(name.lower(), type(None)))


def safe_eval(expression: str, context: Mapping[str, Any] | None = None) -> Any:
    """Evaluate an expression using a small AST whitelist.

    The supported subset covers deterministic contracts and debugger watches:
    literals, variables, list/dict/tuple literals, arithmetic, comparisons,
    boolean operators, indexing, and a small function allowlist. Attribute
    access, imports, lambdas, comprehensions, and arbitrary calls are rejected.
    """
    tree = ast.parse(expression, mode="eval")
    evaluator = _SafeEvaluator(context or {})
    return evaluator.visit(tree.body)


def safe_arithmetic_eval(expression: str) -> Any:
    """Evaluate arithmetic-only expressions for std.math.calc."""
    tree = ast.parse(expression, mode="eval")
    evaluator = _SafeEvaluator({}, arithmetic_only=True)
    return evaluator.visit(tree.body)


class _SafeEvaluator(ast.NodeVisitor):
    def __init__(self, context: Mapping[str, Any], arithmetic_only: bool = False) -> None:
        self.context = dict(context)
        self.arithmetic_only = arithmetic_only

    def generic_visit(self, node: ast.AST) -> Any:
        raise UnsafeExpressionError(f"Unsupported expression node: {type(node).__name__}")

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        if self.arithmetic_only:
            raise UnsafeExpressionError("Names are not allowed in arithmetic expressions")
        if node.id in {"True", "False", "None"}:
            return {"True": True, "False": False, "None": None}[node.id]
        if node.id in _ALLOWED_TYPES:
            return _ALLOWED_TYPES[node.id]
        if node.id not in self.context:
            raise UnsafeExpressionError(f"Unknown name: {node.id}")
        return self.context[node.id]

    def visit_List(self, node: ast.List) -> list[Any]:
        if self.arithmetic_only:
            raise UnsafeExpressionError("Lists are not allowed in arithmetic expressions")
        return [self.visit(item) for item in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> tuple[Any, ...]:
        if self.arithmetic_only:
            raise UnsafeExpressionError("Tuples are not allowed in arithmetic expressions")
        return tuple(self.visit(item) for item in node.elts)

    def visit_Dict(self, node: ast.Dict) -> dict[Any, Any]:
        if self.arithmetic_only:
            raise UnsafeExpressionError("Dicts are not allowed in arithmetic expressions")
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values)}

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op = _ALLOWED_UNARY_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpressionError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op(self.visit(node.operand))

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op = _ALLOWED_BIN_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpressionError(f"Unsupported binary operator: {type(node.op).__name__}")
        return op(self.visit(node.left), self.visit(node.right))

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if self.arithmetic_only:
            raise UnsafeExpressionError("Boolean operators are not allowed in arithmetic expressions")
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = self.visit(value)
                if not result:
                    return result
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value in node.values:
                result = self.visit(value)
                if result:
                    return result
            return result
        raise UnsafeExpressionError(f"Unsupported boolean operator: {type(node.op).__name__}")

    def visit_Compare(self, node: ast.Compare) -> bool:
        if self.arithmetic_only:
            raise UnsafeExpressionError("Comparisons are not allowed in arithmetic expressions")
        left = self.visit(node.left)
        for op_node, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            op = _ALLOWED_CMP_OPS.get(type(op_node))
            if op is None:
                raise UnsafeExpressionError(f"Unsupported comparison operator: {type(op_node).__name__}")
            if not op(left, right):
                return False
            left = right
        return True

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        if self.arithmetic_only:
            raise UnsafeExpressionError("Indexing is not allowed in arithmetic expressions")
        value = self.visit(node.value)
        index = self.visit(node.slice)
        return value[index]

    def visit_Slice(self, node: ast.Slice) -> slice:
        if self.arithmetic_only:
            raise UnsafeExpressionError("Slicing is not allowed in arithmetic expressions")
        return slice(
            self.visit(node.lower) if node.lower else None,
            self.visit(node.upper) if node.upper else None,
            self.visit(node.step) if node.step else None,
        )

    def visit_Call(self, node: ast.Call) -> Any:
        if self.arithmetic_only:
            raise UnsafeExpressionError("Function calls are not allowed in arithmetic expressions")
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpressionError("Only direct allowlisted function calls are supported")
        fn = _ALLOWED_FUNCS.get(node.func.id)
        if fn is None:
            raise UnsafeExpressionError(f"Function is not allowed: {node.func.id}")
        args = [self.visit(arg) for arg in node.args]
        kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords if kw.arg}
        return fn(*args, **kwargs)
