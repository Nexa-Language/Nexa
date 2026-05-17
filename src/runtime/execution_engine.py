"""
Nexa v2.0 ExecutionEngine — ReAct 循环引擎

ExecutionEngine 实现 Agent 的自主 ReAct (Reason→Act→Observe→Reflect) 循环，
是 Harness E-dimension 的运行时核心。

Design Rationale:
  - 每步执行: Reason → Act → Observe → Reflect 四阶段
  - 退出条件: exit_when 语义评估 + max_steps 硬限制 + timeout 超时
  - 错误自纠: try_agent/catch_correction 在 Tool 错误时触发反思注入
  - 可观测性: 每步生成 StepResult，完整 trace 可回放

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.2
"""

from __future__ import annotations

import time
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from .harness_kernel import (
    AutoLoopConfig, AutoLoopResult, StepResult,
    HarnessRuntimeMode, HarnessKernel,
)

logger = logging.getLogger("nexa.execution_engine")


# ═══════════════════════════════════════════════════════════════════════
#  ExecutionEngine — ReAct Loop Engine
# ═══════════════════════════════════════════════════════════════════════

class ExecutionEngine:
    """
    ReAct loop engine for autonomous Agent execution.

    Implements the core E-dimension runtime:
      - run_loop(): Main ReAct cycle with exit conditions
      - _execute_step(): Single Reason→Act→Observe→Reflect step
      - _check_exit_condition(): Semantic exit condition evaluation
      - _generate_correction_reflection(): Error self-correction reflection

    The engine is designed to be used via HarnessKernel.run_autoloop(),
    which delegates to this engine when available.
    """

    def __init__(self, kernel: HarnessKernel) -> None:
        self.kernel = kernel
        self._step_count = 0
        self._correction_count = 0

    def run_loop(self, config: AutoLoopConfig, step_fn: Callable[..., StepResult]) -> AutoLoopResult:
        """
        Execute a complete autoloop ReAct cycle.

        Args:
            config: AutoLoopConfig with max_steps, exit_when, timeout
            step_fn: Callable that executes one step and returns StepResult

        Returns:
            AutoLoopResult with all step results and exit metadata
        """
        result = AutoLoopResult()
        start_time = time.time()

        logger.info(f"autoloop starting: max_steps={config.max_steps}, "
                     f"exit_when={config.exit_when}, timeout={config.timeout}")

        for i in range(config.max_steps):
            self._step_count += 1

            # ─── Timeout check ───
            elapsed = time.time() - start_time
            if config.timeout and elapsed > config.timeout:
                result.exit_reason = "timeout"
                result.total_steps = i
                result.total_time = elapsed
                logger.info(f"autoloop timeout after {i} steps ({elapsed:.1f}s)")
                return result

            # ─── Fire before_step hook ───
            self.kernel.fire_before_step()

            # ─── Execute step ───
            try:
                step = self._execute_step(i + 1, step_fn)
                result.steps.append(step)

                # ─── Fire after_step hook ───
                self.kernel.fire_after_step(step)

                # ─── Check exit condition ───
                if config.exit_when and self._check_exit_condition(config.exit_when, step):
                    result.exit_reason = "exit_when_met"
                    result.final_result = step.observation
                    result.total_steps = i + 1
                    result.total_time = time.time() - start_time
                    logger.info(f"autoloop exit_when met at step {i+1}")
                    return result

            except Exception as e:
                # ─── Fire on_error hook ───
                self.kernel.fire_on_error(e)

                if self.kernel.is_strict():
                    result.success = False
                    result.error = str(e)
                    result.exit_reason = "error"
                    result.total_steps = i
                    result.total_time = time.time() - start_time
                    logger.error(f"autoloop error at step {i+1}: {e}")
                    return result
                else:
                    # WARN mode: record error and continue
                    error_step = StepResult(
                        step_number=i + 1,
                        success=False,
                        error=str(e),
                    )
                    result.steps.append(error_step)
                    logger.warning(f"autoloop error at step {i+1} (continuing): {e}")

            # ─── Step delay ───
            if config.step_delay > 0:
                time.sleep(config.step_delay)

        # ─── Max steps reached ───
        result.exit_reason = "max_steps"
        result.total_steps = config.max_steps
        result.total_time = time.time() - start_time
        if result.steps:
            result.final_result = result.steps[-1].observation
        logger.info(f"autoloop max_steps reached: {config.max_steps}")
        return result

    def _execute_step(self, step_number: int, step_fn: Callable[..., StepResult]) -> StepResult:
        """
        Execute a single ReAct step.

        The step_fn should implement the full Reason→Act→Observe→Reflect cycle.
        This method wraps it with error handling and metadata.
        """
        step = step_fn()
        step.step_number = step_number
        if not step.timestamp:
            step.timestamp = time.time()
        return step

    def _check_exit_condition(self, condition: str, step: StepResult) -> bool:
        """
        Check if the semantic exit_when condition is satisfied.

        Current implementation: substring-based heuristic matching.
        M4 will upgrade this to LLM-based semantic evaluation.
        """
        if not condition or not step.observation:
            return False

        condition_lower = condition.lower().strip()
        observation_lower = step.observation.lower()

        # ─── Resolution signal matching ───
        resolution_signals = {
            "resolved": ["resolved", "complete", "done", "finished", "success"],
            "completed": ["completed", "complete", "done", "finished"],
            "done": ["done", "finished", "complete", "resolved"],
            "success": ["success", "successful", "resolved", "completed"],
            "finished": ["finished", "done", "complete", "resolved"],
        }

        # Check if condition is a known resolution signal
        if condition_lower in resolution_signals:
            return any(sig in observation_lower for sig in resolution_signals[condition_lower])

        # ─── Direct substring match ───
        return condition_lower in observation_lower

    def _generate_correction_reflection(self, error: str, context: Dict) -> str:
        """
        Generate a self-correction reflection for try_agent/catch_correction.

        This produces a reflection string that can be injected into the Agent's
        context to guide self-correction after a Tool error.

        Args:
            error: The error message from the failed tool call
            context: Additional context (tool name, parameters, etc.)

        Returns:
            A reflection string for the Agent to use in self-correction
        """
        self._correction_count += 1
        tool_name = context.get("tool_name", "unknown")
        reflection = (
            f"Error #{self._correction_count}: Tool '{tool_name}' failed with: {error}. "
            f"Consider: (1) retrying with different parameters, "
            f"(2) using an alternative tool, "
            f"(3) simplifying the request."
        )
        return reflection

    def run_try_agent(
        self,
        try_fn: Callable[..., Any],
        catch_fn: Optional[Callable[[str, str], Any]] = None,
        error_type: str = "ToolError",
    ) -> Tuple[Any, Optional[str]]:
        """
        Execute a try_agent/catch_correction cycle.

        Args:
            try_fn: The function to try (may raise an exception)
            catch_fn: The correction function (receives error_var and error_type)
            error_type: The expected error type to catch

        Returns:
            Tuple of (result, error_message). If no error, error_message is None.
        """
        try:
            result = try_fn()
            return (result, None)
        except Exception as e:
            error_msg = str(e)

            # ─── Fire on_error hook ───
            self.kernel.fire_on_error(e)

            if catch_fn:
                # Generate correction reflection
                reflection = self._generate_correction_reflection(
                    error_msg, {"error_type": error_type}
                )

                # Execute correction
                try:
                    correction_result = catch_fn(error_msg, error_type)
                    return (correction_result, error_msg)
                except Exception as correction_error:
                    if self.kernel.is_strict():
                        raise correction_error
                    return (None, f"{error_msg} | correction also failed: {correction_error}")
            else:
                if self.kernel.is_strict():
                    raise e
                return (None, error_msg)

    def get_step_count(self) -> int:
        """Get total steps executed by this engine."""
        return self._step_count

    def get_correction_count(self) -> int:
        """Get total corrections attempted by this engine."""
        return self._correction_count