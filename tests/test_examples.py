"""Every supported example must compile through the real file-aware frontend."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.compiler import compile_file, compile_program
from src.open_programs.model import CheckReport

ROOT = Path(__file__).resolve().parents[1] / 'examples'
MANIFEST = json.loads((ROOT / 'manifest.json').read_text())


@pytest.mark.parametrize('relative', MANIFEST['compiled'])
def test_supported_example_compiles(relative: str) -> None:
    result = compile_file(ROOT / relative)
    assert result.python_code
    assert not result.diagnostics.errors


def test_every_example_has_an_explicit_status() -> None:
    actual = {str(path.relative_to(ROOT)) for path in ROOT.rglob('*.nx')}
    compiled = set(MANIFEST['compiled'])
    drafts = set(MANIFEST['historical_drafts'])
    open_programs = set(MANIFEST['open_programs'])
    assert not compiled.intersection(drafts)
    assert not open_programs.intersection(compiled | drafts)
    assert compiled.union(drafts, open_programs) == actual


@pytest.mark.parametrize('relative', MANIFEST['open_programs'])
def test_open_program_example_checks_offline(relative: str) -> None:
    path = ROOT / relative
    report = compile_program(path.read_text(), source_path=path)
    assert isinstance(report, CheckReport)
    assert report.ok, report.diagnostics
