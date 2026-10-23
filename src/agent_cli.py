"""Run a declared .nx agent with durable, explicit approval and resume."""

from __future__ import annotations

import hashlib
import json
import sys
import types
import uuid
from pathlib import Path

from .compiler import compile_file
from .runtime.agent import NexaAgent
from .runtime.checkpoints import SQLiteCheckpointStore
from .runtime.mcp_client import mcp_session_scope
from .runtime.run_state import RunConfig, RunState, RunStatus


def run_declared_agent(source: str, agent_name: str, task: str | None, *, checkpoint: str = ".nexa/runs.sqlite3",
                       resume: str | None = None, approve: str | None = None, deny: str | None = None,
                       timeout: float = 300.0, max_tool_calls: int = 20) -> RunState:
    compilation = compile_file(source)
    source_hash = hashlib.sha256(compilation.python_code.encode()).hexdigest()
    store = SQLiteCheckpointStore(checkpoint)
    state = store.load(resume) if resume else None
    if state is not None and state.metadata.get("source_hash") != source_hash:
        raise ValueError("Program changed since checkpoint; resume with the original source")
    if approve and deny or (approve or deny) and not resume:
        raise ValueError("Provide one approval decision together with --resume")
    if state is not None and task is not None:
        raise ValueError("Resume does not accept a new task")
    if state is None and task is None:
        raise ValueError("A task is required for a new run")
    if approve or deny:
        state = store.approve(resume or "", approve or deny or "", approved=bool(approve))
    module_name = "nexa_agent_" + uuid.uuid4().hex
    module = types.ModuleType(module_name)
    module.__file__ = str(Path(source).resolve())
    sys.modules[module_name] = module

    def save(run: RunState) -> None:
        run.metadata["source_hash"] = source_hash
        store.save(run)

    try:
        with mcp_session_scope():
            exec(compile(compilation.python_code, module.__file__, "exec"), module.__dict__)  # noqa: S102 - The CLI executes the explicitly selected program.
            agent = getattr(module, agent_name, None)
            if not isinstance(agent, NexaAgent):
                raise TypeError(f"No agent named {agent_name!r} in {source}")
            if state is not None:
                return agent.execute(state=state, save=save)
            return agent.execute(task, config=RunConfig(timeout=timeout, max_tool_calls=max_tool_calls), save=save)
    finally:
        sys.modules.pop(module_name, None)


def print_run(state: RunState) -> int:
    print(json.dumps({"run_id": state.run_id, "status": state.status.value, "output": state.output, "error": state.error,
                      "model_calls": state.model_calls, "tool_calls": state.tool_calls,
                      "input_tokens": state.input_tokens, "output_tokens": state.output_tokens,
                      "pending_calls": state.pending_calls if state.status == RunStatus.WAITING_APPROVAL else []}, ensure_ascii=False))
    return 0 if state.success else 2 if state.status == RunStatus.WAITING_APPROVAL else 1
