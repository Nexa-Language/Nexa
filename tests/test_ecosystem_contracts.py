"""Source navigation and workspace configuration consumed by the 2.4 tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.runtime.inspector import inspect_nexa_file
from src.runtime.secrets import NexaSecrets


def test_inspect_reports_original_included_declaration_spans(tmp_path: Path) -> None:
    library = tmp_path / "library.nx"
    library.write_text('\nagent Imported {\n    prompt: "hello"\n}\n', encoding="utf-8")
    main = tmp_path / "main.nx"
    main.write_text('include "library.nx";\n\nagent Local { prompt: "local" }\nflow main { print("ok"); }\n', encoding="utf-8")
    result = inspect_nexa_file(str(main))
    assert "parse_error" not in result
    imported, local = result["agents"]
    assert imported["source"] == {"file": str(library.resolve()), "line": 2, "column": 1, "end_line": 4, "end_column": 2}
    assert local["source"]["file"] == str(main.resolve())
    assert local["source"]["line"] == 3
    assert result["flows"][0]["source"]["line"] == 4


def test_inspect_parse_fallback_does_not_invent_positions(tmp_path: Path) -> None:
    source = tmp_path / "broken.nx"
    source.write_text('agent Broken { prompt: ', encoding="utf-8")
    result = inspect_nexa_file(str(source))
    assert result["parse_error"]
    assert all("source" not in item for item in result["agents"])


def test_inspect_includes_annotated_tools_and_their_policy(tmp_path: Path) -> None:
    source = tmp_path / "tool.nx"
    source.write_text('@tool("Add", requires_approval: true, risk_level: "high")\nfn add(a: int, b: int): int { python! """return a + b""" }', encoding="utf-8")
    result = inspect_nexa_file(str(source))
    assert result["summary"]["total_tools"] == 1
    tool = result["tools"][0]
    assert tool["name"] == "add" and tool["description"] == "Add"
    assert tool["requires_approval"] is True and tool["risk_level"] == "high"
    assert tool["parameters"] == {"a": "int", "b": "int"}
    assert tool["source"]["line"] == 1 and tool["source"]["end_line"] == 2


@pytest.mark.parametrize("load_from_script", [False, True])
def test_nearest_nxs_config_overrides_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, load_from_script: bool) -> None:
    child = tmp_path / "project"
    child.mkdir()
    (tmp_path / "parent.nxs").write_text('MODE = "parent"\nconfig default {\nBASE_URL = "https://parent.invalid/v1"\n}', encoding="utf-8")
    (child / "project.nxs").write_text('MODE = "project"\nconfig default {\nBASE_URL = "https://project.invalid/v1"\n}', encoding="utf-8")
    monkeypatch.chdir(tmp_path if load_from_script else child)
    config = NexaSecrets()
    if load_from_script:
        config.load_from_script_dir(str(child / "main.py"))
    assert config.get("MODE") == "project"
    assert config.get("BASE_URL") == "https://project.invalid/v1"
