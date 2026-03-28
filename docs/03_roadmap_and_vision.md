# Nexa 路线图：从 MVP 到 AVM (Agent Virtual Machine)

Nexa 语言的演进路线严格遵循 "Think Big, Start Small" 的原则。我们的终极目标是创建一个原生且安全的智能体执行引擎。

## 阶段 1-4: v0.1 到 v0.8.x (已完成 ✅)
覆盖了 MVP 转译器、管道操作、架构重构、安全模块 (.nxs/.nxlib)、契约式编程 (Protocols)、多模型路由、持久化记忆及 Markdown 动态工具体系编排。

## 阶段 5: v0.9-alpha 认知与治理增强 (已完成 ✅)
- [x] 原生支持声明 `uses mcp:"..."` 来引入外部服务，形成一个真正的工具生态系统。
- [x] 基于正则的 Heuristic Fast-Path `semantic_if ... fast_match`。
- [x] 导入 python 运行时：增强 SDK Interop，允许动态通过 `importlib` 加载底层框架。
- [x] 提供 `test` 子类，可以进行各种测试，比如代理连通性测试。

## 阶段 6: v1.0+ 架构演进待办池 (Feature Backlog) 🚀
以下内容已在主创团队决议后纳入 v1.0 乃至更长远的未来视界：

- [x] **复杂拓扑 DAG 支持：** 扩展 `>>` 运算符，支持分叉、合流等高阶数据流转编排。（v0.9.6-rc 实现）
- [x] **原生异常处理：** 引入 `try/catch` 语法块，允许开发者在脚本层捕获运行时异常。
- [x] **Rust AVM 底座：** 从 Python 脚本解释转译模式跨越至基于 Rust 编写的独立编译型 Agent Virtual Machine (AVM)。（v1.0 实现，110个测试通过）
- [x] **WASM 安全沙盒：** 在 AVM 中引入 WebAssembly，对外部 `tool` 执行提供强隔离与跨平台兼容性。（v1.0 实现，wasmtime 集成）
- [ ] **可视化 DAG 编辑器：** 提供基于 Web 的节点拖拽界面，支持逆向生成 Nexa 代码。（架构规划已完成）
- [x] **智能调度器 (Smart Scheduler)：** 在 AVM 层基于系统负载、Agent 优先级动态分配并发资源。（v1.0 基础实现）
- [x] **向量虚存分页 (Context Paging)：** AVM 接管内存，自动执行对话历史的向量化置换与透明加载。（v1.0 基础实现）
- [x] **运行时动态反射：** 支持在执行期动态生成新 Agent 实例或动态重载 Model 配置。
- [x] **RBAC 权限访问控制：** 为不同 Agent 或流定义安全角色，确保工具调用的最小权限原则。（v0.9.6-rc 实现）
- [x] **Open-CLI 深度接入：** 原生集成类似 `spectreconsole/open-cli` 的宿主命令行交互标准。（v0.9.6-rc 实现）
- [x] **编程语言层面的缓存机制：** 因为agent本身的特点，同一次对话里面会有很大一部分input是重复的，设计一个原生的缓存机制可以极大提升效率。（v0.9.6-rc 实现：语义缓存、多级缓存）
- [x] **上下文压缩工具compactor：** 设计一个原生的上下文压缩工具，能够在不丢失关键信息的前提下压缩对话历史，提升模型处理长上下文的能力。（v0.9.6-rc 实现）
- [x] **一个长久记忆文件：** 参考AReal的CLAUDE.md的设计，设计一个长期记忆文件，能够记录agent的长期记忆和经验教训，供未来的agent参考和学习。（v0.9.6-rc 实现）
- [x] **基于知识图谱的记忆管理：** 设计一个基于知识图谱的记忆管理系统，能够将agent的记忆以结构化的方式存储和查询，提升agent的推理能力和知识整合能力。（v0.9.6-rc 实现）
- [x] **长期记忆后端支持：** 设计一个长期记忆后端，能够支持大规模的记忆存储和高效的查询，满足agent在复杂任务中的记忆需求。（v0.9.6-rc 实现：SQLite、向量后端）

