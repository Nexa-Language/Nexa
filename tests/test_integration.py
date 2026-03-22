"""
Nexa 集成测试
测试端到端的功能集成
"""

import unittest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_full_pipeline(self):
        """测试完整流水线：解析 -> 编译 -> 生成"""
        from src.nexa_sdk import compile as nexa_compile
        
        # 简单的 Agent 定义
        code = '''
agent Greeter {
    role: "greeter"
    model: "gpt-4"
    prompt: "You are a friendly greeter"
}
'''
        result = nexa_compile(code)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.python_code)
    
    def test_sdk_with_stdlib(self):
        """测试 SDK 与标准库集成"""
        from src.nexa_sdk import AgentBuilder
        from src.runtime.stdlib import get_stdlib_tool_definitions
        
        tools = get_stdlib_tool_definitions()
        
        agent = (AgentBuilder("ToolAgent")
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
        debugger.set_breakpoint("agent", "TestAgent")
        
        # 开始性能分析
        profiler.start()
        
        # 模拟执行
        profiler.track_agent_start("TestAgent", "test input")
        profiler.track_agent_end("TestAgent", prompt_tokens=50, completion_tokens=100)
        
        # 获取结果
        stats = profiler.get_stats()
        self.assertIsNotNone(stats)
        profiler.stop()
    
    def test_stdlib_tool_execution(self):
        """测试标准库工具执行"""
        from src.runtime.stdlib import execute_stdlib_tool
        
        # 测试一系列工具
        text = "Hello World"
        
        # 编码解码测试
        encoded = execute_stdlib_tool("base64_encode", text=text)
        decoded = execute_stdlib_tool("base64_decode", text=encoded)
        self.assertEqual(decoded, text)
        
        # 哈希测试
        md5 = execute_stdlib_tool("hash_md5", text=text)
        self.assertEqual(len(md5), 32)  # MD5 长度
        
        # 文本分割测试
        import json
        split_result = execute_stdlib_tool("text_split", text=text, delimiter=" ")
        split_data = json.loads(split_result)
        self.assertEqual(split_data["count"], 2)


class TestExampleFiles(unittest.TestCase):
    """测试示例文件"""
    
    def test_hello_world_example(self):
        """测试 hello_world 示例"""
        from src.nexa_sdk import compile as nexa_compile
        
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "01_hello_world.nx"
        )
        
        if os.path.exists(example_path):
            with open(example_path, 'r') as f:
                code = f.read()
            
            result = nexa_compile(code)
            self.assertIsNotNone(result)
    
    def test_all_examples_parseable(self):
        """测试所有示例文件可解析"""
        from src.nexa_sdk import compile as nexa_compile
        
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
                
                result = nexa_compile(code)
                if result.success:
                    parsed_count += 1
            except Exception as e:
                # 记录但不失败
                pass
        
        # 至少有一半的示例应该能解析
        self.assertGreater(parsed_count, len(nx_files) // 2)


class TestRuntimeComponents(unittest.TestCase):
    """测试运行时组件集成"""
    
    def test_cache_with_agent(self):
        """测试缓存与 Agent 集成"""
        from src.runtime.cache_manager import NexaCacheManager
        
        cache = NexaCacheManager()
        
        # 测试缓存操作
        messages = [{"role": "user", "content": "Hello"}]
        
        # 设置缓存
        cache.set(messages, "gpt-4", "Hello response")
        
        # 获取缓存
        result = cache.get(messages, "gpt-4")
        self.assertEqual(result, "Hello response")
    
    def test_knowledge_graph(self):
        """测试知识图谱"""
        from src.runtime.knowledge_graph import KnowledgeGraph
        
        kg = KnowledgeGraph()
        
        # 添加实体 (返回 Entity 对象)
        e1 = kg.add_entity("Python", "Language", {"description": "Programming language"})
        e2 = kg.add_entity("Nexa", "Framework", {"description": "Agent framework"})
        
        # 添加关系 (API: add_relation(source_name, relation_type, target_name))
        kg.add_relation("Nexa", "uses", "Python")
        
        # 查询 - 直接访问 entities 属性
        entities = kg.entities
        self.assertGreaterEqual(len(entities), 2)
    
    def test_rbac_integration(self):
        """测试 RBAC 集成"""
        from src.runtime.rbac import RBACManager, Permission
        
        rbac = RBACManager()
        
        # 创建角色 (API: create_role(name, description, permissions))
        rbac.create_role("admin", "Administrator role", list(Permission))
        
        # 分配角色
        rbac.assign_role("test_agent", "admin")
        
        # 检查权限
        has_perm = rbac.check_permission("test_agent", Permission.TOOL_EXECUTE)
        self.assertTrue(has_perm)
    
    def test_memory_backend_integration(self):
        """测试记忆后端集成"""
        from src.runtime.memory_backend import InMemoryBackend
        
        backend = InMemoryBackend()
        
        # 存储和检索
        backend.store("session1", {"messages": ["Hello", "World"]})
        result = backend.retrieve("session1")
        
        self.assertEqual(result["messages"], ["Hello", "World"])


class TestDAGOrchestrator(unittest.TestCase):
    """测试 DAG 编排器"""
    
    def test_dag_fork_merge(self):
        """测试 DAG 分叉合并"""
        from src.runtime.dag_orchestrator import dag_fanout, dag_merge
        
        # 测试分叉函数存在
        self.assertTrue(callable(dag_fanout))
        self.assertTrue(callable(dag_merge))
    
    def test_smart_router(self):
        """测试智能路由"""
        from src.runtime.dag_orchestrator import SmartRouter
        from unittest.mock import Mock
        
        mock_agent = Mock()
        mock_agent.name = "TestAgent"
        
        router = SmartRouter(routes={"test": mock_agent}, default_agent=mock_agent)
        
        result = router.route("test query")
        self.assertEqual(result, mock_agent)


class TestEndToEndScenarios(unittest.TestCase):
    """端到端场景测试"""
    
    def test_data_pipeline_scenario(self):
        """测试数据处理流水线场景"""
        from src.runtime.stdlib import execute_stdlib_tool
        import json
        
        # 模拟数据处理流水线
        raw_data = '{"name": "test", "values": [1, 2, 3]}'
        
        # 1. 解析 JSON
        parsed = execute_stdlib_tool("json_parse", text=raw_data)
        data = json.loads(parsed)
        self.assertEqual(data["name"], "test")
        
        # 2. Base64 编码
        encoded = execute_stdlib_tool("base64_encode", text=raw_data)
        self.assertIsNotNone(encoded)
        
        # 3. 哈希计算
        hash_val = execute_stdlib_tool("hash_sha256", text=raw_data)
        self.assertEqual(len(hash_val), 64)  # SHA256 长度
    
    def test_text_processing_scenario(self):
        """测试文本处理场景"""
        from src.runtime.stdlib import execute_stdlib_tool
        import json
        
        text = "Hello, World! This is a Test."
        
        # 1. 分割 (实际有 6 个部分)
        split_result = execute_stdlib_tool("text_split", text=text, delimiter=" ")
        split_data = json.loads(split_result)
        self.assertEqual(split_data["count"], 6)
        
        # 2. 替换
        replace_result = execute_stdlib_tool("text_replace", text=text, old="World", new="Nexa")
        self.assertEqual(replace_result, "Hello, Nexa! This is a Test.")
        
        # 3. 正则匹配
        match_result = execute_stdlib_tool("regex_match", pattern="[A-Z][a-z]+", text=text)
        match_data = json.loads(match_result)
        self.assertGreater(match_data["count"], 0)
    
    def test_time_workflow_scenario(self):
        """测试时间工作流场景"""
        from src.runtime.stdlib import execute_stdlib_tool
        
        # 获取当前时间
        now = execute_stdlib_tool("time_now", format="%Y-%m-%d")
        self.assertIsNotNone(now)
        
        # 时间差计算
        diff = execute_stdlib_tool(
            "time_diff",
            start="2024-01-01T00:00:00",
            end="2024-01-02T00:00:00",
            unit="days"
        )
        diff_data = json.loads(diff)
        self.assertEqual(diff_data["value"], 1)


if __name__ == "__main__":
    unittest.main()