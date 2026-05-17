# Nexa v2.0 Agent 快速指南

> **给 AI Agent 的指令**: 这是一个专门为你设计的文档。阅读此文档后，你将能够使用 Nexa 语言创建、修改和运行 Harness Native 智能体应用。将此文档作为你的 skill 加载，以便后续使用 Nexa 语言。

---

## 🚀 快速开始

### 什么是 Nexa？
Nexa 是 **the first Harness Native Agent Language** — 一门为大语言模型与智能体系统量身定制的编程语言，将 Agent 安全从运行时框架下沉为语言级原语。

当前版本：**v2.0.0**，累计 **1800+ 测试**。

### Harness 六元组 H=(E,T,C,S,L,V)
Nexa v2.0 将 Harness 六维度作为语言一等公民：

| 维度 | 含义 | 原语 |
|------|------|------|
| **E** | Execution 执行 | `autoloop`, `try_agent`, `catch_correction` |
| **T** | Tool 工具 | `@tool` 注解 |
| **C** | Context 上下文 | `with_context` |
| **S** | State 状态 | `snapshot()`, `restore()`, `fork/merge` |
| **L** | Lifecycle 生命周期 | `before_step`, `after_step`, `reflect` |
| **V** | Verify 验证 | `verify ... satisfies` |
| **Actor** | 多 Agent 编排 | `spawn`, `pass`, `await` |

---

## 📝 语法速查表

### 1. 声明 Agent
```nexa
agent MyAgent {
    role: "角色描述",
    model: "gpt-4o-mini",
    prompt: "你是一个有用的助手",
    tools: [Tool1, Tool2],      // 可选
    protocol: OutputSchema,      // 可选
    cache: true                  // 可选：启用语义缓存
}

// v1.1+ 支持注解
@limit(max_tokens=2048)
agent SecureBot implements Report {
    requires: input != None      // v1.2 契约前置条件
    ensures: "response is safe"  // v1.2 契约后置条件
}
```

### 2. v2.0 @tool 零成本工具绑定
```nexa
// 新方式：直接声明为函数 (v2.0)
@tool("搜索网络获取信息")
fn web_search(query: string): string {
    return "搜索结果: ...";
}

// 旧方式仍然兼容 (v0.1+)
tool WebSearch {
    description: "搜索网络信息",
    parameters: {"query": "string"}
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
    // 管道操作 (v0.1)
    result = input >> Agent1 >> Agent2;

    // Pipe 操作符 (v1.3.7)
    result = user_input |> ChatBot |> format_output;

    // 并行分叉
    results = input |>> [Agent1, Agent2, Agent3];

    // 合并结果
    final = [Agent1, Agent2] &>> MergerAgent;

    // 条件分支
    output = input ?? TrueAgent : FalseAgent;
}
```

### 5. v2.0 Harness 控制流

#### E-dimension: 自主执行循环
```nexa
// autoloop — 自主 ReAct 循环
autoloop max_steps: 10, exit_when: "任务完成", timeout: 300 {
    result = Agent.run("分析当前状态");
    print(result);
}

// try_agent — AI 专属容错
try_agent {
    result = RiskyAgent.run("执行关键任务");
} catch_correction(e: ToolError) {
    reflect "调整策略，重试";
}
```

#### C-dimension: 上下文管理
```nexa
with_context max_tokens: 50000, strategy: sliding_window {
    result = Agent.run("处理数据");
}
```

#### S-dimension: 状态快照
```nexa
snap = snapshot();           // 创建快照
restore(snap);               // 恢复状态
fork [A.run("x"), B.run("y")] merge best_of;  // 分支探索
```

#### L-dimension: 生命周期与反思
```nexa
before_step { print("[Hook] 步骤开始"); }
after_step { print("[Hook] 步骤完成"); }
reflect "考虑是否有更好的方法？";
```

#### V-dimension: 输出验证
```nexa
result = Agent.run("生成结构化输出");
verify result satisfies string;
```