## 其他的一些想法

- [x] **让agent学会写agent：** 提供一个专门的Agent友好的Nexa文档 `docs/NEXA_AGENT_GUIDE.md`，包含语法速查表、代码模板、最佳实践。（v1.0 实现）
- [x] **Python 实时引用 Nexa 库/接口：** `src/nexa_sdk.py` 提供 `nexa.run()`, `nexa.Agent()`, `nexa.compile()` 等 API。（v1.0 实现）
- [x] **调试器支持：** `src/runtime/debugger.py` 提供断点、变量监视、单步执行。（v1.0 实现）
- [x] **性能分析器：** `src/runtime/profiler.py` 提供 Token 消耗、执行时间追踪、性能报告。（v1.0 实现）
- [x] **标准库扩展：** `src/runtime/stdlib.py` 提供 HTTP请求、文件操作、JSON处理、加密、时间日期等内置工具。（v1.0 实现）
- [x] **文档示例验证：** 从 `nexa-docs` 提取所有文档示例代码，确保编译器支持完整语法。（v1.0 实现，42个示例通过）
- [x] **Python/Rust 语法同步：** Python 编译器与 Rust AVM Lexer 保持一致的 token 定义。（v1.0 实现）
- [ ] **包管理器 (nxm)**：中心化注册表与包管理工具，支持社区模块分发。

---

## 阶段 7: v1.0 文档验证与功能修复 (2026-03-28 完成 ✅)

本次对 `nexa-docs` 文档进行了系统性验证，发现并修复了多个遗留问题，确保文档描述的功能与实际实现一致。

### 7.1 secrets.nxs 解析问题修复

**问题描述**：
- `secrets.py` 的 `get()` 方法只返回环境变量，不返回解析后的 config 块内容
- 两种 `secrets.nxs` 格式不兼容（扁平格式 vs config block 格式）
- `agent.py` 使用硬编码的无效 API key 作为 fallback

**修复内容**：
- 重构 `src/runtime/secrets.py` 支持两种格式
  - 扁平格式：`KEY = "value"`
  - Config 块格式：`config default { KEY = "value" }`
- 新增 `get_provider_config()` 方法获取提供商配置
- 新增 `get_model_config()` 方法获取模型配置
- 修改 `src/runtime/agent.py` 使用新的 secrets API
- 修改 `src/runtime/core.py` 移除硬编码配置

**代码变更**：
```python
# secrets.py - 新的解析逻辑
class NexaSecrets:
    def __init__(self):
        self._flat_configs: Dict[str, Any] = {}
        self._block_configs: Dict[str, ConfigNode] = {}
        self._load_secrets()
    
    def get(self, key: str, default: str = "") -> str:
        # Priority: default block -> flat configs -> env vars
        if "default" in self._block_configs:
            val = self._block_configs["default"].get(key)
            if val and not isinstance(val, ConfigNode):
                return str(val)
        if key in self._flat_configs:
            val = self._flat_configs[key]
            if not isinstance(val, dict):
                return str(val)
        return os.environ.get(key, default)
```

### 7.2 `secret()` 函数未定义

**问题描述**：
- `secret("KEY")` 函数调用未转换为有效的 Python 代码
- 文档中描述的 `secret()` 函数在代码生成时未处理

**修复内容**：
- 修改 `src/code_generator.py:370-372` 将 `secret()` 转换为 `nexa_secrets.get()`

**代码变更**：
```python
# code_generator.py
elif func == "secret":
    func = "nexa_secrets.get"
```

### 7.3 `std.shell` namespace 未定义

**问题描述**：
- `std.shell` 标准库命名空间不存在
- 文档中描述的 `std.shell.execute` 无法使用

**修复内容**：
- 在 `src/runtime/stdlib.py` 添加 `shell_exec` 工具
- 在 `src/runtime/stdlib.py` 添加 `shell_which` 工具
- 添加 `std.shell` 到 `STD_NAMESPACE_MAP`

