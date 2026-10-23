"""Persistent revisions use atomic compare-and-swap and immutable objects."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def test_revision_conflicts_survive_reopening(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError, ProgramEvent, ProgramIR, ProgramRevision
    from src.open_programs.store import ProgramStore

    path = tmp_path / "program.sqlite3"
    original = ProgramRevision(program_id="demo", program=ProgramIR(name="Demo"))
    first = ProgramStore(path)
    assert first.commit_revision(None, original, [ProgramEvent(kind="created", object_id=original.digest)]) == original.digest
    other = ProgramStore(path)
    revision = ProgramRevision(program_id="demo", parent=original.digest, program=ProgramIR(name="Changed"))
    other.commit_revision(original.digest, revision, [ProgramEvent(kind="revised", object_id=revision.digest)])
    with pytest.raises(ProgramError, match="revision_conflict"):
        first.commit_revision(original.digest, original, [])
    current = ProgramStore(path).current_revision("demo")
    assert current is not None and current.program.name == "Changed"
    assert [event.kind for _, event in first.events("demo")] == ["created", "revised"]
    assert len(first.events("demo", after=1)) == 1


def test_invalid_parent_rolls_back_all_writes(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError, ProgramIR, ProgramRevision
    from src.open_programs.store import ProgramStore

    store = ProgramStore(tmp_path / "program.sqlite3")
    revision = ProgramRevision(program_id="demo", parent="not-current", program=ProgramIR(name="Demo"))
    with pytest.raises(ProgramError, match="revision_conflict"):
        store.commit_revision(None, revision, [])
    assert store.current_revision("demo") is None
    assert store.events("demo") == []


def test_unknown_database_version_is_not_modified(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError
    from src.open_programs.store import ProgramStore

    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=99")
    before = path.read_bytes()
    with pytest.raises(ProgramError, match="unsupported_schema"):
        ProgramStore(path)
    assert path.read_bytes() == before


def test_process_exit_before_and_after_revision_commit(tmp_path: Path) -> None:
    import subprocess
    import sys

    from src.open_programs.store import ProgramStore

    path = tmp_path / "crash.db"
    code = '''import os, sys
from pathlib import Path
from src.open_programs.model import ProgramIR, ProgramRevision, ProgramEvent
from src.open_programs.store import ProgramStore
store = ProgramStore(Path(sys.argv[1]))
revision = ProgramRevision(program_id="crash", program=ProgramIR(name="Crash"))
if sys.argv[2] == "before":
 original = store._put
 def die(connection, record):
  original(connection, record)
  os._exit(86)
 store._put = die
store.commit_revision(None, revision, [ProgramEvent(kind="created", object_id=revision.digest)])
os._exit(87)
'''
    before = subprocess.run([sys.executable, "-c", code, str(path), "before"], check=False)
    assert before.returncode == 86
    store = ProgramStore(path)
    assert store.current_revision("crash") is None and store.events("crash") == []
    after = subprocess.run([sys.executable, "-c", code, str(path), "after"], check=False)
    assert after.returncode == 87
    reopened = ProgramStore(path)
    revision = reopened.current_revision("crash")
    assert revision is not None
    assert [event.object_id for _, event in reopened.events("crash")] == [revision.digest]
