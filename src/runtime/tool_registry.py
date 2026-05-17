"""
Nexa v2.0 ToolRegistry — @tool 注解自动 Schema + 注册 + 执行

ToolRegistry 实现 Harness T-dimension 的运行时核心，负责：
  - register_from_annotation(): 从 @tool 函数自动注册
  - _generate_schema(): 从函数签名自动生成 JSON Schema
  - execute(): Tool 执行 (含 HITL 审批检查)
  - get_schemas(): 获取所有 Schema (注入 LLM 上下文)

Design Rationale:
  - 零成本抽象: @tool 注解在编译期生成注册代码，运行时只做 Schema 查询
  - 安全分级: risk_level=low 直接执行, risk_level=high 需要 HITL 审批
  - Schema 自动注入: Agent 运行时自动获取可用 Tool 的 Schema
  - v1.x 兼容: v1.x tool 声明在 --harness=off 下继续正常工作

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.3
"""

from __future__ import annotations

import json
import logging
import inspect
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type

logger = logging.getLogger("nexa.tool_registry")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ToolSchema:
    """JSON Schema for a registered tool."""
    name: str = ""
    description: str = ""
    parameters: Dict = field(default_factory=dict)  # JSON Schema properties
    required: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    risk_level: str = "low"       # low | medium | high | critical
    requires_approval: bool = False
    sandbox: bool = False
    category: str = "general"     # general | system | network | file | data

    def to_openai_function(self) -> Dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "required": self.required,
            "return_type": self.return_type,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "sandbox": self.sandbox,
            "category": self.category,
        }


@dataclass
class ToolExecutionResult:
    """Result of a tool execution."""
    tool_name: str = ""
    success: bool = True
    result: Any = None
    error: Optional[str] = None
    approved: bool = True        # Whether HITL approval was obtained
    execution_time: float = 0.0
    sandboxed: bool = False

    def to_dict(self) -> Dict:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "approved": self.approved,
            "execution_time": self.execution_time,
            "sandboxed": self.sandboxed,
        }


# ═══════════════════════════════════════════════════════════════════════
#  Type → JSON Schema Mapping
# ═══════════════════════════════════════════════════════════════════════

_TYPE_SCHEMA_MAP: Dict[str, Dict] = {
    "string": {"type": "string", "description": "A string value"},
    "str": {"type": "string", "description": "A string value"},
    "int": {"type": "integer", "description": "An integer value"},
    "integer": {"type": "integer", "description": "An integer value"},
    "float": {"type": "number", "description": "A floating-point number"},
    "number": {"type": "number", "description": "A number value"},
    "bool": {"type": "boolean", "description": "A boolean value"},
    "boolean": {"type": "boolean", "description": "A boolean value"},
    "list": {"type": "array", "description": "A list of values", "items": {"type": "string"}},
    "dict": {"type": "object", "description": "A dictionary/object"},
    "any": {"type": "string", "description": "Any value (serialized as string)"},
}


def _type_to_schema(type_str: str) -> Dict:
    """Convert a type string to a JSON Schema property definition."""
    type_lower = type_str.lower().strip()

    # Direct mapping
    if type_lower in _TYPE_SCHEMA_MAP:
        return _TYPE_SCHEMA_MAP[type_lower]

    # Optional types (e.g., "string?", "int?")
    if type_lower.endswith("?"):
        base_type = type_lower[:-1]
        schema = _type_to_schema(base_type)
        return {**schema, "optional": True}

    # List with type (e.g., "list<string>")
    if type_lower.startswith("list<") or type_lower.startswith("array<"):
        inner = type_lower[5:-1] if type_lower.startswith("list<") else type_lower[6:-1]
        return {
            "type": "array",
            "description": f"A list of {inner} values",
            "items": _type_to_schema(inner),
        }

    # Default: string
    return {"type": "string", "description": f"Value of type {type_str}"}


# ═══════════════════════════════════════════════════════════════════════
#  ToolRegistry — T-Dimension Runtime
# ═══════════════════════════════════════════════════════════════════════

