"""Repository checks compare observed behavior against host-owned fixed oracles."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


@pytest.mark.parametrize(("implementation", "expected"), [('def add(a, b):\n return a + b\n', "accepted"),
                                                          ('def add(a, b):\n print("PASSED"); return a - b\n', "rejected")])
def test_patch_regression_oracles_are_outside_the_candidate_tree(tmp_path: Path, implementation: str, expected: str) -> None:
    from src.open_programs.compiler import OpenCompiler
    from src.open_programs.executor import OCIExecutor
    from src.open_programs.model import CompilerEnvironment, GoalSpec, Implementation, RepositoryCase, RepositoryCheck
    from src.open_programs.store import ProgramStore
    from src.open_programs.workspace import snapshot_workspace

    root = tmp_path / "repo"
    root.mkdir()
    (root / "calc.py").write_text('def add(a, b):\n return a - b\n')
    (root / "tests.py").write_text('raise RuntimeError("original test")\n')
    base = snapshot_workspace(root, ["calc.py", "tests.py"])
    changes = [{"path": file.path, "before_digest": file.digest, "content": implementation if file.path == "calc.py" else 'print("PASSED")\n'} for file in base.files]
    patch = {"base_digest": base.digest, "changes": changes}
    checks = RepositoryCheck(name="checks.regression", cases=(RepositoryCase(argv=("python", "-c", "from calc import add; print(add(-2, 5))"), expected_output="3\n"),))
    env = CompilerEnvironment(image=IMAGE, checks=(checks,))
    compiler = OpenCompiler(env, ProgramStore(tmp_path / "state.db"), executor=OCIExecutor())
    goal = GoalSpec(name="repair", return_type="Patch", intent="Fix addition", capabilities=("repo.read", "sandbox.write"), checks=(checks.name,),
                    implementation=Implementation(kind="value", body=json.dumps(patch)))
    result = compiler.resolve_goal(goal, input_json=json.dumps({"repository": base.model_dump(mode="json")}))
    assert result.status == expected
    assert result.evidence[-1].passed is (expected == "accepted")
    assert (root / "calc.py").read_text().endswith('return a - b\n')
    assert result.evidence[-1].artifact_digests
