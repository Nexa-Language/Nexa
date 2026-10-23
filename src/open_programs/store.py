"""Atomic program revisions and content-addressed immutable records in SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from .model import ContextSnapshot, EvidenceRecord, FrozenModel, ProgramError, ProgramEvent, ProgramRevision, content_digest

Record = TypeVar("Record", bound=FrozenModel)
_APPLICATION_ID = 0x4E585033


class ProgramStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            application = connection.execute("PRAGMA application_id").fetchone()[0]
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if version not in {0, 1} or (tables and application != _APPLICATION_ID):
                raise ProgramError("unsupported_schema", f"Database schema {version}; application {application}")
            connection.executescript(f"""
                PRAGMA journal_mode=WAL;
                PRAGMA application_id={_APPLICATION_ID};
                PRAGMA user_version=1;
                CREATE TABLE IF NOT EXISTS objects (digest TEXT PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS objects_kind ON objects(kind);
                CREATE TABLE IF NOT EXISTS evidence_index (digest TEXT PRIMARY KEY, subject TEXT NOT NULL, policy TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS evidence_context ON evidence_index(subject, policy);
                CREATE TABLE IF NOT EXISTS programs (id TEXT PRIMARY KEY, revision TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS refs (name TEXT PRIMARY KEY, digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    program_id TEXT NOT NULL, event_digest TEXT NOT NULL, body TEXT NOT NULL,
                    UNIQUE(program_id, event_digest));
            """)
            missing = connection.execute("SELECT o.digest, o.body FROM objects o LEFT JOIN evidence_index e ON o.digest=e.digest "
                                         "WHERE o.kind='EvidenceRecord' AND e.digest IS NULL").fetchall()
            for digest, body in missing:
                record = EvidenceRecord.model_validate_json(body)
                if record.digest != digest:
                    raise ProgramError("object_corrupt", digest)
                self._index_evidence(connection, record)

    @contextmanager
    def lease(self, name: str) -> Generator[None, None, None]:
        # Kernel locks release on process exit; recovery must never reclaim a live owner.
        import fcntl

        directory = self.path.parent / (self.path.name + ".locks")
        directory.mkdir(exist_ok=True)
        with (directory / content_digest(name)).open("a+b") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ProgramError("operation_busy", "Another controller still owns this operation", retryable=True) from error
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _put(self, connection: sqlite3.Connection, record: FrozenModel) -> str:
        body = record.model_dump_json()
        digest = record.digest
        existing = connection.execute("SELECT kind, body FROM objects WHERE digest=?", (digest,)).fetchone()
        if existing:
            # Locations are diagnostic metadata and can differ for identical semantics.
            if existing[0] != type(record).__name__:
                raise ProgramError("object_conflict", digest)
        else:
            connection.execute("INSERT INTO objects VALUES (?, ?, ?)", (digest, type(record).__name__, body))
        if isinstance(record, EvidenceRecord):
            self._index_evidence(connection, record)
        return digest

    def _index_evidence(self, connection: sqlite3.Connection, record: EvidenceRecord) -> None:
        connection.execute("INSERT OR IGNORE INTO evidence_index VALUES (?, ?, ?)", (record.digest, record.subject_digest, record.policy_digest))

    def evidence_for(self, context: ContextSnapshot) -> list[EvidenceRecord]:
        with self._connection() as connection:
            rows = connection.execute("SELECT digest FROM evidence_index WHERE subject=? AND policy=?", (context.subject_digest, context.policy_digest)).fetchall()
        dependencies = {item.name: item.digest for item in context.dependencies}
        records = []
        for (digest,) in rows:
            record = self.get(digest, EvidenceRecord)
            if any(dependencies.get(item.name) != item.digest for item in record.dependencies):
                continue
            if record.task_id != context.task_id and (record.kind == "human_decision" or (record.kind == "model_review" and not record.model_pinned)):
                continue
            records.append(record)
        return records

    def put(self, record: FrozenModel) -> str:
        with self._connection() as connection:
            return self._put(connection, record)

    def get(self, digest: str, record_type: type[Record]) -> Record:
        with self._connection() as connection:
            row = connection.execute("SELECT kind, body FROM objects WHERE digest=?", (digest,)).fetchone()
        if row is None or row[0] != record_type.__name__:
            raise ProgramError("object_missing", digest)
        record = record_type.model_validate_json(row[1])
        if record.digest != digest:
            raise ProgramError("object_corrupt", digest)
        return record

    def current_revision(self, program_id: str) -> ProgramRevision | None:
        with self._connection() as connection:
            row = connection.execute("SELECT revision FROM programs WHERE id=?", (program_id,)).fetchone()
        return self.get(row[0], ProgramRevision) if row else None

    def commit_revision(self, expected: str | None, revision: ProgramRevision, events: list[ProgramEvent]) -> str:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT revision FROM programs WHERE id=?", (revision.program_id,)).fetchone()
            current = row[0] if row else None
            if current != expected or revision.parent != expected:
                raise ProgramError("revision_conflict", revision.program_id, retryable=True)
            digest = self._put(connection, revision)
            connection.execute("INSERT INTO programs VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision", (revision.program_id, digest))
            for event in events:
                connection.execute("INSERT OR IGNORE INTO events(program_id, event_digest, body) VALUES (?, ?, ?)",
                                   (revision.program_id, event.digest, event.model_dump_json()))
            return digest

    def events(self, program_id: str, *, after: int = 0) -> list[tuple[int, ProgramEvent]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT sequence, body FROM events WHERE program_id=? AND sequence>? ORDER BY sequence", (program_id, after)).fetchall()
        return [(sequence, ProgramEvent.model_validate_json(body)) for sequence, body in rows]

    def reference(self, name: str, record_type: type[Record]) -> Record | None:
        with self._connection() as connection:
            row = connection.execute("SELECT digest FROM refs WHERE name=?", (name,)).fetchone()
        return self.get(row[0], record_type) if row else None

    def references(self, prefix: str, record_type: type[Record]) -> list[Record]:
        with self._connection() as connection:
            rows = connection.execute("SELECT name, digest FROM refs ORDER BY name").fetchall()
        return [self.get(digest, record_type) for name, digest in rows if name.startswith(prefix)]

    def set_reference(self, name: str, expected: str | None, record: FrozenModel, *, events: list[tuple[str, ProgramEvent]] | None = None) -> str:
        self.commit_references([(name, expected, record)], events=events)
        return record.digest

    def commit_references(self, changes: list[tuple[str, str | None, FrozenModel]], *, events: list[tuple[str, ProgramEvent]] | None = None) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for name, expected, record in changes:
                row = connection.execute("SELECT digest FROM refs WHERE name=?", (name,)).fetchone()
                if (row[0] if row else None) != expected:
                    raise ProgramError("revision_conflict", name, retryable=True)
                digest = self._put(connection, record)
                connection.execute("INSERT INTO refs VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET digest=excluded.digest", (name, digest))
            for program_id, event in events or []:
                connection.execute("INSERT OR IGNORE INTO events(program_id, event_digest, body) VALUES (?, ?, ?)",
                                   (program_id, event.digest, event.model_dump_json()))
