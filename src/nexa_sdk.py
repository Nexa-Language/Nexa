# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================
"""
Nexa SDK - Python 互操作接口

提供从 Python 直接使用 Nexa 功能的 API:
- 运行 Nexa 脚本
- 动态创建 Agent
- 编译 Nexa 代码
- 访问运行时组件

使用示例:
    import nexa
    
    # 运行脚本
    result = nexa.run("script.nx")
    
    # 创建 Agent
    bot = nexa.Agent(name="MyBot", prompt="...", model="gpt-4")
    response = bot.run("Hello!")
    
    # 编译代码
    module = nexa.compile("agent TestBot { prompt: 'test' }")
"""

import os
import sys
import io
import contextlib
import importlib.util
import tempfile
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from pathlib import Path

# 导入 Nexa 核心组件
from .nexa_parser import parse
from .ast_transformer import NexaTransformer
from .code_generator import CodeGenerator
from .runtime.agent import NexaAgent
from .runtime.cache_manager import get_cache_manager, init_cache_manager
from .runtime.knowledge_graph import get_knowledge_graph
from .runtime.rbac import get_rbac_manager, Permission, Role


# ==================== 版本信息 ====================

__version__ = "v1.3.7"
__author__ = "Nexa Genesis Team"


# ==================== 编译结果 ====================

@dataclass
class CompileResult:
    """编译结果"""
    success: bool
    python_code: Optional[str] = None
    error: Optional[str] = None
    bytecode_size: int = 0
    compile_time_ms: float = 0.0


# ==================== 运行结果 ====================

@dataclass
class RunResult:
    """运行结果"""
    success: bool
    result: Any = None
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0.0
    tokens_used: int = 0


# ==================== Agent Builder ====================

@dataclass
class AgentBuilder:
    """
    Agent 构建器 - 流式 API 创建 Agent
    
    使用示例:
        agent = (nexa.AgentBuilder("MyBot")
            .with_prompt("你是一个有用的助手")
            .with_model("gpt-4")
            .with_tools([tool1, tool2])
            .with_cache(True)
            .build())
    """
    name: str
    prompt: str = ""
    model: str = "gpt-4"
    role: str = ""
    tools: List[Dict] = field(default_factory=list)
    protocol: Any = None
    cache: bool = False
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    experience: Optional[str] = None
    
    def with_prompt(self, prompt: str) -> "AgentBuilder":
        """设置 prompt"""
        self.prompt = prompt
        return self
    
    def with_model(self, model: str) -> "AgentBuilder":
        """设置模型"""
        self.model = model
        return self
    
    def with_role(self, role: str) -> "AgentBuilder":
        """设置角色"""
        self.role = role
        return self
    
    def with_tools(self, tools: List[Dict]) -> "AgentBuilder":
        """设置工具列表"""
        self.tools = tools
        return self
    
    def add_tool(self, name: str, description: str, parameters: Dict) -> "AgentBuilder":
        """添加单个工具"""
        self.tools.append({
            "name": name,
            "description": description,
            "parameters": parameters
        })
        return self
    
    def with_protocol(self, protocol: Any) -> "AgentBuilder":
        """设置输出协议"""
        self.protocol = protocol
        return self
    
    def with_cache(self, cache: bool = True) -> "AgentBuilder":
        """启用/禁用缓存"""
        self.cache = cache
        return self
    
    def with_max_tokens(self, max_tokens: int) -> "AgentBuilder":
        """设置最大 token 数"""
        self.max_tokens = max_tokens
        return self
    
    def with_temperature(self, temperature: float) -> "AgentBuilder":
        """设置温度"""
        self.temperature = temperature
        return self
    
    def with_experience(self, experience_file: str) -> "AgentBuilder":
        """设置长期记忆文件"""
        self.experience = experience_file
        return self
    
    def build(self) -> NexaAgent:
        """构建 Agent 实例"""
        return NexaAgent(
            name=self.name,
            prompt=self.prompt,
            tools=self.tools if self.tools else None,
            model=self.model,
            role=self.role,
            protocol=self.protocol,
            max_tokens=self.max_tokens,
            stream=False,
            cache=self.cache,
            experience=self.experience
        )


# ==================== Tool Builder ====================

