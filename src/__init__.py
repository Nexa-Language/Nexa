"""
Nexa - 智能体原生编程语言 SDK

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

# 核心运行时
from .api import NexaRuntime

# SDK 函数和类
from .nexa_sdk import (
    # 版本
    __version__,
    __author__,
    
    # 核心函数
    compile,
    run,
    build,
    test,
    batch_run,
    
    # 快捷创建
    Agent,
    Tool,
    AgentBuilder,
    ToolBuilder,
    
    # 结果类型
    CompileResult,
    RunResult,
    
    # 运行时访问
    get_runtime,
    get_cache,
    get_knowledge,
    get_rbac,
)

# 运行时组件
from .runtime.agent import NexaAgent
from .runtime.rbac import Permission, Role
from .runtime.cache_manager import get_cache_manager, init_cache_manager
from .runtime.knowledge_graph import get_knowledge_graph

__all__ = [
    # 版本
    "__version__",
    "__author__",
    
    # 核心类
    "NexaRuntime",
    
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
    
    # 运行时组件
    "NexaAgent",
    "Permission",
    "Role",
    "get_cache_manager",
    "init_cache_manager",
    "get_knowledge_graph",
]
