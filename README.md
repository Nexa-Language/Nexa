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

## 📖 Documentation
- [x] [Nexa v0.9 Syntax Reference](docs/01_nexa_syntax_reference.md)
- [x] [Compiler Architecture](docs/02_compiler_architecture.md)
- [x] [Vision & Roadmap](docs/03_roadmap_and_vision.md)
- [x] [Memory Bank](MEMORY_BANK.md) - 架构设计与版本历史

<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>
