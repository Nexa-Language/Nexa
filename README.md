<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa Language</h1>
  <p><b><i>The Dawn of Agent-Native Programming. Write flows, not glue code.</i></b></p>
  <p>
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"/>
    <img src="https://img.shields.io/badge/Version-v0.5-brightgreen.svg?style=for-the-badge" alt="Version"/>
    <img src="https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg?style=for-the-badge" alt="Python"/>
    <img src="https://img.shields.io/badge/Status-Experimental-orange.svg?style=for-the-badge" alt="Status"/>
  </p>
</div>

---

## ⚡ What is Nexa?

**Nexa** 是一门为大语言模型（LLM）与智能体系统（Agentic Systems）量身定制的**智能体原生 (Agent-Native) 编程语言**。

当代 AI 应用开发充斥着大量的 Prompt 拼接、臃肿的 JSON 解析套件、不可靠的正则皮带，以及复杂的框架。Nexa 将高层级的意图路由、多智能体并发组装、管道流传输以及工具执行沙盒提权为核心语法一等公民，直接通过底层的 `Transpiler` 转换为稳定可靠的 Python Runtime，让你能够用最优雅的语法定义最硬核的 LLM 计算图（DAG）。

---

## 🔥 **v0.5 EPIC RELEASE**：The Orchestration Era

Nexa v0.5 将多智能体协作推向了新的高度。告别传统繁杂的 API 调用调用堆栈，你可以直接使用全新的原生语法：

### 1. 意图路由机制 (`match intent`)
用大模型作为路由切分器，将用户意图精准派发给下游的专业 Agent。
```nexa
match req {
    intent("查询天气") => WeatherBot.run(req),
    intent("世界新闻") => NewsBot.run(req),
    _ => ChitChatBot.run(req)
}
```

### 2. 管道流加工 (`>>`)
使用 Unix 风格的 pipeline，前置智能体产出的结果可以完全无缝衔接进入下一个智能体。
```nexa
translated_news = NewsBot.run("Today's AI news") >> EnglishTranslator >> Summarizer;
```

### 3. 多智能体聚合并发 (`join`)
开启真正的算力并发！平行拉起多个分析师智能体，结束后通过链式汇拢产生共识结论。
```nexa
final_report = join(Researcher_Tech, Researcher_Biz).Summarizer("合并科技与商业的观点。");
```

### 4. 语义循环状态机 (`loop until`)
不再受限于死板的代码布尔条件。在 Nexa 中，由 LLM 大脑通过全局变量树来动态仲裁循环的生命周期。
```nexa
loop {
    feedback = Critic.run(poem);
    poem = Editor.run(poem, feedback);
} until ("诗歌完全符合了严丝合缝的平仄押韵要求并包含科技元素")
```

### 5. 沙盒级工具链 (`tool`)
声明 `uses [tool_name]` 后，底层引擎自动绑定并真实执行 Python 闭包环境下的自定义脚本，将二次执行流闭环回源模型。不再需要你亲手写执行 `tool_calls` 的防御性 JSON Parser 代码！

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
nexa run examples/02_pipeline_and_routing.nx
```
或者审计它转换生成的纯净 Python 代码栈：
```bash
nexa build examples/02_pipeline_and_routing.nx
```

---

## 📖 Documentation
- [x] [v0.5 Syntax Reference](docs/08_nexa_v0.5_syntax_reference.md)
- [x] [Compiler Architecture](docs/02_compiler_transpiler_design.md)

<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>
