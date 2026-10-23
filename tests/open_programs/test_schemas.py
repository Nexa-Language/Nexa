"""Published schemas are generated from exactly the installed API definitions."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.open_programs.schemas import MODELS, schema_for


def test_checked_in_schemas_match_current_runtime() -> None:
    directory = Path(__file__).resolve().parents[2] / "schemas" / "3.0"
    for name in (*MODELS, "author-protocol"):
        current = schema_for(name)
        Draft202012Validator.check_schema(current)
        assert json.loads((directory / (name + ".schema.json")).read_text()) == current
    validator = Draft202012Validator(schema_for("author-protocol"))
    validator.validate({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocol_version": "3.0"}})
    assert not validator.is_valid({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocol_version": "9.0"}})
