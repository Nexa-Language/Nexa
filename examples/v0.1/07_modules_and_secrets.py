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

# ==========================================
# [Target Code] 自动生成的编排逻辑
# ==========================================

__tool_echo_tool_schema = {
    "name": "echo_tool",
    "description": "Echo back the input string",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string"}
        },
        "required": ["text"]
    }
}

LibAgent = NexaAgent(
    name="LibAgent",
    prompt="You are a library agent. Your job is to format text.",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[__tool_echo_tool_schema]
)

MainAgent = NexaAgent(
    name="MainAgent",
    prompt="You are the main agent.",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[STD_TOOLS_SCHEMA['shell_exec'], STD_TOOLS_SCHEMA['shell_which']]
)

def flow_main():
    my_key = nexa_secrets.get("MY_TEST_KEY")
    MainAgent.run("Print this secret key without execution: ", my_key)
    LibAgent.run("Echo this: module included successfully.")

if __name__ == "__main__":
    flow_main()