#### Actor: 多 Agent 编排
```nexa
worker = spawn WorkerAgent("处理数据");
pass "分析此内容" to worker;
result = await worker;
```

### 6. v1.x 控制流 (仍然可用)
```nexa
// 语义条件判断
semantic_if "用户想查询天气" against input {
    result = WeatherAgent.run(input);
} else {
    result = OtherAgent.run(input);
}

// 意图路由
match user_input {
    intent("查询天气") => WeatherBot.run(user_input),
    intent("翻译文本") => Translator.run(user_input),
    _ => DefaultBot.run(user_input)
}

// 语义循环
loop {
    draft = Writer.run(feedback);
    feedback = Reviewer.run(draft);
} until ("文章完美无错")
```

### 7. v1.x 高级表达式
```nexa
// Pipe 操作符 (v1.3.7)
data |> parser |> analyzer |> reporter;

// 字符串插值 (v1.3.7)
let msg = "Hello, #{name}! Today is #{date}";

// 错误传播 (v1.3.2)
let count = parse(input) ?;
let result = risky_operation() otherwise 0;

// 空值合并 (v1.3.7)
let name = config.name ?? "default";

// Pattern Matching (v1.3.7)
match result {
    Option::Some(answer) => answer,
    Option::None => "no response"
}

// ADT (v1.3.7)
enum Option { Some(value), None }
struct Point { x: Int, y: Int }

// Python 逃生舱 (v1.3)
python! """
import os
print(os.getcwd())
"""

// defer (v1.3.7)
defer print("cleanup");

// 异常处理
try {
    result = RiskyAgent.run(input);
} catch {
    result = FallbackAgent.run(input);
}
```

### 8. DSL 声明 (v1.3+)
```nexa
// HTTP Server (v1.3.4)
server 8080 {
    cors { origins: ["*"], methods: ["GET", "POST"] }
    route GET "/chat" => ChatBot
    route POST "/analyze" => Analyzer |>> Reporter
}

// Database (v1.3.5)
db app_db = connect("sqlite://:app.sqlite")

// Background Job (v1.3.3)
job SendEmail on "emails" (retry: 3, timeout: 60) {
    perform(user_id) { /* ... */ }
    on_failure(error, attempt) { /* ... */ }
}

// Auth (v1.3.6)
auth myAuth = enable_auth("providers.json")

// KV Store (v1.3.6)
kv store = open(":memory:")

// Structured Concurrency (v1.3.6)
let task = spawn(Agent.run("x"));
let results = parallel([Agent1, Agent2, Agent3]);
let winner = race([Agent1, Agent2]);
```

### 9. 测试
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
    model: "gpt-4o-mini",
    prompt: "你是一个友好的助手，帮助用户解决问题。"
}

flow main {
    response = ChatBot.run(input);
    print(response);
}
```

### 模板 2: v2.0 Harness Agent
```nexa
@tool("搜索网络获取信息")
fn web_search(query: string): string {
    return "搜索结果: ...";
}

agent Assistant {
    role: "智能助手",
    model: "gpt-4o",
    prompt: "使用工具帮助用户解决问题"
}

flow main {
    // E: 自主循环
    autoloop max_steps: 5, exit_when: "resolved" {
        // C: 上下文管理
        with_context max_tokens: 50000 {
            // S: 状态快照
            snap = snapshot();

            try_agent {
                result = Assistant.run(input);
                // V: 验证输出
                verify result satisfies string;
            } catch_correction(e: ToolError) {
                restore(snap);
                reflect "调整策略重试";
            }
        }
    }
}
```

### 模板 3: Actor System 多 Agent 编排
```nexa
agent Researcher { prompt: "深入研究并收集信息" }
agent Writer { prompt: "基于研究写出文章" }
agent Reviewer { prompt: "审核文章质量和准确性" }