@dataclass
class ToolBuilder:
    """
    Tool 构建器
    
    使用示例:
        tool = (nexa.ToolBuilder("Calculator")
            .with_description("执行数学计算")
            .with_parameter("expression", "string", "数学表达式")
            .build())
    """
    name: str
    description: str = ""
    parameters: Dict[str, Dict] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    mcp_source: Optional[str] = None
    
    def with_description(self, description: str) -> "ToolBuilder":
        """设置描述"""
        self.description = description
        return self
    
    def with_parameter(self, name: str, type_: str, description: str = "", 
                       required: bool = True, enum: List[str] = None) -> "ToolBuilder":
        """添加参数"""
        param = {
            "type": type_,
            "description": description
        }
        if enum:
            param["enum"] = enum
        self.parameters[name] = param
        if required:
            self.required.append(name)
        return self
    
    def with_mcp(self, mcp_source: str) -> "ToolBuilder":
        """设置 MCP 源"""
        self.mcp_source = mcp_source
        return self
    
    def build(self) -> Dict:
        """构建工具定义"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required
            },
            "mcp": self.mcp_source
        }


# ==================== 核心函数 ====================

def compile(source: str) -> CompileResult:
    """
    编译 Nexa 源代码
    
    Args:
        source: Nexa 源代码字符串或文件路径
        
    Returns:
        CompileResult: 编译结果
    """
    import time
    start = time.time()
    
    try:
        # 判断是文件还是代码
        if source.endswith('.nx') and os.path.exists(source):
            with open(source, 'r', encoding='utf-8') as f:
                source = f.read()
        
        # 解析
        tree = parse(source)
        
        # 转换 AST
        transformer = NexaTransformer()
        ast = transformer.transform(tree)
        
        # 生成 Python 代码
        codegen = CodeGenerator(ast)
        py_code = codegen.generate()
        
        return CompileResult(
            success=True,
            python_code=py_code,
            bytecode_size=len(py_code.encode()),
            compile_time_ms=(time.time() - start) * 1000
        )
    except Exception as e:
        return CompileResult(
            success=False,
            error=str(e),
            compile_time_ms=(time.time() - start) * 1000
        )


def run(source: str, inputs: Optional[Dict[str, Any]] = None) -> RunResult:
    """
    运行 Nexa 脚本
    
    Args:
        source: Nexa 源代码字符串或文件路径
        inputs: 输入变量字典
        
    Returns:
        RunResult: 运行结果
    """
    import time
    start = time.time()
    inputs = inputs or {}
    
    try:
        # 编译
        compile_result = compile(source)
        if not compile_result.success:
            return RunResult(
                success=False,
                stderr=compile_result.error,
                execution_time_ms=(time.time() - start) * 1000
            )
        
        py_code = compile_result.python_code
        
        # 执行
        f_out = io.StringIO()
        f_err = io.StringIO()
        
        # 创建临时模块
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(py_code)
            temp_path = f.name
        
        try:
            module_name = "nexa_runtime_" + os.path.basename(temp_path).replace('.py', '')
            spec = importlib.util.spec_from_file_location(module_name, temp_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            
            # 捕获输出
            with contextlib.redirect_stdout(f_out), contextlib.redirect_stderr(f_err):
                spec.loader.exec_module(module)
                
                # 注入输入
                for k, v in inputs.items():
                    setattr(module, k, v)
                
                result = None
                if hasattr(module, 'flow_main'):
                    result = module.flow_main()
        finally:
            os.unlink(temp_path)
        
        return RunResult(
            success=True,
            result=result,
            stdout=f_out.getvalue(),
            stderr=f_err.getvalue(),
            execution_time_ms=(time.time() - start) * 1000
        )
    except Exception as e:
        return RunResult(
            success=False,
            stderr=str(e),
            execution_time_ms=(time.time() - start) * 1000
        )


def build(source: str, output_path: str) -> bool:
    """
    编译 Nexa 脚本并保存为 Python 文件
    
    Args:
        source: Nexa 源代码字符串或文件路径
        output_path: 输出 Python 文件路径
        
    Returns:
        bool: 是否成功
    """
    result = compile(source)
    if result.success:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.python_code)
        return True
    return False


def test(source: str) -> Dict[str, Any]:
    """
    运行 Nexa 测试
    
    Args:
        source: Nexa 测试代码或文件路径
        
    Returns:
        Dict: 测试结果
    """
    result = run(source)
    
    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "execution_time_ms": result.execution_time_ms
    }


# ==================== 快捷函数 ====================

def Agent(name: str, prompt: str = "", model: str = "gpt-4", **kwargs) -> NexaAgent:
    """
    快速创建 Agent 实例
    
    Args:
        name: Agent 名称
        prompt: 系统提示
        model: 模型名称
        **kwargs: 其他参数 (tools, cache, etc.)
        
    Returns:
        NexaAgent: Agent 实例
    """
    return NexaAgent(
        name=name,
        prompt=prompt,
        model=model,
        **kwargs
    )


def Tool(name: str, description: str = "", parameters: Dict = None) -> Dict:
    """
    快速创建工具定义
    
    Args:
        name: 工具名称
        description: 工具描述
        parameters: 参数定义
        
    Returns:
        Dict: 工具定义字典
    """
    return {
        "name": name,
        "description": description,
        "parameters": parameters or {}
    }


# ==================== 运行时访问 ====================

def get_runtime() -> "NexaRuntime":
    """获取 Nexa 运行时实例"""
    from .api import NexaRuntime
    return NexaRuntime()


def get_cache() -> Any:
    """获取缓存管理器"""
    return get_cache_manager()


def get_knowledge() -> Any:
    """获取知识图谱"""
    return get_knowledge_graph()


def get_rbac() -> Any:
    """获取 RBAC 管理器"""
    return get_rbac_manager()


# ==================== 批处理 ====================

def batch_run(sources: List[str], parallel: bool = True) -> List[RunResult]:
    """
    批量运行多个 Nexa 脚本
    
    Args:
        sources: 源代码/文件路径列表
        parallel: 是否并行执行
        
    Returns:
        List[RunResult]: 运行结果列表
    """
    if parallel:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(len(sources), 4)) as executor:
            results = list(executor.map(run, sources))
        return results
    else:
        return [run(source) for source in sources]


# ==================== 导出 ====================

__all__ = [
    # 版本
    "__version__",
    "__author__",
    
    # 核心函数
    "compile",
    "run",
    "build",
    "test",
    "batch_run",
    
    # 快捷创建
    "Agent",
    "Tool",
    "AgentBuilder",
    "ToolBuilder",
    
    # 结果类型
    "CompileResult",
    "RunResult",
    
    # 运行时访问
    "get_runtime",
    "get_cache",
    "get_knowledge",
    "get_rbac",
    
    # 从子模块导出
    "NexaAgent",
    "Permission",
    "Role",
]
