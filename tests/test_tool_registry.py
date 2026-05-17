"""
Nexa v2.0 M2 Tests — ToolRegistry + LifecycleHookManager

Tests cover:
  - ToolRegistry: register_from_annotation, schema generation, execute, HITL approval
  - LifecycleHookManager: register, fire, before/after step/tool, on_error, blocking
  - Integration: ToolRegistry + LifecycleHooks end-to-end

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.3
"""

import pytest
import time
import json

from src.runtime.tool_registry import (
    ToolRegistry, ToolSchema, ToolExecutionResult,
    _type_to_schema, get_tool_registry,
)
from src.runtime.lifecycle_hooks import (
    LifecycleHookManager, HookCallback, HookExecutionResult,
)


# ═══════════════════════════════════════════════════════════════════════
#  Type → Schema Mapping Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTypeToSchema:
    """Type string → JSON Schema conversion tests."""

    def test_string_type(self):
        schema = _type_to_schema("string")
        assert schema["type"] == "string"

    def test_int_type(self):
        schema = _type_to_schema("int")
        assert schema["type"] == "integer"

    def test_float_type(self):
        schema = _type_to_schema("float")
        assert schema["type"] == "number"

    def test_bool_type(self):
        schema = _type_to_schema("bool")
        assert schema["type"] == "boolean"

    def test_list_type(self):
        schema = _type_to_schema("list")
        assert schema["type"] == "array"

    def test_dict_type(self):
        schema = _type_to_schema("dict")
        assert schema["type"] == "object"

    def test_optional_type(self):
        schema = _type_to_schema("string?")
        assert schema["type"] == "string"
        assert schema.get("optional") is True

    def test_list_with_inner_type(self):
        schema = _type_to_schema("list<string>")
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "string"

    def test_unknown_type_defaults_to_string(self):
        schema = _type_to_schema("custom_type")
        assert schema["type"] == "string"


# ═══════════════════════════════════════════════════════════════════════
#  ToolRegistry Tests
# ═══════════════════════════════════════════════════════════════════════

