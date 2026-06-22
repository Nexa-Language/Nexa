<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa Language</h1>
  <p><b><i>The First Harness Native Agent Language. Write flows, not glue code.</i></b></p>
  <p>
    <img src="https://zenodo.org/badge/DOI/10.5281/zenodo.19994263.svg" alt="DOI"/>
    <img src="https://img.shields.io/badge/License-AGPL--3.0-blue.svg" alt="License"/>
    <img src="https://img.shields.io/badge/Version-v2.2.1-brightgreen.svg" alt="Version"/>
    <img src="https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg" alt="Python"/>
    <img src="https://img.shields.io/badge/Tests-1935+-orange.svg" alt="Tests"/>
  </p>
  
  **中文版** | **[English](README_EN.md)**
  
  📚 **文档**: [中文](https://docs.nexa-lang.com/) | [English](https://docs.nexa-lang.com/en/)
</div>

---

## ⚡ What is Nexa?

**Nexa** 是 **the first Harness Native Agent Language**——一门为大语言模型（LLM）与智能体系统（Agentic Systems）量身定制的编程语言，将 Agent 安全从运行时框架下沉为语言级原语。

当代 AI 应用开发充斥着大量的 Prompt 拼接、臃肿的 JSON 解析套件、不可靠的正则皮带，以及复杂的框架。Nexa 将高层级的意图路由、多智能体并发组装、管道流传输以及工具执行沙盒提权为核心语法一等公民，直接通过底层的 `Transpiler` 转换为稳定可靠的 Python Runtime，让你能够用最优雅的语法定义最硬核的 LLM 计算图（DAG）。

---

## 🔥 v2.2.1: Context-as-Structure

Nexa v2.2.1 把 **Context** 提升为 agent 声明的结构属性（与 model、tools 同级），让每个 agent 的上下文行为在**声明时**被完全定义，而不是在使用点（`A >> B`）临时决定。

### 设计动机

面试官观点：**Agent = (Model, Tools, Context) 三元组完全定义**。

- v2.1 及之前：model 和 tools 在 `agent` 声明里定义，但 **context 缺失**（运行时 `self.messages = []` 硬编码），导致 pipeline `A >> B` 只能传字符串。
- v2.2.1：在 agent 声明里增加 `context { ... }` 子块，让 context 行为像 model/tools 一样在结构上完全定义。

### 语法

```nexa
agent Researcher {
    model: "deepseek/deepseek-chat",
    uses: [web_search],
    context {
        source: upstream,                    // "upstream" | "shared:name" | "fresh"
        sink: downstream,                     // "downstream" | "shared:name" | "discard"
        output_schema: ResearchOutput,        // Protocol 类型
        max_history_turns: 20,
        inherit: [messages, artifacts]        // 从上游继承的字段
    }
    prompt: "..."
}
```

### 编译期类型检查（C-004）

Harness Validator 在编译期检查 pipeline `A >> B` 中，A 的 `output_schema` 是否匹配 B 的 `input_schema`。不匹配则编译失败：

```
C-004: Context incompatible in pipeline 'A >> B':
       output_schema='ResearchOutput' is not a subtype of input_schema='WeatherInput'
```

### 向后兼容

- 不加 `context { ... }` 块的 agent 行为**完全不变**（保持 v2.1 的字符串传递语义）
- `context` 块是可选的，旧代码无需修改

详见 [`examples/v2.2/01_context_handoff.nx`](examples/v2.2/01_context_handoff.nx)。

---

## 🔥 v2.1.2: Config Selection & Standard Library

Nexa v2.1.2 引入了多配置切换和标准库系统，让不同环境（开发/测试/生产）使用不同的 API 密钥和模型配置。

### `use config` 多配置切换

在 `secrets.nxs` 中定义多个 config block，在 `.nx` 文件中用 `use config <name>` 选择：

```nexa
// secrets.nxs
config default {
    BASE_URL = "https://aihub.arcsysu.cn/v1"
    API_KEY = "<provider-api-key>"
}

config ali {
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    API_KEY = "<dashscope-api-key>"
    NEWS_API_KEY = "your-newsapi-key"
}
```

```nexa
// your_program.nx
include "stdlib/news.nx";   // 引入标准库新闻搜索工具
use config ali;              // 使用 ali 配置

agent SearchAgent uses search_news {
    model: "deepseek-v4-pro",
    prompt: "Search for news using the search_news tool."
}
```

### 标准库 (`stdlib/`)

通过 `include` 引入标准库工具，Agent 只看到 `uses` 声明的工具：

```nexa
include "stdlib/news.nx";

agent MyAgent uses search_news {
    prompt: "Search for news."
}
```

### Harness Validator strict/warn 模式

```bash
# warn 模式（默认）：警告但编译继续
nexa build program.nx --harness=warn

# strict 模式：所有 warnings 升级为 errors，阻断编译
nexa build program.nx --harness=strict
```

---

## 🔥 v2.1: Production Hardening + v2.0: Harness Native Runtime

Nexa v2.0 将 Harness 六元组 H=(E,T,C,S,L,V) 从编译期验证下沉为**运行时一等公民**。v2.1 在此基础上为 Nexa Code（首个 Harness Native AI 编程助手）新增了 Agent 级别属性，让它能用纯 Nexa 语法运行，不再依赖 `python!` escape hatch。

### v2.1 新增 Agent 属性

这些属性不是框架层面的配置，而是**语言原语**——编译器解析、运行时执行、Harness Validator 检查：

```nexa
agent Coder {
    prompt: "You are a coding assistant.",
    stream: true,                    // 流式输出，逐 token 实时返回
    max_tool_calls: 5,              // 单次请求最多 5 轮工具调用
    tool_call_strategy: "auto"      // auto: 模型自行决定 | required: 强制调用 | none: 禁用工具
}

agent Planner {
    output_format: "json",          // 强制 OpenAI response_format JSON
    output_schema: {                // JSON Schema → 编译器自动生成 Pydantic 模型
        "steps": "string",
        "estimated_time": "string"
    }
}
```

**向后兼容**: 所有 v1.x-v2.0 代码无需修改即可在 v2.1 上运行。

### v2.0 Harness 六元组

| 维度 | 原语 | 运行时组件 | 测试数 |
|------|------|-----------|--------|
| **E** (Execution) | `autoloop`/`try_agent` | HarnessKernel + AutoLoopConfig | 52 |
| **T** (Tool) | `@tool` | ToolRegistry + ToolSchema | 53 |
| **C** (Context) | `with_context` | ContextManager + importance_weighted | 52 |
| **S** (State) | `snapshot/restore` | StateStore + fork/merge | 45 |
| **L** (Lifecycle) | `before_step`/`reflect` | LifecycleHookManager | 53 |
| **V** (Verify) | `verify ... satisfies` | EvaluationInterface + LLMRouter | 59 |
| **Actor** | `spawn/pass/await` | ActorSystem | 18 |
| **WASM** | sandbox integration | WASM Sandbox + full harness | 15 |

### 完整示例目录

```
examples/v2.0/                     examples/v2.1/
  01_autoloop.nx    (E)              01_streaming_agent.nx     流式输出
  02_with_context.nx (C)             02_structured_output.nx   JSON 结构化
  03_try_agent.nx   (E+L)            03_tool_call_control.nx   工具调用控制
  ... (共12个)                       04_spawn_pipeline.nx      DAG |>> 并行
```

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
    model: "deepseek-chat",
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

- **Python 测试**: 1935 tests 全部通过 (v1.x 16 特性 + v2.0 Harness Runtime + v2.1 Agent Properties)
- **Rust AVM**: 0 errors, 0 warnings — `cargo check` clean build
- **v2.0+2.1 示例**: 16/16 全部编译通过 (Harness Validator + `--harness=warn`)

---

## 📖 Documentation

- [x] [Nexa 语法参考手册 v1.3.7](docs/01_nexa_syntax_reference.md) — 25 章节完整语法覆盖
- [x] [编译器与运行时架构 v1.3](docs/02_compiler_architecture.md) — AST scoring、BOILERPLATE、handle-as-dict
- [x] [路线图与愿景](docs/03_roadmap_and_vision.md) — v0.1 到 v2.0 完整里程碑
- [x] [架构演进规划](docs/05_architecture_evolution.md) — Rust AVM 设计蓝图
- [x] [极速上手指南](docs/06_quick_start_guide.md) — 5 分钟入门
- [x] [IDD 完整参考](docs/idd_reference.md) — Intent-Driven Development 详解
- [x] [Harness Agent 设计文档](docs/others/Harness_Agent.md) — Harness 六元组 H=(E,T,C,S,L,V) 详解
- [x] [Feature Changelog v1.1-v1.3.x](docs/others/changelog_v1.1.0-v1.3.x_features.md) — 16 特性变更记录
- [x] [Release Notes](docs/release_notes/) — 每版本独立发布说明

<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>
