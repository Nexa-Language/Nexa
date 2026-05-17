"""
Nexa v2.0 M3 Tests — StateStore + TraceSystem

Tests cover:
  - StateStore: snapshot/restore, fork/merge, state access
  - TraceSystem: record_step, record_reflection, record_error, export
  - Integration: snapshot + trace end-to-end

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.4
"""

import json
import os
import tempfile
import pytest

from src.runtime.state_store import (
    StateStore, SnapshotEntry, ForkBranch, MergeResult,
)
from src.runtime.trace_system import (
    TraceSystem, TraceStep, TraceReflection, TraceError, DecisionTreeNode,
)


# ═══════════════════════════════════════════════════════════════════════
#  StateStore Tests
# ═══════════════════════════════════════════════════════════════════════

class TestStateStore:
    """StateStore snapshot/restore/fork/merge tests."""

    def test_set_get_state(self):
        """Basic state set/get."""
        store = StateStore()
        store.set_state("counter", 42)
        assert store.get_state("counter") == 42

    def test_get_state_default(self):
        """Get state with default value."""
        store = StateStore()
        assert store.get_state("nonexistent", 0) == 0

    def test_get_all_state(self):
        """Get all state as dict."""
        store = StateStore()
        store.set_state("a", 1)
        store.set_state("b", 2)
        all_state = store.get_all_state()
        assert all_state == {"a": 1, "b": 2}

    def test_delete_state(self):
        """Delete a state key."""
        store = StateStore()
        store.set_state("key", "value")
        assert store.delete_state("key")
        assert store.get_state("key") is None

    def test_snapshot_and_restore(self):
        """Snapshot captures state, restore reverts to it."""
        store = StateStore()
        store.set_state("counter", 0)

        snap_id = store.snapshot(label="before_loop")
        store.set_state("counter", 10)
        assert store.get_state("counter") == 10

        restored = store.restore(snap_id)
        assert restored
        assert store.get_state("counter") == 0

    def test_restore_nonexistent(self):
        """Restore nonexistent snapshot returns False."""
        store = StateStore()
        assert not store.restore("nonexistent")

    def test_multiple_snapshots(self):
        """Multiple snapshots can be created and restored independently."""
        store = StateStore()
        store.set_state("x", 0)

        snap1 = store.snapshot(label="snap1")
        store.set_state("x", 1)

        snap2 = store.snapshot(label="snap2")
        store.set_state("x", 2)

        store.restore(snap1)
        assert store.get_state("x") == 0

        store.restore(snap2)
        assert store.get_state("x") == 1

    def test_snapshot_label(self):
        """Snapshot label is stored."""
        store = StateStore()
        snap_id = store.snapshot(label="my_label")
        entry = store.get_snapshot(snap_id)
        assert entry.label == "my_label"

    def test_list_snapshots(self):
        """List all snapshots."""
        store = StateStore()
        store.snapshot(label="a")
        store.snapshot(label="b")
        snapshots = store.list_snapshots()
        assert len(snapshots) == 2

    def test_delete_snapshot(self):
        """Delete a snapshot."""
        store = StateStore()
        snap_id = store.snapshot()
        assert store.delete_snapshot(snap_id)
        assert store.get_snapshot(snap_id) is None

    def test_fork_creates_branches(self):
        """Fork creates multiple branches from current state."""
        store = StateStore()
        store.set_state("base", "value")

        branches = store.fork(["branch_a", "branch_b"])
        assert "branch_a" in branches
        assert "branch_b" in branches
        assert len(branches) == 2

    def test_fork_branches_have_independent_state(self):
        """Fork branches have independent state."""
        store = StateStore()
        store.set_state("shared", 0)

        branches = store.fork(["a", "b"])
        store.set_branch_state(branches["a"], "shared", 1)
        store.set_branch_state(branches["b"], "shared", 2)

        assert store.get_branch_state(branches["a"])["shared"] == 1
        assert store.get_branch_state(branches["b"])["shared"] == 2

    def test_complete_branch(self):
        """Complete a branch with a result."""
        store = StateStore()
        branches = store.fork(["test"])
        bid = branches["test"]

        assert store.complete_branch(bid, "result_value")
        branch = store.get_branch(bid)
        assert branch.status == "completed"
        assert branch.result == "result_value"

    def test_fail_branch(self):
        """Fail a branch."""
        store = StateStore()
        branches = store.fork(["test"])
        bid = branches["test"]

        assert store.fail_branch(bid, "error message")
        branch = store.get_branch(bid)
        assert branch.status == "failed"

    def test_merge_best_of(self):
        """Best-of merge picks highest-scoring branch."""
        store = StateStore()
        store.set_state("base", 0)

        branches = store.fork(["low", "high"])
        store.complete_branch(branches["low"], 10)
        store.complete_branch(branches["high"], 100)

        result = store.merge(strategy="best_of")
        assert result.merge_strategy == "best_of"
        assert result.winning_branch == branches["high"]

    def test_merge_vote(self):
        """Vote merge picks most common result."""
        store = StateStore()
        branches = store.fork(["a", "b", "c"])
        store.complete_branch(branches["a"], "yes")
        store.complete_branch(branches["b"], "yes")
        store.complete_branch(branches["c"], "no")

        result = store.merge(strategy="vote")
        assert result.merge_strategy == "vote"
        assert result.winning_branch in [branches["a"], branches["b"]]

    def test_merge_weighted_average(self):
        """Weighted average merge averages numeric results."""
        store = StateStore()
        branches = store.fork(["a", "b"])
        store.set_branch_state(branches["a"], "score", 10)
        store.set_branch_state(branches["b"], "score", 20)
        store.complete_branch(branches["a"], 10)
        store.complete_branch(branches["b"], 20)

        result = store.merge(strategy="weighted_average")
        assert result.merge_strategy == "weighted_average"

    def test_merge_no_completed_branches(self):
        """Merge with no completed branches returns empty result."""
        store = StateStore()
        store.fork(["a", "b"])
        result = store.merge()
        assert result.winning_branch is None

    def test_stats(self):
        """State store stats are accurate."""
        store = StateStore()
        store.set_state("key", "value")
        store.snapshot()
        store.fork(["a", "b"])

        stats = store.get_stats()
        assert "key" in stats["current_state_keys"]
        assert stats["snapshot_count"] == 2  # 1 explicit + 1 from fork
        assert stats["fork_count"] == 2

    def test_clear(self):
        """Clear removes all state."""
        store = StateStore()
        store.set_state("key", "value")
        store.snapshot()
        store.fork(["a"])
        store.clear()

        stats = store.get_stats()
        assert stats["snapshot_count"] == 0
        assert stats["fork_count"] == 0
        assert store.get_state("key") is None


