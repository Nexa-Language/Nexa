"""Transactional run checkpoints with optimistic concurrency and tool recovery."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .run_state import RunState, RunStatus


class CheckpointConflict(RuntimeError):
    """Another executor already advanced this run."""


class SQLiteCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, state TEXT NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def save(self, state: RunState) -> None:
        revision = state.revision + 1
        payload = json.dumps({**state.to_dict(), "revision": revision}, ensure_ascii=False, allow_nan=False)
        with self._connect() as connection:
            if state.revision == 0:
                try:
                    connection.execute("INSERT INTO runs VALUES (?, ?, ?)", (state.run_id, revision, payload))
                except sqlite3.IntegrityError as error:
                    raise CheckpointConflict(f"Run {state.run_id} already exists") from error
            else:
                cursor = connection.execute("UPDATE runs SET revision=?, state=? WHERE run_id=? AND revision=?",
                                            (revision, payload, state.run_id, state.revision))
                if cursor.rowcount != 1:
                    raise CheckpointConflict(f"Stale checkpoint for run {state.run_id}")
        state.revision = revision

    def load(self, run_id: str) -> RunState:
        with self._connect() as connection:
            row = connection.execute("SELECT state FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return RunState.from_dict(json.loads(row[0]))

    def approve(self, run_id: str, call_id: str, approved: bool) -> RunState:
        state = self.load(run_id)
        if state.status != RunStatus.WAITING_APPROVAL or not any(call["id"] == call_id for call in state.pending_calls):
            raise ValueError("Approval must refer to a pending call in a waiting run")
        if type(approved) is not bool:
            raise TypeError("Approval must be a boolean")
        state.approvals[call_id] = approved
        self.save(state)
        return state

    def resolve_tool(self, run_id: str, call_id: str, content: str, *, success: bool) -> RunState:
        """Record an operator-verified outcome; never automatically repeat a side effect."""
        state = self.load(run_id)
        entry = state.tool_journal.get(call_id)
        if entry is None or entry["status"] != "started" or not any(call["id"] == call_id for call in state.pending_calls):
            raise ValueError("Only an outstanding tool with an unknown outcome can be resolved")
        state.tool_journal[call_id] = {**entry, "status": "completed", "content": content, "success": success, "sandboxed": False}
        state.status, state.error = RunStatus.RUNNING, None
        state.events.append({"sequence": len(state.events), "event": "tool_resolved", "run_id": run_id, "call_id": call_id})
        self.save(state)
        return state
