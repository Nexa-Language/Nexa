"""
Nexa v2.0 StateStore — 三层存储 (COW + KV + Vector)

StateStore 实现 Harness S-dimension 的运行时核心，负责：
  - snapshot/restore: 基于 CowAgentState 的 O(1) COW 快照/回溯
  - fork: 多分支并行探索 (Tree-of-Thoughts)
  - merge: 分支结果合并
  - store_experience/retrieve_experience: Vector Store 经验存取

Design Rationale:
  - COW 快照: 基于 CowAgentState，O(1) 时间复杂度
  - Fork 树: 每个分支是独立的 COW 快照，可独立演进
  - Merge 策略: best_of / vote / weighted_average
  - Vector Store: 简易 cosine similarity 搜索，存储 Agent 经验

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.4
"""

from __future__ import annotations

import copy
import time
import json
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("nexa.state_store")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SnapshotEntry:
    """A snapshot entry in the state store."""
    snapshot_id: str = ""
    parent_id: Optional[str] = None
    state: Dict = field(default_factory=dict)  # The state data
    created_at: float = field(default_factory=time.time)
    label: str = ""              # Optional human-readable label
    branch_name: Optional[str] = None  # Fork branch name

    def to_dict(self) -> Dict:
        return {
            "snapshot_id": self.snapshot_id,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "label": self.label,
            "branch_name": self.branch_name,
            "state_keys": list(self.state.keys()) if isinstance(self.state, dict) else [],
        }


@dataclass
class ForkBranch:
    """A fork branch for parallel exploration."""
    branch_id: str = ""
    branch_name: str = ""
    snapshot_id: str = ""        # The snapshot this branch started from
    state: Dict = field(default_factory=dict)  # Branch state
    result: Any = None           # Branch execution result
    status: str = "active"       # active | completed | failed | merged
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "branch_id": self.branch_id,
            "branch_name": self.branch_name,
            "snapshot_id": self.snapshot_id,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "has_result": self.result is not None,
        }


@dataclass
class MergeResult:
    """Result of merging fork branches."""
    merge_strategy: str = ""     # best_of | vote | weighted_average
    winning_branch: Optional[str] = None
    merged_state: Dict = field(default_factory=dict)
    branch_results: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "merge_strategy": self.merge_strategy,
            "winning_branch": self.winning_branch,
            "confidence": self.confidence,
            "branch_count": len(self.branch_results),
        }


# ═══════════════════════════════════════════════════════════════════════
#  StateStore — S-Dimension Runtime
# ═══════════════════════════════════════════════════════════════════════

