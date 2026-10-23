"""Keep offline tests away from user credentials and working files."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_isolation = pytest.MonkeyPatch()
_workspace: tempfile.TemporaryDirectory[str] | None = None


def pytest_sessionstart(session: pytest.Session) -> None:
    global _workspace
    _workspace = tempfile.TemporaryDirectory(prefix="nexa-test-session-")
    directory = Path(_workspace.name)
    _isolation.chdir(directory)
    _isolation.setattr(Path, "home", classmethod(lambda cls: directory))
    for name in tuple(os.environ):
        if name.startswith(("NEXA_", "OPENAI_", "ANTHROPIC_", "DEEPSEEK_", "MINIMAX_", "DASHSCOPE_")) or name.endswith(
            ("_API_KEY", "_ACCESS_TOKEN", "_AUTH_TOKEN"),
        ):
            _isolation.delenv(name)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _isolation.undo()
    if _workspace is not None:
        _workspace.cleanup()


@pytest.fixture(autouse=True)
def isolated_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
