# Nexa 语言 Agent 快速指南

> **给 AI Agent 的指令**: 这是一个专门为你设计的文档。阅读此文档后，你将能够使用 Nexa 语言创建、修改和运行智能体应用。将此文档作为你的 skill 加载，以便后续使用 Nexa 语言。

---

## 🚀 快速开始

### 什么是 Nexa？
Nexa 是一门**智能体原生 (Agent-Native)** 编程语言，专为 LLM 和 Agentic Systems 设计。

### 核心概念
```
Agent = 智能体 (有 prompt、model、tools)
Tool  = 工具 (外部能力)
Flow  = 流程 (Agent 编排)
```

---

## 📝 语法速查表

### 1. 声明 Agent
```nexa
agent MyAgent {
    role: "角色描述",
    model: "gpt-4",
    prompt: "你是一个有用的助手",
    tools: [Tool1, Tool2],      // 可选
    protocol: OutputSchema,      // 可选
    cache: true                  // 可选：启用缓存
}
```

### 2. 声明 Tool
```nexa
tool MyTool {
    description: "工具描述",
    parameters: {
        "param1": "string",
        "param2": "number"
    }
}
```

### 3. 声明 Protocol (输出约束)
```nexa
protocol OutputSchema {
    field1: "string",
    field2: "number",
    field3: "boolean"
}
```

### 4. 编排 Flow
```nexa
flow main {
    // 管道操作
    result = input >> Agent1 >> Agent2;
    
    // 并行分叉
    results = input |>> [Agent1, Agent2, Agent3];
    
    // 合并结果
    final = [Agent1, Agent2] &>> MergerAgent;
    
    // 条件分支
    output = input ?? TrueAgent : FalseAgent;
}
```

### 5. 控制流
```nexa
// 语义条件判断
semantic_if "用户想查询天气" against input {
    result = WeatherAgent.run(input);
} else {
    result = OtherAgent.run(input);
}

// 快速匹配 (正则预过滤)
semantic_if "包含日期" fast_match r"\d{4}-\d{2}" against input {
    // ...
}

// 语义循环
loop {
    draft = Writer.run(feedback);
    feedback = Reviewer.run(draft);
} until ("文章完美无错")

// 意图路由
match user_input {
    intent("查询天气") => WeatherBot.run(user_input),
    intent("翻译文本") => Translator.run(user_input),
    _ => DefaultBot.run(user_input)
}
```

### 6. 异常处理
```nexa
try {
    result = RiskyAgent.run(input);
} catch {
    result = FallbackAgent.run(input);
}
```

### 7. 测试
```nexa
test "测试名称" {
    result = MyAgent.run("测试输入");
    assert "包含预期内容" against result;
}
```

---

## 🎯 常用代码模板

### 模板 1: 简单对话 Agent
```nexa
agent ChatBot {
    role: "友好助手",
    model: "gpt-4",
    prompt: "你是一个友好的助手，帮助用户解决问题。"
}

flow main {
    response = input >> ChatBot;
    print(response);
}
```

### 模板 2: 带工具的 Agent
```nexa
tool Calculator {
    description: "执行数学计算",
    parameters: {"expression": "string"}
}

tool WebSearch {
    description: "搜索网络信息",
    parameters: {"query": "string"}
}

agent Assistant {
    role: "智能助手",
    model: "gpt-4",
    prompt: "使用工具帮助用户",
    tools: [Calculator, WebSearch]
}
```

### 模板 3: 管道流程
```nexa
agent Researcher {
    role: "研究员",
    prompt: "研究并收集信息"
}

agent Writer {
    role: "作者",
    prompt: "基于研究写出文章"
}

agent Editor {
    role: "编辑",
    prompt: "润色和改进文章"
}

flow main {
    article = input >> Researcher >> Writer >> Editor;
}
```

### 模板 4: 并行处理
```nexa
agent TranslatorCN { prompt: "翻译成中文" }
agent TranslatorEN { prompt: "翻译成英文" }
agent TranslatorJP { prompt: "翻译成日语" }

flow main {
    translations = input |>> [TranslatorCN, TranslatorEN, TranslatorJP];
}
```

### 模板 5: 批评循环
```nexa
agent Writer {
    role: "作家",
    prompt: "写一篇文章"
}

agent Critic {
    role: "评论家",
    prompt: "批评并指出文章的问题"
}

flow improve_article {
    loop {
        draft = Writer.run(feedback);
        feedback = Critic.run(draft);
    } until ("文章质量优秀，无需修改")
}
```

---

## 🔧 Agent 写 Agent 指南

### 如何创建新 Agent

1. **确定 Agent 的职责**
   - 单一职责原则：每个 Agent 只做一件事
   - 清晰描述 role 和 prompt

2. **选择合适的模型**
   - `gpt-4` / `claude-3.5-sonnet`: 复杂推理
   - `gpt-3.5-turbo` / `deepseek-chat`: 简单任务
   - `claude-3-haiku`: 快速响应

