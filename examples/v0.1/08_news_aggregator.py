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
    prompt="You are an intelligent news researcher. Your job is to fetch the current date, then fetch top news from a given URL, summarize the top 3 items, and save the result into a local file with the date included in the summary.",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    tools=[STD_TOOLS_SCHEMA['time_now'], STD_TOOLS_SCHEMA['time_diff'], STD_TOOLS_SCHEMA['http_get'], STD_TOOLS_SCHEMA['http_post'], STD_TOOLS_SCHEMA['file_read'], STD_TOOLS_SCHEMA['file_write'], STD_TOOLS_SCHEMA['file_exists'], STD_TOOLS_SCHEMA['file_list']]
)

def flow_main():
    msg = "Please fetch the current time, then fetch news from https://lite.cnn.com (it's a text-only news site, easy to parse). Extract top 3 headlines and save them to `examples/today_news.md` using the file system tool."
    Researcher.run(msg)

if __name__ == "__main__":
    flow_main()
