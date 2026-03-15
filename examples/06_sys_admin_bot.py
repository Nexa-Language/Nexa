# 此文件由 Nexa v0.5 Code Generator 自动生成
import os
import json
from src.runtime.agent import NexaAgent
from src.runtime.evaluator import nexa_semantic_eval, nexa_intent_routing
from src.runtime.orchestrator import join_agents, nexa_pipeline
from src.runtime.memory import global_memory
from src.runtime.stdlib import STD_TOOLS_SCHEMA

# ==========================================
# [Target Code] 自动生成的编排逻辑
# ==========================================

SysAdminBot = NexaAgent(
    name="SysAdminBot",
    prompt="You are a Linux system administrator bot. Answer questions about the OS by executing commands like `uname -a`, `free -m`, `ls -la`, etc.",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    tools=[STD_TOOLS_SCHEMA['std_shell_execute']]
)

def flow_main():
    SysAdminBot.run("Please run `ls -a` in the current project root, and check the ram usage. Then summarize what's in the repo and how much memory is free.")

if __name__ == "__main__":
    flow_main()
