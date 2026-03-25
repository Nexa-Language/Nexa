#!/usr/bin/env python3
"""
文档示例验证测试脚本
验证 nexa-docs 中所有文档示例代码是否能正确解析和编译
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nexa_parser import parse
from src.code_generator import CodeGenerator


class DocExample:
    """文档示例类"""
    def __init__(self, name: str, source: str, doc_file: str, feature: str):
        self.name = name
        self.source = source
        self.doc_file = doc_file
        self.feature = feature


# ============================================================
# Part 1: 基础语法示例
# ============================================================

PART1_EXAMPLES = [
    DocExample(
        name="basic_agent_definition",
        source='''
agent Greeter {
    role: "友好的问候助手",
    prompt: "你是一个热情友好的助手，用简洁的语言帮助用户。",
    model: "deepseek/deepseek-chat"
}
''',
        doc_file="part1_basic.md",
        feature="agent 定义"
    ),
    DocExample(
        name="agent_with_all_attributes",
        source='''
agent Assistant {
    role: "智能助手",
    prompt: "你是一个专业的助手",
    model: "openai/gpt-4",
    memory: true,
    stream: true,
    cache: true,
    max_tokens: 4096,
    timeout: 30
}
''',
        doc_file="part1_basic.md",
        feature="agent 所有属性"
    ),
    DocExample(
        name="agent_with_fallback",
        source='''
agent SmartBot {
    role: "智能机器人",
    prompt: "你是一个智能助手",
    model: ["openai/gpt-4", fallback: "deepseek/deepseek-chat"]
}
''',
        doc_file="part1_basic.md",
        feature="fallback 降级"
    ),
    DocExample(
        name="agent_with_experience",
        source='''
agent ExpertBot {
    role: "专家机器人",
    prompt: "你是一个领域专家",
    model: "openai/gpt-4",
    experience: "expert_memory.md"
}
''',
        doc_file="part1_basic.md",
        feature="experience 长期记忆"
    ),
    DocExample(
        name="simple_flow",
        source='''
agent Bot {
    prompt: "你是一个助手",
    model: "deepseek/deepseek-chat"
}

flow main {
    result = Bot.run("你好")
    print(result)
}
''',
        doc_file="part1_basic.md",
        feature="flow 基本语法"
    ),
    DocExample(
        name="flow_with_params",
        source='''
agent Bot {
    prompt: "你是一个助手",
    model: "deepseek/deepseek-chat"
}

flow process_user(user_id: string, action: string) {
    result = Bot.run(action)
    return result
}
''',
        doc_file="part1_basic.md",
        feature="flow 带参数"
    ),
    DocExample(
        name="uses_stdlib",
        source='''
agent FileBot uses std.fs, std.http {
    prompt: "你可以读写文件和发送HTTP请求",
    model: "openai/gpt-4"
}
''',
        doc_file="part1_basic.md",
        feature="uses 标准库"
    ),
]


# ============================================================
# Part 2: 高级特性示例
# ============================================================

PART2_EXAMPLES = [
    DocExample(
        name="pipeline_operator",
        source='''
agent Translator {
    prompt: "你是翻译",
    model: "deepseek/deepseek-chat"
}

agent Proofreader {
    prompt: "你是校对",
    model: "deepseek/deepseek-chat"
}

flow main {
    result = "Hello" >> Translator >> Proofreader
    print(result)
}
''',
        doc_file="part2_advanced.md",
        feature="管道操作符 >>"
    ),
    DocExample(
        name="match_intent",
        source='''
agent WeatherBot {
    prompt: "你是天气助手",
    model: "deepseek/deepseek-chat"
}

agent NewsBot {
    prompt: "你是新闻助手",
    model: "deepseek/deepseek-chat"
}

flow main {
    user_input = "今天天气怎么样"
    response = match user_input {
        intent("查询天气") => WeatherBot.run(user_input),
        intent("查询新闻") => NewsBot.run(user_input),
        _ => "抱歉，我无法理解"
    }
    print(response)
}
''',
        doc_file="part2_advanced.md",
        feature="match intent 意图路由"
    ),
    DocExample(
        name="dag_fan_out",
        source='''
agent Researcher {
    prompt: "你是研究员",
    model: "deepseek/deepseek-chat"
}

agent Analyst {
    prompt: "你是分析师",
    model: "deepseek/deepseek-chat"
}

agent Writer {
    prompt: "你是写手",
    model: "deepseek/deepseek-chat"
}

flow main {
    input_data = "研究课题"
    results = input_data |>> [Researcher, Analyst, Writer]
    print(results)
}
''',
        doc_file="part2_advanced.md",
        feature="DAG 分叉操作符 |>>"
    ),
    DocExample(
        name="dag_merge",
        source='''
agent Researcher {
    prompt: "你是研究员",
    model: "deepseek/deepseek-chat"
}

agent Summarizer {
    prompt: "你是总结者",
    model: "deepseek/deepseek-chat"
}

flow main {
    input_data = "研究课题"
    result = input_data |>> [Researcher, Researcher, Researcher] &>> Summarizer
    print(result)
}
''',
        doc_file="part2_advanced.md",
        feature="DAG 合流操作符 &>>"
    ),
    DocExample(
        name="dag_conditional",
        source='''
agent Reviewer {
    prompt: "你是审核员",
    model: "deepseek/deepseek-chat"
}

agent Approver {
    prompt: "你是批准者",
    model: "deepseek/deepseek-chat"
}

agent Rejecter {
    prompt: "你是拒绝者",
    model: "deepseek/deepseek-chat"
}

flow main {
    input_data = "待审核内容"
    result = input_data >> Reviewer ?? {
        "approved" => Approver.run(input_data),
        "rejected" => Rejecter.run(input_data)
    }
    print(result)
}
''',
        doc_file="part2_advanced.md",
        feature="DAG 条件分支操作符 ??"
    ),
    DocExample(
        name="loop_until",
        source='''
agent Writer {
    prompt: "你是写手",
    model: "deepseek/deepseek-chat"
}

agent Reviewer {
    prompt: "你是审核员",
    model: "deepseek/deepseek-chat"
}

flow main {
    draft = "初稿"
    loop {
        draft = Writer.run(draft)
        feedback = Reviewer.run(draft)
    } until ("文章完美")
    print(draft)
}
''',
        doc_file="part2_advanced.md",
        feature="loop until 循环"
    ),
    DocExample(
        name="semantic_if",
        source='''
agent Analyzer {
    prompt: "你是分析员",
    model: "deepseek/deepseek-chat"
}

flow main {
    text = "这是一段文本"
    result = semantic_if (text, "是否包含敏感信息") {
        "是" => Analyzer.run("处理敏感信息: " + text),
        "否" => text
    }
    print(result)
}
''',
        doc_file="part2_advanced.md",
        feature="semantic_if 语义条件"
    ),
    DocExample(
        name="try_catch",
        source='''
agent Bot {
    prompt: "你是助手",
    model: "deepseek/deepseek-chat"
}

flow main {
    try {
        result = Bot.run("你好")
        print(result)
    } catch (error) {
        print("发生错误: " + error)
    }
}
''',
        doc_file="part2_advanced.md",
        feature="try/catch 异常处理"
    ),
]


# ============================================================
# Part 3: 扩展示例
# ============================================================

PART3_EXAMPLES = [
    DocExample(
        name="protocol_basic",
        source='''
protocol UserInfo {
    name: "string",
    age: "int",
    email: "string"
}

agent InfoExtractor implements UserInfo {
    prompt: "从用户输入中提取个人信息",
    model: "deepseek/deepseek-chat"
}

flow main {
    result = InfoExtractor.run("我叫张三，25岁，邮箱是zhangsan@example.com")
    print(result.name)
    print(result.age)
}
''',
        doc_file="part3_extensions.md",
        feature="protocol 定义和 implements"
    ),
    DocExample(
        name="protocol_nested",
        source='''
protocol Address {
    city: "string",
    street: "string"
}

protocol User {
    name: "string",
    address: "Address"
}

agent UserExtractor implements User {
    prompt: "提取用户信息",
    model: "deepseek/deepseek-chat"
}
''',
        doc_file="part3_extensions.md",
        feature="protocol 嵌套类型"
    ),
    DocExample(
        name="protocol_optional",
        source='''
protocol Product {
    name: "string",
    price: "float",
    description: "string?"
}

agent ProductExtractor implements Product {
    prompt: "提取产品信息",
    model: "deepseek/deepseek-chat"
}
''',
        doc_file="part3_extensions.md",
        feature="protocol 可选字段"
    ),
    DocExample(
        name="protocol_enum",
        source='''
protocol Order {
    order_id: "string",
    status: "enum:pending,processing,completed,cancelled"
}

agent OrderProcessor implements Order {
    prompt: "处理订单",
    model: "deepseek/deepseek-chat"
}
''',
        doc_file="part3_extensions.md",
        feature="protocol 枚举值"
    ),
]


# ============================================================
# Part 4: 标准库示例
# ============================================================

PART4_EXAMPLES = [
    DocExample(
        name="stdlib_fs",
        source='''
agent FileBot uses std.fs {
    prompt: "你可以读写文件",
    model: "deepseek/deepseek-chat"
}

flow main {
    content = std.fs.read("data.txt")
    print(content)
}
''',
        doc_file="part4_ecosystem_and_stdlib.md",
        feature="std.fs 文件系统"
    ),
    DocExample(
        name="stdlib_http",
        source='''
agent HttpBot uses std.http {
    prompt: "你可以发送HTTP请求",
    model: "deepseek/deepseek-chat"
}

flow main {
    response = std.http.get("https://api.example.com/data")
    print(response)
}
''',
        doc_file="part4_ecosystem_and_stdlib.md",
        feature="std.http HTTP请求"
    ),
    DocExample(
        name="stdlib_time",
        source='''
agent TimeBot uses std.time {
    prompt: "你可以处理时间",
    model: "deepseek/deepseek-chat"
}

flow main {
    now = std.time.now()
    print(now)
}
''',
        doc_file="part4_ecosystem_and_stdlib.md",
        feature="std.time 时间"
    ),
    DocExample(
        name="stdlib_shell",
        source='''
agent ShellBot uses std.shell {
    prompt: "你可以执行shell命令",
    model: "deepseek/deepseek-chat"
}

flow main {
    result = std.shell.run("ls -la")
    print(result)
}
''',
        doc_file="part4_ecosystem_and_stdlib.md",
        feature="std.shell 终端"
    ),
    DocExample(
        name="ask_human",
        source='''
agent Bot {
    prompt: "你是助手",
    model: "deepseek/deepseek-chat"
}

flow main {
    approval = std.ask_human("是否继续执行?")
    if (approval == "yes") {
        Bot.run("继续执行任务")
    }
}
''',
        doc_file="part4_ecosystem_and_stdlib.md",
        feature="std.ask_human 人在回路"
    ),
    DocExample(
        name="img_multimodal",
        source='''
agent VisionBot {
    prompt: "你可以分析图片",
    model: "openai/gpt-4-vision"
}

flow main {
    image = img("photo.jpg")
    description = VisionBot.run(image)
    print(description)
}
''',
        doc_file="part4_ecosystem_and_stdlib.md",
        feature="img() 多模态"
    ),
    DocExample(
        name="secret_usage",
        source='''
agent Bot {
    prompt: "你是助手",
    model: "deepseek/deepseek-chat"
}

flow main {
    api_key = secret("OPENAI_API_KEY")
    print("已加载密钥")
}
''',
        doc_file="part4_ecosystem_and_stdlib.md",
        feature="secret 密钥"
    ),
]


# ============================================================
# Quickstart 示例
# ============================================================

QUICKSTART_EXAMPLES = [
    DocExample(
        name="hello_world",
        source='''
agent HelloBot {
    role: "热情的问候机器人",
    prompt: "你是一个友好的助手。请用热情、简洁的语言回应用户，不超过50个字。",
    model: "deepseek/deepseek-chat"
}

flow main {
    response = HelloBot.run("你好，请介绍一下你自己！")
    print(response)
}
''',
        doc_file="quickstart.md",
        feature="Hello World"
    ),
    DocExample(
        name="tool_definition",
        source='''
tool Calculator {
    description: "执行数学计算，支持加减乘除",
    parameters: {
        "expression": "string  // 数学表达式，如 2+3*4"
    }
}

agent MathAssistant uses Calculator {
    role: "数学助手",
    prompt: "你是一个数学助手。当用户需要进行计算时，使用 Calculator 工具。",
    model: "deepseek/deepseek-chat"
}

flow main {
    question = "请帮我计算 (123 + 456) * 2 等于多少？"
    result = MathAssistant.run(question)
    print(result)
}
''',
        doc_file="quickstart.md",
        feature="tool 定义"
    ),
    DocExample(
        name="translation_pipeline",
        source='''
agent Translator {
    role: "专业翻译",
    prompt: "你是一个专业的英译中翻译。",
    model: "deepseek/deepseek-chat"
}

agent Proofreader {
    role: "中文校对",
    prompt: "你是一个中文校对专家。",
    model: "deepseek/deepseek-chat"
}

flow main {
    english_text = "Artificial intelligence is transforming the way we live and work."
    final_result = english_text >> Translator >> Proofreader
    print("原文：" + english_text)
    print("译文：" + final_result)
}
''',
        doc_file="quickstart.md",
        feature="翻译流水线"
    ),
    DocExample(
        name="smart_router",
        source='''
agent WeatherBot {
    role: "天气助手",
    prompt: "你负责回答天气相关问题。",
    model: "deepseek/deepseek-chat"
}

agent NewsBot {
    role: "新闻助手",
    prompt: "你负责回答新闻相关问题。",
    model: "deepseek/deepseek-chat"
}

agent ChatBot {
    role: "聊天伙伴",
    prompt: "你是一个友好的聊天伙伴。",
    model: "deepseek/deepseek-chat"
}

flow main {
    user_message = "今天北京天气怎么样？"
    response = match user_message {
        intent("查询天气") => WeatherBot.run(user_message),
        intent("查询新闻") => NewsBot.run(user_message),
        _ => ChatBot.run(user_message)
    }
    print(response)
}
''',
        doc_file="quickstart.md",
        feature="意图路由"
    ),
    DocExample(
        name="structured_output",
        source='''
protocol BookReview {
    title: "string",
    author: "string",
    rating: "int",
    summary: "string",
    recommendation: "string"
}

agent Reviewer implements BookReview {
    role: "书评人",
    prompt: "你是一位专业书评人。根据用户提供的书籍信息，给出结构化的评价。",
    model: "deepseek/deepseek-chat"
}

flow main {
    book_name = "《三体》"
    result = Reviewer.run("请为" + book_name + "写一篇书评")
    print("书名：" + result.title)
    print("作者：" + result.author)
    print("评分：" + result.rating + "/10")
}
''',
        doc_file="quickstart.md",
        feature="结构化输出"
    ),
]


# ============================================================
# Part 5: Reference Manual 新特性示例
# ============================================================

REFERENCE_EXAMPLES = [
    # Agent 修饰器
    DocExample(
        name="agent_with_decorators",
        source='''
@limit(max_tokens=2048)
@timeout(seconds=30)
@retry(max_attempts=3)
agent ConstrainedAgent {
    role: "受限 Agent",
    prompt: "严格遵守 Token 和时间限制",
    model: "deepseek/deepseek-chat"
}
''',
        doc_file="reference.md",
        feature="agent 修饰器"
    ),
    # Tool MCP 声明
    DocExample(
        name="tool_mcp_declaration",
        source='''
tool WebSearch {
    mcp: "github.com/nexa-ai/web-search-mcp"
}
''',
        doc_file="reference.md",
        feature="tool MCP 声明"
    ),
    # 枚举类型 Protocol
    DocExample(
        name="protocol_enum_type",
        source='''
protocol StatusResponse {
    status: "active|inactive|pending",
    message: "string"
}

agent StatusChecker implements StatusResponse {
    role: "状态检查器",
    prompt: "检查并返回状态信息",
    model: "deepseek/deepseek-chat"
}
''',
        doc_file="reference.md",
        feature="枚举类型 Protocol"
    ),
    # DAG 并行不等待 ||
    DocExample(
        name="dag_fire_and_forget",
        source='''
agent Logger {
    prompt: "记录日志",
    model: "deepseek/deepseek-chat"
}

agent Analytics {
    prompt: "分析数据",
    model: "deepseek/deepseek-chat"
}

flow main {
    input = "用户操作"
    input || [Logger, Analytics]
    print("已触发后台任务")
}
''',
        doc_file="reference.md",
        feature="DAG || 并行不等待"
    ),
    # DAG 共识合流 &&
    DocExample(
        name="dag_consensus_merge",
        source='''
agent Agent1 {
    prompt: "评审员1",
    model: "deepseek/deepseek-chat"
}

agent Agent2 {
    prompt: "评审员2",
    model: "deepseek/deepseek-chat"
}

agent JudgeAgent {
    prompt: "裁决者",
    model: "deepseek/deepseek-chat"
}

flow main {
    proposal = "提案内容"
    consensus = [Agent1, Agent2] && JudgeAgent
    print(consensus)
}
''',
        doc_file="reference.md",
        feature="DAG && 共识合流"
    ),
    # 复杂 DAG 拓扑
    DocExample(
        name="complex_dag_topology",
        source='''
agent Researcher {
    prompt: "研究员",
    model: "deepseek/deepseek-chat"
}

agent Analyst {
    prompt: "分析师",
    model: "deepseek/deepseek-chat"
}

agent Writer {
    prompt: "写手",
    model: "deepseek/deepseek-chat"
}

agent Reviewer {
    prompt: "审核员",
    model: "deepseek/deepseek-chat"
}

flow main {
    topic = "研究主题"
    final = topic |>> [Researcher, Analyst] &>> Writer >> Reviewer
    print(final)
}
''',
        doc_file="reference.md",
        feature="复杂 DAG 拓扑"
    ),
    # Fallback 表达式
    DocExample(
        name="fallback_expression",
        source='''
agent PrimaryAgent {
    prompt: "主要处理者",
    model: "deepseek/deepseek-chat"
}

agent BackupAgent {
    prompt: "备用处理者",
    model: "deepseek/deepseek-chat"
}

flow main {
    input = "请求"
    result = PrimaryAgent.run(input) fallback BackupAgent.run(input)
    print(result)
}
''',
        doc_file="reference.md",
        feature="fallback 表达式"
    ),
    # 记忆属性
    DocExample(
        name="memory_attributes",
        source='''
agent RememberingAgent {
    role: "具备记忆的 Agent",
    prompt: "记住用户的偏好和历史对话",
    model: "deepseek/deepseek-chat",
    memory: "long",
    experience: true
}
''',
        doc_file="reference.md",
        feature="记忆属性"
    ),
    # Test 声明
    DocExample(
        name="test_declaration",
        source='''
agent WeatherBot {
    prompt: "天气助手",
    model: "deepseek/deepseek-chat"
}

test "天气查询测试" {
    mock_input = "北京今天天气怎么样"
    result = WeatherBot.run(mock_input)
    assert "包含天气信息" against result
    assert "包含温度数据" against result
}
''',
        doc_file="reference.md",
        feature="test 声明"
    ),
    # semantic_if with fast_match
    DocExample(
        name="semantic_if_fast_match",
        source='''
agent Scheduler {
    prompt: "日程安排",
    model: "deepseek/deepseek-chat"
}

agent Clarifier {
    prompt: "澄清助手",
    model: "deepseek/deepseek-chat"
}

flow main {
    user_input = "明天下午3点开会"
    semantic_if "包含日期和地点信息"
        fast_match r"\d{4}-\d{2}-\d{2}"
        against user_input {
        Scheduler.run(user_input)
    } else {
        Clarifier.run(user_input)
    }
}
''',
        doc_file="reference.md",
        feature="semantic_if with fast_match"
    ),
    # 多阶段并行 DAG
    DocExample(
        name="multi_stage_parallel_dag",
        source='''
agent Preprocess1 {
    prompt: "预处理1",
    model: "deepseek/deepseek-chat"
}

agent Preprocess2 {
    prompt: "预处理2",
    model: "deepseek/deepseek-chat"
}

agent Aggregator {
    prompt: "聚合器",
    model: "deepseek/deepseek-chat"
}

agent Formatter {
    prompt: "格式化器",
    model: "deepseek/deepseek-chat"
}

flow main {
    data = "原始数据"
    report = data |>> [Preprocess1, Preprocess2] &>> Aggregator >> Formatter
    print(report)
}
''',
        doc_file="reference.md",
        feature="多阶段并行 DAG"
    ),
]


# ============================================================
# 测试类
# ============================================================

class TestDocExamples(unittest.TestCase):
    """文档示例测试"""
    
    def _test_example(self, example: DocExample):
        """测试单个示例"""
        try:
            # 解析
            ast = parse(example.source)
            self.assertIsNotNone(ast, f"解析失败: {example.name}")
            
            # 代码生成 - CodeGenerator 需要 ast 作为构造参数
            generator = CodeGenerator(ast)
            code = generator.generate()
            self.assertIsNotNone(code, f"代码生成失败: {example.name}")
            
            # 检查生成的代码不是空的
            self.assertTrue(len(code.strip()) > 0, f"生成的代码为空: {example.name}")
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def test_part1_examples(self):
        """测试 Part 1 基础语法示例"""
        failed = []
        for example in PART1_EXAMPLES:
            success, error = self._test_example(example)
            if not success:
                failed.append({
                    "name": example.name,
                    "feature": example.feature,
                    "error": error
                })
        
        if failed:
            msg = "Part 1 基础语法示例失败:\n"
            for f in failed:
                msg += f"  - {f['name']} ({f['feature']}): {f['error']}\n"
            self.fail(msg)
    
    def test_part2_examples(self):
        """测试 Part 2 高级特性示例"""
        failed = []
        for example in PART2_EXAMPLES:
            success, error = self._test_example(example)
            if not success:
                failed.append({
                    "name": example.name,
                    "feature": example.feature,
                    "error": error
                })
        
        if failed:
            msg = "Part 2 高级特性示例失败:\n"
            for f in failed:
                msg += f"  - {f['name']} ({f['feature']}): {f['error']}\n"
            self.fail(msg)
    
    def test_part3_examples(self):
        """测试 Part 3 扩展示例"""
        failed = []
        for example in PART3_EXAMPLES:
            success, error = self._test_example(example)
            if not success:
                failed.append({
                    "name": example.name,
                    "feature": example.feature,
                    "error": error
                })
        
        if failed:
            msg = "Part 3 扩展示例失败:\n"
            for f in failed:
                msg += f"  - {f['name']} ({f['feature']}): {f['error']}\n"
            self.fail(msg)
    
    def test_part4_examples(self):
        """测试 Part 4 标准库示例"""
        failed = []
        for example in PART4_EXAMPLES:
            success, error = self._test_example(example)
            if not success:
                failed.append({
                    "name": example.name,
                    "feature": example.feature,
                    "error": error
                })
        
        if failed:
            msg = "Part 4 标准库示例失败:\n"
            for f in failed:
                msg += f"  - {f['name']} ({f['feature']}): {f['error']}\n"
            self.fail(msg)
    
    def test_quickstart_examples(self):
        """测试 Quickstart 示例"""
        failed = []
        for example in QUICKSTART_EXAMPLES:
            success, error = self._test_example(example)
            if not success:
                failed.append({
                    "name": example.name,
                    "feature": example.feature,
                    "error": error
                })
        
        if failed:
            msg = "Quickstart 示例失败:\n"
            for f in failed:
                msg += f"  - {f['name']} ({f['feature']}): {f['error']}\n"
            self.fail(msg)
    
    def test_reference_examples(self):
        """测试 Reference Manual 示例"""
        failed = []
        for example in REFERENCE_EXAMPLES:
            success, error = self._test_example(example)
            if not success:
                failed.append({
                    "name": example.name,
                    "feature": example.feature,
                    "error": error
                })
        
        if failed:
            msg = "Reference Manual 示例失败:\n"
            for f in failed:
                msg += f"  - {f['name']} ({f['feature']}): {f['error']}\n"
            self.fail(msg)


class TestDocExamplesSummary(unittest.TestCase):
    """文档示例汇总测试"""
    
    def test_summary(self):
        """输出测试汇总"""
        all_examples = (
            PART1_EXAMPLES +
            PART2_EXAMPLES +
            PART3_EXAMPLES +
            PART4_EXAMPLES +
            QUICKSTART_EXAMPLES +
            REFERENCE_EXAMPLES
        )
        
        total = len(all_examples)
        passed = 0
        failed_examples = []
        
        for example in all_examples:
            try:
                ast = parse(example.source)
                generator = CodeGenerator(ast)
                code = generator.generate()
                if ast and code:
                    passed += 1
                else:
                    failed_examples.append(example)
            except Exception as e:
                failed_examples.append(example)
        
        print(f"\n{'='*60}")
        print(f"文档示例验证汇总")
        print(f"{'='*60}")
        print(f"总计: {total} 个示例")
        print(f"通过: {passed} 个")
        print(f"失败: {len(failed_examples)} 个")
        print(f"通过率: {passed/total*100:.1f}%")
        print(f"{'='*60}")
        
        if failed_examples:
            print("\n失败的示例:")
            for ex in failed_examples:
                print(f"  - {ex.name} ({ex.doc_file}: {ex.feature})")
        
        # 打印详细信息
        self.assertEqual(len(failed_examples), 0, f"有 {len(failed_examples)} 个示例失败")


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)