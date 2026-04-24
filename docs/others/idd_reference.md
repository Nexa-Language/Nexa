# Nexa Intent-Driven Development (IDD) 完整参考

## 概述

Nexa 的 IDD (Intent-Driven Development) 系统让需求文档变成可执行测试，形成"需求→实现→验证"的闭环。这是从 NTNT 语言学习的灵魂特性，融合了 Agent-native 验证，超越 NTNT 的 HTTP-only 模式。

### 核心概念

IDD 系统包含三个核心组件：

1. **IAL (Intent Assertion Language)** — 术语重写引擎，将自然语言断言递归解析为可执行测试
2. **`.nxintent` 文件** — YAML 格式的需求文档，定义 Feature/Scenario/Glossary
3. **`@implements` 注解** — 将代码链接到需求，形成需求→代码→验证的闭环

### 工作流程

```
.nxintent 文件 (需求)           .nx 文件 (实现)
    │                              │
    │ Feature/Scenario/Glossary    │ @implements: feature.id
    │                              │
    └──────┬───────────────────────┘
           │
           ↓
    nexa intent check
           │
           ↓
    IAL 术语重写引擎
    "they see success response"
        ↓ vocabulary lookup
    "component.success_response"
        ↓ component expansion  
    ["status 2xx", "body contains 'ok'"]
        ↓ standard term resolution
    [Check(InRange, "response.status", 200-299), Check(Contains, "response.body", "ok")]
        ↓ execution
    [✓, ✓]
```

---

## 1. `.nxintent` 文件格式

`.nxintent` 文件使用 YAML + Markdown 混合格式，包含三部分：

### 1.1 Glossary（术语表）

使用 Markdown 表格定义领域术语映射：

```yaml
## Glossary

| Term | Means |
|------|-------|
| a user asks {question} | agent run with input {question} |
| the agent responds with {text} | output contains {text} |
| the response is valid | protocol check passes |
| the pipeline produces {text} | pipeline output contains {text} |
| clarification response | output is about clarification or asking for more details |
| weather information | output mentions weather, temperature, conditions or forecast |
```

**术语类型**：
- **模式术语**：含 `{param}` 占位符，如 `they see {text}`
- **精确术语**：无占位符，如 `the response is valid`
- **展开术语**：映射到多个断言，如 `success response → ["status 2xx", "body contains 'ok']`

### 1.2 Feature（特性定义）

```yaml
Feature: Weather Bot
  id: feature.weather_bot
  description: "Weather information agent"
```

### 1.3 Scenario（场景定义）

```yaml
  Scenario: Weather query
    When a user asks "What is the weather in Beijing?"
    → the agent responds with "weather"
    → the response is valid

  Scenario: Invalid query handling
    When a user asks "xyzzy"
    → the agent responds with "clarification"
```

**语法元素**：
- `When ...` — 描述触发条件
- `→ ...` — 断言语句，描述期望行为

### 1.4 分隔线

Glossary 和 Feature 之间使用 `---` 分隔：

```yaml
## Glossary
...
---
Feature: ...
```

---

## 2. @implements 注解

### 2.1 基本语法

在 Nexa 源代码中使用注释格式添加注解：

```nexa
// @implements: feature.weather_bot
agent WeatherBot uses WeatherAPI implements WeatherReport {
    role: "Weather Assistant",
    prompt: "Provide weather information for cities"
}
```

### 2.2 @supports 注解

`@supports` 用于链接约束定义：

```nexa
// @supports: constraint.output_format
agent Formatter {
    role: "Output Formatter"
}
```

### 2.3 注解处理流程

1. **解析阶段**：`nexa_parser.py` 的 `extract_implements_annotations()` 函数从源码中提取注解
2. **AST 注入**：注解信息存入 AST 的 `annotations` 字段
3. **代码生成**：`code_generator.py` 将注解保留为 Python 注释
4. **Intent 验证**：`AnnotationScanner` 从 .nx 文件扫描注解，匹配 intent features

生成的 Python 代码示例：
```python
# @implements: feature.weather_bot
WeatherBot = NexaAgent(
    name="WeatherBot",
    ...
)
```

---

## 3. IAL 引擎架构

### 3.1 术语重写流程

IAL 引擎的核心是递归术语重写：

```
"they see success response"
    ↓ vocabulary lookup        → 找到术语条目
"component.success_response"
    ↓ component expansion      → 展开为多个术语
["status 2xx", "body contains 'ok'"]
    ↓ standard term resolution → 解析为原语
[Check(InRange, "response.status", 200-299), Check(Contains, "response.body", "ok")]
    ↓ execution                → 执行检查
[✓, ✓]
```

