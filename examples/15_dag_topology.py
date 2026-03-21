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

Researcher = NexaAgent(
    name="Researcher",
    prompt="You are a research specialist. Analyze the given topic and provide detailed findings.",
    model="deepseek/deepseek-chat",
    role="Senior Researcher",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[]
)

Analyst = NexaAgent(
    name="Analyst",
    prompt="You are a data analyst. Provide quantitative analysis and insights.",
    model="deepseek/deepseek-chat",
    role="Data Analyst",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[]
)

Writer = NexaAgent(
    name="Writer",
    prompt="You are a technical writer. Synthesize information into clear, engaging content.",
    model="deepseek/deepseek-chat",
    role="Technical Writer",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[]
)

Reviewer = NexaAgent(
    name="Reviewer",
    prompt="You are a quality reviewer. Ensure content is accurate, coherent, and well-structured.",
    model="deepseek/deepseek-chat",
    role="Quality Reviewer",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[]
)

UrgentHandler = NexaAgent(
    name="UrgentHandler",
    prompt="Handle urgent requests with priority and efficiency.",
    model="deepseek/deepseek-chat",
    role="Urgent Response Handler",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[]
)

NormalHandler = NexaAgent(
    name="NormalHandler",
    prompt="Handle standard requests with thorough analysis.",
    model="deepseek/deepseek-chat",
    role="Standard Response Handler",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[]
)

def flow_main():
    simple_result = nexa_pipeline("What is AI?", [ Researcher, Writer ])
    print(simple_result)
    research_data = "Quantum Computing Applications"
    parallel_results = dag_fanout(research_data, [ Researcher, Analyst, Writer ])
    print("Parallel results:")
    print(parallel_results)
    merged_result = dag_merge([ Researcher, Analyst ], strategy="concat", merge_agent=Reviewer)
    print("Merged and reviewed:")
    print(merged_result)
    user_query = "URGENT: System outage detected"
    handled = dag_branch(user_query, lambda x: True, UrgentHandler, NormalHandler)
    print("Handled query:")
    print(handled)

if __name__ == "__main__":
    flow_main()
