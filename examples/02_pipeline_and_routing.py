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

Router = NexaAgent(
    name="Router",
    prompt="",
    model="minimax-m2.5",
    role="User Intent Router",
    memory_scope="local",
    tools=[]
)

WeatherBot = NexaAgent(
    name="WeatherBot",
    prompt="You fetch and report the weather natively.",
    model="minimax-m2.5",
    role="Weather Expert",
    memory_scope="local",
    tools=[]
)

NewsBot = NexaAgent(
    name="NewsBot",
    prompt="You summarize today's big news.",
    model="minimax-m2.5",
    role="News Expert",
    memory_scope="local",
    tools=[]
)

SmallTalkBot = NexaAgent(
    name="SmallTalkBot",
    prompt="You are a very friendly ChatBot for casual conversations.",
    model="minimax-m2.5",
    role="Casual conversationalist",
    memory_scope="local",
    tools=[]
)

Translator = NexaAgent(
    name="Translator",
    prompt="Translate everything to French.",
    model="minimax-m2.5",
    role="Translator",
    memory_scope="local",
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
