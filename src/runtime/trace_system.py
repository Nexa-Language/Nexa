"""
Nexa v2.0 TraceSystem — 思维轨迹追踪

TraceSystem 实现 Agent 执行过程的完整记录，负责：
  - record_step: ReAct step 轨迹记录
  - record_reflection: 反思注入记录
  - record_error: 错误记录
  - export_decision_tree: 导出为决策树 JSON
  - export_timeline: 导出为时间线 JSON

Design Rationale:
  - 完整记录: 每个 ReAct step 的 Reason/Act/Observe/Reflect 四阶段
  - 决策树: 将轨迹组织为树结构，支持 Tree-of-Thoughts 可视化
  - 时间线: 按时间排序的扁平记录，支持回放
  - 可观测性: 所有 Agent 行为可追溯、可审计

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.4
"""

from __future__ import annotations

import json
import time
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("nexa.trace_system")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TraceStep:
    """A single ReAct step in the trace."""
    step_id: str = ""
    step_number: int = 0
    parent_step_id: Optional[str] = None  # For fork branches
    branch_name: Optional[str] = None     # Fork branch name

    # ReAct phases
    reasoning: str = ""       # Why the agent decided this action
    action: str = ""          # What the agent did
    observation: str = ""     # What the agent observed
    reflection: Optional[str] = None  # Self-reflection on the step

    # Metadata
    tool_calls: List[Dict] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0     # Step execution duration

    # Context snapshot reference
    snapshot_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "step_number": self.step_number,
            "parent_step_id": self.parent_step_id,
            "branch_name": self.branch_name,
            "reasoning": self.reasoning,
            "action": self.action,
            "observation": self.observation,
            "reflection": self.reflection,
            "tool_calls": self.tool_calls,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "snapshot_id": self.snapshot_id,
        }


@dataclass
class TraceReflection:
    """A reflection injection in the trace."""
    reflection_id: str = ""
    step_id: str = ""         # The step this reflection is associated with
    content: str = ""         # Reflection content
    source: str = ""          # "agent" | "catch_correction" | "verify" | "manual"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "reflection_id": self.reflection_id,
            "step_id": self.step_id,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp,
        }


@dataclass
class TraceError:
    """An error event in the trace."""
    error_id: str = ""
    step_id: str = ""         # The step where the error occurred
    error_type: str = ""      # "tool_error" | "validation_error" | "runtime_error"
    error_message: str = ""
    correction_applied: bool = False
    correction_result: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "error_id": self.error_id,
            "step_id": self.step_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "correction_applied": self.correction_applied,
            "correction_result": self.correction_result,
            "timestamp": self.timestamp,
        }


@dataclass
class DecisionTreeNode:
    """A node in the decision tree export."""
    node_id: str = ""
    step_number: int = 0
    action: str = ""
    reasoning: str = ""
    observation: str = ""
    success: bool = True
    children: List[str] = field(default_factory=list)  # Child node IDs
    parent_id: Optional[str] = None
    branch_name: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "step_number": self.step_number,
            "action": self.action,
            "reasoning": self.reasoning,
            "observation": self.observation,
            "success": self.success,
            "children": self.children,
            "parent_id": self.parent_id,
            "branch_name": self.branch_name,
        }


# ═══════════════════════════════════════════════════════════════════════
#  TraceSystem — Trace Recording and Export
# ═══════════════════════════════════════════════════════════════════════

