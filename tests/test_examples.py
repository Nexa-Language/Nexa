"""Every supported example must compile through the real file-aware frontend."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.compiler import compile_file

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
    assert not compiled.intersection(drafts)
    assert compiled.union(drafts) == actual
