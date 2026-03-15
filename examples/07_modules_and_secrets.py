# 此文件由 Nexa v0.5 Code Generator 自动生成
import os
import json
from src.runtime.agent import NexaAgent
from src.runtime.evaluator import nexa_semantic_eval, nexa_intent_routing
from src.runtime.orchestrator import join_agents, nexa_pipeline
from src.runtime.memory import global_memory
from src.runtime.stdlib import STD_TOOLS_SCHEMA
from src.runtime.secrets import nexa_secrets

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
    tools=[__tool_echo_tool_schema]
)

MainAgent = NexaAgent(
    name="MainAgent",
    prompt="You are the main agent.",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    tools=[STD_TOOLS_SCHEMA['std_shell_execute']]
)

def flow_main():
    my_key = nexa_secrets.get("MY_TEST_KEY")
    MainAgent.run("Print this secret key without execution: ", my_key)
    LibAgent.run("Echo this: module included successfully.")

if __name__ == "__main__":
    flow_main()