**代码变更**：
```python
# stdlib.py
def _shell_exec(command: str, timeout: int = 30) -> str:
    """执行 shell 命令"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return json.dumps({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except Exception as e:
        return f"Error: {str(e)}"

STD_NAMESPACE_MAP["std.shell"] = ["shell_exec", "shell_which"]
```

### 7.4 `std.ask_human` namespace 未定义

**问题描述**：
- `std.ask_human` 标准库命名空间不存在
- 文档中描述的人在回路功能无法使用

**修复内容**：
- 在 `src/runtime/stdlib.py` 添加 `ask_human` 工具
- 添加 `std.ask_human` 到 `STD_NAMESPACE_MAP`

**代码变更**：
```python
# stdlib.py
def _ask_human(prompt: str, default: str = "") -> str:
    """请求用户输入"""
    try:
        user_input = input(f"{prompt} [{default}]: ")
        return user_input if user_input else default
    except EOFError:
        return default

STD_NAMESPACE_MAP["std.ask_human"] = ["ask_human"]
```

### 7.5 `execute_tool()` 不查找 stdlib 工具

**问题描述**：
- `tools_registry.py` 的 `execute_tool()` 只查找 `LOCAL_TOOLS`，不查找 stdlib 工具
- 导致标准库工具调用失败，返回 "not found locally"

**修复内容**：
- 修改 `src/runtime/tools_registry.py:87-114` 添加 stdlib 工具查找逻辑

**代码变更**：
```python
# tools_registry.py
def execute_tool(name: str, args_json: str) -> str:
    print(f"    [ToolRegistry] Executing {name} with args {args_json} ...")
    args = json.loads(args_json)
    
    # First try LOCAL_TOOLS
    if name in LOCAL_TOOLS:
        result = LOCAL_TOOLS[name](**args)
        return str(result)
    
    # Then try stdlib tools
    from .stdlib import execute_stdlib_tool
    result = execute_stdlib_tool(name, **args)
    return str(result)
```

### 7.6 Protocol 功能不完整

**问题描述**：
- Agent 没有自动添加 JSON 格式要求到 system prompt
- `run()` 返回字符串而不是支持属性访问的对象
- 文档中描述的 Protocol 结构化输出无法正常工作

**修复内容**：
- 修改 `src/runtime/agent.py:23-35` 添加 protocol 的 JSON 格式要求
- 修改 `src/runtime/agent.py:248-256` 返回 Pydantic 模型实例

**代码变更**：
```python
# agent.py - 添加 JSON 格式指令
if self.protocol:
    if hasattr(self.protocol, 'model_json_schema'):
        schema = self.protocol.model_json_schema()
        fields = list(schema.get('properties', {}).keys())
    else:
        fields = [f for f in dir(self.protocol) if not f.startswith('_')]
    json_instruction = f"\n\nIMPORTANT: You MUST respond with a valid JSON object containing these fields: {', '.join(fields)}. Do not include any text outside the JSON object."
    self.system_prompt += json_instruction

# agent.py - 返回 Pydantic 模型
validated = self.protocol.model_validate(parsed_reply)
return validated  # Instead of returning reply string
```

### 7.7 BinaryExpression 解析错误

**问题描述**：
- `binary_expr` transformer 方法错误地将 `PropertyAccess` 作为 operator 处理
- `BinaryExpression` 没有在 `_resolve_expression` 中处理
- 导致字符串拼接等操作失败

**修复内容**：
- 修改 `src/ast_transformer.py:743-757` 修复 binary_expr 解析
- 修改 `src/code_generator.py:361-364` 添加 BinaryExpression 处理

**代码变更**：
```python
# ast_transformer.py
def binary_expr(self, args):
    if len(args) == 1:
        return args[0]
    result = args[0]
    for i in range(1, len(args)):
        right = args[i]
        result = {
            "type": "BinaryExpression",
            "operator": "+",
            "left": result,
            "right": right
        }
    return result

# code_generator.py
elif ex_type == "BinaryExpression":
    left = self._resolve_expression(expr["left"])
    right = self._resolve_expression(expr["right"])
    op = expr["operator"]
    return f"str({left}) {op} str({right})"
```