flow main {
    // Actor: spawn 子 Agent
    r = spawn Researcher("研究主题 X");
    research = await r;

    w = spawn Writer(research);
    pass "基于研究成果写文章" to w;
    draft = await w;

    rev = spawn Reviewer(draft);
    review = await rev;
    print(review);
}
```

### 模板 4: 管道流程 (DAG)
```nexa
agent Researcher { prompt: "研究并收集信息" }
agent Writer { prompt: "基于研究写出文章" }
agent Editor { prompt: "润色和改进文章" }

flow main {
    article = input |> Researcher |> Writer |> Editor;
}
```

### 模板 5: 并行处理
```nexa
agent TranslatorCN { prompt: "翻译成中文" }
agent TranslatorEN { prompt: "翻译成英文" }
agent TranslatorJP { prompt: "翻译成日语" }

flow main {
    translations = input |>> [TranslatorCN, TranslatorEN, TranslatorJP];
}
```

### 模板 6: 批评循环
```nexa
agent Writer { prompt: "写一篇文章" }
agent Critic { prompt: "批评并指出文章的问题" }

flow improve {
    loop {
        draft = Writer.run(feedback);
        feedback = Critic.run(draft);
    } until ("文章质量优秀，无需修改")
}
```

---

## 🔧 Agent 写 Agent 指南

### 如何创建新 Agent

1. **确定 Agent 的职责** — 单一职责原则，清晰描述 role 和 prompt
2. **选择合适的模型** — 复杂推理用 `claude-sonnet-4-20250514` / `gpt-4o`，简单任务用 `gpt-4o-mini`，快速响应用 `claude-3-haiku`
3. **定义工具** — 优先使用 v2.0 `@tool fn` 语法，旧 `tool {}` 语法仍兼容
4. **设计流程** — 串行 `>>`/`|>`、并行 `|>>`、分支 `semantic_if`/`match`
5. **添加 Harness 防护** — 用 `autoloop` 控制循环、`verify` 验证输出、`try_agent` 处理错误

### 模型参考

| 模型 | 适用场景 |
|------|---------|
| `claude-sonnet-4-20250514` | 复杂推理、代码生成 |
| `gpt-4o` / `gpt-4o-mini` | 通用任务 |
| `claude-3.5-sonnet` | 平衡性能与成本 |
| `deepseek-chat` / `deepseek-reasoner` | 高性价比推理 |
| `claude-3-haiku` | 快速简单响应 |
| `glm-5` | 国产替代（通过 OPENAI_BASE_URL 配置） |

---

## ⚡ 高级特性

### 1. 语义缓存
```nexa
agent CachedBot {
    prompt: "...",
    model: "deepseek-chat",
    cache: true  // 相同或相似请求复用结果
}
```

### 2. 长期记忆与经验
```nexa
agent SmartBot {
    prompt: "...",
    experience: "bot_memory.md"  // 加载历史经验
}
```

### 3. 契约式编程 (Design by Contract)
```nexa
agent SecureBot {
    requires: input != None and len(input) < 1000
    ensures: "response is helpful and accurate"
}
```

### 4. RBAC 权限
```python
from src.runtime.rbac import get_rbac_manager, Permission
rbac = get_rbac_manager()
rbac.create_role("readonly", permissions=[Permission.READ])
rbac.assign_role("DataBot", "readonly")
```

### 5. MCP 工具集成
```nexa
tool SearchMCP {
    mcp: "github.com/nexa-ai/search-mcp"
}
```

### 6. DAG 高级拓扑
```nexa
flow complex_pipeline {
    research = topic |>> [WebResearcher, PaperResearcher, NewsResearcher];
    analysis = research &>> Analyst;
    final = analysis ?? DetailedReport : SummaryReport;
}
```

---

## 📚 CLI 命令速查

```bash
# 编译 .nx → .py
nexa build script.nx
nexa build script.nx --harness=warn    # v2.0: 带 Harness 验证
nexa build script.nx --harness=strict  # v2.0: 严格验证模式

