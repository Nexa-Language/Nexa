<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="250" />
  <h1>Nexa Language</h1>
  <p><b><i>The Dawn of Agent-Native Programming. Write flows, not glue code.</i></b></p>
  
  <p>
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"/>
    <img src="https://img.shields.io/badge/Version-v0.1_MVP-brightgreen.svg?style=for-the-badge" alt="Version"/>
    <img src="https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg?style=for-the-badge" alt="Python"/>
    <img src="https://img.shields.io/badge/Status-Experimental-orange.svg?style=for-the-badge" alt="Status"/>
  </p>
</div>

---

## ⚡ What is Nexa?

**Nexa** 是一门为大语言模型（LLM）与智能体系统（Agentic Systems）量身定制的**智能体原生 (Agent-Native) 编程语言**。

当代 AI 应用开发充斥着大量的 Prompt 拼接、臃肿的 JSON 解析套件、不可靠的正则皮带，以及复杂的框架（例如 LangChain/LlamaIndex）。我们认为这是一种“胶水代码灾难”。**Nexa** 将高层级的概率调用（Probabilistic Operations）提权为一等公民，直接降维打击这些混沌的接口，在底层通过基于 AST 的重型转译器 (**Transpiler**) 将其降级回高度确定性的 Python 运行时代码。

在 Nexa 中，`agent`、`tool`、`flow` 以及能够听懂人话的 `semantic_if` 是语言内置的核心关键字，无需额外导入任何第三方库框架。

---

## 🆚 Why Nexa? (The Pain Points)

| 特性维度 | 原生 Python (纯API / LangChain) | Nexa (Agent-Native) |
| :--- | :--- | :--- |
| **基础概念** | 依赖外部类与接口库实例化 `Agent=LLMChain(...)` | 语言级原生结构 `agent` 和 `tool` 一等公民抽象 |
| **工作流编排** | 通过繁杂的图结构节点、回调、状态机（如 LangGraph） | 极简 `flow` 原生语法块，直觉式自上而下调用 |
| **依赖与参数** | `Pydantic Schema`、深层 JSON 构建与 Schema 提取 | 直接书写 `parameters: { "query": "string" }` |
| **控制流条件** | `.contains("Yes")`、或正则 `.*success.*` 强行匹配不可靠文本 | `semantic_if "包含成功暗示" against result` 原生语义判定，内置大模型校验网 |
| **容错与幻觉** | 手写繁复的 Try-Catch 逻辑、解析错误补偿代码 | 编译器内置 `tenacity` 退避重试，拦截 LLM 崩溃 |
| **代码噪声** | 50% 是业务，50% 是胶水和防御性代码 | 99% 是意图逻辑，胶水代码由编译器(Transpiler)隐式生成 |

---

## 🚀 Quick Start

想体验纯正的 AI 原生编程？赶快开始你的 Nexa 之旅：

### 1. 全局安装
克隆此仓库并使用 `pip` 进行本地全局安装。这将自动注册 `nexa` 命令行工具。

```bash
git clone https://github.com/your-org/nexa.git
cd nexa
pip install -e .
```

### 2. 编写你的第一个 Nexa 脚本 (`hello.nx`)

```nexa
tool web_search {
    description: "Search the web for a given query string.",
    parameters: {
        "query": "string"
    }
}

agent Researcher uses web_search {
    prompt: "You are a brilliant researcher."
}

flow main {
    result = Researcher.run("Search latest news about Nexa programming language.");
    
    // Nexa 独有魔法：语义控制流
    semantic_if "The result explicitly mentions 'transpiler'" against result {
        Researcher.run("Provide a 50-word technical summary.", result);
    } else {
        Researcher.run("Just reply: 'No relevant Nexa logic found.'");
    }
}
```

### 3. 一键编译并执行

在你的终端中，只需敲击一行命令即可将 Nexa 直接跑动在 Python 虚拟机之上：

```bash
nexa run hello.nx
```
或者仅仅编译为 Python 代码进行代码审计：
```bash
nexa build hello.nx
```

---

## 📖 Documentation
- [x] [v0.1 Syntax Design](docs/01_nexa_v0.1_syntax.md)
- [x] [Compiler Architecture](docs/02_compiler_transpiler_design.md)
- [x] [Nexa Developer Quick Start](docs/06_quick_start_guide.md)

---
<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>
