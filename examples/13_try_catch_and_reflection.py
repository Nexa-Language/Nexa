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

BaseAgent = NexaAgent(
    name="BaseAgent",
    prompt="I am a base agent.",
    model="deepseek-chat",
    role="",
    memory_scope="local",
    stream=False,
    tools=[]
)

def flow_main():
    try:
        print("尝试触发一个异常操作...")
        invalid = nexa_secrets.get("NOT_EXIST")["oops"]
        print(invalid)
    except Exception as err:
        print("成功捕获到异常:")
        print(err)
    try:
        SuperAgent = BaseAgent.clone(new_name="SuperAgent", model=nexa_secrets.get("MODEL_NAME")["super"])
        result = SuperAgent.run("Hello from the reflection test!")
        print("SuperAgent返回:", result)
    except Exception as e:
        print("API 调用受限，但动态反射对象被成功创建!")

if __name__ == "__main__":
    flow_main()
