#!/usr/bin/env python3
"""
测试文档中的所有示例代码
验证编译器是否支持所有语法特性
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.nexa_parser import NexaParser
from src.code_generator import CodeGenerator

# 文档中的示例代码
EXAMPLES = {
    # Part 1: 基础语法
    "tool_basic": '''
tool Calculator {
    description: "Perform basic math operations",
    parameters: {"expression": "string"}
}
''',
    "tool_mcp": '''
tool SearchMCP {
    mcp: "github.com/nexa-ai/search-mcp"
}
''',
    "protocol_basic": '''
protocol AnalysisReport {
    title: "string",
    sentiment: "string",
    confidence: "number"
}
''',
    "agent_basic": '''
@limit(max_tokens=2048)
agent FinancialAnalyst implements AnalysisReport uses Calculator, SearchMCP {
    role: "Senior Financial Advisor",
    model: "claude-3.5-sonnet",
    prompt: "Analyze financial data and output standard reports."
}
''',
    # Part 2: 编排与控制流
    "flow_basic": '''
flow main {
    raw_data = SearchMCP.run("AAPL Q3 index");
    summary = raw_data >> FinancialAnalyst >> Formatter;
    print(summary);
}
''',
    "match_intent": '''
match user_req {
    intent("查询天气") => WeatherBot.run(user_req),
    intent("查询股市") => StockBot.run(user_req),
    _ => SmallTalkBot.run(user_req)
}
''',
    "semantic_if": '''
semantic_if "包含具体的日期和地点" fast_match r"\\d{4}-\\d{2}-\\d{2}" against user_input {
    schedule_tool.run(user_input);
} else {
    print("需要进一步澄清");
}
''',
    "loop_until": '''
loop {
    draft = Editor.run(feedback);
    feedback = Critic.run(draft);
} until ("Article is engaging and grammatically perfect")
''',
    # Part 3: 测试与断言
    "test_basic": '''
test "financial_analysis_basic_pipeline" {
    mock_input = "Tesla revenue 2023";
    result = FinancialAnalyst.run(mock_input);
    assert "包含具体的马斯克管理评价" against result;
}
''',
    # Part 5: DAG 操作符
    "dag_fork": '''
results = input |>> [Agent1, Agent2, Agent3];
''',
    "dag_fork_fire_forget": '''
input || [Logger, Analytics];
''',
    "dag_merge": '''
result = [Researcher, Analyst] &>> Reviewer;
''',
    "dag_consensus": '''
consensus = [Agent1, Agent2] && JudgeAgent;
''',
    "dag_branch": '''
result = input ?? SpecialistA : GeneralistB;
''',
    # 完整示例
    "complete_example": '''
tool Calculator {
    description: "Perform basic math operations",
    parameters: {"expression": "string"}
}

protocol AnalysisReport {
    title: "string",
    sentiment: "string",
    confidence: "number"
}

agent FinancialAnalyst implements AnalysisReport uses Calculator {
    role: "Senior Financial Advisor",
    model: "claude-3.5-sonnet",
    prompt: "Analyze financial data and output standard reports."
}

flow main {
    raw_data = Calculator.run("2+2");
    print(raw_data);
}
''',
    # try-catch 示例
    "try_catch": '''
try {
    result = RiskyAgent.run(input);
} catch (error) {
    print("Error occurred: " + error);
}
''',
    # fallback 示例
    "fallback": '''
result = PrimaryAgent.run(input) fallback BackupAgent.run(input);
''',
}

def test_example(name, code):
    """测试单个示例"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")
    print(f"代码:\n{code[:200]}...")
    
    try:
        # 解析
        parser = NexaParser()
        ast = parser.parse(code.strip())
        print(f"✅ 解析成功")
        
        # 代码生成
        generator = CodeGenerator()
        python_code = generator.generate(ast)
        print(f"✅ 代码生成成功")
        print(f"生成的 Python 代码 ({len(python_code)} 字符)")
        
        return True, None
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False, str(e)

def main():
    """运行所有测试"""
    results = {}
    
    for name, code in EXAMPLES.items():
        success, error = test_example(name, code)
        results[name] = (success, error)
    
    # 汇总结果
    print(f"\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    
    passed = sum(1 for s, _ in results.values() if s)
    failed = sum(1 for s, _ in results.values() if not s)
    
    print(f"通过: {passed}/{len(results)}")
    print(f"失败: {failed}/{len(results)}")
    
    if failed > 0:
        print("\n失败的测试:")
        for name, (success, error) in results.items():
            if not success:
                print(f"  - {name}: {error}")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)