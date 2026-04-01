"""
测试论文中描述的所有 Nexa 特性
v1.0.2: 包含 Semantic Types 的测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nexa_parser import parse
from src.code_generator import CodeGenerator
import json

def test_semantic_types():
    """测试语义类型定义 - v1.0.2 新特性"""
    print("\n=== Test: Semantic Types ===")
    
    code = '''
type Summary = str @ "A concise summary"
type Sentiment = str @ "positive, negative, or neutral"
type Confidence = float @ "A value between 0.0 and 1.0"
type PlainInt = int
type Tags = list[str]
type Scores = dict[str, float]
'''
    
    ast = parse(code)
    type_decls = [n for n in ast["body"] if n["type"] == "TypeDeclaration"]
    
    assert len(type_decls) == 6, f"Expected 6 type declarations, got {len(type_decls)}"
    
    # 验证带约束的语义类型
    summary_type = type_decls[0]
    assert summary_type["name"] == "Summary"
    assert summary_type["definition"]["type"] == "SemanticType"
    assert summary_type["definition"]["base_type"]["name"] == "str"
    assert summary_type["definition"]["constraint"] == "A concise summary"
    
    # 验证简单类型别名
    plain_int = type_decls[3]
    assert plain_int["name"] == "PlainInt"
    assert plain_int["definition"]["type"] == "BaseType"
    assert plain_int["definition"]["name"] == "int"
    
    # 验证泛型类型
    tags = type_decls[4]
    assert tags["name"] == "Tags"
    assert tags["definition"]["type"] == "GenericType"
    assert tags["definition"]["name"] == "list"
    
    scores = type_decls[5]
    assert scores["name"] == "Scores"
    assert scores["definition"]["type"] == "GenericType"
    assert scores["definition"]["name"] == "dict"
    
    # 验证 Code Generator
    gen = CodeGenerator(ast)
    generated = gen.generate()
    assert "class Summary(pydantic.BaseModel)" in generated
    assert "class Sentiment(pydantic.BaseModel)" in generated
    assert "PlainInt = int" in generated
    assert "Tags = list[str]" in generated
    assert "Scores = dict[str, float]" in generated
    
    print("✅ Semantic Types test passed!")
    return True

def test_binary_expr():
    """测试二元运算符扩展"""
    print("\n=== Test: Binary Expression ===")
    
    code = '''
flow test_binary {
    x = 10 + 5;
    y = 100 - 50;
    z = 7 * 8;
    w = 100 / 10;
    m = 17 % 5;
}
'''
    
    ast = parse(code)
    flow = ast["body"][0]
    stmts = flow["body"]
    
    ops = ["+", "-", "*", "/", "%"]
    for i, stmt in enumerate(stmts):
        assert stmt["type"] == "AssignmentStatement"
        expr = stmt["value"]
        assert expr["type"] == "BinaryExpression"
        assert expr["operator"] == ops[i]
    
    print("✅ Binary Expression test passed!")
    return True

def test_fallback_expr():
    """测试 Fallback 表达式"""
    print("\n=== Test: Fallback Expression ===")
    
    code = '''
agent ResilientAgent {
    model: "openai:gpt-4o",
    fallback: "anthropic:claude-3.5",
    prompt: "Test agent"
}

flow main {
    result = ResilientAgent.run("test") fallback "Fallback Triggered";
}
'''
    
    ast = parse(code)
    
    # 验证 agent fallback 属性
    agent = ast["body"][0]
    assert agent["properties"]["fallback"] == "anthropic:claude-3.5"
    
    # 验证 fallback 表达式
    flow = ast["body"][1]
    stmt = flow["body"][0]
    expr = stmt["value"]
    assert expr["type"] == "FallbackExpr"
    assert expr["primary"]["type"] == "MethodCallExpression"
    assert expr["backup"]["type"] == "StringLiteral"
    
    print("✅ Fallback Expression test passed!")
    return True

def test_traditional_control_flow():
    """测试传统控制流"""
    print("\n=== Test: Traditional Control Flow ===")
    
    code = '''
flow test_control {
    if (x > 10) {
        print("large");
    }
    
    for each item in items {
        print(item);
    }
    
    while (count < 10) {
        count = count + 1;
    }
    
    if (x > 5) {
        print("big");
    } else {
        print("small");
    }
}
'''
    
    ast = parse(code)
    flow = ast["body"][0]
    stmts = flow["body"]
    
    # 验证 if 语句
    assert stmts[0]["type"] == "TraditionalIfStatement"
    
    # 验证 foreach 语句
    assert stmts[1]["type"] == "ForEachStatement"
    
    # 验证 while 语句
    assert stmts[2]["type"] == "WhileStatement"
    
    # 验证 if-else 语句
    assert stmts[3]["type"] == "TraditionalIfStatement"
    assert stmts[3]["else_block"] is not None
    
    print("✅ Traditional Control Flow test passed!")
    return True

def test_python_escape():
    """测试 Python 逃生舱"""
    print("\n=== Test: Python Escape ===")
    
    # Nexa 使用三引号字符串格式
    code = '''
flow test_python {
    python! """import json
