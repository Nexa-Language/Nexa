"""
Nexa v2.0 EvaluationInterface — 四层验证接口

EvaluationInterface 实现 Harness V-dimension 的运行时核心，负责：
  - verify_satisfies: 类型合规性验证
  - verify_semantic: 语义验收 (LLM-based)
  - verify_behavioral: 行为轨迹验证
  - VerifyResult: 结构化验证结果 + correction_hint

Design Rationale:
  - 四层验证: type → semantic → behavioral → integration
  - 非破坏性: verify 失败时返回 correction_hint，不直接抛异常
  - 自纠错: correction_hint 可注入 reflect 进行自纠错
  - 可组合: 多个 verify 语句可链式调用

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.5
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

logger = logging.getLogger("nexa.evaluation_interface")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class VerifyResult:
    """Result of a verify statement evaluation."""
    passed: bool = True
    verify_type: str = ""          # satisfies | semantic | behavioral | method
    target: str = ""               # What was being verified
    condition: str = ""            # The verification condition
    details: str = ""              # Human-readable details
    correction_hint: Optional[str] = None  # Hint for self-correction
    score: float = 1.0             # 0.0-1.0 confidence score
    evidence: List[Dict] = field(default_factory=list)  # Supporting evidence

    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "verify_type": self.verify_type,
            "target": self.target,
            "condition": self.condition,
            "details": self.details,
            "correction_hint": self.correction_hint,
            "score": self.score,
            "evidence": self.evidence,
        }


@dataclass
class BehavioralTrace:
    """A behavioral trace for verify_behavioral."""
    steps: List[Dict] = field(default_factory=list)
    invariants: List[str] = field(default_factory=list)
    assertions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "steps": self.steps,
            "invariants": self.invariants,
            "assertions": self.assertions,
        }


# ═══════════════════════════════════════════════════════════════════════
#  EvaluationInterface — V-Dimension Runtime
# ═══════════════════════════════════════════════════════════════════════

class EvaluationInterface:
    """
    Four-layer verification interface for Agent outputs.

    Implements the V-dimension runtime:
      - verify_satisfies(): Type compliance verification
      - verify_semantic(): Semantic acceptance (LLM-based)
      - verify_behavioral(): Behavioral trace verification
      - verify_method(): Custom method verification

    Usage:
        ei = EvaluationInterface()
        result = ei.verify_satisfies(output, ProtocolSpec)
        if not result.passed:
            reflect(result.correction_hint)
    """

    def __init__(self) -> None:
        self._verification_count = 0
        self._passed_count = 0
        self._failed_count = 0

    # ─── Type Compliance ───

    def verify_satisfies(
        self,
        value: Any,
        protocol: Any,
        context: Optional[Dict] = None,
    ) -> VerifyResult:
        """
        Verify that a value satisfies a type/protocol specification.

        Checks:
          - Type matching (isinstance)
          - Required attributes presence
          - Attribute type matching

        Args:
            value: The value to verify
            protocol: A type, Protocol class, or dict of {attr: type}
            context: Optional verification context

        Returns:
            VerifyResult with pass/fail and correction hint
        """
        self._verification_count += 1

        # Dict-based protocol: {attr_name: expected_type}
        if isinstance(protocol, dict):
            return self._verify_dict_protocol(value, protocol)

        # Type-based protocol: isinstance check
        if isinstance(protocol, type):
            return self._verify_type_protocol(value, protocol)

        # String-based protocol: simple type name check
        if isinstance(protocol, str):
            return self._verify_string_protocol(value, protocol)

        result = VerifyResult(
            passed=False,
            verify_type="satisfies",
            target=str(type(value).__name__),
            condition=str(protocol),
            details=f"Unsupported protocol type: {type(protocol)}",
            correction_hint="Use a type, dict, or string protocol specification",
            score=0.0,
        )
        self._failed_count += 1
        return result

    def _verify_dict_protocol(self, value: Any, protocol: Dict) -> VerifyResult:
        """Verify against a dict-based protocol {attr: expected_type}."""
        if not isinstance(value, dict):
            result = VerifyResult(
                passed=False,
                verify_type="satisfies",
                target=str(type(value).__name__),
                condition=str(protocol),
                details=f"Expected dict-like value, got {type(value).__name__}",
                correction_hint=f"Ensure the output is a dict with keys: {list(protocol.keys())}",
                score=0.0,
            )
            self._failed_count += 1
            return result

        missing = []
        type_mismatches = []

        for attr, expected_type in protocol.items():
            if attr not in value:
                missing.append(attr)
                continue

            actual = value[attr]
            if isinstance(expected_type, type) and not isinstance(actual, expected_type):
                type_mismatches.append({
                    "attr": attr,
                    "expected": expected_type.__name__,
                    "actual": type(actual).__name__,
                })

        if missing or type_mismatches:
            hint_parts = []
            if missing:
                hint_parts.append(f"Add missing attributes: {missing}")
            if type_mismatches:
                for tm in type_mismatches:
                    hint_parts.append(
                        f"Fix type of '{tm['attr']}': expected {tm['expected']}, got {tm['actual']}"
                    )

            result = VerifyResult(
                passed=False,
                verify_type="satisfies",
                target="output",
                condition=str(protocol),
                details=f"Missing: {missing}, Type mismatches: {type_mismatches}",
                correction_hint="; ".join(hint_parts),
                score=0.0,
            )
            self._failed_count += 1
            return result

        result = VerifyResult(
            passed=True,
            verify_type="satisfies",
            target="output",
            condition=str(protocol),
            details="All protocol requirements satisfied",
            score=1.0,
        )
        self._passed_count += 1
        return result

    def _verify_type_protocol(self, value: Any, protocol: type) -> VerifyResult:
        """Verify against a type (isinstance check)."""
        if isinstance(value, protocol):
            result = VerifyResult(
                passed=True,
                verify_type="satisfies",
                target=str(type(value).__name__),
                condition=protocol.__name__,
                details=f"Value is instance of {protocol.__name__}",
                score=1.0,
            )
            self._passed_count += 1
            return result

        result = VerifyResult(
            passed=False,
            verify_type="satisfies",
            target=str(type(value).__name__),
            condition=protocol.__name__,
            details=f"Expected {protocol.__name__}, got {type(value).__name__}",
            correction_hint=f"Ensure the output is of type {protocol.__name__}",
            score=0.0,
        )
        self._failed_count += 1
        return result

    def _verify_string_protocol(self, value: Any, protocol: str) -> VerifyResult:
        """Verify against a string type name."""
        # Nexa type name → Python type name mapping
        NEXA_TYPE_MAP = {
            "string": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "list": "list",
            "dict": "dict",
            "unit": "NoneType",
            "option": "NexaOption",
            "result": "NexaResult",
        }
        type_name = type(value).__name__
        # Map Nexa type names to Python type names for comparison
        mapped_protocol = NEXA_TYPE_MAP.get(protocol.lower(), protocol.lower())
        if type_name.lower() == mapped_protocol.lower():
            result = VerifyResult(
                passed=True,
                verify_type="satisfies",
                target=type_name,
                condition=protocol,
                details=f"Type matches: {type_name}",
                score=1.0,
            )
            self._passed_count += 1
            return result

        result = VerifyResult(
            passed=False,
            verify_type="satisfies",
            target=type_name,
            condition=protocol,
            details=f"Expected type '{protocol}', got '{type_name}'",
            correction_hint=f"Ensure the output type is '{protocol}'",
            score=0.0,
        )
        self._failed_count += 1
        return result

    # ─── Semantic Verification ───

    def verify_semantic(self, condition: str, value: Any, context: Optional[Dict] = None) -> VerifyResult:
        """Evaluate the documented deterministic predicates or an explicit judge."""
        import re
        self._verification_count += 1
        text = condition.strip().lower()
        predicate = None
        if text in {"not empty", "is not empty"} and isinstance(value, (str, list, dict)):
            predicate = bool(value)
        elif text in {"is true", "is false"} and type(value) is bool:
            predicate = value == (text == "is true")
        elif type(value) in {int, float}:
            if text in {"is positive", "is negative", "is zero", "is non-zero", "is nonzero"}:
                predicate = {"is positive": value > 0, "is negative": value < 0, "is zero": value == 0,
                             "is non-zero": value != 0, "is nonzero": value != 0}[text]
            elif match := re.fullmatch(r"(greater than|less than) (-?\d+(?:\.\d+)?)", text):
                predicate = value > float(match[2]) if match[1] == "greater than" else value < float(match[2])
        elif isinstance(value, str) and (match := re.fullmatch(r'contains "(.*)"', condition.strip())):
            predicate = match[1] in value
        if predicate is None and isinstance(value, (str, list, dict)) and (match := re.fullmatch(r"length (>=|<=|==|>|<) (\d+)", text)):
            count, expected = len(value), int(match[2])
            predicate = {">=": count >= expected, "<=": count <= expected, "==": count == expected,
                         ">": count > expected, "<": count < expected}[match[1]]
        if predicate is None:
            judge = (context or {}).get("semantic_evaluator")
            if judge is None:
                self._failed_count += 1
                return VerifyResult(False, "semantic", str(value), condition, "A semantic evaluator is required",
                                    "Configure an explicit semantic evaluator", 0.0)
            return self.verify_method(lambda actual: judge(actual, condition), value)
        self._passed_count += int(predicate)
        self._failed_count += int(not predicate)
        return VerifyResult(predicate, "semantic", str(value), condition, f"Predicate evaluated to {predicate}",
                            None if predicate else "Output does not satisfy the predicate", float(predicate))

    # ─── Behavioral Verification ───

    def verify_behavioral(
        self,
        trace: BehavioralTrace,
        invariants: Optional[List[str]] = None,
        assertions: Optional[List[str]] = None,
    ) -> VerifyResult:
        """
        Verify behavioral trace against invariants and assertions.

        Args:
            trace: BehavioralTrace with steps
            invariants: List of invariant conditions to check
            assertions: List of assertion conditions to check

        Returns:
            VerifyResult with pass/fail and correction hint
        """
        self._verification_count += 1

        all_invariants = invariants or trace.invariants
        all_assertions = assertions or trace.assertions

        failures = []
        if (all_invariants or all_assertions) and not trace.steps:
            failures.append("No execution trace is available")

        # Check invariants (must hold for all steps)
        for inv in all_invariants:
            for i, step in enumerate(trace.steps):
                if not self._check_invariant_on_step(inv, step):
                    failures.append(f"Invariant '{inv}' violated at step {i}")

        # Check assertions (must hold at end)
        if trace.steps:
            final_step = trace.steps[-1]
            for assertion in all_assertions:
                if not self._check_assertion_on_step(assertion, final_step):
                    failures.append(f"Assertion '{assertion}' failed on final step")

        if failures:
            result = VerifyResult(
                passed=False,
                verify_type="behavioral",
                target=f"trace({len(trace.steps)} steps)",
                condition=f"invariants={all_invariants}, assertions={all_assertions}",
                details="; ".join(failures),
                correction_hint=f"Fix the following: {'; '.join(failures)}",
                score=0.0,
            )
            self._failed_count += 1
            return result

        result = VerifyResult(
            passed=True,
            verify_type="behavioral",
            target=f"trace({len(trace.steps)} steps)",
            condition=f"invariants={all_invariants}, assertions={all_assertions}",
            details="All invariants and assertions satisfied",
            score=1.0,
        )
        self._passed_count += 1
        return result

    def _check_invariant_on_step(self, invariant: str, step: Dict) -> bool:
        """Check if an invariant holds on a step."""
        inv_lower = invariant.lower()

        # "success is true" / "step succeeded"
        if "success" in inv_lower:
            return step.get("success") is True

        # "error is None" / "no error"
        if "error" in inv_lower and ("none" in inv_lower or "no error" in inv_lower):
            return step.get("error") is None

        # "observation not empty"
        if "observation" in inv_lower and "not empty" in inv_lower:
            return bool(step.get("observation", ""))

        return False  # Unknown invariants require an explicit evaluator.

    def _check_assertion_on_step(self, assertion: str, step: Dict) -> bool:
        """Check if an assertion holds on a step."""
        return self._check_invariant_on_step(assertion, step)

    # ─── Method Verification ───

    def verify_method(
        self,
        method: Callable,
        value: Any,
        context: Optional[Dict] = None,
    ) -> VerifyResult:
        """
        Verify using a custom method/function.

        Args:
            method: A callable that takes value and returns bool or VerifyResult
            value: The value to verify
            context: Optional verification context

        Returns:
            VerifyResult
        """
        self._verification_count += 1

        try:
            result = method(value, **(context or {}))
            if isinstance(result, VerifyResult):
                if result.passed:
                    self._passed_count += 1
                else:
                    self._failed_count += 1
                return result
            elif isinstance(result, bool):
                passed = result
                if passed:
                    self._passed_count += 1
                else:
                    self._failed_count += 1
                return VerifyResult(
                    passed=passed,
                    verify_type="method",
                    target=str(value)[:100],
                    condition=method.__name__,
                    details=f"Custom method '{method.__name__}' returned {passed}",
                    correction_hint=None if passed else f"Method '{method.__name__}' check failed",
                    score=1.0 if passed else 0.0,
                )
            else:
                self._failed_count += 1
                return VerifyResult(
                    passed=False,
                    verify_type="method",
                    target=str(value)[:100],
                    condition=method.__name__,
                    details=f"Custom method returned: {result}",
                    score=0.0,
                )
        except Exception as e:
            self._failed_count += 1
            return VerifyResult(
                passed=False,
                verify_type="method",
                target=str(value)[:100],
                condition=method.__name__,
                details=f"Method raised: {e}",
                correction_hint=f"Fix error in method '{method.__name__}': {e}",
                score=0.0,
            )

    # ─── Statistics ───

    def get_stats(self) -> Dict:
        """Get verification statistics."""
        return {
            "total_verifications": self._verification_count,
            "passed": self._passed_count,
            "failed": self._failed_count,
            "pass_rate": self._passed_count / max(1, self._verification_count),
        }

    def clear(self) -> None:
        """Clear statistics (for testing)."""
        self._verification_count = 0
        self._passed_count = 0
        self._failed_count = 0