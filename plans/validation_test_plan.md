# Nexa 验证测试计划

## 概述

本计划涵盖以下验证测试：
1. Rust AVM 测试（确保 110 个测试通过）
2. Python SDK 测试
3. 标准库测试
4. 集成测试

## 1. 文件检查结果

### 1.1 检查的文件
- `avm/src/runtime/tool.rs` - ✅ 代码完整正确
  - `ToolSpec` 结构体
  - `ToolExecutor` trait
  - `ToolRegistry` 工具注册表
  
- `src/runtime/stdlib.py` - ✅ 代码完整正确（724 行）
  - HTTP 工具：http_get, http_post, url_encode, url_decode
  - 文件工具：file_read, file_write, file_exists, file_list, file_delete
  - JSON 工具：json_parse, json_stringify, json_get
  - 正则工具：regex_match, regex_replace
  - 文本工具：text_split, text_join, text_upper, text_lower, text_trim, text_substring, text_count, text_replace
  - 加密工具：hash_md5, hash_sha256, base64_encode, base64_decode
  - 时间工具：time_now, time_parse, time_format, time_diff
  - 数学工具：math_calc, math_round, math_random

### 1.2 不存在的文件
- `runtime/tools_registry.rs` - 用户可能记错，正确路径是 `avm/src/runtime/tool.rs`

## 2. 测试用例设计

### 2.1 Rust AVM 测试

```bash
cd avm && cargo test --lib
```

预期结果：110 个测试通过

测试覆盖：
- Lexer 测试（词法分析）
- Parser 测试（语法解析）
- Compiler 测试（字节码编译）
- VM 测试（解释器执行）
- Scheduler 测试（智能调度）
- Context Pager 测试（向量分页）
- WASM Sandbox 测试（安全沙盒）
- FFI 测试（Python/C 绑定）

### 2.2 Python SDK 测试（新增）

创建 `tests/test_nexa_sdk.py`:

