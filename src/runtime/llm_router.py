"""
Nexa v2.0 LLMRouter — 模型无关动态路由

LLMRouter 根据能力需求动态选择最优模型，实现：
  - MODEL_CAPABILITIES: 模型能力矩阵
  - route(): 根据 ModelRequirement 动态路由
  - chat(): 统一 LLM 调用接口 + fallback chain
  - 模型无关: 支持 OpenAI-compatible provider 和本地模型

Design Rationale:
  - 能力矩阵: 每个模型声明其能力 (reasoning/coding/vision/tool_use 等)
  - 动态路由: 根据任务需求自动选择最优模型
  - Fallback chain: 主模型失败时自动降级到备选模型
  - v1.x 兼容: 固定 model 字符串在 --harness=off 下继续工作

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.5
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .secrets import DEFAULT_OPENAI_COMPATIBLE_BASE_URL, nexa_secrets

logger = logging.getLogger("nexa.llm_router")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ModelRequirement:
    """Requirements for model selection."""
    min_reasoning: float = 0.0       # 0.0-1.0 reasoning capability needed
    min_coding: float = 0.0          # 0.0-1.0 coding capability needed
    min_vision: float = 0.0          # 0.0-1.0 vision capability needed
    min_tool_use: float = 0.0        # 0.0-1.0 tool use capability needed
    min_context_window: int = 4096   # Minimum context window size
    max_cost: float = float('inf')   # Maximum cost per 1M tokens
    preferred_provider: Optional[str] = None  # Preferred provider
    task_type: str = "general"       # general | coding | reasoning | vision | tool_use

    def to_dict(self) -> Dict:
        return {
            "min_reasoning": self.min_reasoning,
            "min_coding": self.min_coding,
            "min_vision": self.min_vision,
            "min_tool_use": self.min_tool_use,
            "min_context_window": self.min_context_window,
            "max_cost": self.max_cost,
            "preferred_provider": self.preferred_provider,
            "task_type": self.task_type,
        }


@dataclass
class ModelInfo:
    """Information about a registered model."""
    model_id: str = ""               # e.g., "minimax-m2.5", "deepseek-chat", "glm-5"
    provider: str = ""               # default | openai-compatible | local
    display_name: str = ""
    capabilities: Dict[str, float] = field(default_factory=dict)
    context_window: int = 4096
    cost_per_1m_input: float = 0.0
    cost_per_1m_output: float = 0.0
    supports_tools: bool = False
    supports_vision: bool = False
    supports_streaming: bool = False
    is_default: bool = False

    def to_dict(self) -> Dict:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "display_name": self.display_name,
            "capabilities": self.capabilities,
            "context_window": self.context_window,
            "cost_per_1m_input": self.cost_per_1m_input,
            "cost_per_1m_output": self.cost_per_1m_output,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
        }

    def matches_requirement(self, req: ModelRequirement) -> bool:
        """Check if this model meets the given requirements."""
        caps = self.capabilities

        if caps.get("reasoning", 0) < req.min_reasoning:
            return False
        if caps.get("coding", 0) < req.min_coding:
            return False
        if caps.get("vision", 0) < req.min_vision:
            return False
        if caps.get("tool_use", 0) < req.min_tool_use:
            return False
        if self.context_window < req.min_context_window:
            return False
        if self.cost_per_1m_input > req.max_cost:
            return False
        if req.preferred_provider and self.provider != req.preferred_provider:
            return False

        return True

    def score_for_requirement(self, req: ModelRequirement) -> float:
        """Score this model for a given requirement (higher = better)."""
        caps = self.capabilities
        score = 0.0

        # Weighted capability match
        score += caps.get("reasoning", 0) * req.min_reasoning * 2
        score += caps.get("coding", 0) * req.min_coding * 2
        score += caps.get("vision", 0) * req.min_vision * 2
        score += caps.get("tool_use", 0) * req.min_tool_use * 2

        # Context window bonus
        score += min(self.context_window / 100000, 1.0)

        # Cost penalty (lower cost = higher score)
        if self.cost_per_1m_input > 0:
            score += max(0, 1.0 - self.cost_per_1m_input / 20.0)

        # Preferred provider bonus
        if req.preferred_provider and self.provider == req.preferred_provider:
            score += 2.0

        return score


# ═══════════════════════════════════════════════════════════════════════
#  Default Model Capabilities Matrix
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_MODELS: List[ModelInfo] = [
    ModelInfo(
        model_id="minimax-m2.5",
        provider="default",
        display_name="MiniMax M2.5",
        capabilities={"reasoning": 0.9, "coding": 0.9, "vision": 0.0, "tool_use": 0.85},
        context_window=128000,
        supports_tools=True,
        supports_vision=False,
        supports_streaming=True,
        is_default=True,
    ),
    ModelInfo(
        model_id="deepseek-chat",
        provider="default",
        display_name="DeepSeek Chat",
        capabilities={"reasoning": 0.75, "coding": 0.8, "vision": 0.0, "tool_use": 0.75},
        context_window=128000,
        supports_tools=True,
        supports_vision=False,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="glm-5",
        provider="default",
        display_name="GLM-5",
        capabilities={"reasoning": 0.92, "coding": 0.86, "vision": 0.0, "tool_use": 0.85},
        context_window=128000,
        supports_tools=True,
        supports_vision=False,
        supports_streaming=True,
    ),
]


# ═══════════════════════════════════════════════════════════════════════
#  LLMRouter — Model-Agnostic Dynamic Routing
# ═══════════════════════════════════════════════════════════════════════

class LLMRouter:
    """
    Model-agnostic dynamic router for LLM calls.

    Implements:
      - route(): Select the best model for given requirements
      - chat(): Unified LLM call with fallback chain
      - register_model(): Register a custom model
      - get_models(): List all registered models

    Usage:
        router = LLMRouter()
        model = router.route(ModelRequirement(task_type="coding", min_coding=0.8))
        response = router.chat(messages=[{"role": "user", "content": "Write code"}])
    """

    def __init__(self, mock: Optional[bool] = None) -> None:
        self._models: Dict[str, ModelInfo] = {}
        self._default_model_id: Optional[str] = None
        self._fallback_chain: List[str] = []  # Ordered fallback model IDs
        self._route_count = 0
        self._fallback_count = 0
        self._mock = mock if mock is not None else os.environ.get("NEXA_LLMROUTER_MOCK", "1").lower() in {"1", "true", "yes", "on"}

        for model in DEFAULT_MODELS:
            self.register_model(model)
            if model.is_default:
                self._default_model_id = model.model_id
        self._register_models_from_secrets()

    def _register_models_from_secrets(self) -> None:
        """Register MODEL_NAME entries from secrets.nxs without requiring real API calls."""
        model_config = nexa_secrets.get_model_config()
        role_defaults = {
            "strong": {"reasoning": 0.9, "coding": 0.9, "tool_use": 0.85},
            "weak": {"reasoning": 0.7, "coding": 0.75, "tool_use": 0.7},
            "super": {"reasoning": 0.95, "coding": 0.9, "tool_use": 0.85},
        }
        for role, model_id in model_config.items():
            if not model_id:
                continue
            existing = self._models.get(model_id)
            if existing:
                if role == "strong":
                    existing.is_default = True
                    self._default_model_id = model_id
                continue
            caps = {"vision": 0.0, **role_defaults.get(role, role_defaults["weak"])}
            self.register_model(ModelInfo(
                model_id=model_id,
                provider="default",
                display_name=model_id,
                capabilities=caps,
                context_window=128000,
                supports_tools=True,
                supports_vision=False,
                supports_streaming=True,
                is_default=(role == "strong"),
            ))

    # ─── Model Registration ───

    def register_model(self, model: ModelInfo) -> None:
        """Register a model in the router."""
        self._models[model.model_id] = model
        if model.is_default:
            self._default_model_id = model.model_id
        logger.info(f"Registered model: {model.model_id} ({model.provider})")

    def unregister_model(self, model_id: str) -> bool:
        """Unregister a model."""
        if model_id in self._models:
            del self._models[model_id]
            if self._default_model_id == model_id:
                self._default_model_id = None
            return True
        return False

    def get_models(self) -> List[ModelInfo]:
        """Get all registered models."""
        return list(self._models.values())

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get a specific model by ID."""
        return self._models.get(model_id)

    # ─── Routing ───

    def route(self, requirement: ModelRequirement) -> Optional[ModelInfo]:
        """
        Select the best model for the given requirements.

        Algorithm:
          1. Filter models that meet all minimum requirements
          2. Score each candidate
          3. Return the highest-scoring model

        Args:
            requirement: ModelRequirement with capability thresholds

        Returns:
            Best matching ModelInfo, or None if no model matches
        """
        self._route_count += 1

        candidates = [
            model for model in self._models.values()
            if model.matches_requirement(requirement)
        ]

        if not candidates:
            logger.warning(f"No model matches requirement: {requirement.to_dict()}")
            # Fall back to default model
            if self._default_model_id:
                return self._models.get(self._default_model_id)
            return None

        # Score and sort candidates
        candidates.sort(
            key=lambda m: m.score_for_requirement(requirement),
            reverse=True,
        )

        selected = candidates[0]
        logger.info(f"Routed to {selected.model_id} for task_type={requirement.task_type}")
        return selected

    def build_fallback_chain(self, requirement: ModelRequirement) -> List[str]:
        """
        Build an ordered fallback chain for the given requirements.

        Returns:
            List of model IDs in fallback order
        """
        candidates = [
            model for model in self._models.values()
            if model.matches_requirement(requirement)
        ]

        candidates.sort(
            key=lambda m: m.score_for_requirement(requirement),
            reverse=True,
        )

        return [m.model_id for m in candidates]

    # ─── Chat Interface ───

    def chat(
        self,
        messages: List[Dict],
        requirement: Optional[ModelRequirement] = None,
        model_id: Optional[str] = None,
        fallback: bool = True,
        **kwargs,
    ) -> Dict:
        """
        Unified LLM chat interface with automatic routing and fallback.

        Args:
            messages: List of message dicts with 'role' and 'content'
            requirement: Optional ModelRequirement for routing
            model_id: Optional specific model ID (overrides routing)
            fallback: Whether to use fallback chain on failure
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Dict with 'content', 'model_id', 'usage', 'finish_reason'
        """
        # Determine model
        if model_id:
            model = self._models.get(model_id)
            if not model:
                return {
                    "content": "",
                    "model_id": model_id,
                    "error": f"Model '{model_id}' not found",
                    "finish_reason": "error",
                }
        elif requirement:
            model = self.route(requirement)
        else:
            model = self._models.get(self._default_model_id) if self._default_model_id else None

        if not model:
            return {
                "content": "",
                "model_id": "unknown",
                "error": "No model available",
                "finish_reason": "error",
            }

        # Build fallback chain
        fallback_chain = []
        if fallback and requirement:
            fallback_chain = self.build_fallback_chain(requirement)
            # Remove the primary model from fallback chain
            fallback_chain = [m for m in fallback_chain if m != model.model_id]

        # Try primary model
        result = self._call_model(model, messages, **kwargs)
        if result.get("error") is None:
            return result

        # Try fallback chain
        for fallback_id in fallback_chain:
            self._fallback_count += 1
            fallback_model = self._models.get(fallback_id)
            if not fallback_model:
                continue

            logger.warning(f"Falling back to {fallback_id} after {model.model_id} failed")
            result = self._call_model(fallback_model, messages, **kwargs)
            if result.get("error") is None:
                return result

        # All models failed
        return {
            "content": "",
            "model_id": model.model_id,
            "error": f"All models failed (tried {1 + len(fallback_chain)} models)",
            "finish_reason": "error",
        }

    def _call_model(self, model: ModelInfo, messages: List[Dict], **kwargs) -> Dict:
        """Call a specific model through its provider adapter."""
        if self._mock:
            return self._call_mock(model, messages)

        if model.provider in {"openai", "deepseek", "minimax", "default", "openai-compatible"}:
            return self._call_openai_compatible(model, messages, **kwargs)
        if model.provider == "local":
            return {
                "content": "",
                "model_id": model.model_id,
                "error": "Local provider is not configured in this runtime",
                "finish_reason": "error",
            }
        return {
            "content": "",
            "model_id": model.model_id,
            "error": f"Unsupported provider: {model.provider}",
            "finish_reason": "error",
        }

    def _call_mock(self, model: ModelInfo, messages: List[Dict]) -> Dict:
        """Deterministic no-network adapter used by tests and offline tooling."""
        last_message = messages[-1].get("content", "") if messages else ""
        return {
            "content": f"[{model.display_name}] Response to: {str(last_message)[:50]}...",
            "model_id": model.model_id,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "finish_reason": "stop",
        }

    def _provider_config(self, model: ModelInfo) -> Tuple[str, str]:
        api_key, base_url = nexa_secrets.get_provider_config(model.provider)
        if not api_key:
            api_key = nexa_secrets.get(f"{model.provider.upper()}_API_KEY") or nexa_secrets.get("API_KEY")
        if not base_url:
            base_url = nexa_secrets.get(f"{model.provider.upper()}_BASE_URL") or nexa_secrets.get("BASE_URL")

        if base_url:
            return api_key, base_url
        if model.provider in {"default", "openai", "openai-compatible", "minimax", "deepseek"}:
            return api_key, DEFAULT_OPENAI_COMPATIBLE_BASE_URL
        return api_key, ""

    def _call_openai_compatible(self, model: ModelInfo, messages: List[Dict], **kwargs) -> Dict:
        try:
            from openai import OpenAI

            api_key, base_url = self._provider_config(model)
            if not api_key:
                return self._error_result(model, f"API key not configured for provider '{model.provider}'")

            request_kwargs = dict(kwargs)
            request_kwargs.pop("fallback", None)
            response = OpenAI(api_key=api_key, base_url=base_url).chat.completions.create(
                model=model.model_id,
                messages=messages,
                **request_kwargs,
            )
            choice = response.choices[0]
            usage = getattr(response, "usage", None)
            return {
                "content": choice.message.content or "",
                "model_id": model.model_id,
                "usage": usage.model_dump() if hasattr(usage, "model_dump") else (dict(usage) if usage else {}),
                "finish_reason": choice.finish_reason,
            }
        except Exception as e:
            return self._error_result(model, str(e))

    def _error_result(self, model: ModelInfo, error: str) -> Dict:
        return {
            "content": "",
            "model_id": model.model_id,
            "error": error,
            "finish_reason": "error",
        }

    # ─── Statistics ───

    def get_stats(self) -> Dict:
        """Get router statistics."""
        return {
            "registered_models": len(self._models),
            "default_model": self._default_model_id,
            "route_count": self._route_count,
            "fallback_count": self._fallback_count,
            "model_ids": list(self._models.keys()),
        }

    def clear(self) -> None:
        """Clear all models and reset (for testing)."""
        self._models = {}
        self._default_model_id = None
        self._fallback_chain = []
        self._route_count = 0
        self._fallback_count = 0
