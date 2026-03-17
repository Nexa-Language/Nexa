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

CachedAgent = NexaAgent(
    name="CachedAgent",
    prompt="You are a cached agent testing secrets and memory.",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=True,
    max_history_turns=2,
    experience="examples/my_memory.md",
    tools=[]
)

def flow_main():
    my_key = nexa_secrets.default.API_KEY
    CachedAgent.run("The API key is ", my_key)
    CachedAgent.run("Second message. Hello")
    CachedAgent.run("Third message. Compacting next?")

if __name__ == "__main__":
    flow_main()
