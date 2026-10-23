"""Public CLI preserves the proposal / approval / application boundary."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "src.cli", *args], capture_output=True, text=True, check=False)


def test_cli_maintenance_proposes_then_requires_exact_approval(tmp_path: Path) -> None:
    from src.open_programs.workspace import snapshot_workspace

    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "calc.py").write_text("def add(a, b):\n return a - b\n")
    snapshot = snapshot_workspace(repository, ["calc.py"])
    patch = {"base_digest": snapshot.digest, "changes": [{"path": "calc.py", "before_digest": snapshot.files[0].digest, "content": "def add(a, b):\n return a + b\n"}]}
    source = tmp_path / "maintain.nx"
    source.write_text('language "3.0" program Maintain(repo: Repository) { goal repair(change: ChangeRequest) -> Patch { stage runtime intent "Fix addition" '
                      'capabilities [repo.read, sandbox.write] ensure checks.regression implementation value ' + json.dumps(patch) + ' } '
                      'on change_request as request { let result = resolve repair(request) propose repo.apply(result) requires human.approval } }')
    environment = tmp_path / "environment.json"
    environment.write_text(json.dumps({"image": IMAGE, "checks": [{"name": "checks.regression", "cases": [
        {"argv": ["python", "-c", "from calc import add; print(add(2, 3))"], "expected_output": "5\n"}]}]}))
    state = str(tmp_path / "state.db")
    result = cli("run", str(source), "--environment", str(environment), "--state", state, "--repository", str(repository),
                 "--include", "calc.py", "--request", "Fix addition", "--program-id", "demo", "--json")
    assert result.returncode == 0, result.stderr + result.stdout
    data = json.loads(result.stdout)
    assert data["status"] == "awaiting_approval"
    proposal_id = data["proposal_id"]
    assert (repository / "calc.py").read_text().endswith("return a - b\n")
    denied = cli("open", "apply", proposal_id, "--grant", "unknown", "--environment", str(environment), "--state", state)
    assert denied.returncode != 0
    grant = cli("open", "approve", proposal_id, "--actor", "fixture-operator", "--state", state)
    assert grant.returncode == 0, grant.stderr + grant.stdout
    grant_id = json.loads(grant.stdout)["grant_id"]
    applied = cli("open", "apply", proposal_id, "--grant", grant_id, "--environment", str(environment), "--state", state)
    assert applied.returncode == 0, applied.stderr + applied.stdout
    assert json.loads(applied.stdout)["state"] == "applied"
    assert (repository / "calc.py").read_text().endswith("return a + b\n")
    status = cli("open", "status", "demo", "--state", state)
    assert json.loads(status.stdout)["generation"] == 1