# ═══════════════════════════════════════════════════════════════════════
#  TraceSystem Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTraceSystem:
    """TraceSystem recording and export tests."""

    def test_record_step(self):
        """Record a ReAct step."""
        trace = TraceSystem()
        step = trace.record_step(
            reasoning="Need to search",
            action="search('query')",
            observation="Found 3 results",
            success=True,
        )
        assert step.step_id.startswith("step_")
        assert step.reasoning == "Need to search"
        assert step.success is True

    def test_record_step_with_reflection(self):
        """Record a step with self-reflection."""
        trace = TraceSystem()
        step = trace.record_step(
            reasoning="Try approach A",
            action="execute_A()",
            observation="Failed",
            reflection="Approach A didn't work, try B",
            success=False,
        )
        assert step.reflection == "Approach A didn't work, try B"

    def test_record_step_with_tool_calls(self):
        """Record a step with tool calls."""
        trace = TraceSystem()
        step = trace.record_step(
            action="call_tools",
            observation="done",
            tool_calls=[{"tool": "search", "args": {"q": "test"}}],
        )
        assert len(step.tool_calls) == 1
        assert step.tool_calls[0]["tool"] == "search"

    def test_record_step_with_branch(self):
        """Record a step in a fork branch."""
        trace = TraceSystem()
        step = trace.record_step(
            action="branch_action",
            observation="branch_result",
            parent_step_id="step_1",
            branch_name="explore_a",
        )
        assert step.parent_step_id == "step_1"
        assert step.branch_name == "explore_a"

    def test_record_reflection(self):
        """Record a reflection injection."""
        trace = TraceSystem()
        step = trace.record_step(action="test", observation="ok")
        refl = trace.record_reflection(
            step_id=step.step_id,
            content="Consider alternative approach",
            source="catch_correction",
        )
        assert refl.reflection_id.startswith("refl_")
        assert refl.source == "catch_correction"

    def test_record_error(self):
        """Record an error event."""
        trace = TraceSystem()
        step = trace.record_step(action="test", observation="ok")
        error = trace.record_error(
            step_id=step.step_id,
            error_type="tool_error",
            error_message="Shell execution failed",
            correction_applied=True,
            correction_result="Retried with different params",
        )
        assert error.error_id.startswith("err_")
        assert error.correction_applied is True

    def test_get_steps_in_order(self):
        """Steps are returned in insertion order."""
        trace = TraceSystem()
        trace.record_step(action="step1", observation="ok")
        trace.record_step(action="step2", observation="ok")
        trace.record_step(action="step3", observation="ok")

        steps = trace.get_steps()
        assert len(steps) == 3
        assert steps[0].action == "step1"
        assert steps[2].action == "step3"

    def test_get_reflections_for_step(self):
        """Get reflections associated with a step."""
        trace = TraceSystem()
        step = trace.record_step(action="test", observation="ok")
        trace.record_reflection(step.step_id, "reflection 1")
        trace.record_reflection(step.step_id, "reflection 2")

        reflections = trace.get_reflections_for_step(step.step_id)
        assert len(reflections) == 2

    def test_get_errors_for_step(self):
        """Get errors associated with a step."""
        trace = TraceSystem()
        step = trace.record_step(action="test", observation="ok")
        trace.record_error(step.step_id, "tool_error", "error 1")
        trace.record_error(step.step_id, "validation_error", "error 2")

        errors = trace.get_errors_for_step(step.step_id)
        assert len(errors) == 2

    def test_export_decision_tree(self):
        """Export decision tree to dict."""
        trace = TraceSystem()
        trace.record_step(action="root", observation="start")
        trace.record_step(
            action="branch_a", observation="result_a",
            parent_step_id="step_1", branch_name="a",
        )
        trace.record_step(
            action="branch_b", observation="result_b",
            parent_step_id="step_1", branch_name="b",
        )

        tree = trace.export_decision_tree()
        assert tree["type"] == "decision_tree"
        assert "root_nodes" in tree
        assert "nodes" in tree
        assert tree["metadata"]["total_steps"] == 3

    def test_export_decision_tree_to_file(self):
        """Export decision tree to JSON file."""
        trace = TraceSystem()
        trace.record_step(action="test", observation="ok")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            trace.export_decision_tree(filepath)
            with open(filepath, 'r') as f:
                data = json.load(f)
            assert data["type"] == "decision_tree"
        finally:
            os.unlink(filepath)

    def test_export_timeline(self):
        """Export timeline to dict."""
        trace = TraceSystem()
        step = trace.record_step(action="test", observation="ok")
        trace.record_reflection(step.step_id, "reflection")
        trace.record_error(step.step_id, "tool_error", "error")

        timeline = trace.export_timeline()
        assert timeline["type"] == "timeline"
        assert len(timeline["events"]) == 3  # step + reflection + error

    def test_export_timeline_to_file(self):
        """Export timeline to JSON file."""
        trace = TraceSystem()
        trace.record_step(action="test", observation="ok")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            trace.export_timeline(filepath)
            with open(filepath, 'r') as f:
                data = json.load(f)
            assert data["type"] == "timeline"
        finally:
            os.unlink(filepath)

    def test_stats(self):
        """Trace stats are accurate."""
        trace = TraceSystem()
        trace.record_step(action="ok", observation="ok", success=True)
        trace.record_step(action="fail", observation="error", success=False)

        stats = trace.get_stats()
        assert stats["total_steps"] == 2
        assert stats["successful_steps"] == 1
        assert stats["failed_steps"] == 1

    def test_clear(self):
        """Clear removes all trace data."""
        trace = TraceSystem()
        trace.record_step(action="test", observation="ok")
        trace.clear()
        assert trace.get_step_count() == 0