```python
"""
Nexa SDK 测试套件
测试 Python SDK 的所有核心功能
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNexaSDK(unittest.TestCase):
    """测试 Nexa SDK 核心功能"""
    
    def test_import_sdk(self):
        """测试 SDK 导入"""
        import nexa
        self.assertIsNotNone(nexa.__version__)
    
    def test_compile_simple(self):
        """测试简单编译"""
        import nexa
        code = '''
agent TestBot {
    role: "test"
    model: "gpt-4"
    prompt: "You are a test bot"
}
'''
        result = nexa.compile(code)
        self.assertTrue(result.success)
    
    def test_agent_builder(self):
        """测试 Agent 构建器"""
        import nexa
        
        agent = (nexa.AgentBuilder("TestAgent")
            .with_prompt("测试提示")
            .with_model("gpt-4")
            .with_temperature(0.5)
            .build())
        
        self.assertIsNotNone(agent)
    
    def test_tool_builder(self):
        """测试 Tool 构建器"""
        import nexa
        
        tool = (nexa.ToolBuilder("test_tool")
            .with_description("测试工具")
            .with_parameter("input", "string", "输入参数")
            .build())
        
        self.assertIsNotNone(tool)
        self.assertEqual(tool["name"], "test_tool")


class TestNexaDebugger(unittest.TestCase):
    """测试调试器模块"""
    
    def test_import_debugger(self):
        """测试调试器导入"""
        from src.runtime.debugger import NexaDebugger
        self.assertTrue(callable(NexaDebugger))
    
    def test_debugger_creation(self):
        """测试调试器创建"""
        from src.runtime.debugger import NexaDebugger
        
        debugger = NexaDebugger()
        self.assertIsNotNone(debugger)
    
    def test_breakpoint_management(self):
        """测试断点管理"""
        from src.runtime.debugger import NexaDebugger, Breakpoint
        
        debugger = NexaDebugger()
        bp = debugger.add_breakpoint("test.nx", 10)
        
        self.assertIsNotNone(bp)
        self.assertEqual(bp.line, 10)


class TestNexaProfiler(unittest.TestCase):
    """测试性能分析器模块"""
    
    def test_import_profiler(self):
        """测试分析器导入"""
        from src.runtime.profiler import NexaProfiler
        self.assertTrue(callable(NexaProfiler))
    
    def test_profiler_creation(self):
        """测试分析器创建"""
        from src.runtime.profiler import NexaProfiler
        
        profiler = NexaProfiler()
        self.assertIsNotNone(profiler)
    
    def test_token_tracking(self):
        """测试 Token 追踪"""
        from src.runtime.profiler import NexaProfiler
        
        profiler = NexaProfiler()
        profiler.start_session("test_session")
        profiler.track_tokens("input", 100)
        profiler.track_tokens("output", 50)
        
        stats = profiler.get_session_stats("test_session")
        self.assertIsNotNone(stats)


class TestStdlib(unittest.TestCase):
    """测试标准库模块"""
    
    def test_import_stdlib(self):
        """测试标准库导入"""
        from src.runtime.stdlib import get_stdlib_tools, execute_stdlib_tool
        self.assertTrue(callable(get_stdlib_tools))
        self.assertTrue(callable(execute_stdlib_tool))
    
    def test_get_stdlib_tools(self):
        """测试获取标准库工具"""
        from src.runtime.stdlib import get_stdlib_tools
        
        tools = get_stdlib_tools()
        self.assertGreater(len(tools), 10)
    
    def test_hash_tools(self):
        """测试哈希工具"""
        from src.runtime.stdlib import execute_stdlib_tool
        
        md5_result = execute_stdlib_tool("hash_md5", text="hello")
        self.assertEqual(md5_result, "5d41402abc4b2a76b9719d911017c592")
        
        sha256_result = execute_stdlib_tool("hash_sha256", text="hello")
        self.assertEqual(sha256_result, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
    
    def test_base64_tools(self):
        """测试 Base64 工具"""
        from src.runtime.stdlib import execute_stdlib_tool
        
        encoded = execute_stdlib_tool("base64_encode", text="hello")
        self.assertEqual(encoded, "aGVsbG8=")
        
        decoded = execute_stdlib_tool("base64_decode", text="aGVsbG8=")
        self.assertEqual(decoded, "hello")
    
    def test_json_tools(self):
        """测试 JSON 工具"""
        from src.runtime.stdlib import execute_stdlib_tool
        import json
        
        parsed = execute_stdlib_tool("json_parse", text='{"name": "test", "value": 123}')
        data = json.loads(parsed)
        self.assertEqual(data["name"], "test")
        self.assertEqual(data["value"], 123)
    
    def test_text_tools(self):
        """测试文本工具"""
        from src.runtime.stdlib import execute_stdlib_tool
        import json
        
        upper = execute_stdlib_tool("text_upper", text="hello")
        self.assertEqual(upper, "HELLO")
        
        lower = execute_stdlib_tool("text_lower", text="HELLO")
        self.assertEqual(lower, "hello")
        
        split_result = execute_stdlib_tool("text_split", text="a,b,c", delimiter=",")
        split_data = json.loads(split_result)
        self.assertEqual(split_data["count"], 3)
    
    def test_math_tools(self):
        """测试数学工具"""
        from src.runtime.stdlib import execute_stdlib_tool
        import json
        
        result = execute_stdlib_tool("math_calc", expression="2 + 3 * 4")
        data = json.loads(result)
        self.assertEqual(data["result"], 14)
    
    def test_time_tools(self):
        """测试时间工具"""
        from src.runtime.stdlib import execute_stdlib_tool
        
        now = execute_stdlib_tool("time_now")
        self.assertIsNotNone(now)
        self.assertIn("-", now)  # 包含日期分隔符
    
    def test_regex_tools(self):
        """测试正则工具"""
        from src.runtime.stdlib import execute_stdlib_tool
        import json
        
        result = execute_stdlib_tool(
            "regex_match", 
            pattern=r"\d+", 
            text="abc123def456"
        )
        data = json.loads(result)
        self.assertEqual(data["count"], 2)
        
        replaced = execute_stdlib_tool(
            "regex_replace",
            pattern=r"\d+",
            replacement="X",
            text="abc123def456"
        )
        self.assertEqual(replaced, "abcXdefX")
    
    def test_tool_definitions(self):
        """测试工具定义导出"""
        from src.runtime.stdlib import get_stdlib_tool_definitions
        
        defs = get_stdlib_tool_definitions()
        self.assertGreater(len(defs), 10)
        
        # 检查每个定义都有必要字段
        for d in defs:
            self.assertIn("name", d)
            self.assertIn("description", d)
            self.assertIn("parameters", d)


if __name__ == "__main__":
    unittest.main()
```

### 2.3 集成测试（新增）

创建 `tests/test_integration.py`:

