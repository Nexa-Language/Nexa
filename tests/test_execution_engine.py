"""
Nexa v2.0 M1 Tests — ExecutionEngine + ContextManager + ToolOutputStore

Tests cover:
  - HarnessKernel: initialization, singleton, autoloop delegation
  - ExecutionEngine: run_loop, exit conditions, error handling, try_agent
  - ContextManager: scope management, message add, eviction strategies
  - ToolOutputStore: store/retrieve, file offloading, TTL cleanup
  - Integration: autoloop + context + tool output end-to-end

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.2
"""

import os
import time
import json
import tempfile
import pytest

from src.runtime.harness_kernel import (
    HarnessKernel, HarnessRuntimeMode, AutoLoopConfig,
    AutoLoopResult, StepResult, ContextScope, get_kernel, reset_kernel,
)
from src.runtime.execution_engine import ExecutionEngine
from src.runtime.context_manager import (
    ContextManager, ContextMessage, ToolOutputRef, EvictionStats, estimate_tokens,
)
from src.runtime.tool_output_store import ToolOutputStore, get_tool_output_store


# ═══════════════════════════════════════════════════════════════════════
#  HarnessKernel Tests
# ═══════════════════════════════════════════════════════════════════════

class TestHarnessKernel:
    """HarnessKernel core functionality tests."""

    def setup_method(self):
        reset_kernel()

    def test_singleton_pattern(self):
        """Kernel singleton returns same instance."""
        k1 = HarnessKernel.get_instance()
        k2 = HarnessKernel.get_instance()
        assert k1 is k2

    def test_reset_creates_new_instance(self):
        """Reset allows creating a new instance."""
        k1 = HarnessKernel.get_instance()
        HarnessKernel.reset_instance()
        k2 = HarnessKernel.get_instance(HarnessRuntimeMode.STRICT)
        assert k1 is not k2
        assert k2.mode == HarnessRuntimeMode.STRICT

    def test_default_mode_is_warn(self):
        """Default kernel mode is WARN."""
        k = HarnessKernel()
        assert k.mode == HarnessRuntimeMode.WARN

    def test_off_mode_skips_harness(self):
        """OFF mode: autoloop runs step_fn once."""
        k = HarnessKernel(mode=HarnessRuntimeMode.OFF)
        config = AutoLoopConfig(max_steps=10)

        call_count = 0
        def step_fn():
            nonlocal call_count
            call_count += 1
            return StepResult(observation="done")

        result = k.run_autoloop(config, step_fn)
        assert call_count == 1
        assert result.exit_reason == "off_mode"

    def test_simple_loop_max_steps(self):
        """Simple loop exits at max_steps."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        config = AutoLoopConfig(max_steps=5)

        def step_fn():
            return StepResult(observation="step")

        result = k.run_autoloop(config, step_fn)
        assert result.exit_reason == "max_steps"
        assert result.total_steps == 5

    def test_simple_loop_exit_when(self):
        """Simple loop exits when condition met."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        config = AutoLoopConfig(max_steps=20, exit_when="resolved")

        step_num = 0
        def step_fn():
            nonlocal step_num
            step_num += 1
            if step_num >= 3:
                return StepResult(observation="Task resolved successfully")
            return StepResult(observation="Still working...")

        result = k.run_autoloop(config, step_fn)
        assert result.exit_reason == "exit_when_met"
        assert result.total_steps == 3

    def test_simple_loop_timeout(self):
        """Simple loop exits on timeout."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        config = AutoLoopConfig(max_steps=100, timeout=1)

        def slow_step_fn():
            time.sleep(0.5)
            return StepResult(observation="step")

        result = k.run_autoloop(config, slow_step_fn)
        assert result.exit_reason == "timeout"

    def test_strict_mode_error_exits(self):
        """STRICT mode: error exits the loop."""
        k = HarnessKernel(mode=HarnessRuntimeMode.STRICT)
        config = AutoLoopConfig(max_steps=10)

        def error_step_fn():
            raise RuntimeError("Tool execution failed")

        result = k.run_autoloop(config, error_step_fn)
        assert result.success is False
        assert result.exit_reason == "error"

    def test_warn_mode_error_continues(self):
        """WARN mode: error is recorded but loop continues."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        config = AutoLoopConfig(max_steps=5)

        call_count = 0
        def mixed_step_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Temporary error")
            return StepResult(observation="step ok")

        result = k.run_autoloop(config, mixed_step_fn)
        assert result.exit_reason == "max_steps"
        assert result.total_steps == 5

    def test_context_scope_management(self):
        """Kernel can enter/exit context scopes."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        scope = k.enter_context_scope("main", {"max_tokens": 50000})
        assert scope.max_tokens == 50000
        k.exit_context_scope("main")

    def test_is_strict_is_off(self):
        """Mode check methods work correctly."""
        strict_k = HarnessKernel(mode=HarnessRuntimeMode.STRICT)
        assert strict_k.is_strict()
        assert not strict_k.is_off()

        off_k = HarnessKernel(mode=HarnessRuntimeMode.OFF)
        assert off_k.is_off()
        assert not off_k.is_strict()


# ═══════════════════════════════════════════════════════════════════════
#  ExecutionEngine Tests
# ═══════════════════════════════════════════════════════════════════════

class TestExecutionEngine:
    """ExecutionEngine ReAct loop tests."""

    def setup_method(self):
        reset_kernel()

    def test_run_loop_basic(self):
        """Engine runs a basic autoloop."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        engine = k._execution_engine
        config = AutoLoopConfig(max_steps=3)

        def step_fn():
            return StepResult(observation="step")

        result = engine.run_loop(config, step_fn)
        assert result.exit_reason == "max_steps"
        assert len(result.steps) == 3

    def test_run_loop_exit_when_resolved(self):
        """Engine exits when 'resolved' condition met."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        engine = k._execution_engine
        config = AutoLoopConfig(max_steps=20, exit_when="resolved")

        step_num = 0
        def step_fn():
            nonlocal step_num
            step_num += 1
            if step_num >= 5:
                return StepResult(observation="Task resolved")
            return StepResult(observation="Working...")

        result = engine.run_loop(config, step_fn)
        assert result.exit_reason == "exit_when_met"
        assert result.total_steps == 5

    def test_run_loop_timeout(self):
        """Engine exits on timeout."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        engine = k._execution_engine
        config = AutoLoopConfig(max_steps=100, timeout=2)

        def slow_step():
            time.sleep(1)
            return StepResult(observation="step")

        result = engine.run_loop(config, slow_step)
        assert result.exit_reason == "timeout"

    def test_try_agent_success(self):
        """try_agent with successful execution."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        engine = k._execution_engine

        result, error = engine.run_try_agent(
            try_fn=lambda: "success",
        )
        assert result == "success"
        assert error is None

    def test_try_agent_with_correction(self):
        """try_agent with error and correction."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        engine = k._execution_engine

        def try_fn():
            raise RuntimeError("Tool error")

        def catch_fn(error_var, error_type):
            return f"corrected: {error_var}"

        result, error = engine.run_try_agent(try_fn, catch_fn)
        assert "corrected" in str(result)
        assert error is not None

    def test_try_agent_strict_mode_raises(self):
        """try_agent in strict mode raises on uncorrected error."""
        k = HarnessKernel(mode=HarnessRuntimeMode.STRICT)
        k.initialize()
        engine = k._execution_engine

        with pytest.raises(RuntimeError):
            engine.run_try_agent(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

    def test_correction_reflection_generation(self):
        """Engine generates correction reflection text."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        engine = k._execution_engine

        reflection = engine._generate_correction_reflection(
            "shell_exec failed", {"tool_name": "shell_exec"}
        )
        assert "shell_exec" in reflection
        assert "retrying" in reflection.lower() or "alternative" in reflection.lower()

    def test_step_count_tracking(self):
        """Engine tracks step count."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        engine = k._execution_engine
        config = AutoLoopConfig(max_steps=5)

        engine.run_loop(config, lambda: StepResult(observation="step"))
        assert engine.get_step_count() == 5


# ═══════════════════════════════════════════════════════════════════════
#  ContextManager Tests
# ═══════════════════════════════════════════════════════════════════════

class TestContextManager:
    """ContextManager scope and eviction tests."""

    def setup_method(self):
        reset_kernel()

    def test_enter_exit_scope(self):
        """Scope enter/exit works correctly."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        cm = ContextManager(kernel=k)

        scope = cm.enter_scope("main", {"max_tokens": 50000, "strategy": "sliding_window"})
        assert cm.get_current_max_tokens() == 50000
        assert cm.get_current_strategy() == "sliding_window"

        cm.exit_scope("main")
        # After exit, should return default
        assert cm.get_current_max_tokens() == 100000

    def test_nested_scopes(self):
        """Nested scopes override parent settings."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        cm = ContextManager(kernel=k)

        cm.enter_scope("outer", {"max_tokens": 100000})
        assert cm.get_current_max_tokens() == 100000

        cm.enter_scope("inner", {"max_tokens": 50000})
        assert cm.get_current_max_tokens() == 50000

        cm.exit_scope("inner")
        assert cm.get_current_max_tokens() == 100000

        cm.exit_scope("outer")

    def test_add_message(self):
        """Messages are added with token estimation."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        cm = ContextManager(kernel=k)

        msg = cm.add_message("user", "Hello, agent!")
        assert msg.role == "user"
        assert msg.content == "Hello, agent!"
        assert msg.token_count > 0
        assert cm.get_message_count() == 1

    def test_add_tool_result(self):
        """Tool results are offloaded with summary."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        cm = ContextManager(kernel=k)

        ref = cm.add_tool_result("shell_exec", "large output content here", summary="command succeeded")
        assert ref.tool_name == "shell_exec"
        assert ref.summary == "command succeeded"
        assert cm.get_message_count() == 1  # Only summary in context

    def test_sliding_window_eviction(self):
        """Sliding window removes oldest messages when over limit."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        cm = ContextManager(kernel=k)

        # Set very low token limit
        cm.enter_scope("test", {"max_tokens": 50, "strategy": "sliding_window"})

        # Add many messages to exceed limit
        for i in range(20):
            cm.add_message("user", f"Message {i} with some content to add tokens")

        # Should have evicted some messages
        stats = cm.get_eviction_stats()
        assert stats.total_evictions > 0
        assert stats.messages_removed > 0

        # Total tokens should be under limit now
        assert cm.get_total_tokens() <= 50

        cm.exit_scope("test")

    def test_importance_weighted_eviction(self):
        """Importance-weighted removes low-priority messages first."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        cm = ContextManager(kernel=k)

        cm.enter_scope("test", {"max_tokens": 100, "strategy": "importance_weighted"})

        # Add messages with different priorities
        cm.add_message("system", "System prompt", priority=5)  # Critical
        cm.add_message("user", "Low priority message", priority=1)
        cm.add_message("user", "Medium priority message", priority=3)
        cm.add_message("user", "Another low priority", priority=1)

        # Force eviction by adding more content
        for i in range(10):
            cm.add_message("user", f"Extra message {i}", priority=1)

        # System message should still be present
        messages = cm.get_messages()
        system_msgs = [m for m in messages if m.role == "system"]
        assert len(system_msgs) >= 1

        cm.exit_scope("test")

    def test_smart_summarization_eviction(self):
        """Smart summarization compresses older messages."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        cm = ContextManager(kernel=k)

        cm.enter_scope("test", {"max_tokens": 50, "strategy": "smart_summarization"})

        # Add many messages with enough content to exceed 50 tokens
        for i in range(15):
            cm.add_message("user", f"Message number {i} with enough content to trigger eviction and compression of older messages in the context window")

        stats = cm.get_eviction_stats()
        # Should have done some eviction
        assert stats.total_evictions > 0

        cm.exit_scope("test")

    def test_context_stats(self):
        """Context stats are comprehensive."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        cm = ContextManager(kernel=k)

        cm.add_message("user", "Hello")
        stats = cm.get_context_stats()
        assert "total_tokens" in stats
        assert "max_tokens" in stats
        assert "message_count" in stats
        assert stats["message_count"] == 1

    def test_reset_clears_all(self):
        """Reset clears all messages and scopes."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        cm = ContextManager(kernel=k)

        cm.enter_scope("test", {"max_tokens": 50000})
        cm.add_message("user", "Hello")
        cm.reset()
        assert cm.get_message_count() == 0
        assert len(cm._scope_stack) == 0


# ═══════════════════════════════════════════════════════════════════════
#  Token Estimation Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTokenEstimation:
    """Token estimation utility tests."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_english_text(self):
        # ~4 chars per token
        tokens = estimate_tokens("Hello world, this is a test message")
        assert tokens > 0
        assert tokens < len("Hello world, this is a test message")

    def test_chinese_text(self):
        # ~2 chars per token
        tokens = estimate_tokens("你好世界这是一个测试")
        assert tokens > 0

    def test_mixed_text(self):
        tokens = estimate_tokens("Hello 你好 world 世界")
        assert tokens > 0


# ═══════════════════════════════════════════════════════════════════════
#  ToolOutputStore Tests
# ═══════════════════════════════════════════════════════════════════════

class TestToolOutputStore:
    """ToolOutputStore persistence tests."""

    def test_store_small_output_in_memory(self):
        """Small outputs are kept in memory."""
        store = ToolOutputStore()
        entry = store.store("test_tool", "small output")
        assert entry.content == "small output"
        assert entry.file_path is None

    def test_store_large_output_in_file(self):
        """Large outputs are written to files."""
        store = ToolOutputStore()
        large_output = "x" * 2000  # > 1KB threshold
        entry = store.store("test_tool", large_output)
        assert entry.file_path is not None
        assert os.path.exists(entry.file_path)

    def test_retrieve_from_memory(self):
        """Retrieve small output from memory."""
        store = ToolOutputStore()
        entry = store.store("test_tool", "small output")
        result = store.retrieve(entry.output_id)
        assert result == "small output"

    def test_retrieve_from_file(self):
        """Retrieve large output from file."""
        store = ToolOutputStore()
        large_output = "x" * 2000
        entry = store.store("test_tool", large_output)
        result = store.retrieve(entry.output_id)
        assert result == large_output

    def test_retrieve_nonexistent(self):
        """Retrieve nonexistent output returns None."""
        store = ToolOutputStore()
        result = store.retrieve("nonexistent_id")
        assert result is None

    def test_get_summary(self):
        """Get summary of stored output."""
        store = ToolOutputStore()
        entry = store.store("test_tool", "output content", summary="brief summary")
        summary = store.get_summary(entry.output_id)
        assert summary == "brief summary"

    def test_auto_summary(self):
        """Auto-generated summary truncates long output."""
        store = ToolOutputStore()
        long_output = "word " * 200
        entry = store.store("test_tool", long_output)
        assert len(entry.summary) < len(long_output)

    def test_ttl_cleanup(self):
        """Expired entries are cleaned up."""
        store = ToolOutputStore(default_ttl=1)  # 1 second TTL
        entry = store.store("test_tool", "output")

        # Wait for TTL to expire
        time.sleep(2)

        removed = store.cleanup()
        assert removed == 1

        # Entry should no longer be retrievable
        result = store.retrieve(entry.output_id)
        assert result is None

    def test_stats(self):
        """Store stats are accurate."""
        store = ToolOutputStore()
        store.store("tool1", "small")
        store.store("tool2", "x" * 2000)

        stats = store.get_stats()
        assert stats["total_entries"] == 2
        assert stats["in_memory"] == 1
        assert stats["in_file"] == 1

    def test_clear(self):
        """Clear removes all entries."""
        store = ToolOutputStore()
        store.store("tool1", "output1")
        store.store("tool2", "output2")
        store.clear()
        assert store.get_stats()["total_entries"] == 0


# ═══════════════════════════════════════════════════════════════════════
#  Data Structure Tests
# ═══════════════════════════════════════════════════════════════════════

class TestDataStructures:
    """Core data structure serialization tests."""

    def test_step_result_to_dict(self):
        sr = StepResult(step_number=1, action="search", observation="found")
        d = sr.to_dict()
        assert d["step_number"] == 1
        assert d["action"] == "search"

    def test_autoloop_result_to_dict(self):
        ar = AutoLoopResult(exit_reason="max_steps", total_steps=5)
        d = ar.to_dict()
        assert d["exit_reason"] == "max_steps"
        assert d["total_steps"] == 5

    def test_autoloop_config_to_dict(self):
        ac = AutoLoopConfig(max_steps=50, exit_when="resolved", timeout=300)
        d = ac.to_dict()
        assert d["max_steps"] == 50
        assert d["exit_when"] == "resolved"

    def test_context_scope_to_dict(self):
        cs = ContextScope(max_tokens=100000, strategy="sliding_window")
        d = cs.to_dict()
        assert d["max_tokens"] == 100000
        assert d["strategy"] == "sliding_window"

    def test_context_message_to_dict(self):
        cm = ContextMessage(role="user", content="Hello", token_count=5)
        d = cm.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"

    def test_eviction_stats_to_dict(self):
        es = EvictionStats(total_evictions=3, messages_removed=10)
        d = es.to_dict()
        assert d["total_evictions"] == 3
        assert d["messages_removed"] == 10


# ═══════════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end integration: autoloop + context + tool output."""

    def setup_method(self):
        reset_kernel()

    def test_autoloop_with_context_management(self):
        """Autoloop with context scope and message tracking."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        cm = k._context_manager

        # Enter context scope
        cm.enter_scope("autoloop", {"max_tokens": 50000, "strategy": "sliding_window"})

        config = AutoLoopConfig(max_steps=5, exit_when="done")

        step_num = 0
        def step_fn():
            nonlocal step_num
            step_num += 1
            cm.add_message("assistant", f"Step {step_num} result")
            if step_num >= 3:
                return StepResult(observation="Task done successfully")
            return StepResult(observation="Working...")

        result = k.run_autoloop(config, step_fn)
        assert result.exit_reason == "exit_when_met"

        # Context should have messages
        assert cm.get_message_count() > 0

        cm.exit_scope("autoloop")

    def test_autoloop_with_tool_output_offload(self):
        """Autoloop with tool output offloading."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        cm = k._context_manager

        config = AutoLoopConfig(max_steps=3)

        def step_fn():
            # Simulate tool output
            cm.add_tool_result("shell_exec", "command output: " + "x" * 500, summary="command succeeded")
            return StepResult(observation="step completed")

        result = k.run_autoloop(config, step_fn)
        assert result.exit_reason == "max_steps"

        # Tool output refs should be tracked in context manager
        assert len(cm._tool_output_refs) >= 1

    def test_autoloop_with_error_correction(self):
        """Autoloop with try_agent error correction."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        engine = k._execution_engine

        # Simulate a try_agent cycle
        attempt = 0
        def try_fn():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise RuntimeError("First attempt failed")
            return "success on retry"

        def catch_fn(error_var, error_type):
            nonlocal attempt
            # Correction: retry
            return f"corrected after {error_var}"

        result, error = engine.run_try_agent(try_fn, catch_fn)
        assert "corrected" in str(result)
        assert error is not None

    def test_full_pipeline_well_harnessed(self):
        """Full pipeline: autoloop + context + tool output + exit condition."""
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        k.initialize()
        cm = k._context_manager

        cm.enter_scope("pipeline", {"max_tokens": 100000, "strategy": "importance_weighted"})

        config = AutoLoopConfig(max_steps=10, exit_when="resolved", timeout=30)

        step_num = 0
        def step_fn():
            nonlocal step_num
            step_num += 1
            cm.add_message("assistant", f"Step {step_num}", priority=3)

            if step_num >= 5:
                return StepResult(
                    action="final_step",
                    observation="Task resolved successfully",
                    success=True,
                )
            return StepResult(
                action=f"step_{step_num}",
                observation=f"Working on step {step_num}",
                success=True,
            )

        result = k.run_autoloop(config, step_fn)

        # Verify exit condition
        assert result.exit_reason == "exit_when_met"
        assert result.total_steps == 5
        assert result.success is True

        # Verify context
        assert cm.get_message_count() > 0
        stats = cm.get_context_stats()
        assert stats["total_tokens"] <= 100000

        cm.exit_scope("pipeline")