# ═══════════════════════════════════════════════════════════════════════
#  Data Structure Tests
# ═══════════════════════════════════════════════════════════════════════

class TestDataStructures:
    """Data structure serialization tests."""

    def test_snapshot_entry_to_dict(self):
        entry = SnapshotEntry(snapshot_id="snap_1", label="test")
        d = entry.to_dict()
        assert d["snapshot_id"] == "snap_1"
        assert d["label"] == "test"

    def test_fork_branch_to_dict(self):
        branch = ForkBranch(branch_id="fork_1", branch_name="test", snapshot_id="snap_1")
        d = branch.to_dict()
        assert d["branch_id"] == "fork_1"
        assert d["status"] == "active"

    def test_merge_result_to_dict(self):
        result = MergeResult(merge_strategy="best_of", winning_branch="fork_1")
        d = result.to_dict()
        assert d["merge_strategy"] == "best_of"
        assert d["winning_branch"] == "fork_1"

    def test_trace_step_to_dict(self):
        step = TraceStep(step_id="step_1", step_number=1, action="search", observation="found")
        d = step.to_dict()
        assert d["step_id"] == "step_1"
        assert d["action"] == "search"

    def test_trace_reflection_to_dict(self):
        refl = TraceReflection(reflection_id="refl_1", step_id="step_1", content="test", source="agent")
        d = refl.to_dict()
        assert d["reflection_id"] == "refl_1"
        assert d["source"] == "agent"

    def test_trace_error_to_dict(self):
        error = TraceError(error_id="err_1", step_id="step_1", error_type="tool_error", error_message="fail")
        d = error.to_dict()
        assert d["error_id"] == "err_1"
        assert d["error_type"] == "tool_error"

    def test_decision_tree_node_to_dict(self):
        node = DecisionTreeNode(node_id="step_1", step_number=1, action="test", reasoning="why", observation="result")
        d = node.to_dict()
        assert d["node_id"] == "step_1"
        assert d["children"] == []