### 3.2 原语类型 (Primitives)

IAL 引擎包含以下原语类型，覆盖 Agent-native 和传统验证：

| 原语 | 描述 | Agent-native |
|------|------|:------------:|
| **AgentAssertion** | 直接调用 agent 并检查输出 | ✓ |
| **ProtocolCheck** | 验证输出符合 protocol 约束 | ✓ |
| **PipelineCheck** | 验证 DAG 管道输出 | ✓ |
| **SemanticCheck** | 用 LLM 判断输出是否符合语义预期 | ✓ |
| **Http** | 执行 HTTP 请求并检查响应 | |
| **Cli** | 执行命令行并检查输出 | |
| **CodeQuality** | 代码质量检查 | |
| **ReadFile** | 读取文件内容并检查 | |
| **FunctionCall** | 调用函数并检查返回值 | |
| **PropertyCheck** | 检查对象属性值 | |
| **InvariantCheck** | 验证系统不变式 | |
| **Check** | 通用比较检查（最基础） | |

### 3.3 CheckOp 检查操作

所有 `Check` 原语使用以下比较操作：

| CheckOp | 描述 | 示例 |
|---------|------|------|
| Equals | 等于 | `Check(Equals, "status", 200)` |
| NotEquals | 不等于 | `Check(NotEquals, "status", 500)` |
| Contains | 包含 | `Check(Contains, "output", "weather")` |
| NotContains | 不包含 | `Check(NotContains, "output", "error")` |
| Matches | 正则匹配 | `Check(Matches, "output", "^success")` |
| Exists | 存在 | `Check(Exists, "city", None)` |
| NotExists | 不存在 | `Check(NotExists, "error", None)` |
| LessThan | 小于 | `Check(LessThan, "count", 10)` |
| GreaterThan | 大于 | `Check(GreaterThan, "score", 80)` |
| InRange | 在范围内 | `Check(InRange, "status", (200, 299))` |
| StartsWith | 以...开头 | `Check(StartsWith, "output", "OK")` |
| EndsWith | 以...结尾 | `Check(EndsWith, "output", "done")` |
| IsType | 类型检查 | `Check(IsType, "output", "dict")` |
| HasLength | 长度检查 | `Check(HasLength, "list", 5)` |

### 3.4 标准断言格式

无需词汇表，IAL 也支持常见断言模式：

| 断言格式 | 解析结果 |
|---------|---------|
| `status 2xx` | Check(InRange, "response.status", (200, 299)) |
| `status 200` | Check(Equals, "response.status", 200) |
| `output contains 'text'` | Check(Contains, "output", "text") |
| `output equals 'hello'` | Check(Equals, "output", "hello") |
| `output matches '^pattern'` | Check(Matches, "output", "^pattern") |
| `output exists` | Check(Exists, "output", None) |
| `response is valid` | ProtocolCheck(protocol_name) |
| `body contains 'ok'` | Check(Contains, "response.body", "ok") |

### 3.5 语义检查降级

当断言无法通过词汇表或标准格式解析时，IAL 自动生成 `SemanticCheck`，使用：
1. LLM 判断（如果 API key 可用）
2. 关键词启发式匹配（fallback）

---

## 4. 标准词汇表

Nexa IAL 内置了覆盖常见场景的标准词汇：

### Agent 验证

| 术语 | 映射 |
|------|------|
| `a user asks {question}` | AgentAssertion(input={question}) |
| `the agent responds with {text}` | Check(Contains, "output", {text}) |
| `the agent says {text}` | Check(Contains, "output", {text}) |
| `the agent output equals {text}` | Check(Equals, "output", {text}) |

### Protocol 验证

| 术语 | 映射 |
|------|------|
| `the response is valid` | ProtocolCheck() |
| `protocol check passes` | ProtocolCheck() |
| `the response follows {protocol}` | ProtocolCheck(protocol={protocol}) |

### Pipeline 验证

| 术语 | 映射 |
|------|------|
| `the pipeline produces {text}` | Check(Contains, "output", {text}) |
| `pipeline output contains {text}` | Check(Contains, "output", {text}) |

### HTTP 验证

| 术语 | 映射 |
|------|------|
| `success response` | ["status 2xx", "body contains 'ok'"] |
| `they see {text}` | Check(Contains, "response.body", {text}) |
| `returns status {code}` | Check(Equals, "response.status", {code}) |

### 语义验证

