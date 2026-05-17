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

Test1_Limit100 = NexaAgent(
    name="Test1_Limit100",
    prompt="限制输出100 token",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test2_Limit2000 = NexaAgent(
    name="Test2_Limit2000",
    prompt="限制输出2000 token",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test3_Timeout10 = NexaAgent(
    name="Test3_Timeout10",
    prompt="10秒超时",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test4_Timeout120 = NexaAgent(
    name="Test4_Timeout120",
    prompt="120秒超时",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test5_Retry1 = NexaAgent(
    name="Test5_Retry1",
    prompt="重试1次",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test6_Retry5 = NexaAgent(
    name="Test6_Retry5",
    prompt="重试5次",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test7_Temperature05 = NexaAgent(
    name="Test7_Temperature05",
    prompt="温度0.5",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test8_Temperature01 = NexaAgent(
    name="Test8_Temperature01",
    prompt="温度0.1 - 更确定性",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test9_Temperature09 = NexaAgent(
    name="Test9_Temperature09",
    prompt="温度0.9 - 更随机",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test10_Combined3 = NexaAgent(
    name="Test10_Combined3",
    prompt="三个修饰器组合",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test11_AllDecorators = NexaAgent(
    name="Test11_AllDecorators",
    prompt="所有修饰器组合测试",
    model="minimax-m2.5",
    role="全面测试Agent",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test12_DecoratorWithProps = NexaAgent(
    name="Test12_DecoratorWithProps",
    prompt="修饰器与属性混用",
    model="deepseek/deepseek-chat",
    role="混用测试",
    memory_scope="local",
    stream=False,
    cache=True,
    timeout=30,
    retry=3,
    tools=[]
)

def flow_main():
    print("========== Agent 修饰器测试开始 ==========")
    result1 = Test1_Limit100.run("测试 @limit(max_tokens=100)")
    print("Test 1 - @limit(100): PASS")
    result2 = Test2_Limit2000.run("测试 @limit(max_tokens=2000)")
    print("Test 2 - @limit(2000): PASS")
    result3 = Test3_Timeout10.run("测试 @timeout(seconds=10)")
    print("Test 3 - @timeout(10): PASS")
    result4 = Test4_Timeout120.run("测试 @timeout(seconds=120)")
    print("Test 4 - @timeout(120): PASS")
    result5 = Test5_Retry1.run("测试 @retry(max_attempts=1)")
    print("Test 5 - @retry(1): PASS")
    result6 = Test6_Retry5.run("测试 @retry(max_attempts=5)")
    print("Test 6 - @retry(5): PASS")
    result7 = Test7_Temperature05.run("测试 @temperature(value=0.5)")
    print("Test 7 - @temperature(0.5): PASS")
    result8 = Test8_Temperature01.run("测试 @temperature(value=0.1)")
    print("Test 8 - @temperature(0.1): PASS")
    result9 = Test9_Temperature09.run("测试 @temperature(value=0.9)")
    print("Test 9 - @temperature(0.9): PASS")
    result10 = Test10_Combined3.run("测试三个修饰器组合")
    print("Test 10 - 三修饰器组合: PASS")
    result11 = Test11_AllDecorators.run("测试所有四个修饰器")
    print("Test 11 - 四修饰器组合: PASS")
    result12 = Test12_DecoratorWithProps.run("测试修饰器与属性混用")
    print("Test 12 - 修饰器与属性混用: PASS")
    print("========== Agent 修饰器测试完成 ==========")

if __name__ == "__main__":
    flow_main()
