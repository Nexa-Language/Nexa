<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa Language</h1>
  <p><b><i>The Dawn of Agent-Native Programming. Write flows, not glue code.</i></b></p>
  <p>
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"/>
    <img src="https://img.shields.io/badge/Version-v1.0--alpha-brightgreen.svg?style=for-the-badge" alt="Version"/>
    <img src="https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg?style=for-the-badge" alt="Python"/>
    <img src="https://img.shields.io/badge/Status-Experimental-orange.svg?style=for-the-badge" alt="Status"/>
  </p>
  
  **中文版** | **[English](README_EN.md)**
  
  📚 **文档**: [中文](https://ouyangyipeng.github.io/Nexa-docs/) | [English](https://ouyangyipeng.github.io/Nexa-docs/en/)
</div>

---

## ⚡ What is Nexa?

**Nexa** 是一门为大语言模型（LLM）与智能体系统（Agentic Systems）量身定制的**智能体原生 (Agent-Native) 编程语言**。
当代 AI 应用开发充斥着大量的 Prompt 拼接、臃肿的 JSON 解析套件、不可靠的正则皮带，以及复杂的框架。Nexa 将高层级的意图路由、多智能体并发组装、管道流传输以及工具执行沙盒提权为核心语法一等公民，直接通过底层的 `Transpiler` 转换为稳定可靠的 Python Runtime，让你能够用最优雅的语法定义最硬核的 LLM 计算图（DAG）。

---

## 🔥 **v1.0-alpha AVM RELEASE**: The Agent Virtual Machine Era

Nexa v1.0-alpha 引入了革命性的 **Agent Virtual Machine (AVM)** - 一个用 Rust 编写的高性能、安全隔离的智能体执行引擎：

### 🦀 Rust AVM 底座
从 Python 脚本解释转译模式跨越至基于 Rust 编写的独立编译型 Agent Virtual Machine：
- **高性能字节码解释器** - 原生执行编译后的 Nexa 字节码
- **完整编译器前端** - Lexer → Parser → AST → Bytecode
- **110+ 测试覆盖** - 全链路测试保证稳定性

### 🔒 WASM 安全沙盒
在 AVM 中引入 WebAssembly，对外部 `tool` 执行提供强隔离：
- **wasmtime 集成** - 高性能 WASM 运行时
- **权限分级** - None/Standard/Elevated/Full 四级权限模型
- **资源限制** - 内存、CPU、执行时间限制
- **审计日志** - 完整的操作审计追踪

### ⚡ 智能调度器
在 AVM 层基于系统负载动态分配并发资源：
- **优先级队列** - 基于 Agent 优先级的任务调度
- **负载均衡** - RoundRobin/LeastLoaded/Adaptive 策略
- **DAG 拓扑排序** - 自动依赖解析与并行度分析
- **资源分配** - 内存、CPU 核心分配优化

### 📄 向量虚存分页
AVM 接管内存，自动执行对话历史的向量化置换：
- **LRU/LFU/Hybrid 淘汰策略** - 智能页面置换
- **嵌入向量相似度搜索** - 语义相关性加载
- **透明页面加载** - 无感知的内存管理
- **自动压缩** - 旧页面摘要压缩

---

## 📚 v0.9.7-rc 企业特性回顾

### 1. 复杂拓扑 DAG 支持
新增强大的 DAG 操作符，支持分叉、合流、条件分支：
```nexa
// 分叉：并行发送到多个 Agent
results = input |>> [Researcher, Analyst, Writer];

// 合流：合并多个结果
report = [Researcher, Analyst] &>> Reviewer;

// 条件分支：根据输入选择路径
result = input ?? UrgentHandler : NormalHandler;
```

### 2. 智能缓存系统
多级缓存 + 语义缓存，大幅减少 Token 消耗：
```nexa
agent CachedBot {
    prompt: "...",
    model: "deepseek/deepseek-chat",
    cache: true  // 启用智能缓存
}
```

### 3. 知识图谱记忆
结构化知识存储和推理能力：
```python
from src.runtime.knowledge_graph import get_knowledge_graph
kg = get_knowledge_graph()
kg.add_relation("Nexa", "is_a", "Agent Language")
```

### 4. RBAC 权限控制
角色基础的访问控制，确保最小权限原则：
```python
from src.runtime.rbac import get_rbac_manager, Permission
rbac = get_rbac_manager()
rbac.assign_role("DataBot", "agent_readonly")
```

### 5. 长期记忆系统
CLAUDE.md 风格的持久化记忆，支持经验和知识积累：
```nexa
agent SmartBot {
    prompt: "...",
    experience: "bot_memory.md"  // 加载长期记忆
}
```

### 6. Open-CLI 深度接入
原生交互式命令行支持，富文本输出：
```bash
nexa > run script.nx --debug
nexa > cache stats
nexa > agent list
```

---

## 📖 v0.9-alpha 特性回顾

### 原生测试与断言 (`test` & `assert`)
```nexa
test "login_agent" {
    result = LoginBot.run("user: admin");
    assert "包含成功确认信息" against result;
}
```

### MCP 支持 (`mcp: "..."`)
```nexa
tool SearchGlobal {
    mcp: "github.com/nexa-ai/search-mcp"
}
```

### 高速启发式评估 (`fast_match`)
```nexa
semantic_if "是一句日期提示" fast_match r"\d{4}-\d{2}" against req { ... }
```

---

## 🚀 Quick Start

### 1. 全局安装
```bash
git clone https://github.com/ouyangyipeng/Nexa.git
cd Nexa
pip install -e .
```

### 2. Agent 工具安装法 🤖
如果你正在使用 AI Agent 工具（如 Claude Code、Cursor、Copilot 等），只需输入以下指令：

```
按照 https://github.com/ouyangyipeng/Nexa/AGENT_LEARN 的指引，安装并试运行这门语言
```

你的 Agent 将会：
1. 自动访问 `AGENT_LEARN/INSTALL_AND_HELLO_WORLD.md` 完成安装
2. 运行 Hello World 程序验证安装
3. 将 `AGENT_LEARN/AGENT_GUIDE.md` 作为 skill 加载
4. 掌握 Nexa 语言的语法和用法

**Agent 专用文档目录**:
- [`AGENT_LEARN/INSTALL_AND_HELLO_WORLD.md`](AGENT_LEARN/INSTALL_AND_HELLO_WORLD.md) - 安装与 Hello World 指南
- [`AGENT_LEARN/AGENT_GUIDE.md`](AGENT_LEARN/AGENT_GUIDE.md) - Agent 语法速查与代码模板

### 3. 执行与测试工作流
```bash
# 执行流
python -m src.cli run examples/01_hello_world.nx

# 进行语义断言测试 (v0.9+)
python -m src.cli test examples/12_v0.9_features.nx

# 审计生成的纯净 Python 代码栈
python -m src.cli build examples/01_hello_world.nx
```

---

## ✅ 文档示例验证 (Documentation Validation)

所有文档示例代码已通过编译验证：
- **Python 测试**: 42/42 示例通过 (100%)
- **Rust AVM 测试**: 110/110 测试通过 (100%)

新增语法支持：
- **Agent Decorators**: `@limit`, `@timeout`, `@retry`, `@temperature`
- **MCP/Python Tool Body**: `mcp: "..."`, `python: "..."`
- **DAG Parallel Operators**: `||` (fire-forget), `&&` (consensus)
- **Literal Types**: `Regex`, `Float`

---

## 🔧 v1.0 文档验证与功能修复 (2026-03-28)

对 `nexa-docs` 全部 15 个文档进行了系统性验证，发现并修复了 8 个遗留问题，确保文档描述的功能与实际实现完全一致。

### 修复 1: secrets.nxs 解析重构

**问题**: `secrets.py` 的 `get()` 方法只返回环境变量，不返回解析后的 config 块内容；两种 `secrets.nxs` 格式不兼容；`agent.py` 使用硬编码的无效 API key。

**修复**: 重构 `src/runtime/secrets.py`，支持扁平格式 (`KEY = "value"`) 和 config 块格式 (`config default { ... }`)，新增 `get_provider_config()` 和 `get_model_config()` 方法。修改 `agent.py` 和 `core.py` 移除硬编码配置。

### 修复 2: `secret()` 函数支持

**问题**: 文档中描述的 `secret("KEY")` 函数在代码生成时未处理，导致运行时 NameError。

**修复**: 在 `src/code_generator.py` 中将 `secret()` 调用转换为 `nexa_secrets.get()`。

### 修复 3: `std.shell` 命名空间

**问题**: `std.shell` 标准库命名空间不存在，文档中描述的 `std.shell.execute` 无法使用。

**修复**: 在 `src/runtime/stdlib.py` 中添加 `shell_exec` 和 `shell_which` 工具，注册到 `STD_NAMESPACE_MAP`。

### 修复 4: `std.ask_human` 命名空间

**问题**: `std.ask_human` 标准库命名空间不存在，人在回路功能无法使用。

**修复**: 在 `src/runtime/stdlib.py` 中添加 `ask_human` 工具，注册到 `STD_NAMESPACE_MAP`。

### 修复 5: 工具执行查找逻辑

**问题**: `tools_registry.py` 的 `execute_tool()` 只查找 `LOCAL_TOOLS`，不查找 stdlib 工具，导致标准库工具调用失败。

**修复**: 修改 `execute_tool()` 添加 stdlib 工具查找逻辑，优先查找 LOCAL_TOOLS，然后查找 stdlib。

### 修复 6: Protocol 结构化输出

**问题**: Agent 没有自动添加 JSON 格式要求到 system prompt；`run()` 返回字符串而不是支持属性访问的 Pydantic 对象。

**修复**: 在 `agent.py` 中为 protocol 自动添加 JSON 格式指令；`run()` 返回 Pydantic 模型实例而非字符串。

### 修复 7: BinaryExpression 解析

**问题**: `binary_expr` transformer 方法错误地将 `PropertyAccess` 作为 operator 处理；`BinaryExpression` 没有在 `_resolve_expression` 中处理。

**修复**: 修正 `ast_transformer.py` 的 `binary_expr` 方法；在 `code_generator.py` 中添加 `BinaryExpression` 处理。

### 修复 8: 标准库工具扩展

**问题**: 文档中描述的多个标准库工具未实现。

**修复**: 新增 10+ 标准库工具，完整覆盖文档描述的所有命名空间：

| 命名空间 | 工具 |
|---------|------|
| `std.fs` | read, write, exists, list, **append**, **delete** |
| `std.http` | get, post, **put**, **delete** |
| `std.time` | now, diff, **format**, **sleep**, **timestamp** |
| `std.json` | parse, get, **stringify** |
| `std.shell` | **exec**, **which** |
| `std.ask_human` | **call** |

### 修改文件清单

| 文件 | 修改类型 |
|-----|---------|
| `src/runtime/secrets.py` | 重构 |
| `src/runtime/agent.py` | 修改 |
| `src/runtime/core.py` | 修改 |
| `src/runtime/stdlib.py` | 添加功能 |
| `src/runtime/tools_registry.py` | 修改 |
| `src/code_generator.py` | 修改 |
| `src/ast_transformer.py` | 修改 |
| `secrets.nxs` | 更新格式 |
| `examples/test_protocol.nx` | 新增测试 |
| `docs/validation_report.md` | 新增文档 |

> 详细验证报告见 [`docs/validation_report.md`](docs/validation_report.md)，完整修复记录见 [`docs/03_roadmap_and_vision.md`](docs/03_roadmap_and_vision.md)。

---

## 🔧 v0.9.7-alpha 文档验证第二轮 (2026-03-28)

对 `nexa-docs` 进行第二轮系统性验证，发现并修复了 9 个原语/属性未实现问题。

### 新增功能

| 功能 | 文件 | 说明 |
|-----|------|------|
| **CLI `--version`** | `src/cli.py` | 添加版本显示参数 |
| **CLI `cache clear`** | `src/cli.py` | 添加缓存清理命令 |
| **Agent `timeout`** | `src/runtime/agent.py` | 执行超时控制（默认 30s） |
| **Agent `retry`** | `src/runtime/agent.py` | 重试次数控制（默认 3 次） |
| **`runtime.meta`** | `src/runtime/meta.py` | 循环元数据（loop_count/last_result） |
| **`break` 语句** | `src/nexa_parser.py` | 循环中断语句支持 |
| **`reason()` 原语** | `src/runtime/reason.py` | 类型感知推理原语 |
| **`wait_for_human()`** | `src/runtime/hitl.py` | 人在回路审批原语 |

### reason() 原语使用示例

```python
from src.runtime.reason import reason, reason_int, reason_bool

# 类型感知推理
count = reason_int("How many planets in the solar system?")
approved = reason_bool("Should I proceed with this action?")
data = reason_dict("Generate a user profile JSON")
```

### wait_for_human() 原语使用示例

```python
from src.runtime.hitl import wait_for_human, ApprovalStatus

# 请求人工审批
status = wait_for_human("Please approve this plan", channel="Slack", timeout=300)

if status == ApprovalStatus.APPROVED:
    proceed()
elif status == ApprovalStatus.REJECTED:
    handle_rejection()
else:
    handle_timeout()
```

### 新增文件清单

| 文件 | 说明 |
|-----|------|
| `src/runtime/meta.py` | Runtime 元数据模块 |
| `src/runtime/reason.py` | 类型感知推理原语 |
| `src/runtime/hitl.py` | Human-in-the-loop 原语 |
| `tests/test_v097_validation.py` | 综合验证测试套件 |
| `docs/validation_report_v2.md` | 第二轮验证报告 |

> 详细修复记录见 [`docs/03_roadmap_and_vision.md`](docs/03_roadmap_and_vision.md) 阶段 8。

---

## 📖 Documentation
- [x] [Nexa v0.9 Syntax Reference](docs/01_nexa_syntax_reference.md)
- [x] [Compiler Architecture](docs/02_compiler_architecture.md)
- [x] [Vision & Roadmap](docs/03_roadmap_and_vision.md)
- [x] [Memory Bank](MEMORY_BANK.md) - 架构设计与版本历史
- [x] [Documentation Validation Report](docs/validation_report.md) - 文档验证与修复报告

<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>