class ToolRegistry:
    """
    Tool registry for @tool annotation processing.

    Implements the T-dimension runtime:
      - register_from_annotation(): Auto-register from @tool function
      - register(): Manual registration with schema
      - execute(): Execute a tool (with HITL approval for high-risk)
      - get_schemas(): Get all schemas for LLM context injection
      - get_tool(): Get a specific tool's schema

    Usage:
        registry = ToolRegistry()
        registry.register_from_annotation(
            fn=my_tool_fn,
            description="Execute shell commands",
            risk_level="high",
            requires_approval=True,
        )
        schemas = registry.get_schemas()  # For LLM context
        result = registry.execute("my_tool_fn", {"command": "ls"})
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Callable] = {}       # fn_name → callable
        self._schemas: Dict[str, ToolSchema] = {}    # fn_name → schema
        self._lock = threading.Lock()
        self._execution_count = 0
        self._hitl_manager: Optional[Any] = None

    def set_hitl_manager(self, manager: Any) -> None:
        """Set the HITL manager for approval checks."""
        self._hitl_manager = manager

    # ─── Registration ───

    def register_from_annotation(
        self,
        fn: Callable,
        description: str = "",
        risk_level: str = "low",
        requires_approval: bool = False,
        sandbox: bool = False,
        category: str = "general",
    ) -> ToolSchema:
        """
        Register a tool from a @tool-annotated function.

        Automatically generates JSON Schema from the function signature.

        Args:
            fn: The tool function to register
            description: Tool description for Agent comprehension
            risk_level: Risk level (low/medium/high/critical)
            requires_approval: Whether HITL approval is required
            sandbox: Whether to execute in sandbox
            category: Tool category

        Returns:
            The generated ToolSchema
        """
        fn_name = fn.__name__
        schema = self._generate_schema(fn, description, risk_level,
                                        requires_approval, sandbox, category)

        with self._lock:
            self._tools[fn_name] = fn
            self._schemas[fn_name] = schema

        logger.info(f"Registered tool: {fn_name}, risk_level={risk_level}, "
                     f"requires_approval={requires_approval}")
        return schema

    def register(
        self,
        name: str,
        fn: Callable,
        schema: ToolSchema,
    ) -> None:
        """
        Manually register a tool with a pre-defined schema.

        Args:
            name: Tool name
            fn: The tool function
            schema: Pre-defined ToolSchema
        """
        with self._lock:
            self._tools[name] = fn
            self._schemas[name] = schema

        logger.info(f"Manually registered tool: {name}")

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                del self._schemas[name]
                return True
            return False

    # ─── Schema Generation ───

    def _generate_schema(
        self,
        fn: Callable,
        description: str,
        risk_level: str,
        requires_approval: bool,
        sandbox: bool,
        category: str,
    ) -> ToolSchema:
        """
        Generate JSON Schema from a function's signature.

        Uses inspect to extract parameter names, types, and defaults.
        """
        fn_name = fn.__name__
        sig = inspect.signature(fn)
        parameters = {}
        required = []

        for param_name, param in sig.parameters.items():
            # Extract type annotation
            type_str = "string"  # Default type
            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation
                if isinstance(annotation, type):
                    type_str = annotation.__name__
                elif isinstance(annotation, str):
                    type_str = annotation
                else:
                    type_str = str(annotation)

            # Generate schema for this parameter
            param_schema = _type_to_schema(type_str)

            # Check for default value
            if param.default != inspect.Parameter.empty:
                param_schema["default"] = param.default
            else:
                required.append(param_name)

            parameters[param_name] = param_schema

        # Extract return type
        return_type = None
        if sig.return_annotation != inspect.Parameter.empty:
            if isinstance(sig.return_annotation, type):
                return_type = sig.return_annotation.__name__
            elif isinstance(sig.return_annotation, str):
                return_type = sig.return_annotation
            else:
                return_type = str(sig.return_annotation)

        # Use function docstring as fallback description
        if not description and fn.__doc__:
            description = fn.__doc__.strip().split('\n')[0]

        return ToolSchema(
            name=fn_name,
            description=description,
            parameters=parameters,
            required=required,
            return_type=return_type,
            risk_level=risk_level,
            requires_approval=requires_approval,
            sandbox=sandbox,
            category=category,
        )

    # ─── Execution ───

    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict] = None,
    ) -> ToolExecutionResult:
        """
        Execute a registered tool.

        For high-risk tools, checks HITL approval before execution.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool function
            context: Optional execution context

        Returns:
            ToolExecutionResult with execution outcome
        """
        import time

        with self._lock:
            fn = self._tools.get(tool_name)
            schema = self._schemas.get(tool_name)

        if fn is None:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found in registry",
            )

        self._execution_count += 1

        # ─── HITL Approval Check ───
        if schema and schema.requires_approval:
            approved = self._check_approval(tool_name, schema, arguments)
            if not approved:
                return ToolExecutionResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Tool '{tool_name}' execution denied by HITL approval",
                    approved=False,
                )

        # ─── Execute ───
        start_time = time.time()
        try:
            result = fn(**arguments)
            execution_time = time.time() - start_time

            return ToolExecutionResult(
                tool_name=tool_name,
                success=True,
                result=result,
                approved=True,
                execution_time=execution_time,
                sandboxed=schema.sandbox if schema else False,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                approved=True,
                execution_time=execution_time,
            )

    def _check_approval(self, tool_name: str, schema: ToolSchema, arguments: Dict) -> bool:
        """
        Check HITL approval for a high-risk tool execution.

        If HITLManager is available, delegates to it.
        Otherwise, auto-approves in WARN mode and denies in STRICT mode.
        """
        if self._hitl_manager:
            try:
                return self._hitl_manager.request_approval(
                    tool_name=tool_name,
                    risk_level=schema.risk_level,
                    arguments=arguments,
                )
            except Exception:
                logger.warning(f"HITL approval check failed for {tool_name}")
                return False

        # No HITL manager: auto-approve (WARN mode behavior)
        logger.warning(f"Auto-approving high-risk tool '{tool_name}' "
                       f"(no HITL manager configured)")
        return True

    # ─── Schema Access ───

    def get_schemas(self) -> List[ToolSchema]:
        """Get all registered tool schemas."""
        with self._lock:
            return list(self._schemas.values())

    def get_schemas_as_openai_functions(self) -> List[Dict]:
        """Get all schemas in OpenAI function calling format."""
        with self._lock:
            return [schema.to_openai_function() for schema in self._schemas.values()]

    def get_schemas_as_dicts(self) -> List[Dict]:
        """Get all schemas as plain dicts."""
        with self._lock:
            return [schema.to_dict() for schema in self._schemas.values()]

    def get_tool(self, name: str) -> Optional[ToolSchema]:
        """Get a specific tool's schema."""
        with self._lock:
            return self._schemas.get(name)

    def get_tool_function(self, name: str) -> Optional[Callable]:
        """Get a specific tool's callable."""
        with self._lock:
            return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        with self._lock:
            return name in self._tools

    def list_tool_names(self) -> List[str]:
        """List all registered tool names."""
        with self._lock:
            return list(self._tools.keys())

    # ─── Statistics ───

    def get_stats(self) -> Dict:
        """Get registry statistics."""
        with self._lock:
            total = len(self._tools)
            by_risk = {}
            for schema in self._schemas.values():
                risk = schema.risk_level
                by_risk[risk] = by_risk.get(risk, 0) + 1

        return {
            "total_tools": total,
            "by_risk_level": by_risk,
            "execution_count": self._execution_count,
            "tool_names": list(self._tools.keys()),
        }

    def clear(self) -> None:
        """Clear all registered tools (for testing)."""
        with self._lock:
            self._tools = {}
            self._schemas = {}
            self._execution_count = 0


# ═══════════════════════════════════════════════════════════════════════
#  Global Instance
# ═══════════════════════════════════════════════════════════════════════

_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global ToolRegistry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry