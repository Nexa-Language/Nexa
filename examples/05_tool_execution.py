# 此文件由 Nexa v0.5 Code Generator 自动生成
import os
import json
from src.runtime.agent import NexaAgent
from src.runtime.evaluator import nexa_semantic_eval, nexa_intent_routing
from src.runtime.orchestrator import join_agents, nexa_pipeline
from src.runtime.memory import global_memory

# ==========================================
# [Target Code] 自动生成的编排逻辑
# ==========================================

__tool_calculate_hash_schema = {
    "name": "calculate_hash",
    "description": "Calculates the SHA256 string for any given input string.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string"}
        },
        "required": ["text"]
    }
}

CryptoBot = NexaAgent(
    name="CryptoBot",
    prompt="You are a crypto bot. When asked for a hash, you must use the calculate_hash tool to compute the actual hash.",
    model="minimax-m2.5",
    role="Cryptography Expert",
    memory_scope="local",
    tools=[__tool_calculate_hash_schema]
)

def flow_main():
    res = CryptoBot.run("Please compute the hash for 'Hello Nexa v0.5!'")

if __name__ == "__main__":
    flow_main()
