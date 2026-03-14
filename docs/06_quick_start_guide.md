# Nexa 极速上手开发指南 (Developer Quick Start)

欢迎来到大模型原生时代。这篇文档将以开发者第一视角，带你用 5 分钟了解并精通 Nexa。

---

## 1. 概念建立：为什么要用 ".nx" 脚本？

过去，我们要实现一个包含搜索工具的智能体并在代码里做条件分流，大概需要写 100 行以上的 Python API 调用和类型处理代码。在 Nexa 中，一切逻辑和“胶水”不仅被隐式压缩了，而且语言本身就能理解抽象指令。你编写的 `.nx` 将被编译器底层精准推断，随后自动转译执行。

---

## 2. 认识 Nexa 的三大基石 

Nexa 脚本总是由这三个最核心的主件构成：`tool`, `agent` 和 `flow`。

### 2.1 声明式 Tool 注册
你不再需要硬写恶心的 JSON Schema 给 OpenAI API，只需要声明式定义并描述类型：
```nexa
tool calculate_tax {
    description: "Calculate tax rate based on annual income.",
    parameters: {
        "income": "number"
    }
}
```
此时此刻，编译器已经在背后默默替你完成了 Pydantic 模型绑定、Schema 提取的脏活。

### 2.2 定义你的 Agent 并装备弹药
Agent 直接是一个关键字，你能轻松给它赋能之前注册过的 Tool。
```nexa
agent Accountant uses calculate_tax {
    prompt: "You are an expert accountant focused on maximizing legal tax returns."
}
```

### 2.3 在 Flow 中运筹帷幄 (Flow Orchestration)
`flow` 就是执行流片段。我们的目标是极简。
```nexa
flow main {
    report = Accountant.run("My income is $150,000.");
}
```

---

## 3. 神奇的 Semantic If (语义控制流)

这是 Nexa 的杀手级特性。所有写过 LLM 业务逻辑的人都知道，传统代码很难去**解析由 LLM 输出的一长段不确定文本**。比如，如果用户想要判断“账单里提到了偷税漏税”，以前我们要么强迫 LLM 输出 JSON 然后手动解析出布尔值，要么写正则表达式匹配。

在 Nexa 中，我们引入了 `semantic_if`：

```nexa
semantic_if "The result explicitly suggests something illegal like tax evasion" against report {
    # 如果自然语言暗示了非法操作：
    ComplianceAgent.run("Flag this user and write a warning log.");
} else {
    # 正常流程
    Print.run("Tax processed successfully.");
}
```

### 它是如何工作的？
遇到 `semantic_if` 时，Nexa 编译器并**不会**将它转译成简单的正则判断代码！
在背后的 Python 运行时中，Nexa 会自动：
1. 静默唤起一个小参数规模的 LLM（例如 deepseek-chat 或 gpt-4o-mini）。
2. 让其作为评判器（Judge Model），判定 `target` 的信息是否满足 `condition`（提示词级语义匹配）。
3. 自动使用内置的容错方案（如 `json_object` Fallback）获取严谨的布尔返回值。
4. 提供基于 `tenacity` 的**自愈退避重试**以防止网络或幻觉崩溃。

你只写了 3 行代码，但 Nexa 背后为你部署了固若金汤的验证网。

---

## 4. 下一步？

打开你的代码编辑器，新建 `test.nx`，开始敲击：
```bash
# 编写后执行
nexa run test.nx
```
欢迎进入“写业务流而非填表代码”的美好新时代。