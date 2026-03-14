# Nexa v0.5 Syntax Evolution Proposal (RFC)

**Author:** Nexa Core Team
**Status:** DRAFT (Targeting v0.5)

---

## 1. 摘要 (Abstract)
随着 v0.1 MVP 对 Transpiler 与基础声明式语法的成功论证，v0.5 的目标是深入解决“多 Agent 协作”、“数据流转”、“运行时幻觉治理”等高阶痛点。本 RFC 结合主创设计师方案，详细定义了即将引入的新核心层语法。

---

## 2. 核心特性提案 

### 2.1 基于管道的流式编排 (Pipeline & Flow Control)
Agent 的本质是信息加工节点。我们计划引入类似 Unix 的灵感操作符 `>>`，使多 Agent 的串联调用彻底抛弃繁茂的中转变量赋值。

**【语法设计】**
```nexa
flow content_creation_pipeline {
    // Researcher 产出报告后，其文本直接作为 Writer 的输入，其结果被保存在 article
    article = Researcher.run("Deep Learning in 2026") >> Writer >> Editor;
}
```

针对复杂的问答网关结构，抛弃漫长的多次 `semantic_if/else`，引入**意图路由 (Intent Routing)** 语句块：
```nexa
// match intent 将隐式调用路由判决小模型（低延迟），然后发往不同节点
match user_input {
    intent("coding") => Developer >> CodeReviewer,
    intent("creative") => Writer,
    _ => Assistant
}
```

### 2.2 并发协作与共识机制 (Concurrency & Consensus)
解决单线程执行导致的延迟问题以及单次推理不稳定的现象。

**【Join 发散与收敛】**
```nexa
flow brainstorm {
    // 隐式异步并发触发
    ideas = join(AnalyzerA, AnalyzerB, AnalyzerC).summarize();
}
```

**【批评者模式 (Critic Pattern)】**
原生支持“生成-评审”循环，解决当前需要通过 Python `while` 和手写评分逻辑的问题：
```nexa
loop {
    draft = Writer.write("Write a sci-fi short story");
} until (Editor.approve(draft) || iterations > 3)
```
*Note: `Editor.approve` 期望是一个强类型布尔出口工具节点。*

### 2.3 声明式特性进阶 (Persona & 作用域内存)
Agent 定义块将引入更多原生描述符：
```nexa
agent Researcher {
    model: "minimax-m2.5",
    role: "专业数据分析师",
    skills: [web_search, text_summarize], // 支持 tool，也可直接嵌套子 Agent 作为被调用技能
    memory: shared // local(对话内), shared(跨agent黑板), persistent(向量持久化)
}
```

### 2.4 原生类型安全约束
目前我们依赖 `tenacity` 在后端捕捉异常，但 v0.5 计划将 `agent` 或者 `flow` 的输出直接加上类型尾缀，由运行时强制触发 Retry：
```nexa
agent Extractor -> JSON<UserRecord> {
    prompt: "Extract user details."
}
// 如果 LLM 未输出正确的 UserRecord 结构，Runtime 将自动向它提示幻觉并要求修正。
```

---

## 3. 对编译器后端的变更推演
为了支撑这几大原生特性（特别是并发 `join`，管道阻塞，持久化 `memory` 以及 `loop until`），目前将 Boilerplate 硬塞到 `code_generator.py` 的架构**已不敷使用**。

我们需要在项目根目录构建 `runtime/` 层。转译后的 Python 代码仅仅是一份 DAG 定义与配置图，实际复杂的队列排版、沙箱、对话窗口压缩都将被代理至 `import nexa.runtime` 中执行。