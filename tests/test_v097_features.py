"""
Nexa v0.9.7-rc 功能测试套件
测试所有新添加的运行时模块
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch, MagicMock


class TestDAGOrchestrator(unittest.TestCase):
    """测试 DAG 编排模块"""
    
    def test_import_dag_module(self):
        """测试 DAG 模块导入"""
        from src.runtime.dag_orchestrator import dag_fanout, dag_merge, dag_branch, SmartRouter
        self.assertTrue(callable(dag_fanout))
        self.assertTrue(callable(dag_merge))
        self.assertTrue(callable(dag_branch))
        self.assertTrue(callable(SmartRouter))
    
    def test_dag_node_types(self):
        """测试 DAG 节点类型"""
        from src.runtime.dag_orchestrator import DAGNode, DAGNodeType, ForkNode, MergeNode
        node = DAGNode(id="test", node_type=DAGNodeType.AGENT)
        self.assertEqual(node.id, "test")
        self.assertEqual(node.node_type, DAGNodeType.AGENT)
    
    def test_smart_router(self):
        """测试智能路由器"""
        from src.runtime.dag_orchestrator import SmartRouter
        mock_agent = Mock()
        mock_agent.name = "TestAgent"
        router = SmartRouter(routes={"test": mock_agent}, default_agent=mock_agent)
        self.assertEqual(router.route("test query"), mock_agent)


class TestCacheManager(unittest.TestCase):
    """测试缓存管理模块"""
    
    def test_import_cache_manager(self):
        """测试缓存管理器导入"""
        from src.runtime.cache_manager import NexaCacheManager
        self.assertTrue(callable(NexaCacheManager))


class TestCompactor(unittest.TestCase):
    """测试上下文压缩模块"""
    
    def test_import_compactor(self):
        """测试压缩器导入"""
        from src.runtime.compactor import ContextCompactor
        self.assertTrue(callable(ContextCompactor))


class TestLongTermMemory(unittest.TestCase):
    """测试长期记忆模块"""
    
    def test_import_long_term_memory(self):
        """测试长期记忆导入"""
        from src.runtime.long_term_memory import LongTermMemory
        self.assertTrue(callable(LongTermMemory))


class TestKnowledgeGraph(unittest.TestCase):
    """测试知识图谱模块"""
    
    def test_import_knowledge_graph(self):
        """测试知识图谱导入"""
        from src.runtime.knowledge_graph import KnowledgeGraph, Entity, Relation
        self.assertTrue(callable(KnowledgeGraph))
        self.assertTrue(callable(Entity))
        self.assertTrue(callable(Relation))


class TestMemoryBackend(unittest.TestCase):
    """测试记忆后端模块"""
    
    def test_import_memory_backend(self):
        """测试记忆后端导入"""
        from src.runtime.memory_backend import SQLiteMemoryBackend, InMemoryBackend, VectorMemoryBackend
        self.assertTrue(callable(SQLiteMemoryBackend))
        self.assertTrue(callable(InMemoryBackend))
        self.assertTrue(callable(VectorMemoryBackend))
    
    def test_in_memory_backend(self):
        """测试内存后端"""
        from src.runtime.memory_backend import InMemoryBackend
        
        backend = InMemoryBackend()
        backend.store("key1", {"data": "value1"})
        
        result = backend.retrieve("key1")
        self.assertEqual(result["data"], "value1")
    
    def test_sqlite_backend(self):
        """测试 SQLite 后端"""
        from src.runtime.memory_backend import SQLiteMemoryBackend
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            backend = SQLiteMemoryBackend(db_path=db_path)
            
            backend.store("key1", {"data": "value1"})
            result = backend.retrieve("key1")
            self.assertEqual(result["data"], "value1")


class TestRBAC(unittest.TestCase):
    """测试 RBAC 权限控制模块"""
    
    def test_import_rbac(self):
        """测试 RBAC 导入"""
        from src.runtime.rbac import RBACManager, Role, Permission, SecurityContext
        self.assertTrue(callable(RBACManager))
        self.assertTrue(callable(Role))
        self.assertTrue(callable(SecurityContext))


class TestOpenCLI(unittest.TestCase):
    """测试 Open-CLI 模块"""
    
    def test_import_opencli(self):
        """测试 OpenCLI 导入"""
        from src.runtime.opencli import OpenCLI, NexaCLI
        self.assertTrue(callable(OpenCLI))
        self.assertTrue(callable(NexaCLI))
    
    def test_cli_initialization(self):
        """测试 CLI 初始化"""
        from src.runtime.opencli import NexaCLI
        
        cli = NexaCLI()
        self.assertIsNotNone(cli)


class TestDAGParser(unittest.TestCase):
    """测试 DAG 表达式解析"""
    
    def test_dag_fork_parsing(self):
        """测试分叉表达式解析"""
        from src.nexa_parser import parse
        from src.ast_transformer import NexaTransformer
        
        code = '''
agent A { role: "test", model: "gpt-4", prompt: "test" }
agent B { role: "test", model: "gpt-4", prompt: "test" }
flow main {
    result = "input" |>> [A, B];
}
'''
        tree = parse(code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        
        # 找到 flow 中的赋值语句
        flow = None
        for item in ast['body']:
            if item.get('type') == 'FlowDeclaration':
                flow = item
                break
        
        self.assertIsNotNone(flow)
        stmt = flow['body'][0]
        self.assertEqual(stmt['type'], 'AssignmentStatement')
        
        expr = stmt['value']
        self.assertEqual(expr['type'], 'DAGForkExpression')
        self.assertEqual(expr['agents'], ['A', 'B'])
    
    def test_dag_merge_parsing(self):
        """测试合流表达式解析"""
        from src.nexa_parser import parse
        from src.ast_transformer import NexaTransformer
        
        code = '''
agent A { role: "test", model: "gpt-4", prompt: "test" }
agent B { role: "test", model: "gpt-4", prompt: "test" }
agent C { role: "test", model: "gpt-4", prompt: "test" }
flow main {
    result = [A, B] &>> C;
}
'''
        tree = parse(code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        
        flow = None
        for item in ast['body']:
            if item.get('type') == 'FlowDeclaration':
                flow = item
                break
        
        self.assertIsNotNone(flow)
        stmt = flow['body'][0]
        self.assertEqual(stmt['type'], 'AssignmentStatement')
        
        expr = stmt['value']
        self.assertEqual(expr['type'], 'DAGMergeExpression')
        self.assertEqual(expr['agents'], ['A', 'B'])
    
    def test_dag_branch_parsing(self):
        """测试条件分支表达式解析"""
        from src.nexa_parser import parse
        from src.ast_transformer import NexaTransformer
        
        code = '''
agent A { role: "test", model: "gpt-4", prompt: "test" }
agent B { role: "test", model: "gpt-4", prompt: "test" }
flow main {
    result = "input" ?? A : B;
}
'''
        tree = parse(code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        
        flow = None
        for item in ast['body']:
            if item.get('type') == 'FlowDeclaration':
                flow = item
                break
        
        self.assertIsNotNone(flow)
        stmt = flow['body'][0]
        self.assertEqual(stmt['type'], 'AssignmentStatement')
        
        expr = stmt['value']
        self.assertEqual(expr['type'], 'DAGBranchExpression')


class TestDAGCodeGeneration(unittest.TestCase):
    """测试 DAG 表达式代码生成"""
    
    def test_dag_fork_code_generation(self):
        """测试分叉表达式代码生成"""
        from src.nexa_parser import parse
        from src.ast_transformer import NexaTransformer
        from src.code_generator import CodeGenerator
        
        code = '''
agent A { role: "test", model: "gpt-4", prompt: "test" }
agent B { role: "test", model: "gpt-4", prompt: "test" }
flow main {
    result = "input" |>> [A, B];
}
'''
        tree = parse(code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        
        generator = CodeGenerator(ast)
        python_code = generator.generate()
        
        self.assertIn('dag_fanout', python_code)
        self.assertIn('A', python_code)
        self.assertIn('B', python_code)
    
    def test_dag_merge_code_generation(self):
        """测试合流表达式代码生成"""
        from src.nexa_parser import parse
        from src.ast_transformer import NexaTransformer
        from src.code_generator import CodeGenerator
        
        code = '''
agent A { role: "test", model: "gpt-4", prompt: "test" }
agent B { role: "test", model: "gpt-4", prompt: "test" }
agent C { role: "test", model: "gpt-4", prompt: "test" }
flow main {
    result = [A, B] &>> C;
}
'''
        tree = parse(code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        
        generator = CodeGenerator(ast)
        python_code = generator.generate()
        
        self.assertIn('dag_merge', python_code)
        self.assertIn('A', python_code)
        self.assertIn('B', python_code)
        self.assertIn('C', python_code)


class TestAllExamplesCompile(unittest.TestCase):
    """测试所有示例文件编译"""
    
    def test_example_01_compiles(self):
        """测试 01_hello_world.nx 编译"""
        from src.nexa_parser import parse
        from src.ast_transformer import NexaTransformer
        from src.code_generator import CodeGenerator
        
        with open('examples/01_hello_world.nx', 'r', encoding='utf-8') as f:
            code = f.read()
        
        tree = parse(code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        generator = CodeGenerator(ast)
        python_code = generator.generate()
        
        self.assertIn('NexaAgent', python_code)
    
    def test_example_15_dag_compiles(self):
        """测试 15_dag_topology.nx 编译"""
        from src.nexa_parser import parse
        from src.ast_transformer import NexaTransformer
        from src.code_generator import CodeGenerator
        
        with open('examples/15_dag_topology.nx', 'r', encoding='utf-8') as f:
            code = f.read()
        
        tree = parse(code)
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        generator = CodeGenerator(ast)
        python_code = generator.generate()
        
        self.assertIn('dag_fanout', python_code)
        self.assertIn('dag_merge', python_code)
        self.assertIn('dag_branch', python_code)


if __name__ == '__main__':
    unittest.main(verbosity=2)