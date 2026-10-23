"""Read-only legacy checkpoint export into a separate, inert 3.0 archive."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Literal

from src.runtime.run_state import RunState

from .model import FrozenModel, ProgramError, ProgramEvent, canonical_json, content_digest
from .store import ProgramStore


class LegacyRunArchive(FrozenModel):
    schema_version: Literal[1] = 1
    source_version: Literal["2.4"] = "2.4"
    run_id: str
    revision: int
    state_json: str
    unknown_effects: tuple[str, ...] = ()
    resume_allowed: Literal[False] = False


class MigrationIssue(FrozenModel):
    run_id: str
    code: str


class MigrationReport(FrozenModel):
    schema_version: Literal[1] = 1
    source_snapshot_digest: str
    imported: tuple[str, ...]
    errors: tuple[MigrationIssue, ...]
    archive_digests: tuple[str, ...]
    next_steps: tuple[str, ...] = ("Declare explicit 3.0 goals, capabilities and acceptance checks.",
                                   "Reconcile archived unknown effects before new external operations.",
                                   "Build and activate a new program; archived runs are never replayed.")


def _read_snapshot(source: Path) -> list[tuple[str, int, str]]:
    uri = source.resolve(strict=True).as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            columns = connection.execute("PRAGMA table_info(runs)").fetchall()
            if [column[1] for column in columns] != ["run_id", "revision", "state"]:
                raise ProgramError("legacy_schema_unsupported", "Expected a Nexa 2.4 runs table")
            return connection.execute("SELECT run_id, revision, state FROM runs ORDER BY run_id").fetchall()
    except sqlite3.Error as error:
        raise ProgramError("legacy_database_invalid", "Cannot read legacy checkpoint snapshot") from error


def _convert(row: tuple[str, int, str]) -> LegacyRunArchive:
    run_id, revision, payload = row
    state = RunState.from_dict(json.loads(payload))
    if state.run_id != run_id or state.revision != revision or not isinstance(state.tool_journal, dict):
        raise ValueError("legacy_identity_mismatch")
    if any(not isinstance(entry, dict) or entry.get("status") not in {"started", "completed"} for entry in state.tool_journal.values()):
        raise ValueError("legacy_effect_invalid")
    unknown = tuple(sorted(key for key, entry in state.tool_journal.items() if entry["status"] == "started"))
    return LegacyRunArchive(run_id=run_id, revision=revision, state_json=canonical_json(state.to_dict()), unknown_effects=unknown)


def migrate_checkpoint(source: Path, target: Path) -> MigrationReport:
    rows = _read_snapshot(source)
    archives, issues = [], []
    for row in rows:
        try:
            archives.append(_convert(row))
        except (ValueError, TypeError, KeyError, AttributeError):
            issues.append(MigrationIssue(run_id=str(row[0]), code="legacy_state_invalid"))
    report = MigrationReport(source_snapshot_digest=content_digest(rows), imported=tuple(item.run_id for item in archives),
                             errors=tuple(issues), archive_digests=tuple(item.digest for item in archives))
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError as error:
        raise ProgramError("migration_target_exists", "Migration requires a new destination database") from error
    os.close(descriptor)
    store = ProgramStore(target)
    changes: list[tuple[str, str | None, FrozenModel]] = [("legacy.run:" + item.run_id, None, item) for item in archives]
    changes.append(("migration:" + report.source_snapshot_digest, None, report))
    store.commit_references(changes, events=[("migration", ProgramEvent(kind="legacy_archived", object_id=report.digest))])
    return report
