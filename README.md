<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa Language</h1>
  <p><b><i>The Dawn of Agent-Native Programming. Write flows, not glue code.</i></b></p>
  <p>
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"/>
    <img src="https://img.shields.io/badge/Version-v0.8-brightgreen.svg?style=for-the-badge" alt="Version"/>
    <img src="https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg?style=for-the-badge" alt="Python"/>
    <img src="https://img.shields.io/badge/Status-Experimental-orange.svg?style=for-the-badge" alt="Status"/>
  </p>
</div>

---

## ⚡ What is Nexa?

**Nexa** 是一门为大语言模型（LLM）与智能体系统（Agentic Systems）量身定制的**智能体原生 (Agent-Native) 编程语言**。
当代 AI 应用开发充斥着大量的 Prompt 拼接、臃肿的 JSON 解析套件、不可靠的正则皮带，以及复杂的框架。Nexa 将高层级的意图路由、多智能体并发组装、管道流传输以及工具执行沙盒提权为核心语法一等公民，直接通过底层的 `Transpiler` 转换为稳定可靠的 Python Runtime，让你能够用最优雅的语法定义最硬核的 LLM 计算图（DAG）。

---

## 🔥 **v0.8 EPIC RELEASE**：Cognitive Architecture Era

Nexa v0.8 引入了全新的认知架构（Cognitive Architecture）功能，重点强化了类型安全、资源治理以及人机协同（HITL）：

### 1. 强类型协议约束 (`protocol` & `implements`)
原生支持契约式编程，利用 Pydantic 动态编译，让 Agent 产出严格遵守 Schema，自带自修正重试循环机制：
```nexa
protocol ReviewResult {
    score: "int"
    summary: "string"
}
agent Reviewer implements ReviewResult { ... }
```

### 2. 多模型动态路由 (`model` prefix & Routing)
解耦单一模型强依赖，动态指定运行时的模型端点，构建灵活的跨厂模型流水线：
```nexa
agent Coder { model: "minimax/abab6.5-chat", prompt: "..." }
agent Reviewer { model: "deepseek/deepseek-chat", prompt: "..." }
```

### 3. 人类介入机制 (Human-in-the-Loop)
通过内置标准库无缝实现流中断与人工复核，轻松挂载交互鉴权断点：
```nexa
agent Interactor {
    uses [std.ask_human]
    prompt: "调用 ask_human 向人类请示是否继续。"
}
```

### 4. 运行时资源配额控制 (`@limit`)
支持装饰器语法级的 Token 安全拦截与用量截断，保护 API 预算：
```nexa
@limit(max_tokens=1500)
agent SafeBot { ... }
```

*(向下兼容 v0.5 的流式 `>>`, `match intent`, `join`, `loop until` 等编排语法)*

---

## 🚀 Quick Start

### 1. 全局安装
```bash
git clone https://github.com/your-org/nexa.git
cd nexa
pip install -e .
```

### 2. 执行你的第一个 Nexa 工作流
```bash
nexa run examples/09_cognitive_architecture.nx
```
或者审计它转换生成的纯净 Python 代码栈：
```bash
nexa build examples/09_cognitive_architecture.nx
```

---

## 📖 Documentation
- [x] [v0.8 Syntax Reference](docs/08_nexa_v0.5_syntax_reference.md)
- [x] [Compiler Architecture](docs/02_compiler_transpiler_design.md)

<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>
