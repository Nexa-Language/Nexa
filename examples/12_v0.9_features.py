# 此文件由 Nexa v0.5 Code Generator 自动生成
import os
import json
import pydantic
from src.runtime.stdlib import STD_NAMESPACE_MAP
from src.runtime.agent import NexaAgent
from src.runtime.evaluator import nexa_semantic_eval, nexa_intent_routing
from src.runtime.orchestrator import join_agents, nexa_pipeline
from src.runtime.memory import global_memory
from src.runtime.stdlib import STD_TOOLS_SCHEMA, STD_NAMESPACE_MAP
from src.runtime.secrets import nexa_secrets
from src.runtime.core import nexa_fallback, nexa_img_loader
from src.runtime.mcp_client import fetch_mcp_tools

# ==========================================
# [Target Code] 自动生成的编排逻辑
# ==========================================

McpAgent = NexaAgent(
    name="McpAgent",
    prompt="",
    model="dummy_model",
    role="",
    memory_scope="local",
    stream=False,
    tools=[*fetch_mcp_tools('http://fake.url')]
)

def test_my_agent_test():
    msg = "hello"
    if nexa_semantic_eval("包含打招呼", msg, r"(hello|hi)"):
        msg = "matched"
    assert msg

if __name__ == "__main__":
    flow_main()