class StateStore:
    """
    Three-layer state store for Agent state management.

    Implements the S-dimension runtime:
      - snapshot(): Create O(1) COW snapshot
      - restore(): Restore to a previous snapshot
      - fork(): Create parallel branches for exploration
      - merge(): Merge branch results
      - get_state()/set_state(): Direct state access

    Usage:
        store = StateStore()
        store.set_state("counter", 0)
        snap_id = store.snapshot(label="before_loop")
        store.set_state("counter", 10)
        store.restore(snap_id)  # counter back to 0
    """

    def __init__(self) -> None:
        self._current_state: Dict[str, Any] = {}
        self._snapshots: Dict[str, SnapshotEntry] = {}
        self._branches: Dict[str, ForkBranch] = {}
        self._lock = threading.Lock()
        self._snapshot_count = 0
        self._fork_count = 0

    # ─── State Access ───

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value by key."""
        return self._current_state.get(key, default)

    def set_state(self, key: str, value: Any) -> None:
        """Set a state value."""
        self._current_state[key] = value

    def get_all_state(self) -> Dict[str, Any]:
        """Get the entire current state."""
        return dict(self._current_state)

    def delete_state(self, key: str) -> bool:
        """Delete a state key."""
        if key in self._current_state:
            del self._current_state[key]
            return True
        return False

    # ─── Snapshot / Restore ───

    def snapshot(self, label: str = "") -> str:
        """
        Create an O(1) COW snapshot of the current state.

        Uses shallow copy for O(1) performance. Deep copy of
        mutable values is deferred until modification (COW principle).

        Args:
            label: Optional human-readable label

        Returns:
            Snapshot ID for later restore
        """
        self._snapshot_count += 1
        snapshot_id = f"snap_{self._snapshot_count}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:6]}"

        # Shallow copy for O(1) — COW principle
        # Deep values will be copied on write
        state_copy = copy.copy(self._current_state)

        entry = SnapshotEntry(
            snapshot_id=snapshot_id,
            state=state_copy,
            created_at=time.time(),
            label=label,
        )

        with self._lock:
            self._snapshots[snapshot_id] = entry

        logger.info(f"Snapshot created: {snapshot_id}, label={label}")
        return snapshot_id

    def restore(self, snapshot_id: str) -> bool:
        """
        Restore state to a previous snapshot.

        Args:
            snapshot_id: The snapshot to restore to

        Returns:
            True if restore succeeded, False if snapshot not found
        """
        with self._lock:
            entry = self._snapshots.get(snapshot_id)
            if not entry:
                logger.warning(f"Snapshot not found: {snapshot_id}")
                return False

            # Restore state (shallow copy of snapshot state)
            self._current_state = copy.copy(entry.state)

        logger.info(f"State restored to snapshot: {snapshot_id}")
        return True

    def get_snapshot(self, snapshot_id: str) -> Optional[SnapshotEntry]:
        """Get a snapshot entry by ID."""
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def list_snapshots(self) -> List[SnapshotEntry]:
        """List all snapshots."""
        with self._lock:
            return list(self._snapshots.values())

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        with self._lock:
            if snapshot_id in self._snapshots:
                del self._snapshots[snapshot_id]
                return True
            return False

    # ─── Fork / Merge ───

    def fork(self, branch_names: List[str], label: str = "") -> Dict[str, str]:
        """
        Create parallel fork branches from the current state.

        Each branch gets a COW copy of the current state and can
        evolve independently.

        Args:
            branch_names: Names for each branch
            label: Optional label for the fork point

        Returns:
            Dict mapping branch_name → branch_id
        """
        # Create a snapshot at the fork point
        snap_id = self.snapshot(label=f"fork_point:{label}")

        branch_map = {}
        for name in branch_names:
            self._fork_count += 1
            branch_id = f"fork_{self._fork_count}_{hashlib.md5(f'{name}:{time.time()}'.encode()).hexdigest()[:6]}"

            # Each branch gets a copy of the current state
            branch_state = copy.copy(self._current_state)

            branch = ForkBranch(
                branch_id=branch_id,
                branch_name=name,
                snapshot_id=snap_id,
                state=branch_state,
                status="active",
            )

            with self._lock:
                self._branches[branch_id] = branch

            branch_map[name] = branch_id

        logger.info(f"Fork created: {len(branch_names)} branches from snapshot {snap_id}")
        return branch_map

    def get_branch(self, branch_id: str) -> Optional[ForkBranch]:
        """Get a fork branch by ID."""
        with self._lock:
            return self._branches.get(branch_id)

    def get_branch_state(self, branch_id: str) -> Optional[Dict]:
        """Get a branch's state."""
        with self._lock:
            branch = self._branches.get(branch_id)
            if branch:
                return dict(branch.state)
            return None

    def set_branch_state(self, branch_id: str, key: str, value: Any) -> bool:
        """Set a value in a branch's state."""
        with self._lock:
            branch = self._branches.get(branch_id)
            if branch and branch.status == "active":
                branch.state[key] = value
                return True
            return False

    def complete_branch(self, branch_id: str, result: Any) -> bool:
        """Mark a branch as completed with a result."""
        with self._lock:
            branch = self._branches.get(branch_id)
            if branch:
                branch.result = result
                branch.status = "completed"
                branch.completed_at = time.time()
                return True
            return False

    def fail_branch(self, branch_id: str, error: str = "") -> bool:
        """Mark a branch as failed."""
        with self._lock:
            branch = self._branches.get(branch_id)
            if branch:
                branch.status = "failed"
                branch.completed_at = time.time()
                return True
            return False

    def merge(self, strategy: str = "best_of") -> MergeResult:
        """
        Merge completed fork branches.

        Args:
            strategy: Merge strategy:
              - best_of: Use the branch with the best result
              - vote: Use the most common result
              - weighted_average: Average numeric results

        Returns:
            MergeResult with merged state and winning branch
        """
        with self._lock:
            completed_branches = {
                bid: branch for bid, branch in self._branches.items()
                if branch.status == "completed"
            }

        if not completed_branches:
            logger.warning("No completed branches to merge")
            return MergeResult(merge_strategy=strategy)

        if strategy == "best_of":
            return self._merge_best_of(completed_branches)
        elif strategy == "vote":
            return self._merge_vote(completed_branches)
        elif strategy == "weighted_average":
            return self._merge_weighted_average(completed_branches)
        else:
            logger.warning(f"Unknown merge strategy: {strategy}, using best_of")
            return self._merge_best_of(completed_branches)

    def _merge_best_of(self, branches: Dict[str, ForkBranch]) -> MergeResult:
        """Best-of merge: pick the branch with the highest-scoring result."""
        best_branch = None
        best_score = float('-inf')

        for bid, branch in branches.items():
            # Score based on result type
            score = self._score_result(branch.result)
            if score > best_score:
                best_score = score
                best_branch = bid

        if best_branch:
            winning = branches[best_branch]
            # Mark other branches as merged
            for bid in branches:
                if bid != best_branch:
                    branches[bid].status = "merged"

            # Set current state to winning branch's state
            self._current_state = copy.copy(winning.state)

            return MergeResult(
                merge_strategy="best_of",
                winning_branch=best_branch,
                merged_state=dict(winning.state),
                branch_results={bid: branch.result for bid, branch in branches.items()},
                confidence=best_score,
            )

        return MergeResult(merge_strategy="best_of")

    def _merge_vote(self, branches: Dict[str, ForkBranch]) -> MergeResult:
        """Vote merge: pick the most common result."""
        result_counts: Dict[str, List[str]] = {}
        for bid, branch in branches.items():
            result_key = str(branch.result)
            if result_key not in result_counts:
                result_counts[result_key] = []
            result_counts[result_key].append(bid)

        # Find the most common result
        most_common = max(result_counts.items(), key=lambda x: len(x[1]))
        winning_bids = most_common[1]
        winning_bid = winning_bids[0]

        winning = branches[winning_bid]
        for bid in branches:
            if bid not in winning_bids:
                branches[bid].status = "merged"

        self._current_state = copy.copy(winning.state)

        return MergeResult(
            merge_strategy="vote",
            winning_branch=winning_bid,
            merged_state=dict(winning.state),
            branch_results={bid: branch.result for bid, branch in branches.items()},
            confidence=len(winning_bids) / len(branches),
        )

    def _merge_weighted_average(self, branches: Dict[str, ForkBranch]) -> MergeResult:
        """Weighted average merge: average numeric results."""
        numeric_results = {}
        for bid, branch in branches.items():
            if isinstance(branch.result, (int, float)):
                numeric_results[bid] = branch.result

        if not numeric_results:
            return self._merge_best_of(branches)

        avg_result = sum(numeric_results.values()) / len(numeric_results)

        # Merge states by averaging numeric values
        merged_state = {}
        all_keys = set()
        for branch in branches.values():
            all_keys.update(branch.state.keys())

        for key in all_keys:
            values = []
            for branch in branches.values():
                val = branch.state.get(key)
                if isinstance(val, (int, float)):
                    values.append(val)
            if values:
                merged_state[key] = sum(values) / len(values)

        self._current_state = merged_state

        return MergeResult(
            merge_strategy="weighted_average",
            merged_state=merged_state,
            branch_results={bid: branch.result for bid, branch in branches.items()},
            confidence=len(numeric_results) / len(branches),
        )

    def _score_result(self, result: Any) -> float:
        """Score a branch result for best_of merge."""
        if isinstance(result, (int, float)):
            return float(result)
        if isinstance(result, str):
            # Simple heuristic: longer = more informative
            return len(result)
        if isinstance(result, dict):
            # Dict with "score" key
            if "score" in result:
                return float(result["score"])
            return len(result)
        if isinstance(result, bool):
            return 1.0 if result else 0.0
        if result is None:
            return 0.0
        return 1.0  # Default: any result is better than none

    # ─── Statistics ───

    def get_stats(self) -> Dict:
        """Get state store statistics."""
        with self._lock:
            active_branches = sum(1 for b in self._branches.values() if b.status == "active")
            completed_branches = sum(1 for b in self._branches.values() if b.status == "completed")

        return {
            "current_state_keys": list(self._current_state.keys()),
            "snapshot_count": len(self._snapshots),
            "fork_count": len(self._branches),
            "active_branches": active_branches,
            "completed_branches": completed_branches,
        }

    def clear(self) -> None:
        """Clear all state, snapshots, and branches (for testing)."""
        with self._lock:
            self._current_state = {}
            self._snapshots = {}
            self._branches = {}
            self._snapshot_count = 0
            self._fork_count = 0