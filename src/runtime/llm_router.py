"""
Nexa v2.0 LLMRouter — 模型无关动态路由

LLMRouter 根据能力需求动态选择最优模型，实现：
  - MODEL_CAPABILITIES: 模型能力矩阵
  - route(): 根据 ModelRequirement 动态路由
  - chat(): 统一 LLM 调用接口 + fallback chain
  - 模型无关: 支持 OpenAI/Anthropic/本地模型

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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

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
    model_id: str = ""               # e.g., "gpt-4o", "claude-sonnet-4-20250514"
    provider: str = ""               # openai | anthropic | local
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
        model_id="gpt-4o",
        provider="openai",
        display_name="GPT-4o",
        capabilities={"reasoning": 0.9, "coding": 0.85, "vision": 0.9, "tool_use": 0.9},
        context_window=128000,
        cost_per_1m_input=2.50,
        cost_per_1m_output=10.00,
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
        is_default=True,
    ),
    ModelInfo(
        model_id="gpt-4o-mini",
        provider="openai",
        display_name="GPT-4o Mini",
        capabilities={"reasoning": 0.7, "coding": 0.65, "vision": 0.7, "tool_use": 0.7},
        context_window=128000,
        cost_per_1m_input=0.15,
        cost_per_1m_output=0.60,
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="claude-sonnet-4-20250514",
        provider="anthropic",
        display_name="Claude Sonnet 4",
        capabilities={"reasoning": 0.9, "coding": 0.9, "vision": 0.85, "tool_use": 0.9},
        context_window=200000,
        cost_per_1m_input=3.00,
        cost_per_1m_output=15.00,
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="claude-haiku-4-20250514",
        provider="anthropic",
        display_name="Claude Haiku 4",
        capabilities={"reasoning": 0.6, "coding": 0.55, "vision": 0.5, "tool_use": 0.6},
        context_window=200000,
        cost_per_1m_input=0.80,
        cost_per_1m_output=4.00,
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
    ),
    ModelInfo(
        model_id="deepseek-v3",
        provider="deepseek",
        display_name="DeepSeek V3",
        capabilities={"reasoning": 0.85, "coding": 0.85, "vision": 0.0, "tool_use": 0.8},
        context_window=128000,
        cost_per_1m_input=0.27,
        cost_per_1m_output=1.10,
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

    def __init__(self) -> None:
        self._models: Dict[str, ModelInfo] = {}
        self._default_model_id: Optional[str] = None
        self._fallback_chain: List[str] = []  # Ordered fallback model IDs
        self._route_count = 0
        self._fallback_count = 0

        # Register default models
        for model in DEFAULT_MODELS:
            self.register_model(model)
            if model.is_default:
                self._default_model_id = model.model_id

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
        """
        Call a specific model.

        This is a stub that returns a simulated response.
        In production, this would call the actual LLM API.
        """
        # Simulate a response for testing
        last_message = messages[-1]["content"] if messages else ""
        return {
            "content": f"[{model.display_name}] Response to: {last_message[:50]}...",
            "model_id": model.model_id,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "finish_reason": "stop",
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