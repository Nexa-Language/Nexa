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

class ReviewResult(pydantic.BaseModel):
    score: int
    summary: str

Coder = NexaAgent(
    name="Coder",
    prompt="Write a short Python implementation of quicksort.",
    model="minimax/minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[]
)

Reviewer = NexaAgent(
    name="Reviewer",
    prompt="Review the provided code. Give a score from 1 to 10 and a brief summary. Return as JSON.",
    model="deepseek/deepseek-chat",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    protocol=ReviewResult,
    tools=[]
)

HumanInterface = NexaAgent(
    name="HumanInterface",
    prompt="Show the review result to the human and summarize what to do based on their input.",
    model="minimax/minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[]
)

def flow_main():
    res = nexa_pipeline(Coder.run("Generate code"), [ Reviewer, HumanInterface ])

if __name__ == "__main__":
    flow_main()
