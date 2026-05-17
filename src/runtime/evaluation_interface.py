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

    def verify_semantic(
        self,
        condition: str,
        value: Any,
        context: Optional[Dict] = None,
    ) -> VerifyResult:
        """
        Verify a semantic condition against a value.

        Uses heuristic matching for simple conditions.
        Full LLM-based semantic evaluation is available via verify_semantic_llm().

        Args:
            condition: Natural language condition (e.g., "result is positive")
            value: The value to check
            context: Optional verification context

        Returns:
            VerifyResult with pass/fail and correction hint
        """
        self._verification_count += 1

        # Heuristic checks for common patterns
        condition_lower = condition.lower()

        # Bool checks (must be before int since bool is subclass of int)
        if isinstance(value, bool):
            return self._verify_bool_semantic(condition_lower, value)

        # Numeric checks
        if isinstance(value, (int, float)):
            return self._verify_numeric_semantic(condition_lower, value)

        # String checks
        if isinstance(value, str):
            return self._verify_string_semantic(condition_lower, value)

        # List/dict checks
        if isinstance(value, (list, dict)):
            return self._verify_collection_semantic(condition_lower, value)

        # Default: pass with low confidence (needs LLM)
        result = VerifyResult(
            passed=True,
            verify_type="semantic",
            target=str(value)[:100],
            condition=condition,
            details="Heuristic check passed (low confidence, consider LLM verification)",
            score=0.5,
        )
        self._passed_count += 1
        return result

    def _verify_numeric_semantic(self, condition: str, value: float) -> VerifyResult:
        """Semantic verification for numeric values."""
        import re

        # "is positive" / "is negative" / "is zero"
        if "positive" in condition:
            passed = value > 0
            hint = None if passed else f"Value {value} is not positive"
        elif "negative" in condition:
            passed = value < 0
            hint = None if passed else f"Value {value} is not negative"
        elif "zero" in condition or "is 0" in condition:
            passed = value == 0
            hint = None if passed else f"Value {value} is not zero"
        elif "non-zero" in condition or "nonzero" in condition:
            passed = value != 0
            hint = None if passed else f"Value {value} is zero"
        # "greater than X" / "> X"
        elif m := re.search(r'greater than\s+(-?\d+\.?\d*)', condition):
            threshold = float(m.group(1))
            passed = value > threshold
            hint = None if passed else f"Value {value} is not greater than {threshold}"
        elif m := re.search(r'>\s*(-?\d+\.?\d*)', condition):
            threshold = float(m.group(1))
            passed = value > threshold
            hint = None if passed else f"Value {value} <= {threshold}"
        # "less than X" / "< X"
        elif m := re.search(r'less than\s+(-?\d+\.?\d*)', condition):
            threshold = float(m.group(1))
            passed = value < threshold
            hint = None if passed else f"Value {value} is not less than {threshold}"
        elif m := re.search(r'<\s*(-?\d+\.?\d*)', condition):
            threshold = float(m.group(1))
            passed = value < threshold
            hint = None if passed else f"Value {value} >= {threshold}"
        else:
            passed = True
            hint = None

        if passed:
            self._passed_count += 1
        else:
            self._failed_count += 1

        return VerifyResult(
            passed=passed,
            verify_type="semantic",
            target=str(value),
            condition=condition,
            details=f"Numeric check: {value} {'passes' if passed else 'fails'} '{condition}'",
            correction_hint=hint,
            score=1.0 if passed else 0.0,
        )

    def _verify_string_semantic(self, condition: str, value: str) -> VerifyResult:
        """Semantic verification for string values."""
        # "contains X"
        import re
        if m := re.search(r'contains?\s+"([^"]*)"', condition):
            substring = m.group(1)
            passed = substring in value
            hint = None if passed else f"String does not contain '{substring}'"
        elif m := re.search(r"contains?\s+'([^']*)'", condition):
            substring = m.group(1)
            passed = substring in value
            hint = None if passed else f"String does not contain '{substring}'"
        # "not empty" / "non-empty"
        elif "not empty" in condition or "non-empty" in condition or "nonempty" in condition:
            passed = bool(value.strip())
            hint = None if passed else "String is empty"
        # "empty"
        elif "empty" in condition:
            passed = not value.strip()
            hint = None if passed else f"String is not empty: '{value[:50]}'"
        else:
            passed = True
            hint = None

        if passed:
            self._passed_count += 1
        else:
            self._failed_count += 1

        return VerifyResult(
            passed=passed,
            verify_type="semantic",
            target=value[:100],
            condition=condition,
            details=f"String check: '{value[:50]}' {'passes' if passed else 'fails'} '{condition}'",
            correction_hint=hint,
            score=1.0 if passed else 0.0,
        )

    def _verify_bool_semantic(self, condition: str, value: bool) -> VerifyResult:
        """Semantic verification for boolean values."""
        if "true" in condition.lower():
            passed = value is True
            hint = None if passed else "Expected True, got False"
        elif "false" in condition.lower():
            passed = value is False
            hint = None if passed else "Expected False, got True"
        else:
            passed = True
            hint = None

        if passed:
            self._passed_count += 1
        else:
            self._failed_count += 1

        return VerifyResult(
            passed=passed,
            verify_type="semantic",
            target=str(value),
            condition=condition,
            details=f"Bool check: {value} {'passes' if passed else 'fails'} '{condition}'",
            correction_hint=hint,
            score=1.0 if passed else 0.0,
        )

    def _verify_collection_semantic(self, condition: str, value: Any) -> VerifyResult:
        """Semantic verification for list/dict values."""
        import re

        if isinstance(value, list):
            if "not empty" in condition or "non-empty" in condition:
                passed = len(value) > 0
                hint = None if passed else "List is empty"
            elif "empty" in condition:
                passed = len(value) == 0
                hint = None if passed else f"List has {len(value)} items"
            elif m := re.search(r'length\s*(>=|>|==|<|<=)\s*(\d+)', condition):
                op, n = m.group(1), int(m.group(2))
                ops = {">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
                       "==": lambda a, b: a == b, "<": lambda a, b: a < b,
                       "<=": lambda a, b: a <= b}
                passed = ops.get(op, lambda a, b: True)(len(value), n)
                hint = None if passed else f"List length {len(value)} does not satisfy {op} {n}"
            else:
                passed = True
                hint = None
        elif isinstance(value, dict):
            if "not empty" in condition or "non-empty" in condition:
                passed = len(value) > 0
                hint = None if passed else "Dict is empty"
            elif "empty" in condition:
                passed = len(value) == 0
                hint = None if passed else f"Dict has {len(value)} keys"
            else:
                passed = True
                hint = None
        else:
            passed = True
            hint = None

        if passed:
            self._passed_count += 1
        else:
            self._failed_count += 1

        return VerifyResult(
            passed=passed,
            verify_type="semantic",
            target=f"{type(value).__name__}(len={len(value)})",
            condition=condition,
            details=f"Collection check: {'passes' if passed else 'fails'} '{condition}'",
            correction_hint=hint,
            score=1.0 if passed else 0.0,
        )

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
            return step.get("success", True)

        # "error is None" / "no error"
        if "error" in inv_lower and ("none" in inv_lower or "no error" in inv_lower):
            return step.get("error") is None

        # "observation not empty"
        if "observation" in inv_lower and "not empty" in inv_lower:
            return bool(step.get("observation", ""))

        return True  # Unknown invariant: pass

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
                self._passed_count += 1
                return VerifyResult(
                    passed=True,
                    verify_type="method",
                    target=str(value)[:100],
                    condition=method.__name__,
                    details=f"Custom method returned: {result}",
                    score=0.5,
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