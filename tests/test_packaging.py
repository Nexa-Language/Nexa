"""Exercise built distributions from outside the source checkout."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_python(arguments: list[str], directory: Path, pythonpath: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    if pythonpath is not None:
        environment["PYTHONPATH"] = str(pythonpath)
    return subprocess.run([sys.executable, *arguments], cwd=directory, env=environment, capture_output=True, text=True, timeout=60, check=False)


@pytest.fixture
def package_source(tmp_path: Path) -> Path:
    destination = tmp_path / "source"
    destination.mkdir()
    for name in ("src", "stdlib"):
        shutil.copytree(ROOT / name, destination / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("setup.py", "pyproject.toml", "requirements.txt", "MANIFEST.in", "README.md", "LICENSE", "VERSION"):
        if (ROOT / name).exists():
            shutil.copy2(ROOT / name, destination / name)
    return destination


def test_source_distribution_can_rebuild_wheel(package_source: Path, tmp_path: Path) -> None:
    result = run_python(["-m", "build", "--sdist", "--no-isolation"], package_source)
    assert result.returncode == 0, result.stdout + result.stderr
    archive = next((package_source / "dist").glob("*.tar.gz"))
    extracted = tmp_path / "extracted"
    with tarfile.open(archive) as package:
        package.extractall(extracted, filter="data")
    source = next(extracted.iterdir())
    result = run_python(["-m", "build", "--wheel", "--no-isolation"], source)
    assert result.returncode == 0, result.stdout + result.stderr


def test_wheel_reports_version_and_compiles_bundled_stdlib(package_source: Path, tmp_path: Path) -> None:
    result = run_python(["-m", "build", "--wheel", "--no-isolation"], package_source)
    assert result.returncode == 0, result.stdout + result.stderr
    installed = tmp_path / "installed"
    with zipfile.ZipFile(next((package_source / "dist").glob("*.whl"))) as package:
        package.extractall(installed)
    application = tmp_path / "application"
    application.mkdir()
    result = run_python(["-m", "src.cli", "--version"], application, installed)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "v" + (ROOT / "VERSION").read_text().strip() in result.stdout
    program = application / "main.nx"
    program.write_text('include "stdlib/news.nx";\nflow main { print("ready"); }\n')
    result = run_python(["-m", "src.cli", "build", str(program)], application, installed)
    assert result.returncode == 0, result.stdout + result.stderr
    assert program.with_suffix(".py").exists()
