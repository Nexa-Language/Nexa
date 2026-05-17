"""
Nexa v2.0 HarnessKernel — 核心调度器框架

HarnessKernel 是 v2.0 的运行时入口，协调 ExecutionEngine、ContextManager、
ToolRegistry、StateStore、LifecycleHooks、TraceSystem 等子系统。

Design Rationale:
  - 单例模式: 全局唯一 HarnessKernel 实例，由 Nexa Runtime 自动初始化
  - 插件式架构: 各子系统通过 register_* 方法注入，松耦合
  - 配置驱动: harness_mode (strict/warn/off) 控制运行时行为
  - v1.x 兼容: harness_mode=off 时，HarnessKernel 退化为空壳，不影响 v1.x 代码

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.2
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════
#  Core Data Structures
# ═══════════════════════════════════════════════════════════════════════

class HarnessRuntimeMode(Enum):
    """Runtime harness mode — mirrors compile-time HarnessMode but for runtime."""
    STRICT = "strict"  # Errors raise exceptions
    WARN = "warn"      # Errors become warnings, execution continues
    OFF = "off"        # No harness enforcement, v1.x compatibility


@dataclass
class AutoLoopConfig:
    """Configuration for an autoloop execution cycle."""
    max_steps: int = 50
    exit_when: Optional[str] = None  # Semantic exit condition (evaluated by LLM)
    timeout: Optional[int] = None    # Timeout in seconds
    step_delay: float = 0.0          # Delay between steps (seconds)

    def to_dict(self) -> Dict:
        return {
            "max_steps": self.max_steps,
            "exit_when": self.exit_when,
            "timeout": self.timeout,
            "step_delay": self.step_delay,
        }


@dataclass
class StepResult:
    """Result of a single ReAct step within an autoloop."""
    step_number: int = 0
    action: str = ""           # What the agent decided to do
    observation: str = ""      # What the agent observed
    reflection: Optional[str] = None  # Self-reflection on the step
    tool_calls: List[Dict] = field(default_factory=list)  # Tool calls made
    success: bool = True       # Whether the step succeeded
    error: Optional[str] = None  # Error message if step failed
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "observation": self.observation,
            "reflection": self.reflection,
            "tool_calls": self.tool_calls,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class AutoLoopResult:
    """Result of a complete autoloop execution."""
    steps: List[StepResult] = field(default_factory=list)
    exit_reason: str = ""      # "exit_when_met" | "max_steps" | "timeout" | "error"
    final_result: Any = None   # The final output of the loop
    total_steps: int = 0
    total_time: float = 0.0
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "exit_reason": self.exit_reason,
            "final_result": self.final_result,
            "total_steps": self.total_steps,
            "total_time": self.total_time,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class ContextScope:
    """A context scope created by with_context."""
    max_tokens: int = 100000
    strategy: str = "sliding_window"  # sliding_window | importance_weighted | smart_summarization
    priority_tags: Set[str] = field(default_factory=set)
    messages: List[Dict] = field(default_factory=list)
    tool_outputs: List[Dict] = field(default_factory=list)
    parent_scope: Optional[str] = None  # Scope nesting

    def to_dict(self) -> Dict:
        return {
            "max_tokens": self.max_tokens,
            "strategy": self.strategy,
            "priority_tags": list(self.priority_tags),
            "message_count": len(self.messages),
            "tool_output_count": len(self.tool_outputs),
            "parent_scope": self.parent_scope,
        }


# ═══════════════════════════════════════════════════════════════════════
#  HarnessKernel — Core Orchestrator
# ═══════════════════════════════════════════════════════════════════════

class HarnessKernel:
    """
    Core runtime orchestrator for the Harness system.

    Coordinates all v2.0 subsystems:
      - ExecutionEngine: autoloop ReAct cycles
      - ContextManager: with_context scope management
      - ToolRegistry: @tool annotation processing
      - StateStore: snapshot/restore/fork
      - LifecycleHooks: before/after step/tool hooks
      - TraceSystem: execution trace logging

    Usage:
        kernel = HarnessKernel(mode=HarnessRuntimeMode.WARN)
        kernel.initialize()
        result = kernel.run_autoloop(config, step_fn)
    """

    _instance: Optional[HarnessKernel] = None
    _lock = threading.Lock()

    def __init__(self, mode: HarnessRuntimeMode = HarnessRuntimeMode.WARN) -> None:
        self.mode = mode
        self._initialized = False
        self._execution_engine: Optional[Any] = None
        self._context_manager: Optional[Any] = None
        self._tool_registry: Optional[Any] = None
        self._state_store: Optional[Any] = None
        self._lifecycle_hooks: Optional[Any] = None
        self._trace_system: Optional[Any] = None
        self._step_count = 0
        self._active_scopes: Dict[str, ContextScope] = {}

    @classmethod
    def get_instance(cls, mode: HarnessRuntimeMode = HarnessRuntimeMode.WARN) -> HarnessKernel:
        """Get the global HarnessKernel instance (singleton)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(mode)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the global instance (for testing)."""
        with cls._lock:
            cls._instance = None

    def initialize(self) -> None:
        """Initialize all subsystems. Called once before first use."""
        if self._initialized:
            return

        # Lazy-import subsystems to avoid circular dependencies
        if self.mode != HarnessRuntimeMode.OFF:
            from .execution_engine import ExecutionEngine
            from .context_manager import ContextManager

            self._execution_engine = ExecutionEngine(kernel=self)
            self._context_manager = ContextManager(kernel=self)

        self._initialized = True

    def register_execution_engine(self, engine: Any) -> None:
        """Register a custom ExecutionEngine."""
        self._execution_engine = engine

    def register_context_manager(self, manager: Any) -> None:
        """Register a custom ContextManager."""
        self._context_manager = manager

    def register_tool_registry(self, registry: Any) -> None:
        """Register a ToolRegistry."""
        self._tool_registry = registry

    def register_state_store(self, store: Any) -> None:
        """Register a StateStore."""
        self._state_store = store

    def register_lifecycle_hooks(self, hooks: Any) -> None:
        """Register a LifecycleHooks manager."""
        self._lifecycle_hooks = hooks

    def register_trace_system(self, trace: Any) -> None:
        """Register a TraceSystem."""
        self._trace_system = trace

    # ─── Execution ───

    def run_autoloop(self, config: AutoLoopConfig, step_fn: Callable[..., StepResult]) -> AutoLoopResult:
        """
        Run an autoloop cycle with the given configuration and step function.

        Args:
            config: AutoLoopConfig with max_steps, exit_when, timeout
            step_fn: A callable that executes one ReAct step and returns StepResult

        Returns:
            AutoLoopResult with all step results and exit reason
        """
        if self.mode == HarnessRuntimeMode.OFF:
            # In OFF mode, just run the step function once (v1.x compatibility)
            result = AutoLoopResult()
            step = step_fn()
            result.steps.append(step)
            result.exit_reason = "off_mode"
            result.total_steps = 1
            return result

        if not self._initialized:
            self.initialize()

        if self._execution_engine:
            return self._execution_engine.run_loop(config, step_fn)

        # Fallback: simple loop without engine
        return self._simple_loop(config, step_fn)

    def _simple_loop(self, config: AutoLoopConfig, step_fn: Callable[..., StepResult]) -> AutoLoopResult:
        """Simple autoloop fallback when ExecutionEngine is not available."""
        result = AutoLoopResult()
        start_time = time.time()

        for i in range(config.max_steps):
            self._step_count += 1

            # Check timeout
            if config.timeout and (time.time() - start_time) > config.timeout:
                result.exit_reason = "timeout"
                result.total_steps = i
                result.total_time = time.time() - start_time
                return result

            # Execute step
            try:
                step = step_fn()
                step.step_number = i + 1
                result.steps.append(step)

                # Check exit condition (simple string match for now)
                if config.exit_when and step.observation:
                    if self._check_exit_condition(config.exit_when, step):
                        result.exit_reason = "exit_when_met"
                        result.final_result = step.observation
                        result.total_steps = i + 1
                        result.total_time = time.time() - start_time
                        return result

            except Exception as e:
                if self.mode == HarnessRuntimeMode.STRICT:
                    result.success = False
                    result.error = str(e)
                    result.exit_reason = "error"
                    result.total_steps = i
                    result.total_time = time.time() - start_time
                    return result
                else:
                    # WARN mode: log error and continue
                    step = StepResult(
                        step_number=i + 1,
                        success=False,
                        error=str(e),
                    )
                    result.steps.append(step)

            # Step delay
            if config.step_delay > 0:
                time.sleep(config.step_delay)

        result.exit_reason = "max_steps"
        result.total_steps = config.max_steps
        result.total_time = time.time() - start_time
        if result.steps:
            result.final_result = result.steps[-1].observation
        return result

    def _check_exit_condition(self, condition: str, step: StepResult) -> bool:
        """
        Check if the exit_when condition is met.

        Simple implementation: substring match in observation.
        Full implementation (M4): LLM-based semantic evaluation.
        """
        if not condition or not step.observation:
            return False

        # Simple substring match
        condition_lower = condition.lower()
        observation_lower = step.observation.lower()

        # Check for common resolution signals
        resolution_signals = ["resolved", "completed", "done", "success", "finished"]
        if condition_lower in resolution_signals:
            return any(sig in observation_lower for sig in resolution_signals)

        # Direct substring match
        return condition_lower in observation_lower

    # ─── Context ───

    def enter_context_scope(self, scope_name: str, config: Dict) -> ContextScope:
        """Enter a with_context scope."""
        scope = ContextScope(
            max_tokens=config.get("max_tokens", 100000),
            strategy=config.get("strategy", "sliding_window"),
            priority_tags=set(config.get("priority_tags", [])),
        )
        self._active_scopes[scope_name] = scope
        return scope

    def exit_context_scope(self, scope_name: str) -> None:
        """Exit a with_context scope."""
        if scope_name in self._active_scopes:
            del self._active_scopes[scope_name]

    def get_active_scope(self) -> Optional[ContextScope]:
        """Get the currently active context scope."""
        if self._active_scopes:
            # Return the most recently entered scope
            return list(self._active_scopes.values())[-1]
        return None

    # ─── Lifecycle Hooks ───

    def fire_before_step(self) -> None:
        """Fire before_step lifecycle hook."""
        if self._lifecycle_hooks:
            self._lifecycle_hooks.fire("before_step")

    def fire_after_step(self, step_result: StepResult) -> None:
        """Fire after_step lifecycle hook."""
        if self._lifecycle_hooks:
            self._lifecycle_hooks.fire("after_step", step_result)

    def fire_on_error(self, error: Exception) -> None:
        """Fire on_error lifecycle hook."""
        if self._lifecycle_hooks:
            self._lifecycle_hooks.fire("on_error", error)

    def fire_before_tool(self, tool_name: str) -> None:
        """Fire before_tool lifecycle hook."""
        if self._lifecycle_hooks:
            self._lifecycle_hooks.fire("before_tool", tool_name)

    def fire_after_tool(self, tool_name: str, result: Any) -> None:
        """Fire after_tool lifecycle hook."""
        if self._lifecycle_hooks:
            self._lifecycle_hooks.fire("after_tool", tool_name, result)

    # ─── State ───

    def create_snapshot(self) -> str:
        """Create a state snapshot and return its ID."""
        if self._state_store:
            return self._state_store.snapshot()
        return f"snap_{int(time.time())}"

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """Restore a state snapshot."""
        if self._state_store:
            return self._state_store.restore(snapshot_id)
        return False

    # ─── Trace ───

    def trace_event(self, event_type: str, data: Dict) -> None:
        """Log a trace event."""
        if self._trace_system:
            self._trace_system.log(event_type, data)

    # ─── Utility ───

    def get_step_count(self) -> int:
        """Get the total number of steps executed."""
        return self._step_count

    def is_strict(self) -> bool:
        """Check if running in strict mode."""
        return self.mode == HarnessRuntimeMode.STRICT

    def is_off(self) -> bool:
        """Check if running in off mode (v1.x compatibility)."""
        return self.mode == HarnessRuntimeMode.OFF


# ═══════════════════════════════════════════════════════════════════════
#  Global Runtime Instance
# ═══════════════════════════════════════════════════════════════════════

# Default global kernel instance
_kernel: Optional[HarnessKernel] = None


def get_kernel(mode: Optional[HarnessRuntimeMode] = None) -> HarnessKernel:
    """Get the global HarnessKernel instance."""
    global _kernel
    if _kernel is None:
        _kernel = HarnessKernel.get_instance(mode or HarnessRuntimeMode.WARN)
    return _kernel


def reset_kernel() -> None:
    """Reset the global kernel (for testing)."""
    global _kernel
    _kernel = None
    HarnessKernel.reset_instance()