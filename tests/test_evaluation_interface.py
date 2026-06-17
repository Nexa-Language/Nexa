"""
Nexa v2.0 M4 Tests — EvaluationInterface + LLMRouter

Tests cover:
  - EvaluationInterface: verify_satisfies, verify_semantic, verify_behavioral, verify_method
  - LLMRouter: route, chat, fallback chain, model registration
  - Integration: verify + router end-to-end

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.5
"""

import pytest

from src.runtime.evaluation_interface import (
    EvaluationInterface, VerifyResult, BehavioralTrace,
)
from src.runtime.llm_router import (
    LLMRouter, ModelRequirement, ModelInfo, DEFAULT_MODELS,
)


# ═══════════════════════════════════════════════════════════════════════
#  EvaluationInterface Tests
# ═══════════════════════════════════════════════════════════════════════

class TestVerifySatisfies:
    """Type compliance verification tests."""

    def test_dict_protocol_pass(self):
        ei = EvaluationInterface()
        result = ei.verify_satisfies(
            {"name": "test", "count": 42},
            {"name": str, "count": int},
        )
        assert result.passed is True
        assert result.verify_type == "satisfies"

    def test_dict_protocol_missing_key(self):
        ei = EvaluationInterface()
        result = ei.verify_satisfies(
            {"name": "test"},
            {"name": str, "count": int},
        )
        assert result.passed is False
        assert "count" in result.details
        assert result.correction_hint is not None

    def test_dict_protocol_type_mismatch(self):
        ei = EvaluationInterface()
        result = ei.verify_satisfies(
            {"name": "test", "count": "not_a_number"},
            {"name": str, "count": int},
        )
        assert result.passed is False
        assert "count" in result.details

    def test_dict_protocol_non_dict_value(self):
        ei = EvaluationInterface()
        result = ei.verify_satisfies("not_a_dict", {"name": str})
        assert result.passed is False

    def test_type_protocol_pass(self):
        ei = EvaluationInterface()
        result = ei.verify_satisfies("hello", str)
        assert result.passed is True

    def test_type_protocol_fail(self):
        ei = EvaluationInterface()
        result = ei.verify_satisfies(42, str)
        assert result.passed is False

    def test_string_protocol_pass(self):
        ei = EvaluationInterface()
        result = ei.verify_satisfies("hello", "str")
        assert result.passed is True

    def test_string_protocol_fail(self):
        ei = EvaluationInterface()
        result = ei.verify_satisfies(42, "str")
        assert result.passed is False


