"""Legacy migration reads a consistent WAL snapshot and never resumes effects."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.open_programs.model import ProgramError
from src.open_programs.store import ProgramStore
from src.runtime.checkpoints import SQLiteCheckpointStore
from src.runtime.run_state import RunState


def test_legacy_export_preserves_source_and_quarantines_unknown_effect(tmp_path: Path) -> None:
    from src.open_programs.migration import LegacyRunArchive, migrate_checkpoint

    source = tmp_path / "legacy.db"
    state = RunState(run_id="old", tool_journal={"call": {"status": "started", "name": "send"}})
    SQLiteCheckpointStore(source).save(state)
    # Keep a connection alive so migration must see committed rows still in WAL.
    connection = sqlite3.connect(source)
    connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute("UPDATE runs SET revision=2, state=?", (json.dumps({**state.to_dict(), "revision": 2}),))
    connection.commit()
    before = source.read_bytes()
    try:
        target = tmp_path / "converted.db"
        report = migrate_checkpoint(source, target)
        assert source.read_bytes() == before
        assert report.imported == ("old",) and not report.errors
        archive = ProgramStore(target).reference("legacy.run:old", LegacyRunArchive)
        assert archive is not None and archive.revision == 2
        assert archive.unknown_effects == ("call",) and archive.resume_allowed is False
        assert json.loads(archive.state_json)["tool_journal"] == state.tool_journal
        assert ProgramStore(target).current_revision("old") is None
        with pytest.raises(ProgramError, match="migration_target_exists"):
            migrate_checkpoint(source, target)
    finally:
        connection.close()


def test_unsupported_legacy_rows_report_errors_without_rewriting_input(tmp_path: Path) -> None:
    from src.open_programs.migration import migrate_checkpoint

    source = tmp_path / "legacy.db"
    SQLiteCheckpointStore(source).save(RunState(run_id="future"))
    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE runs SET state=?", (json.dumps({"schema_version": 99}),))
    before = source.read_bytes()
    report = migrate_checkpoint(source, tmp_path / "converted.db")
    assert source.read_bytes() == before
    assert report.imported == () and report.errors[0].run_id == "future"
    assert report.errors[0].code == "legacy_state_invalid"
