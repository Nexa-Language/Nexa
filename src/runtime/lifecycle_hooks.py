"""
Nexa v2.0 LifecycleHookManager — 生命周期钩子管理器

LifecycleHookManager 实现 Harness L-dimension 的运行时核心，负责：
  - register(): 注册钩子回调函数
  - fire(): 触发特定类型的钩子
  - fire_before_step/fire_after_step/fire_on_error: step 级钩子
  - fire_before_tool/fire_after_tool: tool 级钩子

Design Rationale:
  - 钩子类型: before_step, after_step, on_error, before_tool, after_tool
  - 多回调: 同一钩子类型可注册多个回调，按注册顺序执行
  - 错误隔离: 钩子回调中的错误不会中断主流程 (WARN 模式)
  - 条件触发: before_tool 钩子可按 tool_name 过滤

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.3
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("nexa.lifecycle_hooks")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class HookCallback:
    """A registered hook callback."""
    hook_type: str = ""           # before_step | after_step | on_error | before_tool | after_tool
    callback: Callable = None     # The callback function
    tool_name: Optional[str] = None  # For before_tool/after_tool: specific tool filter
    priority: int = 0             # Execution priority (lower = earlier)
    registered_at: float = 0.0    # Registration timestamp

    def to_dict(self) -> Dict:
        return {
            "hook_type": self.hook_type,
            "tool_name": self.tool_name,
            "priority": self.priority,
            "callback_name": self.callback.__name__ if self.callback else "",
        }


@dataclass
class HookExecutionResult:
    """Result of a hook execution."""
    hook_type: str = ""
    callbacks_executed: int = 0
    errors: List[str] = field(default_factory=list)
    blocked: bool = False         # Whether a before_* hook blocked the action
    block_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "hook_type": self.hook_type,
            "callbacks_executed": self.callbacks_executed,
            "errors": self.errors,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
        }


# ═══════════════════════════════════════════════════════════════════════
#  LifecycleHookManager — L-Dimension Runtime
# ═══════════════════════════════════════════════════════════════════════

class LifecycleHookManager:
    """
    Lifecycle hook manager for step/tool execution interception.

    Implements the L-dimension runtime:
      - register(): Register a hook callback
      - fire(): Trigger all callbacks for a hook type
      - fire_before_step(): Pre-step interception
      - fire_after_step(): Post-step interception
      - fire_on_error(): Error interception
      - fire_before_tool(): Pre-tool interception (with tool_name filter)
      - fire_after_tool(): Post-tool interception (with tool_name filter)

    Usage:
        hooks = LifecycleHookManager()
        hooks.register("before_step", lambda: print("Starting step"))
        hooks.register("after_step", lambda result: print(f"Step done: {result}"))
        hooks.register("before_tool", lambda tool: print(f"Calling {tool}"), tool_name="shell_exec")
        hooks.fire_before_step()
    """

    VALID_HOOK_TYPES = {
        "before_step", "after_step", "on_error",
        "before_tool", "after_tool",
    }

    def __init__(self) -> None:
        self._hooks: Dict[str, List[HookCallback]] = {}
        self._lock = threading.Lock()
        self._fire_count: Dict[str, int] = {}
        self._strict_mode = False  # If True, hook errors raise exceptions

        # Initialize hook type lists
        for hook_type in self.VALID_HOOK_TYPES:
            self._hooks[hook_type] = []
            self._fire_count[hook_type] = 0

    def set_strict_mode(self, strict: bool) -> None:
        """Set strict mode — hook errors raise exceptions instead of being logged."""
        self._strict_mode = strict

    # ─── Registration ───

    def register(
        self,
        hook_type: str,
        callback: Callable,
        tool_name: Optional[str] = None,
        priority: int = 0,
    ) -> HookCallback:
        """
        Register a hook callback.

        Args:
            hook_type: One of: before_step, after_step, on_error, before_tool, after_tool
            callback: The callback function to execute
            tool_name: For before_tool/after_tool: filter by specific tool name
            priority: Execution priority (lower = earlier)

        Returns:
            The registered HookCallback
        """
        import time

        if hook_type not in self.VALID_HOOK_TYPES:
            raise ValueError(f"Invalid hook type: {hook_type}. "
                             f"Must be one of: {self.VALID_HOOK_TYPES}")

        hook_cb = HookCallback(
            hook_type=hook_type,
            callback=callback,
            tool_name=tool_name,
            priority=priority,
            registered_at=time.time(),
        )

        with self._lock:
            self._hooks[hook_type].append(hook_cb)
            # Sort by priority (lower = earlier)
            self._hooks[hook_type].sort(key=lambda h: h.priority)

        logger.info(f"Registered hook: {hook_type}, "
                     f"callback={callback.__name__}, "
                     f"tool_name={tool_name}, priority={priority}")
        return hook_cb

    def unregister(self, hook_type: str, callback: Callable) -> bool:
        """Unregister a specific callback from a hook type."""
        with self._lock:
            hooks = self._hooks.get(hook_type, [])
            for i, hook_cb in enumerate(hooks):
                if hook_cb.callback == callback:
                    hooks.pop(i)
                    return True
            return False

    def unregister_all(self, hook_type: Optional[str] = None) -> int:
        """
        Unregister all callbacks for a hook type (or all types).

        Returns:
            Number of callbacks removed
        """
        count = 0
        with self._lock:
            if hook_type:
                count = len(self._hooks.get(hook_type, []))
                self._hooks[hook_type] = []
            else:
                for ht in self.VALID_HOOK_TYPES:
                    count += len(self._hooks.get(ht, []))
                    self._hooks[ht] = []
        return count

    # ─── Firing ───

    def fire(self, hook_type: str, *args: Any, **kwargs: Any) -> HookExecutionResult:
        """
        Fire all callbacks for a hook type.

        Args:
            hook_type: The hook type to fire
            *args, **kwargs: Arguments to pass to callbacks

        Returns:
            HookExecutionResult with execution details
        """
        result = HookExecutionResult(hook_type=hook_type)

        with self._lock:
            callbacks = list(self._hooks.get(hook_type, []))
            self._fire_count[hook_type] = self._fire_count.get(hook_type, 0) + 1

        # For before_tool/after_tool, filter by tool_name if provided
        if hook_type in ("before_tool", "after_tool"):
            tool_name = kwargs.get("tool_name") or (args[0] if args else None)
            if tool_name:
                callbacks = [
                    cb for cb in callbacks
                    if cb.tool_name is None or cb.tool_name == tool_name
                ]

        for cb in callbacks:
            try:
                ret = cb.callback(*args, **kwargs)
                result.callbacks_executed += 1

                # Check if callback returned a block signal
                # before_* hooks can return False/str to block the action
                if hook_type in ("before_step", "before_tool"):
                    if ret is False:
                        result.blocked = True
                        result.block_reason = f"Blocked by {cb.callback.__name__}"
                        break
                    elif isinstance(ret, str) and ret.startswith("BLOCK:"):
                        result.blocked = True
                        result.block_reason = ret[6:]
                        break

            except Exception as e:
                error_msg = f"Hook callback {cb.callback.__name__} error: {e}"
                result.errors.append(error_msg)

                if self._strict_mode:
                    raise
                else:
                    logger.warning(error_msg)

        return result

    # ─── Convenience Methods ───

    def fire_before_step(self) -> HookExecutionResult:
        """Fire before_step hooks."""
        return self.fire("before_step")

    def fire_after_step(self, step_result: Any = None) -> HookExecutionResult:
        """Fire after_step hooks with step result."""
        return self.fire("after_step", step_result)

    def fire_on_error(self, error: Any = None) -> HookExecutionResult:
        """Fire on_error hooks with error info."""
        return self.fire("on_error", error)

    def fire_before_tool(self, tool_name: str, arguments: Dict = None) -> HookExecutionResult:
        """Fire before_tool hooks for a specific tool."""
        return self.fire("before_tool", tool_name=tool_name, arguments=arguments or {})

    def fire_after_tool(self, tool_name: str, result: Any = None) -> HookExecutionResult:
        """Fire after_tool hooks for a specific tool."""
        return self.fire("after_tool", tool_name=tool_name, result=result)

    # ─── Query ───

    def get_hooks(self, hook_type: Optional[str] = None) -> List[HookCallback]:
        """Get registered hooks (all or by type)."""
        with self._lock:
            if hook_type:
                return list(self._hooks.get(hook_type, []))
            return [cb for cbs in self._hooks.values() for cb in cbs]

    def get_hook_count(self, hook_type: Optional[str] = None) -> int:
        """Get number of registered hooks."""
        with self._lock:
            if hook_type:
                return len(self._hooks.get(hook_type, []))
            return sum(len(cbs) for cbs in self._hooks.values())

    def get_fire_count(self, hook_type: str) -> int:
        """Get number of times a hook type has been fired."""
        return self._fire_count.get(hook_type, 0)

    # ─── Statistics ───

    def get_stats(self) -> Dict:
        """Get comprehensive hook statistics."""
        with self._lock:
            hook_counts = {ht: len(cbs) for ht, cbs in self._hooks.items()}

        return {
            "hook_counts": hook_counts,
            "total_hooks": sum(hook_counts.values()),
            "fire_counts": dict(self._fire_count),
            "strict_mode": self._strict_mode,
        }

    def clear(self) -> None:
        """Clear all hooks (for testing)."""
        with self._lock:
            for ht in self.VALID_HOOK_TYPES:
                self._hooks[ht] = []
                self._fire_count[ht] = 0