class TestVerifySemantic:
    """Semantic verification tests."""

    def test_numeric_positive(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("is positive", 42)
        assert result.passed is True

    def test_numeric_negative_fail(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("is positive", -5)
        assert result.passed is False

    def test_numeric_greater_than(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("greater than 10", 15)
        assert result.passed is True

    def test_numeric_greater_than_fail(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("greater than 10", 5)
        assert result.passed is False

    def test_numeric_less_than(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("less than 10", 5)
        assert result.passed is True

    def test_numeric_zero(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("is zero", 0)
        assert result.passed is True

    def test_string_contains(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic('contains "hello"', "hello world")
        assert result.passed is True

    def test_string_contains_fail(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic('contains "xyz"', "hello world")
        assert result.passed is False

    def test_string_not_empty(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("not empty", "hello")
        assert result.passed is True

    def test_string_empty_fail(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("not empty", "")
        assert result.passed is False

    def test_bool_true(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("is true", True)
        assert result.passed is True

    def test_bool_false_fail(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("is true", False)
        assert result.passed is False

    def test_list_not_empty(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("not empty", [1, 2, 3])
        assert result.passed is True

    def test_list_empty_fail(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("not empty", [])
        assert result.passed is False

    def test_list_length(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("length >= 3", [1, 2, 3, 4])
        assert result.passed is True

    def test_dict_not_empty(self):
        ei = EvaluationInterface()
        result = ei.verify_semantic("not empty", {"a": 1})
        assert result.passed is True


class TestVerifyBehavioral:
    """Behavioral trace verification tests."""

    def test_all_invariants_pass(self):
        ei = EvaluationInterface()
        trace = BehavioralTrace(
            steps=[
                {"success": True, "observation": "step 1"},
                {"success": True, "observation": "step 2"},
            ],
            invariants=["success is true"],
        )
        result = ei.verify_behavioral(trace)
        assert result.passed is True

    def test_invariant_violated(self):
        ei = EvaluationInterface()
        trace = BehavioralTrace(
            steps=[
                {"success": True, "observation": "step 1"},
                {"success": False, "error": "failed", "observation": "step 2"},
            ],
            invariants=["success is true"],
        )
        result = ei.verify_behavioral(trace)
        assert result.passed is False

    def test_assertion_on_final_step(self):
        ei = EvaluationInterface()
        trace = BehavioralTrace(
            steps=[
                {"success": True, "observation": "step 1"},
                {"success": True, "observation": "final"},
            ],
            assertions=["observation not empty"],
        )
        result = ei.verify_behavioral(trace)
        assert result.passed is True

    def test_empty_trace(self):
        ei = EvaluationInterface()
        trace = BehavioralTrace(steps=[], invariants=["success is true"])
        result = ei.verify_behavioral(trace)
        assert result.passed is True


class TestVerifyMethod:
    """Custom method verification tests."""

    def test_method_returns_true(self):
        ei = EvaluationInterface()
        result = ei.verify_method(lambda v: v > 0, 42)
        assert result.passed is True

    def test_method_returns_false(self):
        ei = EvaluationInterface()
        result = ei.verify_method(lambda v: v > 0, -5)
        assert result.passed is False

    def test_method_returns_verify_result(self):
        ei = EvaluationInterface()
        def custom_check(v):
            return VerifyResult(passed=v > 0, verify_type="method", target=str(v), condition="custom", details="ok")
        result = ei.verify_method(custom_check, 42)
        assert result.passed is True

    def test_method_raises_exception(self):
        ei = EvaluationInterface()
        def failing_check(v):
            raise ValueError("check failed")
        result = ei.verify_method(failing_check, 42)
        assert result.passed is False
        assert "check failed" in result.details


class TestVerifyResult:
    """VerifyResult data structure tests."""

    def test_to_dict(self):
        vr = VerifyResult(passed=True, verify_type="satisfies", target="x", condition="int", details="ok")
        d = vr.to_dict()
        assert d["passed"] is True
        assert d["verify_type"] == "satisfies"

    def test_correction_hint(self):
        vr = VerifyResult(passed=False, verify_type="semantic", target="x", condition=">0",
                          details="fail", correction_hint="Make value positive")
        assert vr.correction_hint == "Make value positive"


class TestEvaluationStats:
    """Evaluation statistics tests."""

    def test_stats_tracking(self):
        ei = EvaluationInterface()
        ei.verify_satisfies("hello", str)
        ei.verify_satisfies(42, str)
        stats = ei.get_stats()
        assert stats["total_verifications"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1

    def test_clear(self):
        ei = EvaluationInterface()
        ei.verify_satisfies("hello", str)
        ei.clear()
        stats = ei.get_stats()
        assert stats["total_verifications"] == 0


# ═══════════════════════════════════════════════════════════════════════
#  LLMRouter Tests
# ═══════════════════════════════════════════════════════════════════════

class TestModelRequirement:
    """ModelRequirement data structure tests."""

    def test_default_requirement(self):
        req = ModelRequirement()
        assert req.task_type == "general"

    def test_coding_requirement(self):
        req = ModelRequirement(task_type="coding", min_coding=0.8)
        assert req.min_coding == 0.8

    def test_to_dict(self):
        req = ModelRequirement(task_type="reasoning", min_reasoning=0.9)
        d = req.to_dict()
        assert d["task_type"] == "reasoning"


class TestModelInfo:
    """ModelInfo matching and scoring tests."""

    def test_matches_requirement(self):
        model = ModelInfo(
            model_id="test-model",
            provider="openai",
            capabilities={"reasoning": 0.9, "coding": 0.8},
            context_window=128000,
        )
        req = ModelRequirement(min_reasoning=0.7, min_coding=0.7)
        assert model.matches_requirement(req)

    def test_fails_requirement(self):
        model = ModelInfo(
            model_id="test-model",
            provider="openai",
            capabilities={"reasoning": 0.5, "coding": 0.5},
            context_window=4096,
        )
        req = ModelRequirement(min_reasoning=0.8)
        assert not model.matches_requirement(req)

    def test_context_window_check(self):
        model = ModelInfo(
            model_id="test-model",
            provider="openai",
            capabilities={"reasoning": 0.9},
            context_window=4096,
        )
        req = ModelRequirement(min_context_window=100000)
        assert not model.matches_requirement(req)

    def test_preferred_provider(self):
        model = ModelInfo(
            model_id="test-model",
            provider="openai",
            capabilities={"reasoning": 0.9},
            context_window=128000,
        )
        req = ModelRequirement(preferred_provider="local")
        assert not model.matches_requirement(req)

    def test_score_higher_for_better_match(self):
        model_a = ModelInfo(
            model_id="model-a", provider="openai",
            capabilities={"reasoning": 0.9, "coding": 0.9},
            context_window=200000, cost_per_1m_input=1.0,
        )
        model_b = ModelInfo(
            model_id="model-b", provider="openai",
            capabilities={"reasoning": 0.5, "coding": 0.5},
            context_window=8000, cost_per_1m_input=10.0,
        )
        req = ModelRequirement(min_reasoning=0.5, min_coding=0.5)
        assert model_a.score_for_requirement(req) > model_b.score_for_requirement(req)


class TestLLMRouter:
    """LLMRouter routing and chat tests."""

    def test_default_models_registered(self):
        router = LLMRouter()
        models = router.get_models()
        model_ids = {model.model_id for model in models}
        assert len(models) >= 3
        assert {"minimax-m2.5", "deepseek-chat", "glm-5"}.issubset(model_ids)
        assert router.get_stats()["default_model"] == "minimax-m2.5"

    def test_route_coding_task(self):
        router = LLMRouter()
        req = ModelRequirement(task_type="coding", min_coding=0.8)
        model = router.route(req)
        assert model is not None
        assert model.capabilities["coding"] >= 0.8

    def test_route_reasoning_task(self):
        router = LLMRouter()
        req = ModelRequirement(task_type="reasoning", min_reasoning=0.8)
        model = router.route(req)
        assert model is not None
        assert model.capabilities["reasoning"] >= 0.8

    def test_route_no_match_falls_back_to_default(self):
        router = LLMRouter()
        req = ModelRequirement(min_vision=1.0)  # No model has perfect vision
        model = router.route(req)
        # Should fall back to default model
        assert model is not None

    def test_route_with_provider_preference(self):
        router = LLMRouter()
        req = ModelRequirement(preferred_provider="default", min_reasoning=0.5)
        model = router.route(req)
        assert model is not None
        assert model.provider == "default"

    def test_chat_with_routing(self):
        router = LLMRouter()
        req = ModelRequirement(task_type="general")
        response = router.chat(
            messages=[{"role": "user", "content": "Hello"}],
            requirement=req,
        )
        assert "content" in response
        assert "model_id" in response
        assert response.get("error") is None

    def test_chat_with_specific_model(self):
        router = LLMRouter()
        response = router.chat(
            messages=[{"role": "user", "content": "Hello"}],
            model_id="deepseek-chat",
        )
        assert response["model_id"] == "deepseek-chat"

    def test_provider_config_uses_default_compatible_endpoint(self):
        router = LLMRouter()
        model = router.get_model("minimax-m2.5")
        assert model is not None
        _api_key, base_url = router._provider_config(model)
        assert base_url.endswith("/v1")

    def test_chat_unknown_model(self):
        router = LLMRouter()
        response = router.chat(
            messages=[{"role": "user", "content": "Hello"}],
            model_id="nonexistent-model",
        )
        assert response.get("error") is not None

    def test_build_fallback_chain(self):
        router = LLMRouter()
        req = ModelRequirement(min_coding=0.5)
        chain = router.build_fallback_chain(req)
        assert len(chain) >= 2  # At least 2 models match

    def test_register_custom_model(self):
        router = LLMRouter()
        custom = ModelInfo(
            model_id="custom-model",
            provider="local",
            capabilities={"reasoning": 0.3, "coding": 0.3},
            context_window=4096,
        )
        router.register_model(custom)
        assert router.get_model("custom-model") is not None

    def test_unregister_model(self):
        router = LLMRouter()
        router.register_model(ModelInfo(
            model_id="temp-model", provider="local",
            capabilities={}, context_window=4096,
        ))
        assert router.unregister_model("temp-model")
        assert router.get_model("temp-model") is None

    def test_stats(self):
        router = LLMRouter()
        router.route(ModelRequirement(task_type="coding", min_coding=0.8))
        stats = router.get_stats()
        assert stats["route_count"] == 1
        assert stats["registered_models"] >= 3

    def test_clear(self):
        router = LLMRouter()
        router.clear()
        assert router.get_stats()["registered_models"] == 0


# ═══════════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end: EvaluationInterface + LLMRouter."""

    def test_verify_then_route_for_correction(self):
        """Verify failure triggers model routing for correction."""
        ei = EvaluationInterface()
        router = LLMRouter()

        # Verify output
        result = ei.verify_satisfies(
            {"name": "test"},  # Missing 'count'
            {"name": str, "count": int},
        )
        assert result.passed is False

        # Route to a capable model for correction
        req = ModelRequirement(task_type="coding", min_coding=0.7)
        model = router.route(req)
        assert model is not None

        # Simulate correction
        correction_prompt = f"Fix the output: {result.correction_hint}"
        response = router.chat(
            messages=[{"role": "user", "content": correction_prompt}],
            requirement=req,
        )
        assert response.get("error") is None

    def test_verify_in_autoloop_context(self):
        """Verify can be used within autoloop for self-correction."""
        from src.runtime.harness_kernel import HarnessKernel, HarnessRuntimeMode, AutoLoopConfig, StepResult

        ei = EvaluationInterface()
        k = HarnessKernel(mode=HarnessRuntimeMode.WARN)

        config = AutoLoopConfig(max_steps=3, exit_when="resolved")

        step_num = 0
        def step_fn():
            nonlocal step_num
            step_num += 1

            if step_num == 1:
                # First attempt: wrong type
                result = ei.verify_satisfies("not_a_dict", {"name": str})
                return StepResult(
                    action="verify",
                    observation=f"Verify failed: {result.correction_hint}",
                    success=False,
                )
            else:
                # Corrected
                result = ei.verify_satisfies({"name": "fixed"}, {"name": str})
                return StepResult(
                    action="verify",
                    observation="Task resolved" if result.passed else "Still failing",
                    success=result.passed,
                )

        loop_result = k.run_autoloop(config, step_fn)
        assert loop_result.exit_reason in ("exit_when_met", "max_steps")
