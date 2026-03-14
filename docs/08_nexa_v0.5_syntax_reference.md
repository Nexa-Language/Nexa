# Nexa v0.5 Syntax Reference 🚀

Nexa v0.5 引入了全面升级的多智能体并发与工作流编排语法。通过原生的 `match intent` 意图路、`>>` 管道操作和 `join()` 聚合方法，Nexa 现在能够原生支持复杂的 DAG（有向无环图）的业务流转场景。

## 1. 代理声明 (Agent Declaration)

在 v0.5 中，Agent 支持完整的属性配置，用于精准设定模型和内存作用域。

```nexa
agent Researcher {
    role: "Tech Researcher",
    model: "minimax-m2.5",
    prompt: "Provide an in-depth analysis based on user query."
}
```

## 2. 意图路由 (Match Intent)

使用 `match target { intent("...") => ... }` 将用户的自然语言请求路由给合适的 Agent。系统将底层自动调用深度语义模型进行评估匹配。

```nexa
match req {
    intent("Check weather") => WeatherBot.run(req),
    intent("Check daily news") => NewsBot.run(req),
    _ => SmallTalkBot.run(req)
}
```

## 3. 管道组合 (Pipeline `>>`)

Unix 风格的 `>>` 操作符被用于无缝串联 Agent 间的输入/输出。前一个Agent的返回将自动成为下一个Agent的输入。

```nexa
flow main {
    # 自动完成: 获取新闻 -> 翻译 -> 最终输出
    result = NewsBot.run("Today's tech news") >> Translator;
}
```

## 4. 并发聚合 (`join()`)

通过 `join` 函数，可以并线触发多个 Agent，并在所有请求完成后，将组合结果发送给末端节点。

```nexa
flow main {
    tech_view = Researcher_Tech.run("Quantum Computing advances");
    biz_view = Researcher_Biz.run("Quantum Computing business impact");
    
    # join 将汇集 tech_view 和 biz_view 并最终交由 Summarizer 智能体生成报告
    final_report = join(Researcher_Tech, Researcher_Biz).Summarizer("Synthesize the reports");
}
```

## 5. 循环与语义评价 (Loop / Semantic If)

v0.5 原生支持了 `loop { ... } until ("condition")` 结构机制。`until` 不再是简单的布尔判断，而是一个自然语言的评估诉求！底层的执行引擎会基于当前上下文的变量（如 `locals()`）进行大模型校验。

```nexa
flow main {
    poem = Writer.run("Write a poem about Artificial General Intelligence");
    
    loop {
        feedback = Critic.run(poem);
        poem = Editor.run(feedback);
    } until ("Poem has rhyme and mentions singularity")
}
```

---
**提示**: 上述语法已被底层的 `Nexa Runtime` 原生实现，可使用全局提供的 `nexa run` 直接加载并执行。