# ═══════════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end: StateStore + TraceSystem."""

    def test_snapshot_with_trace(self):
        """Snapshot creation is recorded in trace."""
        store = StateStore()
        trace = TraceSystem()

        store.set_state("counter", 0)
        snap_id = store.snapshot(label="before_loop")

        trace.record_step(
            action="snapshot",
            observation=f"Created snapshot {snap_id}",
            snapshot_id=snap_id,
        )

        store.set_state("counter", 10)
        store.restore(snap_id)

        trace.record_step(
            action="restore",
            observation=f"Restored to snapshot {snap_id}",
            snapshot_id=snap_id,
        )

        steps = trace.get_steps()
        assert len(steps) == 2
        assert steps[0].snapshot_id == snap_id
        assert steps[1].snapshot_id == snap_id

    def test_fork_with_trace(self):
        """Fork branches are recorded in trace."""
        store = StateStore()
        trace = TraceSystem()

        root_step = trace.record_step(action="root", observation="start")
        branches = store.fork(["a", "b"])

        for name, bid in branches.items():
            trace.record_step(
                action=f"branch_{name}",
                observation=f"Exploring {name}",
                parent_step_id=root_step.step_id,
                branch_name=name,
            )

        tree = trace.export_decision_tree()
        assert tree["metadata"]["total_steps"] == 3

    def test_full_workflow(self):
        """Full workflow: snapshot → fork → merge → trace."""
        store = StateStore()
        trace = TraceSystem()

        # Initial state
        store.set_state("task", "solve_problem")
        trace.record_step(action="init", observation="Task initialized")

        # Snapshot
        snap_id = store.snapshot(label="before_exploration")
        trace.record_step(action="snapshot", observation=f"Snapshot: {snap_id}")

        # Fork exploration
        branches = store.fork(["approach_a", "approach_b"])
        for name, bid in branches.items():
            store.set_branch_state(bid, "score", 10 if name == "approach_a" else 20)
            store.complete_branch(bid, 10 if name == "approach_a" else 20)
            trace.record_step(
                action=f"explore_{name}",
                observation=f"Score: {10 if name == 'approach_a' else 20}",
                branch_name=name,
            )

        # Merge
        merge_result = store.merge(strategy="best_of")
        trace.record_step(
            action="merge",
            observation=f"Merged: winner={merge_result.winning_branch}",
        )

        # Verify
        assert merge_result.winning_branch is not None
        assert trace.get_step_count() == 5
        assert store.get_stats()["fork_count"] == 2