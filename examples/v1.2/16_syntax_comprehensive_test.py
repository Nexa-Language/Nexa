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

class AnalysisResult(pydantic.BaseModel):
    score: int
    summary: str
    is_valid: str

SimpleAgent = NexaAgent(
    name="SimpleAgent",
    prompt="Respond with a short greeting.",
    model="deepseek/deepseek-chat",
    role="Simple Test Agent",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

AgentWithCache = NexaAgent(
    name="AgentWithCache",
    prompt="Repeat the input exactly.",
    model="deepseek/deepseek-chat",
    role="Cached Agent",
    memory_scope="local",
    stream=False,
    cache=True,
    timeout=30,
    retry=3,
    tools=[]
)

Translator = NexaAgent(
    name="Translator",
    prompt="Translate the input to Chinese.",
    model="deepseek/deepseek-chat",
    role="Translator",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Summarizer = NexaAgent(
    name="Summarizer",
    prompt="Summarize the input in one sentence.",
    model="deepseek/deepseek-chat",
    role="Summarizer",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Worker1 = NexaAgent(
    name="Worker1",
    prompt="Count the number of words in the input. Just return the number.",
    model="deepseek/deepseek-chat",
    role="Worker 1",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Worker2 = NexaAgent(
    name="Worker2",
    prompt="Count the number of characters in the input. Just return the number.",
    model="deepseek/deepseek-chat",
    role="Worker 2",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Aggregator = NexaAgent(
    name="Aggregator",
    prompt="Combine all inputs into a summary.",
    model="deepseek/deepseek-chat",
    role="Aggregator",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

RiskyAgent = NexaAgent(
    name="RiskyAgent",
    prompt="Process the input.",
    model="deepseek/deepseek-chat",
    role="Risky Agent",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

FallbackAgent = NexaAgent(
    name="FallbackAgent",
    prompt="Say 'fallback executed'.",
    model="deepseek/deepseek-chat",
    role="Fallback Agent",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

def flow_test_dag_fanout():
    input_text = "The quick brown fox jumps over the lazy dog."
    results = dag_fanout(input_text, [ Worker1, Worker2 ])
    print("DAG Fan-out results:")
    print(results)

def flow_test_dag_chain():
    input_text = "Artificial intelligence is transforming industries worldwide."
    final = dag_merge(dag_fanout(input_text, [ Worker1, Worker2 ]), strategy="concat", merge_agent=Aggregator)
    print("DAG Chain result:")
    print(final)

def flow_test_try_catch():
    try:
        result = RiskyAgent.run("Process this")
        print("Success:")
        print(result)
    except Exception as err:
        print("Caught error:")
        print(err)
        fallback_result = FallbackAgent.run("error occurred")
        print(fallback_result)

def flow_main():
    print("========== Nexa 语法特征综合测试 ==========")
    print("")
    print("=== Test 1: DAG Fan-out ===")
    flow_test_dag_fanout()
    print("=== Test 2: DAG Chain ===")
    flow_test_dag_chain()
    print("=== Test 3: Try/Catch ===")
    flow_test_try_catch()
    print("")
    print("========== 测试完成 ==========")

if __name__ == "__main__":
    flow_main()
