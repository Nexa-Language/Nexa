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
        from src import nexa_sdk
        self.assertIsNotNone(nexa_sdk.__version__)
    
    def test_compile_simple(self):
        """测试简单编译"""
        from src.nexa_sdk import compile as nexa_compile
        code = '''
agent TestBot {
    role: "test"
    model: "gpt-4"
    prompt: "You are a test bot"
}
'''
        result = nexa_compile(code)
        self.assertTrue(result.success)
    
    def test_agent_builder(self):
        """测试 Agent 构建器"""
        from src.nexa_sdk import AgentBuilder
        
        agent = (AgentBuilder("TestAgent")
            .with_prompt("测试提示")
            .with_model("gpt-4")
            .with_temperature(0.5)
            .build())
        
        self.assertIsNotNone(agent)
    
    def test_tool_builder(self):
        """测试 Tool 构建器"""
        from src.nexa_sdk import ToolBuilder
        
        tool = (ToolBuilder("test_tool")
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
        from src.runtime.debugger import NexaDebugger
        
        debugger = NexaDebugger()
        bp = debugger.set_breakpoint("agent", "TestAgent")
        
        self.assertIsNotNone(bp)
        self.assertEqual(bp.target, "TestAgent")
        
        # 测试删除断点
        result = debugger.remove_breakpoint("agent", "TestAgent")
        self.assertTrue(result)
    
    def test_variable_watch(self):
        """测试变量监视"""
        from src.runtime.debugger import NexaDebugger
        
        debugger = NexaDebugger()
        watch = debugger.add_watch("test_var", "test_expression")
        
        self.assertIsNotNone(watch)
        
        # 测试获取监视变量
        watches = debugger.watches
        self.assertEqual(len(watches), 1)


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
        profiler.start()
        
        # 追踪 Agent 执行
        profiler.track_agent_start("TestAgent", "test input")
        profiler.track_agent_end("TestAgent", prompt_tokens=100, completion_tokens=50)
        
        # 获取统计
        stats = profiler.get_stats()
        self.assertIsNotNone(stats)
        profiler.stop()
    
    def test_execution_time_tracking(self):
        """测试执行时间追踪"""
        from src.runtime.profiler import NexaProfiler
        import time
        
        profiler = NexaProfiler()
        profiler.start()
        
        profiler.track_agent_start("TimingAgent")
        time.sleep(0.01)  # 10ms
        profiler.track_agent_end("TimingAgent")
        
        stats = profiler.get_stats()
        self.assertIsNotNone(stats)
        profiler.stop()


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
        
        # 测试 json_get
        result = execute_stdlib_tool("json_get", text='{"data": {"items": [1, 2, 3]}}', path="data.items")
        self.assertIsNotNone(result)
    
    def test_text_tools(self):
        """测试文本工具"""
        from src.runtime.stdlib import execute_stdlib_tool
        import json
        
        # 测试 text_split
        split_result = execute_stdlib_tool("text_split", text="a,b,c", delimiter=",")
        split_data = json.loads(split_result)
        self.assertEqual(split_data["count"], 3)
        
        # 测试 text_replace
        replace_result = execute_stdlib_tool("text_replace", text="hello world", old="world", new="nexa")
        self.assertEqual(replace_result, "hello nexa")
    
    def test_math_tools(self):
        """测试数学工具"""
        from src.runtime.stdlib import execute_stdlib_tool
        import json
        
        result = execute_stdlib_tool("math_calc", expression="2 + 3 * 4")
        data = json.loads(result)
        self.assertEqual(data["result"], 14)
        
        # 测试 math_random (返回随机数字符串)
        random_result = execute_stdlib_tool("math_random", min_val=1, max_val=100)
        random_val = int(random_result)
        self.assertGreaterEqual(random_val, 1)
        self.assertLessEqual(random_val, 100)
    
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
    
    def test_namespace_map(self):
        """测试命名空间映射"""
        from src.runtime.stdlib import STD_NAMESPACE_MAP
        
        self.assertIn("std.fs", STD_NAMESPACE_MAP)
        self.assertIn("std.http", STD_NAMESPACE_MAP)
        self.assertIn("std.time", STD_NAMESPACE_MAP)
        
        # 验证部分工具存在（只测试已注册的工具）
        from src.runtime.stdlib import get_stdlib_tools
        tools = get_stdlib_tools()
        
        # 测试每个命名空间至少有一个工具存在
        for namespace, tool_names in STD_NAMESPACE_MAP.items():
            found_any = any(tool_name in tools for tool_name in tool_names)
            self.assertTrue(found_any, f"No tools found for namespace {namespace}")


class TestSDKHelpers(unittest.TestCase):
    """测试 SDK 辅助函数"""
    
    def test_run_function_exists(self):
        """测试 run 函数存在"""
        from src.nexa_sdk import run
        self.assertTrue(callable(run))
    
    def test_compile_function_exists(self):
        """测试 compile 函数存在"""
        from src.nexa_sdk import compile
        self.assertTrue(callable(compile))
    
    def test_build_function_exists(self):
        """测试 build 函数存在"""
        from src.nexa_sdk import build
        self.assertTrue(callable(build))
    
    def test_agent_builder_exists(self):
        """测试 AgentBuilder 存在"""
        from src.nexa_sdk import AgentBuilder
        self.assertTrue(callable(AgentBuilder))
    
    def test_tool_builder_exists(self):
        """测试 ToolBuilder 存在"""
        from src.nexa_sdk import ToolBuilder
        self.assertTrue(callable(ToolBuilder))


if __name__ == "__main__":
    unittest.main()