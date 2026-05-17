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

Router = NexaAgent(
    name="Router",
    prompt="",
    model="minimax-m2.5",
    role="User Intent Router",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

WeatherBot = NexaAgent(
    name="WeatherBot",
    prompt="You fetch and report the weather natively.",
    model="minimax-m2.5",
    role="Weather Expert",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

NewsBot = NexaAgent(
    name="NewsBot",
    prompt="You summarize today's big news. Use std.http_get tool to fetch news from news APIs or websites if available. If no tool is available, summarize based on your knowledge of recent major world events.",
    model="minimax-m2.5",
    role="News Expert",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

SmallTalkBot = NexaAgent(
    name="SmallTalkBot",
    prompt="You are a very friendly ChatBot for casual conversations.",
    model="minimax-m2.5",
    role="Casual conversationalist",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Translator = NexaAgent(
    name="Translator",
    prompt="You are a professional translation agent. Your ONLY task is to translate the input text to French. Do not respond conversationally. Do not comment on the source or content. Output ONLY the French translation, nothing else.",
    model="minimax-m2.5",
    role="Translator",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

def flow_main():
    req = "Tell me what is happening in the world today!"
    __matched_intent = nexa_intent_routing([ "Check weather", "Check daily news"], req)
    if __matched_intent == "Check weather":
        nexa_pipeline(WeatherBot.run(req), [ Translator ])
    elif __matched_intent == "Check daily news":
        nexa_pipeline(NewsBot.run(req), [ Translator ])
    else:
        SmallTalkBot.run(req)

if __name__ == "__main__":
    flow_main()
