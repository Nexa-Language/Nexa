"""Cancellation survives a second client and reaches a running resolution."""
from __future__ import annotations

import threading
from pathlib import Path

from src.open_programs.compiler import OpenCompiler
from src.open_programs.controller import RuntimeController
from src.open_programs.executor import OCIExecutor
from src.open_programs.model import CompilerEnvironment, GoalSpec, ProgramIR, ProgramRevision
from src.open_programs.store import ProgramStore
from src.runtime.providers import ModelReply, ModelRequest


def test_second_controller_cancels_inflight_model_request(tmp_path: Path) -> None:
    entered, release = threading.Event(), threading.Event()

    class Provider:
        name = "blocking-fixture"

        def complete(self, request: ModelRequest, on_text=None) -> ModelReply:
            entered.set()
            assert release.wait(5)
            return ModelReply({"role": "assistant", "content": '{"implementation":{"kind":"value","body":"42"},"clarification":""}'},
                              input_tokens=1, output_tokens=1, usage_reported=True)

    store = ProgramStore(tmp_path / "state.db")
    compiler = OpenCompiler(CompilerEnvironment(image="python@sha256:" + "a" * 64, allow_model=True), store, executor=OCIExecutor(), provider=Provider())
    controller = RuntimeController(compiler)
    program = ProgramIR(name="Demo", goals=(GoalSpec(name="answer", stage="runtime", return_type="Int", intent="Answer"),))
    revision = ProgramRevision(program_id="demo", program=program, environment_digest=compiler.environment.digest)
    store.commit_revision(None, revision, [])
    artifact = compiler.build(program, lock_path=tmp_path / "demo.lock")
    controller.activate_revision(controller.propose_revision(None, revision, artifact), None)
    activity = controller.start_activity("demo", "answer")
    results = []
    thread = threading.Thread(target=lambda: results.append(controller.resolve_activity(activity.activity_id)))
    thread.start()
    try:
        assert entered.wait(5)
        other = RuntimeController(OpenCompiler(compiler.environment, ProgramStore(store.path), executor=OCIExecutor()))
        other.cancel(activity.activity_id)
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert results[0].status == "cancelled"
    assert controller.activity(activity.activity_id).state == "cancelled"
