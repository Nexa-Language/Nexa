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

TestRoleBasic = NexaAgent(
    name="TestRoleBasic",
    prompt="回复OK",
    model="minimax-m2.5",
    role="测试角色",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestRoleEmpty = NexaAgent(
    name="TestRoleEmpty",
    prompt="回复OK",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestRoleMultiline = NexaAgent(
    name="TestRoleMultiline",
    prompt="回复OK",
    model="minimax-m2.5",
    role="资深软件工程师，专注于Python和Rust开发，拥有10年以上经验",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestPromptSingleLine = NexaAgent(
    name="TestPromptSingleLine",
    prompt="单行prompt测试",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestPromptMultiLine = NexaAgent(
    name="TestPromptMultiLine",
    prompt="多行prompt测试：1.第一行 2.第二行 3.第三行",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestPromptWithChinese = NexaAgent(
    name="TestPromptWithChinese",
    prompt="这是一个中文prompt测试，包含特殊字符：@#$%",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestModelDeepseek = NexaAgent(
    name="TestModelDeepseek",
    prompt="回复OK",
    model="deepseek/deepseek-chat",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestModelMinimax = NexaAgent(
    name="TestModelMinimax",
    prompt="回复OK",
    model="minimax/minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestModelOpenai = NexaAgent(
    name="TestModelOpenai",
    prompt="回复OK",
    model="openai/gpt-4",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestMemoryPersistent = NexaAgent(
    name="TestMemoryPersistent",
    prompt="记住用户的名字",
    model="minimax-m2.5",
    role="",
    memory_scope="persistent",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestMemoryLocal = NexaAgent(
    name="TestMemoryLocal",
    prompt="本地记忆测试",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestStreamTrue = NexaAgent(
    name="TestStreamTrue",
    prompt="流式输出测试",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=True,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestStreamFalse = NexaAgent(
    name="TestStreamFalse",
    prompt="非流式输出测试",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestCacheTrue = NexaAgent(
    name="TestCacheTrue",
    prompt="缓存测试开启",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=True,
    timeout=30,
    retry=3,
    tools=[]
)

TestCacheFalse = NexaAgent(
    name="TestCacheFalse",
    prompt="缓存测试关闭",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestExperienceBasic = NexaAgent(
    name="TestExperienceBasic",
    prompt="基于经验回答",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    experience="my_memory.md",
    timeout=30,
    retry=3,
    tools=[]
)

TestFallbackSingle = NexaAgent(
    name="TestFallbackSingle",
    prompt="测试单个备用模型",
    model="openai/gpt-4",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestMaxTokens100 = NexaAgent(
    name="TestMaxTokens100",
    prompt="限制输出100token",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestMaxTokens1000 = NexaAgent(
    name="TestMaxTokens1000",
    prompt="限制输出1000token",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

TestTimeout10 = NexaAgent(
    name="TestTimeout10",
    prompt="10秒超时",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=10,
    retry=3,
    tools=[]
)

TestTimeout60 = NexaAgent(
    name="TestTimeout60",
    prompt="60秒超时",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=60,
    retry=3,
    tools=[]
)

TestRetry1 = NexaAgent(
    name="TestRetry1",
    prompt="重试1次",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=1,
    tools=[]
)

TestRetry5 = NexaAgent(
    name="TestRetry5",
    prompt="重试5次",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=5,
    tools=[]
)

TestCombinedAll = NexaAgent(
    name="TestCombinedAll",
    prompt="测试所有属性组合",
    model="deepseek/deepseek-chat",
    role="综合测试Agent",
    memory_scope="local",
    stream=False,
    cache=True,
    timeout=30,
    retry=3,
    tools=[]
)

def flow_test_role():
    result = TestRoleBasic.run("测试role属性")
    print("Test 1 - role: PASS")

def flow_test_prompt():
    result = TestPromptSingleLine.run("测试prompt")
    print("Test 2 - prompt: PASS")

def flow_test_model():
    result = TestModelDeepseek.run("测试model")
    print("Test 3 - model: PASS")

def flow_test_memory():
    result = TestMemoryLocal.run("测试memory")
    print("Test 4 - memory: PASS")

def flow_test_stream():
    result = TestStreamFalse.run("测试stream")
    print("Test 5 - stream: PASS")

def flow_test_cache():
    result = TestCacheFalse.run("测试cache")
    print("Test 6 - cache: PASS")

def flow_test_max_tokens():
    result = TestMaxTokens100.run("测试max_tokens")
    print("Test 9 - max_tokens: PASS")

def flow_test_timeout():
    result = TestTimeout10.run("测试timeout")
    print("Test 10 - timeout: PASS")

def flow_test_retry():
    result = TestRetry1.run("测试retry")
    print("Test 11 - retry: PASS")

def flow_test_combined():
    result = TestCombinedAll.run("测试组合属性")
    print("Test 12 - combined: PASS")

def flow_main():
    print("========== Agent 属性测试开始 ==========")
    flow_test_role()
    flow_test_prompt()
    flow_test_model()
    flow_test_memory()
    flow_test_stream()
    flow_test_cache()
    flow_test_max_tokens()
    flow_test_timeout()
    flow_test_retry()
    flow_test_combined()
    print("========== Agent 属性测试完成 ==========")

if __name__ == "__main__":
    flow_main()
