"""Missing evidence and evaluator errors never count as passing assertions."""

from __future__ import annotations

import pytest

from src.ial.execute import execute_primitive
from src.ial.primitives import CheckStatus, SemanticCheck


@pytest.mark.parametrize("output", ["", "The operation is not successful", "successful"])
def test_semantic_check_requires_evidence_and_judge(output: str) -> None:
    result = execute_primitive(SemanticCheck(actual=output, intent="operation successful"))
    assert not result.passed
    assert result.status == (CheckStatus.FAIL if not output else CheckStatus.SKIP)


def test_semantic_judge_failure_is_visible() -> None:
    def judge(actual: str, intent: str) -> bool:
        raise TimeoutError("fixture")
    result = execute_primitive(SemanticCheck(actual="content", intent="accurate"), {"semantic_evaluator": judge})
    assert result.status == CheckStatus.ERROR
    assert not result.passed


def test_semantic_verdict_uses_judge_not_keyword_overlap() -> None:
    result = execute_primitive(SemanticCheck(actual="not successful", intent="successful"), {"semantic_evaluator": lambda actual, intent: False})
    assert result.status == CheckStatus.FAIL
