"""Bounded parallel runs with ordered results and a shared cancellation signal."""

from __future__ import annotations

import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from .run_state import RunConfig, RunState

if TYPE_CHECKING:
    from .agent import NexaAgent


class ParallelRunError(RuntimeError):
    def __init__(self, states: list[RunState]) -> None:
        self.states = states
        failed = next(state for state in states if not state.success)
        super().__init__(f"Parallel agent {failed.agent_name} ended with {failed.status.value}: {failed.error}")


def run_many(jobs: list[tuple[NexaAgent, Any]], *, max_workers: int = 8, config: RunConfig | None = None,
             cancel: threading.Event | None = None) -> list[RunState]:
    if max_workers < 1:
        raise ValueError("Parallel worker count must be positive")
    if not jobs:
        return []
    signal = cancel if cancel is not None else threading.Event()
    results: dict[int, RunState] = {}

    def execute(context: contextvars.Context, agent: NexaAgent, value: Any) -> RunState:
        return context.run(agent.execute, value, config=config, cancel=signal)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(jobs))) as executor:
        futures = {executor.submit(execute, contextvars.copy_context(), agent, value): index
                   for index, (agent, value) in enumerate(jobs)}
        try:
            for future in as_completed(futures):
                state = future.result()
                results[futures[future]] = state
                if not state.success:
                    signal.set()
        except BaseException:
            signal.set()
            raise
    states = [results[index] for index in range(len(jobs))]
    if any(not state.success for state in states):
        raise ParallelRunError(states)
    return states
