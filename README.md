<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa Language</h1>
  <p><b><i>The Dawn of Agent-Native Programming. Write flows, not glue code.</i></b></p>
  <p>
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"/>
    <img src="https://img.shields.io/badge/Version-v1.3.7-brightgreen.svg?style=for-the-badge" alt="Version"/>
    <img src="https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg?style=for-the-badge" alt="Python"/>
    <img src="https://img.shields.io/badge/Tests-1500+-orange.svg?style=for-the-badge" alt="Tests"/>
  </p>
  
  **中文版** | **[English](README_EN.md)**
  
  📚 **文档**: [中文](https://ouyangyipeng.github.io/Nexa-docs/) | [English](https://ouyangyipeng.github.io/Nexa-docs/en/)
</div>

---

## ⚡ What is Nexa?

**Nexa** 是一门为大语言模型（LLM）与智能体系统（Agentic Systems）量身定制的**智能体原生 (Agent-Native) 编程语言**。

当代 AI 应用开发充斥着大量的 Prompt 拼接、臃肿的 JSON 解析套件、不可靠的正则皮带，以及复杂的框架。Nexa 将高层级的意图路由、多智能体并发组装、管道流传输以及工具执行沙盒提权为核心语法一等公民，直接通过底层的 `Transpiler` 转换为稳定可靠的 Python Runtime，让你能够用最优雅的语法定义最硬核的 LLM 计算图（DAG）。

---

## 🔥 v1.1-v1.3.7 特性总览

Nexa 从 v1.1.0 到 v1.3.7 共发布了 **16 个核心特性**，涵盖 4 个优先级层级（P0-P3），总计 **1500+ 测试**。

### 🏆 P0: 核心差异化特性

| 版本 | 特性 | 测试数 | 亮点 |
|------|------|--------|------|
| **v1.1.0** | Intent-Driven Development (IDD) | 104 | `.nxintent` 文件 + IAL 术语重写引擎 + `@implements` 注解 |
| **v1.2.0** | Design by Contract (DbC) | 47 | `requires`/`ensures`/`invariant` + ContractViolation 跨模块集成 |
| **v1.3.0** | Agent-Native Tooling | 41 | `nexa inspect`/`validate`/`lint` CLI 命令 |

### 📦 P1: 必要特性

| 版本 | 特性 | 测试数 | 亮点 |
|------|------|--------|------|
| **v1.3.1** | Gradual Type System | 79 | `Int`/`String`/`Bool`/`List[T]`/`Option[T]`/`Result[T,E]` + 三级模式 |
| **v1.3.2** | Error Propagation | 82 | `?` 操作符 + `otherwise` + `NexaResult`/`NexaOption` |
| **v1.3.3** | Background Job System | 73 | `job` DSL + 优先级队列 + Cron + 退避策略 |
| **v1.3.4** | Built-In HTTP Server | 94 | `server` DSL + CORS/CSP + 路由守卫 + 热重载 |
| **v1.3.5** | Database Integration | 79+5 | `db` DSL + SQLite/PostgreSQL + Agent 记忆 API |

### 🎯 P2: 高级特性

| 版本 | 特性 | 测试数 | 亮点 |
|------|------|--------|------|
| **v1.3.6** | Auth & OAuth | 79+5 | 3层认证 (API Key + JWT + OAuth PKCE) |
| **v1.3.6** | Structured Concurrency | 172 | `spawn`/`parallel`/`race`/`channel` + 18 API |
| **v1.3.6** | KV Store | 81 | SQLite 后端 + TTL + Agent 语义查询 |
| **v1.3.6** | Template System | 209 | `template"""..."""` + 30+ 滤镜 + Agent 模板 |

### ✨ P3: 语言表达力

| 版本 | 特性 | 测试数 | 亮点 |
|------|------|--------|------|
| **v1.3.7** | Pipe Operator `|>` | 84 | `x |> f` → `f(x)` 左到右数据流 |
| **v1.3.7** | defer Statement | 84 | LIFO 清理，scope exit 自动执行 |
| **v1.3.7** | Null Coalescing `??` | 84 | `expr ?? fallback` 安全回退 |
| **v1.3.7** | String Interpolation `#{}` | 100 | Ruby 风格字符串插值 |
| **v1.3.7** | Pattern Matching | 91 | 7 pattern types + `match`/`let`/`for` 解构 |
| **v1.3.7** | ADT (Struct/Enum/Trait) | 100 | 代数数据类型 + handle-as-dict |

---

## 🦀 Rust AVM 底座 (v1.0-alpha)

Nexa v1.0-alpha 引入了革命性的 **Agent Virtual Machine (AVM)** — 用 Rust 编写的高性能、安全隔离的智能体执行引擎：

- **高性能字节码解释器** — 原生执行编译后的 Nexa 字节码
- **WASM 安全沙盒** — wasmtime 集成 + 四级权限模型
- **智能调度器** — DAG 拓扑排序 + 自动依赖解析
- **向量虚存分页** — LRU/LFU/Hybrid 淘汰 + 语义相关性加载

---

## 🚀 Quick Start

### 1. 全局安装
```bash
git clone https://github.com/ouyangyipeng/Nexa.git
cd Nexa
pip install -e .
```

### 2. Agent 工具安装法 🤖
如果你正在使用 AI Agent 工具（如 Claude Code、Cursor、Copilot 等），只需输入：

```
按照 https://github.com/ouyangyipeng/Nexa/AGENT_LEARN 的指引，安装并试运行这门语言
```

你的 Agent 将会自动访问 `AGENT_LEARN/` 完成安装并掌握 Nexa 语法。

**Agent 专用文档**:
- [`AGENT_LEARN/INSTALL_AND_HELLO_WORLD.md`](AGENT_LEARN/INSTALL_AND_HELLO_WORLD.md)
- [`AGENT_LEARN/AGENT_GUIDE.md`](AGENT_LEARN/AGENT_GUIDE.md)

### 3. 执行与测试工作流
```bash
# 执行流
python -m src.cli run examples/01_hello_world.nx

# 语义断言测试
python -m src.cli test examples/12_v0.9_features.nx

# 审计生成的 Python 代码栈
python -m src.cli build examples/01_hello_world.nx

# Agent-Native 工具 (v1.3+)
python -m src.cli inspect examples/01_hello_world.nx
python -m src.cli validate examples/01_hello_world.nx
python -m src.cli lint examples/01_hello_world.nx
```

---

## 📖 语法示例

### Agent 声明 + 管道流
```nexa
agent ChatBot {
    role: "Helpful Assistant",
    model: "gpt-4o-mini",
    prompt: "Answer user questions concisely"
}

flow main {
    result = user_input |> ChatBot |> format_output;
}
```

### Contract 契约式编程 (v1.2)
```nexa
agent SecureBot {
    requires: input != None and input.length < 1000
    ensures: "response is helpful and accurate"
}
```

### 类型注解 + 错误传播 (v1.3.1-v1.3.2)
```nexa
let count: Int = parse(input) ?
let result = risky_operation() otherwise 0
```

### HTTP Server (v1.3.4)
```nexa
server 8080 {
    cors { origins: ["*"], methods: ["GET", "POST"] }
    route GET "/chat" => ChatBot
    route POST "/analyze" => Analyzer
}
```

### Pattern Matching + ADT (v1.3.7)
```nexa
enum Option { Some(value), None }
struct Point { x: Int, y: Int }

match result {
    Option::Some(answer) => answer
    Option::None => "no response"
}
```

---

## ✅ 文档与测试验证

- **Python 测试**: 1500+ 测试通过 (16 特性全覆盖)
- **Rust AVM 测试**: 110+ 测试通过 (100%)

---

## 📖 Documentation

- [x] [Nexa 语法参考手册 v1.3.7](docs/01_nexa_syntax_reference.md) — 25 章节完整语法覆盖
- [x] [编译器与运行时架构 v1.3](docs/02_compiler_architecture.md) — AST scoring、BOILERPLATE、handle-as-dict
- [x] [路线图与愿景](docs/03_roadmap_and_vision.md) — v0.1 到 v1.3.7 完整里程碑
- [x] [架构演进规划](docs/05_architecture_evolution.md) — Rust AVM 设计蓝图
- [x] [极速上手指南](docs/06_quick_start_guide.md) — 5 分钟入门
- [x] [IDD 完整参考](docs/idd_reference.md) — Intent-Driven Development 详解
- [x] [Feature Changelog v1.1-v1.3.x](docs/changelog_v1.1.0-v1.3.x_features.md) — 16 特性变更记录
- [x] [Release Notes](docs/release_notes/) — 每版本独立发布说明

<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>