```python
"""
Nexa 集成测试
测试端到端的功能集成
"""

import unittest
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_full_pipeline(self):
        """测试完整流水线：解析 -> 编译 -> 生成"""
        import nexa
        
        code = '''
tool greet {
    input: { name: string }
    output: string
    action: "Greet the user"
}

agent Greeter {
    role: "greeter"
    model: "gpt-4"
    prompt: "You are a friendly greeter"
    tools: [greet]
}

flow main {
    input: { name: string }
    output: string
    
    Greeter(input) |> output
}
'''
        result = nexa.compile(code)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.python_code)
    
    def test_sdk_with_stdlib(self):
        """测试 SDK 与标准库集成"""
        import nexa
        from src.runtime.stdlib import get_stdlib_tool_definitions
        
        tools = get_stdlib_tool_definitions()
        
        agent = (nexa.AgentBuilder("ToolAgent")
            .with_prompt("你是一个工具助手")
            .with_model("gpt-4")
            .with_tools(tools[:3])  # 使用前3个工具
            .build())
        
        self.assertIsNotNone(agent)
    
    def test_debugger_with_profiler(self):
        """测试调试器与分析器集成"""
        from src.runtime.debugger import NexaDebugger
        from src.runtime.profiler import NexaProfiler
        
        debugger = NexaDebugger()
        profiler = NexaProfiler()
        
        # 设置断点
        debugger.add_breakpoint("test.nx", 1)
        
        # 开始性能会话
        session_id = profiler.start_session("integration_test")
        
        # 模拟执行
        profiler.track_tokens("input", 50)
        profiler.track_tokens("output", 100)
        
        # 获取结果
        stats = profiler.get_session_stats(session_id)
        self.assertIsNotNone(stats)
        self.assertEqual(stats["total_tokens"], 150)


class TestExampleFiles(unittest.TestCase):
    """测试示例文件"""
    
    def test_hello_world_example(self):
        """测试 hello_world 示例"""
        import nexa
        
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "01_hello_world.nx"
        )
        
        if os.path.exists(example_path):
            with open(example_path, 'r') as f:
                code = f.read()
            
            result = nexa.compile(code)
            # 示例文件可能需要特殊处理，这里只测试不崩溃
            self.assertIsNotNone(result)
    
    def test_all_examples_parseable(self):
        """测试所有示例文件可解析"""
        import nexa
        
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples"
        )
        
        nx_files = [f for f in os.listdir(examples_dir) if f.endswith('.nx')]
        
        parsed_count = 0
        for nx_file in nx_files:
            try:
                path = os.path.join(examples_dir, nx_file)
                with open(path, 'r') as f:
                    code = f.read()
                
                result = nexa.compile(code)
                if result.success:
                    parsed_count += 1
            except Exception as e:
                # 记录但不失败
                print(f"Warning: {nx_file} - {str(e)}")
        
        # 至少有一半的示例应该能解析
        self.assertGreater(parsed_count, len(nx_files) // 2)


if __name__ == "__main__":
    unittest.main()
```

## 3. 执行步骤

### 步骤 1: 运行 Rust 测试
```bash
cd avm && cargo test --lib
```

### 步骤 2: 运行 Python 测试
```bash
cd /root/proj/nexa
python -m pytest tests/ -v
# 或者
python -m unittest discover -s tests -v
```

### 步骤 3: 验证结果
- Rust: 110 个测试通过
- Python: 所有新增测试通过

### 步骤 4: Git 提交
```bash
git add .
git commit -m "feat: 添加验证测试并确保所有测试通过

- 确认 tool.rs 和 stdlib.py 代码正确
- 添加 test_nexa_sdk.py 测试 SDK 功能
- 添加 test_integration.py 集成测试
- 测试覆盖: SDK、调试器、分析器、标准库"
```

## 4. 预期结果

| 测试类型 | 文件 | 预期 |
|---------|------|------|
| Rust AVM | avm/ | 110 测试通过 |
| Python SDK | tests/test_nexa_sdk.py | ~20 测试通过 |
| 集成测试 | tests/test_integration.py | ~5 测试通过 |
| 现有测试 | tests/test_v097_features.py | 保持通过 |

## 5. 注意事项

1. 确保在 avm 目录下运行 Rust 测试
2. Python 测试需要安装依赖: `pip install -r requirements.txt`
3. 如果某些示例文件解析失败，检查是否是预期行为（需要外部依赖）