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

# ==========================================
# [Target Code] 自动生成的编排逻辑
# ==========================================

__tool_get_weather_schema = {
    "name": "get_weather",
    "description": "Get current weather of a city",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "The name of the city, e.g., Beijing"
            }
        },
        "required": [
            "city"
        ]
    }
}
__tool_calculate_hash_schema = {
    "name": "calculate_hash",
    "description": "Calculate hash of string",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The string to hash"
            }
        },
        "required": [
            "text"
        ]
    }
}
StreamBot = NexaAgent(
    name="StreamBot",
    prompt="I am a helpful assistant. Call the calculate_hash tool to calculate the hash of 'Nexa' and then output 'Done!' via streaming.",
    model="minimax/minimax-m2.5",
    role="",
    memory_scope="persistent",
    stream=True,
    tools=[__tool_get_weather_schema, __tool_calculate_hash_schema]
)

def flow_main():
    msg = StreamBot.run("Please do your task.")

if __name__ == "__main__":
    flow_main()