# 编译并运行
nexa run script.nx
nexa run script.nx --harness=warn

# 运行测试
nexa test tests.nx

# v2.0: Harness 验证
nexa harness-check app.nx
nexa harness-check app.nx --harness=warn --json

# v1.3: Agent-Native 工具
nexa inspect app.nx --format json|text
nexa validate app.nx --json --quiet
nexa lint app.nx --strict

# v1.1: IDD 意图验证
nexa intent check app.nx --intent spec.nxintent --verbose
nexa intent coverage app.nx

# v1.3.4: HTTP Server
nexa serve app.nx --port 3000
nexa routes app.nx --json

# v1.3.3: Job System
nexa jobs list --status pending --limit 20
nexa jobs status <job_id>
nexa workers start app.nx --worker-id worker-1
nexa workers status

# 缓存管理
nexa cache clear

# 版本
nexa --version
```

如果没有全局安装，可用 `python -m src.cli <command>` 替代 `nexa`。

---

## 🐛 调试技巧

### 1. 使用 print 输出中间结果
```nexa
flow debug_flow {
    step1 = input |> Agent1;
    print(step1);
    step2 = step1 |> Agent2;
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
nexa build script.nx
# 查看同目录下的 script.py 了解运行逻辑
```

### 4. v2.0 Harness 检查
```bash
nexa harness-check script.nx --harness=warn
# 查看六维度约束是否满足
```

---

## 🎓 最佳实践

1. **命名规范** — Agent/Tool: `PascalCase`，Flow: `snake_case`，@tool fn: `snake_case`
2. **Prompt 设计** — 明确角色和职责，提供具体行为指导，包含输出格式要求
3. **流程设计** — 保持简单，合理使用并行，添加错误处理分支
4. **Harness 防护** — 用 `autoloop` 限制循环步数，`verify` 确保输出质量，`snapshot/restore` 实现安全回溯
5. **性能优化** — 对重复请求启用 `cache: true`，合理选择模型，用 `with_context` 控制上下文大小

---

## 🔗 Python 互操作

### 使用 Nexa SDK
```python
import nexa

# 运行脚本
result = nexa.run("script.nx")

# 编译代码
module = nexa.compile("agent TestBot { prompt: '测试' }")

# 动态创建 Agent
bot = nexa.Agent(
    name="MyBot",
    prompt="你是一个有用的助手",
    model="gpt-4o-mini"
)
response = bot.run("Hello!")
```

### 直接使用运行时组件
```python
from src.runtime.agent import NexaAgent
from src.runtime.cache_manager import get_cache_manager
from src.runtime.rbac import get_rbac_manager, Permission
from src.runtime.harness_kernel import get_kernel
```

---

## 🏗 Nexa Code — 用 Nexa 写的 AI 编程助手

[Nexa Code](examples/Nexa-Code/) 是用 Nexa 语言自身编写的交互式 AI 编程助手，类似 Claude Code 的 CLI 框架。它使用了全部 Harness 六维度特性，是学习 v2.0 最佳实践的完整参考。

运行方式：
```bash
nexa run examples/Nexa-Code/main.nx --harness=warn
```

---

## 📖 完整文档

- [安装与 Hello World](INSTALL_AND_HELLO_WORLD.md)
- [语法参考手册](../docs/01_nexa_syntax_reference.md)
- [编译器架构](../docs/02_compiler_architecture.md)
- [路线图与愿景](../docs/03_roadmap_and_vision.md)
- [极速上手指南](../docs/06_quick_start_guide.md)
- [Harness Agent 设计文档](../docs/others/Harness_Agent.md)
- [v2.0.0 Release Notes](../docs/release_notes/v2.0.0.md)
- [Feature Changelog v1.1-v1.3.x](../docs/others/changelog_v1.1.0-v1.3.x_features.md)

---

*此文档专为 AI Agent 设计，让你能够快速理解和应用 Nexa v2.0 语言。*