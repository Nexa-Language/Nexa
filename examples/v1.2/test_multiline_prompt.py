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

Test1_Basic = NexaAgent(
    name="Test1_Basic",
    prompt="""
    This is a multi-line prompt.
    It spans multiple lines.
    """,
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test2_Newlines = NexaAgent(
    name="Test2_Newlines",
    prompt="""
    Line 1
    Line 2
    Line 3
    """,
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test3_SpecialChars = NexaAgent(
    name="Test3_SpecialChars",
    prompt="""
    Special characters: @#$%^&*()
    More special: <>&"'
    """,
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test4_Quotes = NexaAgent(
    name="Test4_Quotes",
    prompt="""
    This contains "quotes" inside.
    Also 'single quotes' here.
    """,
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test5_Empty = NexaAgent(
    name="Test5_Empty",
    prompt="",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test6_Combined = NexaAgent(
    name="Test6_Combined",
    prompt="""
    这是一个多行 prompt 测试。
    包含多行内容。
    与其他属性组合使用。
    """,
    model="deepseek/deepseek-chat",
    role="测试角色",
    memory_scope="local",
    stream=False,
    cache=True,
    timeout=30,
    retry=3,
    tools=[]
)

Test7_CodeBlock = NexaAgent(
    name="Test7_CodeBlock",
    prompt="""
    请分析以下代码：
    ```python
    def hello():
        print("Hello, World!")
    ```
    注意缩进和格式。
    """,
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test8_JSON = NexaAgent(
    name="Test8_JSON",
    prompt="""
    解析以下 JSON 格式：
    {
        "name": "Nexa",
        "version": "1.0",
        "features": ["agent", "flow", "protocol"]
    }
    """,
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test9_Chinese = NexaAgent(
    name="Test9_Chinese",
    prompt="""
    这是一个中文多行 prompt 测试。
    包含以下内容：
    1. 第一行说明
    2. 第二行说明
    3. 第三行说明
    """,
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test10_MultilineRole = NexaAgent(
    name="Test10_MultilineRole",
    prompt="回复 OK",
    model="minimax-m2.5",
    role="""
    资深软件工程师
    专注于 Python 和 Rust 开发
    拥有 10 年以上经验
    """,
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test11_SingleLineInMultiline = NexaAgent(
    name="Test11_SingleLineInMultiline",
    prompt="单行内容但在三引号中",
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

Test12_Indented = NexaAgent(
    name="Test12_Indented",
    prompt="""
        带缩进的多行 prompt
        每行都有缩进
        测试缩进处理
    """,
    model="minimax-m2.5",
    role="",
    memory_scope="local",
    stream=False,
    cache=False,
    timeout=30,
    retry=3,
    tools=[]
)

def flow_main():
    print("========== 多行 Prompt 测试开始 ==========")
    result1 = Test1_Basic.run("测试基本三引号")
    print("Test 1 - 基本三引号: PASS")
    result2 = Test2_Newlines.run("测试换行")
    print("Test 2 - 包含换行: PASS")
    result3 = Test3_SpecialChars.run("测试特殊字符")
    print("Test 3 - 特殊字符: PASS")
    result4 = Test4_Quotes.run("测试引号")
    print("Test 4 - 包含引号: PASS")
    result5 = Test5_Empty.run("测试空 prompt")
    print("Test 5 - 空 prompt: PASS")
    result6 = Test6_Combined.run("测试组合属性")
    print("Test 6 - 组合属性: PASS")
    result7 = Test7_CodeBlock.run("测试代码块")
    print("Test 7 - 代码块: PASS")
    result8 = Test8_JSON.run("测试 JSON")
    print("Test 8 - JSON 内容: PASS")
    result9 = Test9_Chinese.run("测试中文")
    print("Test 9 - 中文内容: PASS")
    result10 = Test10_MultilineRole.run("测试多行 role")
    print("Test 10 - 多行 role: PASS")
    result11 = Test11_SingleLineInMultiline.run("测试单行三引号")
    print("Test 11 - 单行三引号: PASS")
    result12 = Test12_Indented.run("测试缩进")
    print("Test 12 - 带缩进: PASS")
    print("========== 多行 Prompt 测试完成 ==========")

if __name__ == "__main__":
    flow_main()
