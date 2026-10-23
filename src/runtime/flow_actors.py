"""Flow-owned actors process mailbox inputs in isolated, bounded agent sessions."""
from __future__ import annotations

import copy
import queue
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import replace
from typing import Any

from .agent_execution import execute_agent
from .run_state import RunConfig


class FlowActor:
    def __init__(self, agent: Any, args: tuple[Any, ...], cancel: threading.Event, executor: ThreadPoolExecutor) -> None:
        self.agent = copy.copy(agent)
        self.agent._run_lock = threading.RLock()
        self.agent._provider_items, self.agent._provider_cursor = [], 0
        self.history = [{'role': 'system', 'content': agent.system_prompt}]
        self.cancel = cancel
        self.mailbox: queue.Queue[tuple[Any, ...] | None] = queue.Queue()
        self.mailbox.put(args)
        self.closed = False
        self.joined = False
        self.config = RunConfig(timeout=agent.timeout, max_tool_calls=agent.max_tool_calls, retries=max(0, agent.retry - 1))
        self.deadline = time.monotonic() + self.config.timeout
        context = copy_context()
        self.future: Future[Any] = executor.submit(lambda: context.run(self._run))

    def send(self, value: Any) -> None:
        if self.closed:
            raise RuntimeError('Cannot send to an actor after await')
        self.mailbox.put((value,))

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.mailbox.put(None)

    def join(self) -> Any:
        self.close()
        self.joined = True
        return self.future.result(timeout=max(0.001, self.deadline - time.monotonic()))

    def _run(self) -> Any:
        value = None
        model_calls = tool_calls = 0
        try:
            while True:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Actor deadline exceeded')
                args = self.mailbox.get(timeout=remaining)
                if args is None:
                    return value
                config = replace(self.config, timeout=remaining, max_model_calls=self.config.max_model_calls - model_calls,
                                 max_tool_calls=self.config.max_tool_calls - tool_calls)
                execution = execute_agent(self.agent, args, history=self.history, config=config, cancel=self.cancel)
                state = execution.state
                if not state.success:
                    raise execution.exception or RuntimeError(f'Actor stopped: {state.status.value}: {state.error}')
                self.history = state.messages
                self.agent._provider_items, self.agent._provider_cursor = state.provider_items, state.provider_cursor
                model_calls += state.model_calls
                tool_calls += state.tool_calls
                value = execution.value
        except BaseException:
            self.cancel.set()
            raise


class FlowActors:
    def __init__(self) -> None:
        self.cancel = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix='nexa-actor')
        self.actors: list[FlowActor] = []

    def spawn(self, agent: Any, args: tuple[Any, ...]) -> FlowActor:
        self.actors = [actor for actor in self.actors if not (actor.joined and actor.future.done())]
        if sum(not actor.future.done() for actor in self.actors) >= 8:
            raise ValueError('A flow supports at most eight active actors')
        actor = FlowActor(agent, args, self.cancel, self.executor)
        self.actors.append(actor)
        return actor

    def shutdown(self, failed: bool) -> None:
        unjoined = any(not actor.joined for actor in self.actors)
        if failed or unjoined:
            self.cancel.set()
        for actor in self.actors:
            actor.close()
        self.executor.shutdown(wait=True, cancel_futures=True)
        if unjoined and not failed:
            raise RuntimeError('Every spawned actor must be awaited before the flow returns')
