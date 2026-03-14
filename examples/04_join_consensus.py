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

Researcher_Tech = NexaAgent(
    name="Researcher_Tech",
    prompt="Provide a quick overview of Quantum Computing for tech audience.",
    model="minimax-m2.5",
    role="Tech Researcher",
    memory_scope="local",
    tools=[]
)

Researcher_Biz = NexaAgent(
    name="Researcher_Biz",
    prompt="Provide a quick business use-case for Quantum Computing.",
    model="minimax-m2.5",
    role="Business Researcher",
    memory_scope="local",
    tools=[]
)

Summarizer = NexaAgent(
    name="Summarizer",
    prompt="Merge the perspectives into a 1-paragraph summary.",
    model="deepseek-chat",
    role="Editor",
    memory_scope="local",
    tools=[]
)

def flow_main():
    tech_view = Researcher_Tech.run("Quantum Computing advances")
    biz_view = Researcher_Biz.run("Quantum Computing business impact")
    final_report = Summarizer.run(join_agents([ Researcher_Tech, Researcher_Biz], "Synthesize the reports"))

if __name__ == "__main__":
    flow_main()
