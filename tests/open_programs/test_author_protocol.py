"""Authors share a revision-aware JSON-RPC interface with durable events."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SOURCE = 'language "3.0" program Demo { goal answer() -> Int { intent "Return 42" implementation open } }'


def server(tmp_path: Path):
    from src.open_programs.protocol import AuthorProtocol
    from src.open_programs.store import ProgramStore

    return AuthorProtocol(ProgramStore(tmp_path / "author.sqlite3"))


def request(service, method: str, params: dict[str, object], identifier: int = 1):
    return service.handle({"jsonrpc": "2.0", "id": identifier, "method": method, "params": params})


def test_author_revisions_use_compare_and_swap(tmp_path: Path) -> None:
    service = server(tmp_path)
    first = request(service, "revision/propose", {"program_id": "demo", "source": SOURCE, "expected_revision": None})
    revision = first["result"]["revision"]
    changed = SOURCE.replace("Return 42", "Return 43")
    second = request(service, "revision/propose", {"program_id": "demo", "source": changed, "expected_revision": revision})
    assert "result" in second
    conflict = request(service, "revision/propose", {"program_id": "demo", "source": SOURCE, "expected_revision": revision})
    assert conflict["error"]["data"]["code"] == "revision_conflict"
    events = request(service, "events/read", {"program_id": "demo", "after": 1})["result"]["events"]
    assert len(events) == 1
    assert events[0]["event"]["kind"] == "revision_proposed"


def test_check_protocol_returns_holes_and_source_spans(tmp_path: Path) -> None:
    response = request(server(tmp_path), "program/check", {"source": SOURCE, "path": "test.nx"})
    assert response["result"]["obligations"] == ["answer"]
    assert response["result"]["program"]["goals"][0]["span"]["path"] == "test.nx"


@pytest.mark.parametrize("payload", [None, [], {"jsonrpc": "1.0", "id": 1}, {"jsonrpc": "2.0", "id": [], "method": "program/check"}])
def test_invalid_rpc_envelopes_return_structured_errors(tmp_path: Path, payload: object) -> None:
    assert server(tmp_path).handle(payload)["error"]["code"] == -32600


def test_clarification_requires_known_request_and_revision(tmp_path: Path) -> None:
    response = request(server(tmp_path), "author/answer", {"program_id": "demo", "request_id": "invented", "answer": "42", "expected_revision": "old"})
    assert response["error"]["data"]["code"] == "clarification_missing"


def test_stdio_framing_preserves_following_messages(tmp_path: Path) -> None:
    import io

    from src.open_programs.protocol import serve_stdio

    input_stream = io.StringIO('invalid-json\n' + json.dumps({"jsonrpc": "2.0", "id": 7, "method": "program/check", "params": {"source": SOURCE}}) + '\n')
    output = io.StringIO()
    serve_stdio(server(tmp_path), input_stream, output)
    messages = [json.loads(line) for line in output.getvalue().splitlines()]
    assert messages[0]["error"]["code"] == -32700
    assert messages[1]["id"] == 7 and messages[1]["result"]["obligations"] == ["answer"]


def test_json_rpc_notifications_have_no_response(tmp_path: Path) -> None:
    service = server(tmp_path)
    assert service.handle({"jsonrpc": "2.0", "method": "program/check", "params": {"source": SOURCE}}) is None
    response = request(service, "unknown/method", {})
    assert response["error"]["code"] == -32601


def test_clarification_answer_changes_spec_and_resumes_same_program(tmp_path: Path) -> None:
    import time

    from src.open_programs.compiler import OpenCompiler
    from src.open_programs.executor import OCIExecutor
    from src.open_programs.model import CompilerEnvironment
    from src.open_programs.protocol import AuthorProtocol
    from src.open_programs.store import ProgramStore
    from src.runtime.providers import ModelReply

    class Provider:
        name = "scripted"

        def __init__(self):
            self.replies = [{"clarification": "Which answer?"}, {"implementation": {"kind": "value", "body": "42"}}]

        def complete(self, request, on_text=None):
            return ModelReply({"role": "assistant", "content": json.dumps(self.replies.pop(0))}, input_tokens=1, output_tokens=1, usage_reported=True)

    store = ProgramStore(tmp_path / "dialog.sqlite3")
    environment = CompilerEnvironment(image="python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704", model="test", allow_model=True)
    service = AuthorProtocol(store, OpenCompiler(environment, store, executor=OCIExecutor(), provider=Provider()))
    try:
        revision = request(service, "revision/propose", {"program_id": "demo", "source": SOURCE, "expected_revision": None})["result"]["revision"]
        for turn in range(2):
            identifier = request(service, "goal/resolve", {"program_id": "demo", "expected_revision": revision, "goal": "answer"})["result"]["activity_id"]
            deadline = time.monotonic() + 15
            while True:
                activity = request(service, "activity/read", {"object_id": identifier})["result"]
                if activity["state"] != "running" or time.monotonic() > deadline:
                    break
                time.sleep(.02)
            if turn == 0:
                assert activity["state"] == "blocked"
                answered = request(service, "author/answer", {"program_id": "demo", "expected_revision": revision,
                                                             "request_id": activity["request_id"], "answer": "Return 42"})
                revision = answered["result"]["revision"]
            else:
                assert activity["state"] == "completed", activity
                assert activity["result"]["output_json"] == "42"
    finally:
        service.close()


def test_initialize_reports_version_and_rejects_unsupported_client(tmp_path: Path) -> None:
    service = server(tmp_path)
    accepted = request(service, "initialize", {"protocol_version": "3.0", "client": "fixture-agent"})
    assert accepted["result"]["protocol_version"] == "3.0"
    assert "revision/propose" in accepted["result"]["methods"]
    rejected = request(service, "initialize", {"protocol_version": "9.0", "client": "future-agent"})
    assert rejected["error"]["code"] == -32602


def test_oversized_frame_is_drained_before_next_request(tmp_path: Path) -> None:
    import io

    from src.open_programs.protocol import serve_stdio

    following = json.dumps({"jsonrpc": "2.0", "id": 9, "method": "program/check", "params": {"source": SOURCE}})
    output = io.StringIO()
    serve_stdio(server(tmp_path), io.StringIO("x" * (2 * 1024 * 1024 + 20) + "\n" + following + "\n"), output)
    frames = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(frames) == 2 and frames[0]["error"]["code"] == -32600
    assert frames[1]["id"] == 9
