# 此文件由 Nexa v0.5 Code Generator 自动生成
import os
import json
import pydantic
from src.runtime.stdlib import STD_NAMESPACE_MAP
from src.runtime.agent import NexaAgent
from src.runtime.evaluator import nexa_semantic_eval, nexa_intent_routing
from src.runtime.orchestrator import join_agents, nexa_pipeline
from src.runtime.dag_orchestrator import dag_fanout, dag_merge, dag_branch, dag_parallel_map, SmartRouter
from src.runtime.memory import global_memory
from src.runtime.stdlib import STD_TOOLS_SCHEMA, STD_NAMESPACE_MAP
from src.runtime.secrets import nexa_secrets
from src.runtime.core import nexa_fallback, nexa_img_loader
from src.runtime.mcp_client import fetch_mcp_tools
from src.runtime.meta import runtime, get_loop_count, get_last_result, set_loop_count, set_last_result
from src.runtime.reason import reason, reason_float, reason_int, reason_bool, reason_str, reason_dict, reason_list, reason_model
from src.runtime.hitl import wait_for_human, ApprovalStatus, HITLManager

# ==========================================
# [Target Code] 自动生成的编排逻辑
# ==========================================

class Summary(pydantic.BaseModel):
    value: str

    @pydantic.field_validator("value")
    def validate_semantic(cls, v):
        """语义约束: A concise summary"""
        # TODO: 使用 LLM 进行语义验证
        return v

class Sentiment(pydantic.BaseModel):
    value: str

    @pydantic.field_validator("value")
    def validate_semantic(cls, v):
        """语义约束: positive, negative, or neutral"""
        # TODO: 使用 LLM 进行语义验证
        return v

class Confidence(pydantic.BaseModel):
    value: float

    @pydantic.field_validator("value")
    def validate_semantic(cls, v):
        """语义约束: A value between 0.0 and 1.0"""
        # TODO: 使用 LLM 进行语义验证
        return v

PlainInt = int

PlainStr = str

Tags = list[str]

Scores = dict[str, float]

CustomRef = Summary

Summarizer = NexaAgent(
    name="Summarizer",
    prompt="Summarize the given text concisely",
    model="minimax:minimax-m2.5",
    role="Text Summarization Agent",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

def flow_main():
    print("Semantic Types Test - v1.0.2")

if __name__ == "__main__":
    flow_main()
