"""The same source programs and expected behavior are consumed by Rust tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_agent_execution import FakeClient, completion

from src import nexa_sdk
from src.runtime.agent import NexaAgent

CASES = json.loads((Path(__file__).parent / "fixtures/conformance/programs.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_python_semantics(case: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([completion(case.get("model_reply", ""))])
    monkeypatch.setattr(NexaAgent, "_get_client", lambda self: client)
    result = nexa_sdk.run(case["source"])
    assert result.success, result.stderr
    assert result.result == case["expected"]
    if "agent_input" in case:
        assert client.requests[0]["messages"][-1]["content"] == case["agent_input"]
