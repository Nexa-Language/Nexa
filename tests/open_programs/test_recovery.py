"""An unknown external outcome stays blocked until explicitly reconciled."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_unknown_non_idempotent_effect_is_never_automatically_repeated(tmp_path: Path) -> None:
    from src.open_programs.controller import EffectJournal
    from src.open_programs.model import ProgramError
    from src.open_programs.store import ProgramStore

    journal = EffectJournal(ProgramStore(tmp_path / "state.db"))
    intent = journal.prepare("demo", "send-once", "payload-digest", idempotent=False)
    calls = []
    def crash(key: str) -> str:
        calls.append(key)
        raise SystemExit("after external side effect")
    with pytest.raises(SystemExit):
        journal.execute(intent.operation_id, crash)
    recovered = EffectJournal(ProgramStore(tmp_path / "state.db"))
    assert recovered.recover("demo")[0].state == "unknown"
    with pytest.raises(ProgramError, match="effect_unknown"):
        recovered.execute(intent.operation_id, crash)
    assert calls == [intent.operation_id]
    recovered.reconcile(intent.operation_id, result_json='{"receipt":"confirmed"}', actor="operator")
    assert recovered.execute(intent.operation_id, crash) == '{"receipt":"confirmed"}'
    assert len(calls) == 1


def test_idempotent_effect_reuses_same_key_and_rejects_payload_drift(tmp_path: Path) -> None:
    from src.open_programs.controller import EffectJournal
    from src.open_programs.model import ProgramError
    from src.open_programs.store import ProgramStore

    journal = EffectJournal(ProgramStore(tmp_path / "state.db"))
    intent = journal.prepare("demo", "upsert", "one", idempotent=True)
    seen = set()
    calls = []
    def handler(key: str) -> str:
        calls.append(key)
        if key not in seen:
            seen.add(key)
            raise SystemExit()
        return '42'
    with pytest.raises(SystemExit):
        journal.execute(intent.operation_id, handler)
    journal.recover("demo")
    assert journal.execute(intent.operation_id, handler) == "42"
    assert calls == [intent.operation_id] * 2 and len(seen) == 1
    assert journal.prepare("demo", "upsert", "one", idempotent=True).state == "completed"
    with pytest.raises(ProgramError, match="effect_conflict"):
        journal.prepare("demo", "upsert", "two", idempotent=True)


def test_recovery_refuses_a_live_effect_owner(tmp_path: Path) -> None:
    import threading

    from src.open_programs.controller import EffectJournal
    from src.open_programs.model import ProgramError
    from src.open_programs.store import ProgramStore

    store = ProgramStore(tmp_path / "state.db")
    journal = EffectJournal(store)
    intent = journal.prepare("demo", "live", "one", idempotent=True)
    entered = threading.Event()
    release = threading.Event()
    errors = []
    def handler(key: str) -> str:
        entered.set()
        release.wait(5)
        return '1'
    def run() -> None:
        try:
            journal.execute(intent.operation_id, handler)
        except ProgramError as error:
            errors.append(error)
    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert entered.wait(5)
        with pytest.raises(ProgramError, match="operation_busy"):
            EffectJournal(ProgramStore(store.path)).recover("demo")
    finally:
        release.set()
        thread.join(5)
    assert not errors


def test_pending_effect_blocks_new_runtime_work(tmp_path: Path) -> None:
    from test_revision_runtime import revision, runtime

    from src.open_programs.model import ProgramError

    controller, compiler = runtime(tmp_path)
    rev, artifact = revision(compiler, 42)
    controller.activate_revision(controller.propose_revision(None, rev, artifact), None)
    controller.effects.prepare("demo", "outstanding", "payload", idempotent=False)
    with pytest.raises(ProgramError, match="pending_effect"):
        controller.start_activity("demo", "answer")