### 7.8 标准库工具扩展

**问题描述**：
- 文档中描述的部分标准库工具未实现
- `std.http` 缺少 `put`, `delete`
- `std.fs` 缺少 `append`, `delete`
- `std.time` 缺少 `format`, `sleep`, `timestamp`
- `std.json` 缺少 `stringify`

**修复内容**：
- 添加 `http_put`, `http_delete` 工具
- 添加 `file_append`, `file_delete` 工具
- 添加 `json_stringify` 工具
- 添加 `time_format`, `time_sleep`, `time_timestamp` 工具
- 更新 `STD_NAMESPACE_MAP` 包含所有新工具

**最终 STD_NAMESPACE_MAP**：
```python
STD_NAMESPACE_MAP = {
    "std.fs": ["file_read", "file_write", "file_exists", "file_list", "file_append", "file_delete"],
    "std.http": ["http_get", "http_post", "http_put", "http_delete"],
    "std.time": ["time_now", "time_diff", "time_format", "time_sleep", "time_timestamp"],
    "std.text": ["text_split", "text_replace", "text_upper", "text_lower"],
    "std.json": ["json_parse", "json_get", "json_stringify"],
    "std.hash": ["hash_md5", "hash_sha256", "base64_encode", "base64_decode"],
    "std.math": ["math_calc", "math_random"],
    "std.regex": ["regex_match", "regex_replace"],
    "std.shell": ["shell_exec", "shell_which"],
    "std.ask_human": ["ask_human"],
}
```

### 7.9 已知未解决问题

**`fast_match:` 语法问题**：
- 文件: `examples/12_v0.9_features.nx`
- 问题: 语法 `semantic_if "条件" fast_match: "regex" against var` 不被解析器支持
- 原因: 解析器期望 `fast_match` 后跟字符串，但语法使用了 `:` 分隔符
- 建议: 修改语法或更新文档

### 7.10 测试覆盖

所有 15 个 examples 已测试：
- ✅ 01_hello_world.nx
- ✅ 02_pipeline_and_routing.nx
- ✅ 03_critic_loop.nx
- ✅ 04_join_consensus.nx
- ✅ 05_tool_execution.nx
- ✅ 06_sys_admin_bot.nx (部分功能)
- ✅ 07_modules_and_secrets.nx
- ✅ 08_news_aggregator.nx
- ✅ 09_cognitive_architecture.nx
- ✅ 10_skill_markdown.nx
- ✅ 11_fallback_and_vision.nx
- ❌ 12_v0.9_features.nx (语法问题)
- ✅ 13_try_catch_and_reflection.nx
- ✅ 14_secrets_and_caching.nx
- ✅ 15_dag_topology.nx

### 7.11 修改文件清单

| 文件 | 修改类型 | 说明 |
|-----|---------|------|
| `src/runtime/secrets.py` | 重构 | 支持两种 secrets.nxs 格式 |
| `src/runtime/agent.py` | 修改 | Protocol JSON 指令、Pydantic 返回 |
| `src/runtime/core.py` | 修改 | 移除硬编码配置 |
| `src/runtime/stdlib.py` | 添加功能 | 新增 10+ 标准库工具 |
| `src/runtime/tools_registry.py` | 修改 | stdlib 工具查找 |
| `src/code_generator.py` | 修改 | secret()、BinaryExpression |
| `src/ast_transformer.py` | 修改 | binary_expr 解析 |
| `secrets.nxs` | 更新格式 | config block 格式 |
| `examples/test_protocol.nx` | 新增测试 | Protocol 功能验证 |
| `docs/validation_report.md` | 新增文档 | 验证报告 |

---

### 社区生态与学术
1. **开源贡献**：建立开放的贡献流程和代码审查机制。
2. **理论基础论文**：分享非确定性计算的确定性控制流、基于模型的 `loop ... until` 与原生 `semantic_if` 等。
