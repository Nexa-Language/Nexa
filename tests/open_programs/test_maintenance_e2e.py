"""Replay the saved real-model six-stage demo through actual OCI and persistence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.open_programs.flagship import RecordedProvider, run_flagship
from src.open_programs.model import CompilerEnvironment
from src.runtime.providers import ModelReply


@pytest.mark.timeout(90)
def test_six_stage_maintenance_replays_recorded_model_responses(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    environment = CompilerEnvironment.model_validate_json((root / "examples/open_programs/maintain-aliyun.json").read_text()).model_copy(update={"provider": None})
    records = json.loads((root / "tests/fixtures/open_programs/flagship-responses.json").read_text())
    provider = RecordedProvider(replies=[ModelReply(**record) for record in records])
    summary = run_flagship(tmp_path / "flagship", environment, provider)
    assert summary["status"] == "passed", summary
    report = json.loads((tmp_path / "flagship/summary.json").read_text())
    assert len(report["stages"]) == 6
    assert all(stage["host_unchanged_before_approval"] for stage in report["stages"] if "host_unchanged_before_approval" in stage)
    assert report["stages"][-1]["bootstrap_identical"]
    assert report["stages"][-1]["bootstrap_generation_requests"] == 0
    assert not provider.replies