class TraceSystem:
    """
    Trace recording system for Agent execution.

    Implements complete trace recording:
      - record_step(): Record a ReAct step
      - record_reflection(): Record a reflection injection
      - record_error(): Record an error event
      - export_decision_tree(): Export as decision tree JSON
      - export_timeline(): Export as timeline JSON

    Usage:
        trace = TraceSystem()
        trace.record_step(reasoning="Need to search", action="search('query')",
                          observation="Found 3 results", success=True)
        trace.export_decision_tree("decision_tree.json")
    """

    def __init__(self) -> None:
        self._steps: Dict[str, TraceStep] = {}
        self._reflections: Dict[str, TraceReflection] = {}
        self._errors: Dict[str, TraceError] = {}
        self._step_order: List[str] = []  # Ordered list of step IDs
        self._lock = threading.Lock()
        self._step_counter = 0
        self._reflection_counter = 0
        self._error_counter = 0
        self._start_time = time.time()

    # ─── Recording ───

    def record_step(
        self,
        reasoning: str = "",
        action: str = "",
        observation: str = "",
        reflection: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        success: bool = True,
        error: Optional[str] = None,
        duration: float = 0.0,
        parent_step_id: Optional[str] = None,
        branch_name: Optional[str] = None,
        snapshot_id: Optional[str] = None,
    ) -> TraceStep:
        """
        Record a ReAct step in the trace.

        Args:
            reasoning: Why the agent decided this action
            action: What the agent did
            observation: What the agent observed
            reflection: Self-reflection on the step
            tool_calls: Tool calls made during this step
            success: Whether the step succeeded
            error: Error message if step failed
            duration: Step execution duration
            parent_step_id: Parent step (for fork branches)
            branch_name: Fork branch name
            snapshot_id: State snapshot reference

        Returns:
            The recorded TraceStep
        """
        self._step_counter += 1
        step_id = f"step_{self._step_counter}"

        step = TraceStep(
            step_id=step_id,
            step_number=self._step_counter,
            parent_step_id=parent_step_id,
            branch_name=branch_name,
            reasoning=reasoning,
            action=action,
            observation=observation,
            reflection=reflection,
            tool_calls=tool_calls or [],
            success=success,
            error=error,
            timestamp=time.time(),
            duration=duration,
            snapshot_id=snapshot_id,
        )

        with self._lock:
            self._steps[step_id] = step
            self._step_order.append(step_id)

        logger.info(f"Trace step recorded: {step_id}, action={action[:50]}")
        return step

    def record_reflection(
        self,
        step_id: str,
        content: str,
        source: str = "agent",
    ) -> TraceReflection:
        """
        Record a reflection injection in the trace.

        Args:
            step_id: The step this reflection is associated with
            content: Reflection content
            source: Source of the reflection

        Returns:
            The recorded TraceReflection
        """
        self._reflection_counter += 1
        reflection_id = f"refl_{self._reflection_counter}"

        reflection = TraceReflection(
            reflection_id=reflection_id,
            step_id=step_id,
            content=content,
            source=source,
        )

        with self._lock:
            self._reflections[reflection_id] = reflection

        logger.info(f"Trace reflection recorded: {reflection_id}, source={source}")
        return reflection

    def record_error(
        self,
        step_id: str,
        error_type: str,
        error_message: str,
        correction_applied: bool = False,
        correction_result: Optional[str] = None,
    ) -> TraceError:
        """
        Record an error event in the trace.

        Args:
            step_id: The step where the error occurred
            error_type: Type of error
            error_message: Error message
            correction_applied: Whether a correction was applied
            correction_result: Result of the correction

        Returns:
            The recorded TraceError
        """
        self._error_counter += 1
        error_id = f"err_{self._error_counter}"

        error = TraceError(
            error_id=error_id,
            step_id=step_id,
            error_type=error_type,
            error_message=error_message,
            correction_applied=correction_applied,
            correction_result=correction_result,
        )

        with self._lock:
            self._errors[error_id] = error

        logger.info(f"Trace error recorded: {error_id}, type={error_type}")
        return error

    # ─── Query ───

    def get_step(self, step_id: str) -> Optional[TraceStep]:
        """Get a step by ID."""
        with self._lock:
            return self._steps.get(step_id)

    def get_steps(self) -> List[TraceStep]:
        """Get all steps in order."""
        with self._lock:
            return [self._steps[sid] for sid in self._step_order if sid in self._steps]

    def get_step_count(self) -> int:
        """Get total number of recorded steps."""
        return len(self._steps)

    def get_reflections(self) -> List[TraceReflection]:
        """Get all reflections."""
        with self._lock:
            return list(self._reflections.values())

    def get_errors(self) -> List[TraceError]:
        """Get all errors."""
        with self._lock:
            return list(self._errors.values())

    def get_reflections_for_step(self, step_id: str) -> List[TraceReflection]:
        """Get reflections associated with a specific step."""
        with self._lock:
            return [r for r in self._reflections.values() if r.step_id == step_id]

    def get_errors_for_step(self, step_id: str) -> List[TraceError]:
        """Get errors associated with a specific step."""
        with self._lock:
            return [e for e in self._errors.values() if e.step_id == step_id]

    # ─── Export ───

    def export_decision_tree(self, filepath: Optional[str] = None) -> Dict:
        """
        Export trace as a decision tree.

        The decision tree organizes steps into a tree structure,
        where fork branches become child nodes.

        Args:
            filepath: Optional file path to write JSON output

        Returns:
            Decision tree as a dict
        """
        with self._lock:
            # Build tree nodes
            nodes: Dict[str, DecisionTreeNode] = {}
            root_nodes: List[str] = []

            for step_id in self._step_order:
                step = self._steps.get(step_id)
                if not step:
                    continue

                node = DecisionTreeNode(
                    node_id=step.step_id,
                    step_number=step.step_number,
                    action=step.action,
                    reasoning=step.reasoning,
                    observation=step.observation,
                    success=step.success,
                    parent_id=step.parent_step_id,
                    branch_name=step.branch_name,
                )

                nodes[step.step_id] = node

                # Build parent-child relationships
                if step.parent_step_id and step.parent_step_id in nodes:
                    parent = nodes[step.parent_step_id]
                    parent.children.append(step.step_id)
                else:
                    root_nodes.append(step.step_id)

        tree = {
            "type": "decision_tree",
            "root_nodes": root_nodes,
            "nodes": {nid: node.to_dict() for nid, node in nodes.items()},
            "metadata": {
                "total_steps": len(nodes),
                "total_reflections": len(self._reflections),
                "total_errors": len(self._errors),
                "start_time": self._start_time,
                "export_time": time.time(),
            },
        }

        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(tree, f, indent=2, ensure_ascii=False)
            logger.info(f"Decision tree exported to: {filepath}")

        return tree

    def export_timeline(self, filepath: Optional[str] = None) -> Dict:
        """
        Export trace as a timeline.

        The timeline is a flat, time-ordered list of all events
        (steps, reflections, errors).

        Args:
            filepath: Optional file path to write JSON output

        Returns:
            Timeline as a dict
        """
        with self._lock:
            # Collect all events with timestamps
            events = []

            for step_id in self._step_order:
                step = self._steps.get(step_id)
                if step:
                    events.append({
                        "type": "step",
                        "timestamp": step.timestamp,
                        "data": step.to_dict(),
                    })

            for reflection in self._reflections.values():
                events.append({
                    "type": "reflection",
                    "timestamp": reflection.timestamp,
                    "data": reflection.to_dict(),
                })

            for error in self._errors.values():
                events.append({
                    "type": "error",
                    "timestamp": error.timestamp,
                    "data": error.to_dict(),
                })

            # Sort by timestamp
            events.sort(key=lambda e: e["timestamp"])

        timeline = {
            "type": "timeline",
            "events": events,
            "metadata": {
                "total_events": len(events),
                "total_steps": len(self._steps),
                "total_reflections": len(self._reflections),
                "total_errors": len(self._errors),
                "start_time": self._start_time,
                "export_time": time.time(),
                "duration": time.time() - self._start_time,
            },
        }

        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(timeline, f, indent=2, ensure_ascii=False)
            logger.info(f"Timeline exported to: {filepath}")

        return timeline

    # ─── Statistics ───

    def get_stats(self) -> Dict:
        """Get trace statistics."""
        with self._lock:
            successful = sum(1 for s in self._steps.values() if s.success)
            failed = sum(1 for s in self._steps.values() if not s.success)

        return {
            "total_steps": len(self._steps),
            "successful_steps": successful,
            "failed_steps": failed,
            "total_reflections": len(self._reflections),
            "total_errors": len(self._errors),
            "duration": time.time() - self._start_time,
        }

    def clear(self) -> None:
        """Clear all trace data (for testing)."""
        with self._lock:
            self._steps = {}
            self._reflections = {}
            self._errors = {}
            self._step_order = []
            self._step_counter = 0
            self._reflection_counter = 0
            self._error_counter = 0
            self._start_time = time.time()