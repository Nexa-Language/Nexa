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

Writer = NexaAgent(
    name="Writer",
    prompt="Write a short 2-sentence poem about AGI.",
    model="minimax-m2.5",
    role="Writer",
    memory_scope="local",
    tools=[]
)

Critic = NexaAgent(
    name="Critic",
    prompt="Review the poem and suggest exactly one concrete poetry improvement.",
    model="deepseek-chat",
    role="Critic",
    memory_scope="local",
    tools=[]
)

Editor = NexaAgent(
    name="Editor",
    prompt="Improve the poem based on the critic feedback.",
    model="minimax-m2.5",
    role="Editor",
    memory_scope="local",
    tools=[]
)

def flow_main():
    poem = Writer.run("Write a poem about Artificial General Intelligence")
    while True:
        feedback = Critic.run(poem)
        poem = Editor.run(poem, feedback)
        if nexa_semantic_eval("Poem has rhyme and mentions singularity", str(locals())):
            break


if __name__ == "__main__":
    flow_main()