| 术语 | 映射 |
|------|------|
| `response mentions {text}` | SemanticCheck(intent={text}) |
| `output is about {topic}` | SemanticCheck(intent={topic}) |
| `clarification response` | SemanticCheck(intent=clarification) |
| `weather information` | SemanticCheck(intent=weather data) |
| `helpful response` | SemanticCheck(intent=helpful) |

---

## 5. CLI 命令

### 5.1 intent check

验证代码是否符合 intent 定义：

```bash
nexa intent check <file.nx> [--intent <intent_file>] [--verbose]
```

**输出示例**：
```
🔍 Intent Check: weather_bot.nx
   Intent file: weather_bot.nxintent

📋 Feature: Weather Bot (feature.weather_bot)
  🎯 Scenario: Weather query
    ✓ Check(contains, output, "weather")
    ✓ ProtocolCheck(WeatherReport)
    ✓ Weather query: 2/2 checks passed

  🎯 Scenario: Invalid query handling
    ✓ Check(contains, output, "clarification")
    ✓ Invalid query handling: 1/1 checks passed

==================================================
✅ All features passed!
  Features:  1
  Scenarios: 2/2 passed
  Checks:    3/3 passed (0 skipped)
==================================================
```

**彩色输出**：
- 🟢 绿色 ✓ — 检查通过
- 🔴 红色 ✗ — 检查失败
- 🟡 黄色 ⏭️ — 检查跳过（无 runtime 可用）

### 5.2 intent coverage

显示特性覆盖率报告：

```bash
nexa intent coverage <file.nx> [--intent <intent_file>]
```

**输出示例**：
```
📊 Intent Coverage Report
==================================================
  ✓ Weather Bot (feature.weather_bot)
    Implemented: ✓  Scenarios: ✓ (2)
==================================================
  Coverage: 100.0% (1/1 features implemented)
==================================================
```

---

## 6. IAL 模块结构

```
src/ial/
├── __init__.py        # 公共 API（resolve, execute, create_vocabulary）
├── primitives.py      # 原语类型定义（Check, AgentAssertion, ProtocolCheck 等）
├── vocabulary.py      # 术语存储和模式匹配引擎
├── resolve.py         # 递归术语重写引擎
├── execute.py         # 原语执行引擎
└── standard.py        # 标准词汇定义

src/runtime/
└── intent.py          # .nxintent 解析 + @implements 扫描 + check/coverage 执行

src/
├── nexa_parser.py     # @implements/@supports 注解提取
├── code_generator.py  # 注解保留为注释
├── cli.py             # intent 子命令（check/coverage）
```

---

## 7. 设计原则

1. **引擎固定，词汇可扩展** — IAL 引擎是固定的，新断言只需添加词汇条目，不需要改代码
2. **Agent-native 验证** — Nexa 的验证超越 HTTP-only，直接运行 agent 检查输出
3. **语义断言** — 利用 Nexa 已有的 semantic_if 机制做 LLM 判断
4. **互补而非替代** — IDD 与现有 `test/assert` 体系互补，不替代
5. **Glossary call 关键词** — 可调用 Nexa agent 单元测试

---

## 8. 完整示例

### 8.1 Nexa 源代码 (weather_bot.nx)

```nexa
// Weather Bot — Nexa Intent-Driven Development Demo

protocol WeatherReport {
    city: "string",
    temperature: "string",
    conditions: "string",
    forecast: "string"
}

tool WeatherAPI {
    description: "Fetch weather data for a city",
    parameters: {"city": "string"}
}

// @implements: feature.weather_bot
agent WeatherBot uses WeatherAPI implements WeatherReport {
    role: "Weather Assistant",
    model: "minimax-m2.5",
    prompt: "Provide weather information for cities. When asked about weather, include temperature, conditions, and forecast."
}

flow main {
    result = WeatherBot.run("What is the weather in Beijing?");
    print(result);
}
```

### 8.2 Intent 文件 (weather_bot.nxintent)

```yaml
## Glossary

| Term | Means |
|------|-------|
| a user asks {question} | agent run with input {question} |
| the agent responds with {text} | output contains {text} |
| the response is valid | protocol check passes |
| clarification response | output is about clarification or asking for more details |
| weather information | output mentions weather, temperature, conditions or forecast |

---

Feature: Weather Bot
  id: feature.weather_bot
  description: "Weather information agent"

  Scenario: Weather query
    When a user asks "What is the weather in Beijing?"
    → the agent responds with "weather"
    → the response is valid

  Scenario: Invalid query handling
    When a user asks "xyzzy"
    → the agent responds with "clarification"
```

### 8.3 执行验证

```bash
$ nexa intent check examples/intent_demo/weather_bot.nx

$ nexa intent coverage examples/intent_demo/weather_bot.nx