class TestToolRegistry:
    """ToolRegistry registration and execution tests."""

    def test_register_from_annotation(self):
        """Register a tool from a function annotation."""
        registry = ToolRegistry()

        def my_tool(command: str, timeout: int = 30) -> str:
            """Execute a shell command."""
            return f"executed: {command}"

        schema = registry.register_from_annotation(
            fn=my_tool,
            description="Execute shell commands safely",
            risk_level="high",
            requires_approval=True,
        )

        assert schema.name == "my_tool"
        assert schema.description == "Execute shell commands safely"
        assert schema.risk_level == "high"
        assert schema.requires_approval is True
        assert "command" in schema.parameters
        assert "timeout" in schema.parameters
        assert "command" in schema.required
        assert "timeout" not in schema.required  # Has default

    def test_register_from_annotation_with_docstring(self):
        """Description falls back to function docstring."""
        registry = ToolRegistry()

        def search_tool(query: str) -> str:
            """Search the web for information."""
            return f"results for {query}"

        schema = registry.register_from_annotation(fn=search_tool)
        assert schema.description == "Search the web for information."

    def test_schema_generation_types(self):
        """Schema correctly maps parameter types."""
        registry = ToolRegistry()

        def typed_tool(name: str, count: int, ratio: float, active: bool) -> str:
            return "ok"

        schema = registry.register_from_annotation(fn=typed_tool, description="Test")
        assert schema.parameters["name"]["type"] == "string"
        assert schema.parameters["count"]["type"] == "integer"
        assert schema.parameters["ratio"]["type"] == "number"
        assert schema.parameters["active"]["type"] == "boolean"

    def test_schema_default_values(self):
        """Schema includes default values."""
        registry = ToolRegistry()

        def tool_with_defaults(query: str, limit: int = 10) -> str:
            return "ok"

        schema = registry.register_from_annotation(fn=tool_with_defaults, description="Test")
        assert schema.parameters["limit"]["default"] == 10
        assert "query" in schema.required
        assert "limit" not in schema.required

    def test_schema_return_type(self):
        """Schema captures return type annotation."""
        registry = ToolRegistry()

        def returning_tool() -> str:
            return "ok"

        schema = registry.register_from_annotation(fn=returning_tool, description="Test")
        assert schema.return_type == "str"

    def test_execute_tool_success(self):
        """Execute a registered tool successfully."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        registry.register_from_annotation(fn=add, description="Add two numbers")

        result = registry.execute("add", {"a": 3, "b": 5})
        assert result.success is True
        assert result.result == 8
        assert result.tool_name == "add"

    def test_execute_tool_not_found(self):
        """Execute unregistered tool returns error."""
        registry = ToolRegistry()
        result = registry.execute("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error

    def test_execute_tool_exception(self):
        """Tool execution error is captured."""
        registry = ToolRegistry()

        def failing_tool() -> str:
            raise RuntimeError("Tool failed")

        registry.register_from_annotation(fn=failing_tool, description="Fails")

        result = registry.execute("failing_tool", {})
        assert result.success is False
        assert "Tool failed" in result.error

    def test_execute_high_risk_auto_approved(self):
        """High-risk tool auto-approved when no HITL manager."""
        registry = ToolRegistry()

        def dangerous_tool(cmd: str) -> str:
            return f"executed: {cmd}"

        registry.register_from_annotation(
            fn=dangerous_tool, description="Dangerous",
            risk_level="high", requires_approval=True,
        )

        result = registry.execute("dangerous_tool", {"cmd": "rm -rf /"})
        assert result.success is True
        assert result.approved is True

    def test_execute_high_risk_hitl_denied(self):
        """High-risk tool denied by HITL manager."""
        registry = ToolRegistry()

        # Mock HITL manager that always denies
        class MockHITL:
            def request_approval(self, **kwargs):
                return False

        registry.set_hitl_manager(MockHITL())

        def dangerous_tool(cmd: str) -> str:
            return f"executed: {cmd}"

        registry.register_from_annotation(
            fn=dangerous_tool, description="Dangerous",
            risk_level="high", requires_approval=True,
        )

        result = registry.execute("dangerous_tool", {"cmd": "rm -rf /"})
        assert result.success is False
        assert result.approved is False
        assert "denied" in result.error

    def test_get_schemas(self):
        """Get all registered schemas."""
        registry = ToolRegistry()

        def tool_a() -> str: return "a"
        def tool_b() -> str: return "b"

        registry.register_from_annotation(fn=tool_a, description="Tool A")
        registry.register_from_annotation(fn=tool_b, description="Tool B")

        schemas = registry.get_schemas()
        assert len(schemas) == 2

    def test_get_schemas_as_openai_functions(self):
        """Schemas convert to OpenAI function format."""
        registry = ToolRegistry()

        def search(query: str) -> str:
            return "results"

        registry.register_from_annotation(fn=search, description="Search")

        functions = registry.get_schemas_as_openai_functions()
        assert len(functions) == 1
        assert functions[0]["type"] == "function"
        assert functions[0]["function"]["name"] == "search"

    def test_get_schemas_as_dicts(self):
        """Schemas convert to plain dicts."""
        registry = ToolRegistry()

        def tool() -> str: return "ok"

        registry.register_from_annotation(fn=tool, description="Test")
        dicts = registry.get_schemas_as_dicts()
        assert len(dicts) == 1
        assert dicts[0]["name"] == "tool"

    def test_has_tool(self):
        """Check if tool is registered."""
        registry = ToolRegistry()

        def my_tool() -> str: return "ok"

        registry.register_from_annotation(fn=my_tool, description="Test")
        assert registry.has_tool("my_tool")
        assert not registry.has_tool("nonexistent")

    def test_list_tool_names(self):
        """List all registered tool names."""
        registry = ToolRegistry()

        def tool_a() -> str: return "a"
        def tool_b() -> str: return "b"

        registry.register_from_annotation(fn=tool_a, description="A")
        registry.register_from_annotation(fn=tool_b, description="B")

        names = registry.list_tool_names()
        assert "tool_a" in names
        assert "tool_b" in names

    def test_unregister(self):
        """Unregister a tool."""
        registry = ToolRegistry()

        def my_tool() -> str: return "ok"

        registry.register_from_annotation(fn=my_tool, description="Test")
        assert registry.unregister("my_tool")
        assert not registry.has_tool("my_tool")

    def test_stats(self):
        """Registry stats are accurate."""
        registry = ToolRegistry()

        def tool_a() -> str: return "a"
        def tool_b() -> str: return "b"

        registry.register_from_annotation(fn=tool_a, description="A", risk_level="low")
        registry.register_from_annotation(fn=tool_b, description="B", risk_level="high")

        stats = registry.get_stats()
        assert stats["total_tools"] == 2
        assert stats["by_risk_level"]["low"] == 1
        assert stats["by_risk_level"]["high"] == 1

    def test_clear(self):
        """Clear removes all tools."""
        registry = ToolRegistry()

        def tool() -> str: return "ok"

        registry.register_from_annotation(fn=tool, description="Test")
        registry.clear()
        assert registry.get_stats()["total_tools"] == 0

    def test_manual_register(self):
        """Manually register with pre-defined schema."""
        registry = ToolRegistry()

        def my_fn() -> str: return "ok"

        schema = ToolSchema(
            name="custom_tool",
            description="Custom tool",
            parameters={"input": {"type": "string"}},
            required=["input"],
            risk_level="medium",
        )

        registry.register("custom_tool", my_fn, schema)
        assert registry.has_tool("custom_tool")
        assert registry.get_tool("custom_tool").risk_level == "medium"


# ═══════════════════════════════════════════════════════════════════════
#  ToolSchema Tests
# ═══════════════════════════════════════════════════════════════════════

class TestToolSchema:
    """ToolSchema serialization tests."""

    def test_to_openai_function(self):
        schema = ToolSchema(
            name="search",
            description="Search the web",
            parameters={"query": {"type": "string"}},
            required=["query"],
        )
        func = schema.to_openai_function()
        assert func["type"] == "function"
        assert func["function"]["name"] == "search"
        assert func["function"]["parameters"]["type"] == "object"

    def test_to_dict(self):
        schema = ToolSchema(
            name="test",
            description="Test tool",
            risk_level="high",
            requires_approval=True,
        )
        d = schema.to_dict()
        assert d["name"] == "test"
        assert d["risk_level"] == "high"
        assert d["requires_approval"] is True


# ═══════════════════════════════════════════════════════════════════════
#  LifecycleHookManager Tests
# ═══════════════════════════════════════════════════════════════════════

class TestLifecycleHookManager:
    """LifecycleHookManager registration and firing tests."""

    def test_register_before_step(self):
        """Register a before_step hook."""
        hooks = LifecycleHookManager()
        cb = hooks.register("before_step", lambda: None)
        assert cb.hook_type == "before_step"
        assert hooks.get_hook_count("before_step") == 1

    def test_register_after_step(self):
        """Register an after_step hook."""
        hooks = LifecycleHookManager()
        hooks.register("after_step", lambda result: None)
        assert hooks.get_hook_count("after_step") == 1

    def test_register_on_error(self):
        """Register an on_error hook."""
        hooks = LifecycleHookManager()
        hooks.register("on_error", lambda error: None)
        assert hooks.get_hook_count("on_error") == 1

    def test_register_before_tool(self):
        """Register a before_tool hook."""
        hooks = LifecycleHookManager()
        hooks.register("before_tool", lambda tool: None, tool_name="shell_exec")
        assert hooks.get_hook_count("before_tool") == 1

    def test_register_invalid_hook_type(self):
        """Invalid hook type raises ValueError."""
        hooks = LifecycleHookManager()
        with pytest.raises(ValueError):
            hooks.register("invalid_type", lambda: None)

    def test_fire_before_step(self):
        """Fire before_step hooks."""
        hooks = LifecycleHookManager()
        called = []
        hooks.register("before_step", lambda: called.append("before"))
        result = hooks.fire_before_step()
        assert result.callbacks_executed == 1
        assert "before" in called

    def test_fire_after_step(self):
        """Fire after_step hooks with result."""
        hooks = LifecycleHookManager()
        results = []
        hooks.register("after_step", lambda r: results.append(r))
        hooks.fire_after_step("step_result")
        assert "step_result" in results

    def test_fire_on_error(self):
        """Fire on_error hooks with error."""
        hooks = LifecycleHookManager()
        errors = []
        hooks.register("on_error", lambda e: errors.append(str(e)))
        hooks.fire_on_error(RuntimeError("test error"))
        assert "test error" in errors[0]

    def test_fire_before_tool_with_filter(self):
        """before_tool hooks filter by tool_name."""
        hooks = LifecycleHookManager()
        calls = []

        hooks.register("before_tool", lambda **kw: calls.append(("global", kw.get("tool_name"))))
        hooks.register("before_tool", lambda **kw: calls.append(("shell", kw.get("tool_name"))), tool_name="shell_exec")

        hooks.fire_before_tool("shell_exec")
        assert len(calls) == 2  # Both global and specific

        calls.clear()
        hooks.fire_before_tool("other_tool")
        assert len(calls) == 1  # Only global
        assert calls[0][0] == "global"

    def test_fire_after_tool_with_filter(self):
        """after_tool hooks filter by tool_name."""
        hooks = LifecycleHookManager()
        calls = []

        hooks.register("after_tool", lambda **kw: calls.append(("global", kw.get("tool_name"))))
        hooks.register("after_tool", lambda **kw: calls.append(("specific", kw.get("tool_name"))), tool_name="search")

        hooks.fire_after_tool("search", result="found")
        assert len(calls) == 2

    def test_multiple_callbacks_same_type(self):
        """Multiple callbacks for same hook type execute in order."""
        hooks = LifecycleHookManager()
        order = []

        hooks.register("before_step", lambda: order.append(1), priority=1)
        hooks.register("before_step", lambda: order.append(2), priority=2)
        hooks.register("before_step", lambda: order.append(0), priority=0)

        hooks.fire_before_step()
        assert order == [0, 1, 2]  # Sorted by priority

    def test_hook_error_in_warn_mode(self):
        """Hook error in WARN mode is logged, not raised."""
        hooks = LifecycleHookManager()
        hooks.set_strict_mode(False)

        def failing_hook():
            raise RuntimeError("Hook failed")

        hooks.register("before_step", failing_hook)
        result = hooks.fire_before_step()
        assert result.callbacks_executed == 0  # Failed callback not counted as executed
        assert len(result.errors) > 0

    def test_hook_error_in_strict_mode(self):
        """Hook error in STRICT mode raises exception."""
        hooks = LifecycleHookManager()
        hooks.set_strict_mode(True)

        def failing_hook():
            raise RuntimeError("Hook failed")

        hooks.register("before_step", failing_hook)
        with pytest.raises(RuntimeError):
            hooks.fire_before_step()

    def test_unregister(self):
        """Unregister a specific callback."""
        hooks = LifecycleHookManager()
        cb = lambda: None
        hooks.register("before_step", cb)
        assert hooks.unregister("before_step", cb)
        assert hooks.get_hook_count("before_step") == 0

    def test_unregister_all(self):
        """Unregister all callbacks."""
        hooks = LifecycleHookManager()
        hooks.register("before_step", lambda: None)
        hooks.register("after_step", lambda: None)
        count = hooks.unregister_all()
        assert count == 2
        assert hooks.get_hook_count() == 0

    def test_unregister_all_by_type(self):
        """Unregister all callbacks for a specific type."""
        hooks = LifecycleHookManager()
        hooks.register("before_step", lambda: None)
        hooks.register("before_step", lambda: None)
        hooks.register("after_step", lambda: None)
        count = hooks.unregister_all("before_step")
        assert count == 2
        assert hooks.get_hook_count("before_step") == 0
        assert hooks.get_hook_count("after_step") == 1

    def test_fire_count_tracking(self):
        """Fire count is tracked per hook type."""
        hooks = LifecycleHookManager()
        hooks.register("before_step", lambda: None)
        hooks.fire_before_step()
        hooks.fire_before_step()
        assert hooks.get_fire_count("before_step") == 2

    def test_stats(self):
        """Hook stats are comprehensive."""
        hooks = LifecycleHookManager()
        hooks.register("before_step", lambda: None)
        hooks.register("after_step", lambda: None)
        hooks.fire_before_step()

        stats = hooks.get_stats()
        assert stats["total_hooks"] == 2
        assert stats["hook_counts"]["before_step"] == 1
        assert stats["fire_counts"]["before_step"] == 1

    def test_clear(self):
        """Clear removes all hooks."""
        hooks = LifecycleHookManager()
        hooks.register("before_step", lambda: None)
        hooks.clear()
        assert hooks.get_hook_count() == 0


# ═══════════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end: ToolRegistry + LifecycleHooks."""

    def test_tool_execution_with_hooks(self):
        """Tool execution triggers before/after hooks."""
        registry = ToolRegistry()
        hooks = LifecycleHookManager()

        hook_calls = []

        def before_fn(**kwargs):
            hook_calls.append(("before", kwargs.get("tool_name")))

        def after_fn(**kwargs):
            hook_calls.append(("after", kwargs.get("tool_name")))

        hooks.register("before_tool", before_fn)
        hooks.register("after_tool", after_fn)

        def my_tool(query: str) -> str:
            return f"result: {query}"

        registry.register_from_annotation(fn=my_tool, description="Search")

        # Fire hooks around tool execution
        hooks.fire_before_tool("my_tool")
        result = registry.execute("my_tool", {"query": "test"})
        hooks.fire_after_tool("my_tool", result=result)

        assert result.success is True
        assert len(hook_calls) == 2
        assert hook_calls[0][0] == "before"
        assert hook_calls[1][0] == "after"

    def test_tool_with_approval_and_hooks(self):
        """High-risk tool with HITL approval and lifecycle hooks."""
        registry = ToolRegistry()
        hooks = LifecycleHookManager()

        approval_requests = []

        class MockHITL:
            def request_approval(self, **kwargs):
                approval_requests.append(kwargs)
                return True  # Approve

        registry.set_hitl_manager(MockHITL())

        hooks.register("before_tool", lambda **kw: None, tool_name="dangerous")

        def dangerous_tool(cmd: str) -> str:
            return f"executed: {cmd}"

        registry.register_from_annotation(
            fn=dangerous_tool, description="Dangerous",
            risk_level="high", requires_approval=True,
        )

        hooks.fire_before_tool("dangerous")
        result = registry.execute("dangerous_tool", {"cmd": "ls"})
        hooks.fire_after_tool("dangerous", result=result)

        assert result.success is True
        assert result.approved is True
        assert len(approval_requests) == 1

    def test_step_hooks_with_autoloop(self):
        """Step hooks fire around autoloop steps (kernel fires them automatically)."""
        from src.runtime.harness_kernel import HarnessKernel, HarnessRuntimeMode, AutoLoopConfig, StepResult

        hooks = LifecycleHookManager()
        step_events = []

        hooks.register("before_step", lambda: step_events.append("before"))
        hooks.register("after_step", lambda r: step_events.append(("after", r)))

        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.register_lifecycle_hooks(hooks)

        config = AutoLoopConfig(max_steps=3)

        def step_fn():
            return StepResult(observation="step")

        result = k.run_autoloop(config, step_fn)
        assert result.exit_reason == "max_steps"
        # Kernel's _simple_loop fires before_step + after_step per step
        assert len(step_events) == 6  # 3 before + 3 after

    def test_tool_schema_injection_for_llm(self):
        """Tool schemas can be injected into LLM context."""
        registry = ToolRegistry()

        def search(query: str) -> str: return "results"
        def calculate(expr: str) -> float: return 42.0

        registry.register_from_annotation(fn=search, description="Search the web")
        registry.register_from_annotation(fn=calculate, description="Calculate math")

        # Get schemas in OpenAI function format
        functions = registry.get_schemas_as_openai_functions()
        assert len(functions) == 2

        # Verify format is correct for LLM injection
        for func in functions:
            assert "type" in func
            assert "function" in func
            assert "name" in func["function"]
            assert "parameters" in func["function"]