data = {"key": "value"}
print(json.dumps(data))"""
}
'''
    
    ast = parse(code)
    flow = ast["body"][0]
    stmt = flow["body"][0]
    
    assert stmt["type"] == "PythonEscapeStatement"
    assert "import json" in stmt["code"]
    
    print("✅ Python Escape test passed!")
    return True

def test_dag_operators():
    """测试 DAG 操作符"""
    print("\n=== Test: DAG Operators ===")
    
    # Nexa DAG 操作符使用 |>> 和 &>>，不需要分号
    code = '''
agent A { prompt: "A" }
agent B { prompt: "B" }
agent C { prompt: "C" }
agent D { prompt: "D" }

flow test_dag {
    result1 = A |>> [B, C]
    result2 = [B, C] &>> D
}
'''
    
    ast = parse(code)
    flow = ast["body"][4]  # 前四个是 agents
    
    # 验证 DAG 分叉
    stmt1 = flow["body"][0]
    expr1 = stmt1["value"]
    assert expr1["type"] == "DAGForkExpression"
    
    # 验证 DAG 合流
    stmt2 = flow["body"][1]
    expr2 = stmt2["value"]
    assert expr2["type"] == "DAGMergeExpression"
    
    print("✅ DAG Operators test passed!")
    return True

def test_protocol():
    """测试 Protocol 定义"""
    print("\n=== Test: Protocol ===")
    
    code = '''
protocol AnalysisResult {
    summary: "str",
    sentiment: "str",
    confidence: "float"
}

agent Analyzer implements AnalysisResult {
    prompt: "Analyze text"
}
'''
    
    ast = parse(code)
    
    # 验证 Protocol 定义
    proto = ast["body"][0]
    assert proto["type"] == "ProtocolDeclaration"
    assert proto["name"] == "AnalysisResult"
    assert "summary" in proto["fields"]
    
    # 验证 implements
    agent = ast["body"][1]
    assert agent["implements"] == "AnalysisResult"
    
    print("✅ Protocol test passed!")
    return True

def test_match_intent():
    """测试意图路由"""
    print("\n=== Test: Match Intent ===")
    
    # Nexa 使用 match var { intent("...") => ... , _ => ... } 语法
    code = '''
agent GreetAgent { prompt: "Greet" }
agent QA { prompt: "QA" }
agent General { prompt: "General" }

flow test_routing {
    user_input = "hello"
    result = match user_input {
        intent("greeting") => GreetAgent.run(user_input),
        intent("question") => QA.run(user_input),
        _ => General.run(user_input)
    }
}
'''
    
    ast = parse(code)
    flow = ast["body"][3]  # 前三个是 agents
    
    # 找到 match 语句
    stmt = flow["body"][1]  # 第一个是赋值 user_input
    assert stmt["type"] == "AssignmentStatement"
    match_expr = stmt["value"]
    assert match_expr["type"] == "MatchIntentStatement"
    
    print("✅ Match Intent test passed!")
    return True

def test_loop_until():
    """测试语义循环"""
    print("\n=== Test: Loop Until ===")
    
    # Nexa 使用 loop { ... } until ("自然语言条件") 语法
    code = '''
agent Writer { prompt: "Write content" }
agent Critic { prompt: "Critique content" }

flow test_loop {
    draft = Writer.run("write intro")
    loop {
        feedback = Critic.run(draft)
        draft = Writer.run("improve: " + feedback)
    } until ("content is excellent")
}
'''
    
    ast = parse(code)
    flow = ast["body"][2]  # 前两个是 agents
    
    # 找到 loop 语句
    stmt = flow["body"][1]  # 第一个是赋值 draft
    assert stmt["type"] == "LoopUntilStatement"
    assert stmt["condition"]["type"] == "StringLiteral"
    
    print("✅ Loop Until test passed!")
    return True

def run_all_tests():
    """运行所有测试"""
    tests = [
        test_semantic_types,
        test_binary_expr,
        test_fallback_expr,
        test_traditional_control_flow,
        test_python_escape,
        test_dag_operators,
        test_protocol,
        test_match_intent,
        test_loop_until,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Total: {passed} passed, {failed} failed")
    print(f"{'='*50}")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)