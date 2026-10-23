"""Regressions at state, cache, trace, and orchestration boundaries."""

from __future__ import annotations

from typing import Any

from src.runtime.cache_manager import NexaCacheManager
from src.runtime.context_manager import ContextManager
from src.runtime.dag_orchestrator import DAGExecutor, DAGNode, DAGNodeType, ForkNode
from src.runtime.harness_kernel import HarnessKernel
from src.runtime.state_store import StateStore
from src.runtime.trace_system import TraceSystem


def test_nested_state_does_not_mutate_snapshots_or_sibling_branches() -> None:
    store = StateStore()
    value = {"items": [1]}
    store.set_state("nested", value)
    snapshot = store.snapshot()
    value["items"].append(2)
    assert store.restore(snapshot)
    assert store.get_state("nested") == {"items": [1]}
    branches = store.fork(["left", "right"])
    branch = store.get_branch_state(branches["left"])
    assert branch is not None
    branch["nested"]["items"].append(3)
    store.set_branch_state(branches["left"], "nested", branch["nested"])
    sibling = store.get_branch_state(branches["right"])
    assert sibling is not None
    assert sibling["nested"] == {"items": [1]}
    leaked = store.get_snapshot(snapshot)
    assert leaked is not None
    leaked.state["nested"]["items"].append(4)
    store.restore(snapshot)
    assert store.get_state("nested") == {"items": [1]}


def test_semantic_cache_respects_model_history_and_tools() -> None:
    cache = NexaCacheManager(enable_disk_cache=False)
    original = [{"role": "system", "content": "Return German"}, {"role": "user", "content": "Translate hello"}]
    cache.set(original, "model-a", "Hallo", tools=[{"name": "german"}])
    assert cache.get(original, "model-a", tools=[{"name": "german"}]) == "Hallo"
    assert cache.get(original, "model-b", tools=[{"name": "german"}]) is None
    assert cache.get(original, "model-a", tools=[{"name": "french"}]) is None
    changed = [{"role": "system", "content": "Return French"}, original[-1]]
    assert cache.get(changed, "model-a", tools=[{"name": "german"}]) is None


def test_registered_trace_accepts_kernel_context_events() -> None:
    kernel = HarnessKernel()
    trace = TraceSystem()
    kernel.register_trace_system(trace)
    ContextManager(kernel).add_message("user", "hello")
    assert trace.export_timeline()["events"]


def test_dag_fork_executes_each_branch_once_and_continues() -> None:
    visits: list[int] = []

    def increment(value: int, context: dict[str, Any]) -> int:
        visits.append(value)
        return value + 1

    child = DAGNode("child", DAGNodeType.TRANSFORM, transform_fn=increment)
    last = DAGNode("last", DAGNodeType.TRANSFORM, transform_fn=increment)
    child.next_nodes = [last]
    fork = ForkNode("fork")
    fork.next_nodes = [child]
    executor = DAGExecutor(fork)
    assert executor.run(1) == [3]
    assert visits == [1, 2]
    assert executor.node_results["child"] == 2
    assert executor.node_results["last"] == 3
