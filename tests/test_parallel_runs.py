"""Concurrent orchestration preserves ordering, independent history, and cancellation."""

from __future__ import annotations

import threading
from typing import Any

import pytest

from src.runtime.agent import NexaAgent
from src.runtime.parallel_runs import ParallelRunError, run_many
from src.runtime.providers import ModelReply, ModelRequest


def test_parallel_runs_are_bounded_and_ordered(monkeypatch: pytest.MonkeyPatch) -> None:
    barrier = threading.Barrier(2, timeout=5)
    lock = threading.Lock()
    active = 0
    maximum = 0

    class Provider:
        name = "fixture"

        def complete(self, request: ModelRequest, on_text: Any = None) -> ModelReply:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(active, maximum)
            barrier.wait()
            assert len(request.messages) == 2
            with lock:
                active -= 1
            return ModelReply({"role": "assistant", "content": request.messages[-1]["content"]})

    agent = NexaAgent("worker")
    monkeypatch.setattr(agent, "_provider_adapter", lambda: Provider())
    initial_messages = list(agent.messages)
    states = run_many([(agent, str(index)) for index in range(8)], max_workers=2)
    assert maximum == 2
    assert [state.output for state in states] == [str(index) for index in range(8)]
    assert agent.messages == initial_messages


def test_parent_cancellation_reaches_every_child() -> None:
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(ParallelRunError) as error:
        run_many([(NexaAgent("child"), "hi")] * 3, cancel=cancelled)
    assert all(state.status.value == "cancelled" and state.model_calls == 0 for state in error.value.states)
