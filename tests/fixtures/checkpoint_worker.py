"""Isolated process that can die after an external write or a committed result."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from src.runtime.agent import NexaAgent
from src.runtime.checkpoints import SQLiteCheckpointStore
from src.runtime.providers import ModelReply, ModelRequest
from src.runtime.run_state import RunState

PHASE, WINDOW = sys.argv[1:]
STORE = SQLiteCheckpointStore('runs.sqlite')


class FixtureProvider:
    name = 'fixture'

    def complete(self, request: ModelRequest, on_text: Any = None) -> ModelReply:
        if PHASE == 'start':
            return ModelReply({'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'write-1', 'type': 'function', 'function': {'name': 'write', 'arguments': '{}'}},
            ]})
        return ModelReply({'role': 'assistant', 'content': 'done'})


def write() -> str:
    with Path('effects.txt').open('a') as handle:
        handle.write('written\n')
        handle.flush()
        os.fsync(handle.fileno())
    if WINDOW == 'after_effect':
        os._exit(73)
    return 'written'


def save(state: RunState) -> None:
    STORE.save(state)
    Path('run-id.txt').write_text(state.run_id)
    if PHASE == 'start' and WINDOW == 'after_result' and state.events[-1]['event'] == 'tool_completed':
        os._exit(73)


agent = NexaAgent('recovery', model='fixture', tools=[{'name': 'write', 'parameters': {'type': 'object'}, '_handler': write}])
state = None if PHASE == 'start' else STORE.load(Path('run-id.txt').read_text())
result = agent.execute(*(['write'] if state is None else []), state=state, save=save, provider=FixtureProvider())
print(result.status.value)
