"""A versioned budget proposal preserves old semantics and narrows model authority."""
from __future__ import annotations

from pathlib import Path

import pytest

SOURCE = 'language "3.0" program Budget { goal answer() -> Int { intent "Return 42" implementation open } }'
IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"


def test_explicit_extension_migrates_old_program_without_semantic_change() -> None:
    from src.open_programs.extensions import parse_budget_program, upgrade_budget_program
    from src.open_programs.frontend import check
    from src.open_programs.model import SourceBundle

    old = check(SourceBundle(text=SOURCE)).program
    assert old is not None
    upgraded = upgrade_budget_program(SOURCE)
    assert upgraded.program.digest == old.digest and not upgraded.limits
    source = SOURCE.replace('"3.0"', '"3.1-budget"').replace('intent "Return 42"', 'intent "Return 42" budget model_calls 0')
    assert not check(SourceBundle(text=source)).ok
    extended = parse_budget_program(source)
    assert extended.program.digest == old.digest
    assert extended.limits[0].max_model_calls == 0


def test_zero_language_budget_prevents_model_calls(tmp_path: Path) -> None:
    from src.open_programs.compiler import OpenCompiler
    from src.open_programs.executor import OCIExecutor
    from src.open_programs.extensions import parse_budget_program, resolve_budget_goal
    from src.open_programs.model import CompilerEnvironment, ResolutionBudget
    from src.open_programs.store import ProgramStore

    class ForbiddenProvider:
        name = "forbidden"
        def complete(self, request, on_text=None):
            pytest.fail("A zero language budget must never reach a provider")
    compiler = OpenCompiler(CompilerEnvironment(image=IMAGE, allow_model=True), ProgramStore(tmp_path / "state.db"), executor=OCIExecutor(), provider=ForbiddenProvider())
    program = parse_budget_program(SOURCE.replace('"3.0"', '"3.1-budget"').replace('intent "Return 42"', 'intent "Return 42" budget model_calls 0'))
    result = resolve_budget_goal(program, "answer", compiler, budget=ResolutionBudget(max_model_calls=5))
    assert result.status == "blocked" and result.reason == "model_call_budget"
    assert result.model_calls == 0


def test_duplicate_or_out_of_range_budget_is_rejected() -> None:
    from src.open_programs.extensions import parse_budget_program
    from src.open_programs.model import ProgramError

    source = SOURCE.replace('"3.0"', '"3.1-budget"')
    for clause in ('budget model_calls 101', 'budget model_calls 1 budget model_calls 2'):
        with pytest.raises(ProgramError, match="extension_invalid"):
            parse_budget_program(source.replace('intent "Return 42"', 'intent "Return 42" ' + clause))