3. **定义工具 (如需要)**
   - 明确参数类型
   - 提供清晰的 description

4. **设计流程**
   - 使用 `>>` 进行串行
   - 使用 `|>>` 进行并行
   - 使用 `semantic_if` 进行分支

### 示例：创建一个研究助手

```nexa
// Step 1: 定义工具
tool WebSearch {
    description: "搜索网络获取信息",
    parameters: {"query": "string"}
}

tool Summarizer {
    description: "总结长文本",
    parameters: {"text": "string"}
}

// Step 2: 定义输出协议
protocol ResearchReport {
    topic: "string",
    key_findings: "string",
    sources: "string",
    confidence: "number"
}

// Step 3: 定义 Agent
agent Researcher implements ResearchReport {
    role: "研究分析师",
    model: "claude-3.5-sonnet",
    prompt: "深入研究给定主题，提供结构化的研究报告",
    tools: [WebSearch, Summarizer]
}

agent Reviewer {
    role: "质量审核员",
    model: "gpt-4",
    prompt: "审核研究报告的准确性和完整性"
}

// Step 4: 定义流程
flow research_pipeline {
    report = input >> Researcher >> Reviewer;
    print(report);
}
```

---

## ⚡ 高级特性

### 1. 启用缓存
```nexa
agent CachedBot {
    prompt: "...",
    model: "deepseek-chat",
    cache: true  // 语义缓存，相同或相似请求复用结果
}
```

### 2. 长期记忆
```nexa
agent SmartBot {
    prompt: "...",
    experience: "bot_memory.md"  // 加载历史经验
}
```

### 3. RBAC 权限
```python
# 在 Python 中配置
from src.runtime.rbac import get_rbac_manager, Permission
rbac = get_rbac_manager()
rbac.create_role("readonly", permissions=[Permission.READ])
rbac.assign_role("DataBot", "readonly")
```

### 4. DAG 高级拓扑
```nexa
// 复杂工作流
flow complex_pipeline {
    // 并行研究
    research = topic |>> [WebResearcher, PaperResearcher, NewsResearcher];
    
    // 合并分析
    analysis = research &>> Analyst;
    
    // 条件输出
    final = analysis ?? DetailedReport : SummaryReport;
}
```

---

## 📚 运行命令

```bash
# 运行脚本
nexa run script.nx

# 运行测试
nexa test tests.nx

# 编译查看 Python 输出
nexa build script.nx

# 交互模式
nexa repl
```

---

## 🐛 调试技巧

### 1. 使用 print 输出中间结果
```nexa
flow debug_flow {
    step1 = input >> Agent1;
    print(step1);  // 查看中间结果
    
    step2 = step1 >> Agent2;
    print(step2);
}
```

### 2. 使用 test 验证
```nexa
test "验证 Agent 输出" {
    result = MyAgent.run("测试输入");
    assert "包含预期字段" against result;
}
```

### 3. 查看生成的 Python
```bash
nexa build script.nx --output out.py
# 然后查看 out.py 了解运行逻辑
```

---

## 🎓 最佳实践

1. **命名规范**
   - Agent: `PascalCase` (如 `ChatBot`, `Researcher`)
   - Tool: `PascalCase` (如 `WebSearch`)
   - Flow: `snake_case` (如 `main_flow`)

2. **Prompt 设计**
   - 明确角色和职责
   - 提供具体的行为指导
   - 包含输出格式要求

3. **流程设计**
   - 保持简单，避免过度复杂
   - 合理使用并行提高效率
   - 添加错误处理分支

4. **性能优化**
   - 对重复请求启用 `cache: true`
   - 使用 `fast_match` 减少语义判断开销
   - 合理选择模型（简单任务用快模型）

---

## 🔗 Python 互操作

从 Python 调用 Nexa:

```python
import nexa

# 方式 1: 运行脚本
result = nexa.run("script.nx")

# 方式 2: 创建 Agent
bot = nexa.Agent(
    name="MyBot",
    prompt="你是一个有用的助手",
    model="gpt-4"
)
response = bot.run("Hello!")

# 方式 3: 编译代码
module = nexa.compile("""
agent TestBot {
    prompt: "测试"
}
""")

# 方式 4: 访问运行时
from src.runtime.agent import NexaAgent
from src.runtime.cache_manager import get_cache_manager
```

---

## 📖 完整文档

- [安装与 Hello World](INSTALL_AND_HELLO_WORLD.md)
- [语法参考手册](../docs/01_nexa_syntax_reference.md)
- [编译器架构](../docs/02_compiler_architecture.md)
- [路线图与愿景](../docs/03_roadmap_and_vision.md)
- [快速入门指南](../docs/06_quick_start_guide.md)

---

*此文档专为 AI Agent 设计，让你能够快速理解和应用 Nexa 语言。*