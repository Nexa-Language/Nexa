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
    recommendation: str

Reviewer = NexaAgent(
    name="Reviewer",
    prompt="审查代码并给出评分和总结",
    model="minimax-m2.5",
    role="代码审查员",
    memory_scope="local",
    stream=False,
    cache=False,
    protocol=ReviewResult,
    tools=[]
)

def flow_main():
    code = "def hello(): print('hello world')"
    result = Reviewer.run(code)
    print(str("评分: ") + str(result.score))
    print(str("总结: ") + str(result.summary))

if __name__ == "__main__":
    flow_main()
