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

Writer = NexaAgent(
    name="Writer",
    prompt="Write a short 2-sentence poem about AGI.",
    model="minimax-m2.5",
    role="Writer",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Critic = NexaAgent(
    name="Critic",
    prompt="Review the poem and suggest exactly one concrete poetry improvement.",
    model="deepseek-chat",
    role="Critic",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Editor = NexaAgent(
    name="Editor",
    prompt="Improve the poem based on the critic feedback.",
    model="minimax-m2.5",
    role="Editor",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

def flow_main():
    poem = Writer.run("Write a poem about Artificial General Intelligence")
    set_loop_count(0)
    set_last_result(None)
    while True:
        set_loop_count(get_loop_count() + 1)
        feedback = Critic.run(poem)
        poem = Editor.run(poem, feedback)
        if nexa_semantic_eval("Poem has rhyme and mentions singularity", str(locals())):
            break


if __name__ == "__main__":
    flow_main()
