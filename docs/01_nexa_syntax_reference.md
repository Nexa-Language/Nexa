# Nexa 语法参考手册 (v1.1)

本手册涵盖了 Nexa 语言从基础语法到 v1.1 引入的全部高级特性，包括智能体声明、路由协作、语义分支、测试断言、MCP 扩展、传统控制流以及 Intent-Driven Development (意图驱动开发)。所有符合本手册规范的代码皆可由 Nexa Compiler 直接转译并在 Nexa Runtime 中执行。

## 🆕 v1.1 新特性

本版本新增以下核心特性：

1. **传统控制流** - 确定性的 if/else if/else、for each、while、break、continue
2. **Python 逃生舱** - 使用 `python! """..."""` 直接嵌入 Python 代码
3. **二元运算符扩展** - 支持 +、-、*、/、% 算术运算
4. **比较运算符** - 支持 ==、!=、<、>、<=、>= 比较运算
5. **Intent-Driven Development (IDD)** - `@implements`/`@supports` 注解 + `.nxintent` 文件 + IAL 引擎

## 1. 核心层级结构 (Core Hierarchy)

Nexa 采用极简的顶层声明系统。核心一等公民包括 `agent`, `tool`, `protocol`, `flow`, `test`。

### 1.1 工具声明 (`tool`)

用于挂载外部执行能力。支持绑定本地 Python 模块，并在 v0.9-alpha 中支持 MCP (Model Context Protocol)。

```nexa
// 绑定本地工具
tool Calculator {
    description: "Perform basic math operations",
    parameters: {"expression": "string"}
}

// v0.9 绑定 MCP 工具
tool SearchMCP {
    mcp: "github.com/nexa-ai/search-mcp"
}
```

### 1.2 协议声明 (`protocol`)

基于强制类型的输出约束，在底层被转译为 Pydantic Schema。

```nexa
protocol AnalysisReport {
    title: "string",
    sentiment: "string",
    confidence: "number"
}
```

### 1.3 智能体声明 (`agent`)

定义语言模型实例及其附带的工具或协议。支持模型路由与系统指令。

```nexa
@limit(max_tokens=2048)
agent FinancialAnalyst implements AnalysisReport uses Calculator, SearchMCP {
    role: "Senior Financial Advisor",
    model: "claude-3.5-sonnet",
    prompt: "Analyze financial data and output standard reports."
}
```

## 2. 编排与控制流 (Choreography & Control Flow)

### 2.1 主流程 (`flow`)

控制调度的中心单元。支持类似 Unix 管道的语法符。

```nexa
flow main {
    raw_data = SearchMCP.run("AAPL Q3 index");
    // 管道组合符 >> 将前面的输出传递给后一节点
    summary = raw_data >> FinancialAnalyst >> Formatter;
    print(summary);
}
```

### 2.2 意图路由 (`match intent`)

依据自然语言使用底层文本大模型进行分发。

```nexa
match user_req {
    intent("查询天气") => WeatherBot.run(user_req),
    intent("查询股市") => StockBot.run(user_req),
    _ => SmallTalkBot.run(user_req)
}
```

### 2.3 语义分支 (`semantic_if` & `fast_match`)

允许在传统布尔逻辑之外，针对非结构化文本进行语义条件判断。v0.9 引入了基于正则前置过滤的快速匹配，避免重复消耗 Token。

```nexa
semantic_if "包含具体的日期和地点" fast_match r"\\d{4}-\\d{2}-\\d{2}" against user_input {
    schedule_tool.run(user_input);
} else {
    print("需要进一步澄清");
}
```

### 2.4 语义级循环 (`loop until`)

条件终止支持自然语言求值机制。

```nexa
loop {
    draft = Editor.run(feedback);
    feedback = Critic.run(draft);
} until ("Article is engaging and grammatically perfect")
```

## 3. 测试与断言 (Testing Framework)

在 v0.9-alpha 引入的原生测试与调试支持。可通过 `nexa test` 调用。

```nexa
test "financial_analysis_basic_pipeline" {
    mock_input = "Tesla revenue 2023";
    result = FinancialAnalyst.run(mock_input);
    
    // 断言结果符合特定语义预期
    assert "包含具体的马斯克管理评价" against result;
}
```

## 4. 完整的 EBNF 语法定义归档

```ebnf
program ::= script_stmt*
script_stmt ::= tool_decl | protocol_decl | agent_decl | flow_decl | test_decl

tool_decl ::= "tool" IDENTIFIER "{" tool_body "}"
tool_body ::= ("description:" STRING_LITERAL "," "parameters:" json_object) | ("mcp:" STRING_LITERAL)

protocol_decl ::= "protocol" IDENTIFIER "{" (IDENTIFIER ":" STRING_LITERAL)+ "}"

agent_modifier ::= "@" IDENTIFIER "(" IDENTIFIER "=" NUMBER ")"
agent_decl ::= [agent_modifier] "agent" IDENTIFIER ["implements" IDENTIFIER] ["uses" identifier_list] "{" agent_body "}"
agent_body ::= (IDENTIFIER ":" STRING_LITERAL)+

flow_decl ::= "flow" IDENTIFIER "{" flow_stmt* "}"
test_decl ::= "test" STRING_LITERAL "{" flow_stmt* "}"

flow_stmt ::= assignment_stmt | expr_stmt | semantic_if_stmt | loop_stmt | match_stmt | assert_stmt | try_catch_stmt

assignment_stmt ::= IDENTIFIER "=" expression ";"
expr_stmt ::= expression ";"
assert_stmt ::= "assert" STRING_LITERAL "against" IDENTIFIER ";"
try_catch_stmt ::= "try" block "catch" "(" IDENTIFIER ")" block

semantic_if_stmt ::= "semantic_if" STRING_LITERAL ["fast_match" REGEX_LITERAL] "against" IDENTIFIER "{" flow_stmt* "}" ("else" "{" flow_stmt* "}")?
loop_stmt ::= "loop" "{" flow_stmt* "}" "until" "(" STRING_LITERAL ")"
match_stmt ::= "match" IDENTIFIER "{" match_branch+ ("_" "=>" expression)? "}"
match_branch ::= "intent" "(" STRING_LITERAL ")" "=>" expression ","

expression ::= dag_expr | pipeline_expr | fallback_expr | base_expr

# DAG 表达式 (v0.9.7+)
dag_expr ::= dag_fork_expr | dag_merge_expr | dag_branch_expr
dag_fork_expr ::= base_expr ("|>>" | "||") "[" identifier_list "]"
dag_merge_expr ::= "[" identifier_list "]" ("&>>" | "&&") base_expr
dag_branch_expr ::= base_expr "??" base_expr ":" base_expr

pipeline_expr ::= base_expr (">>" base_expr)+
fallback_expr ::= base_expr "fallback" expression

base_expr ::= join_call | method_call | STRING_LITERAL | IDENTIFIER

join_call ::= "join" "(" identifier_list ")" ["." IDENTIFIER "(" argument_list ")"]
method_call ::= IDENTIFIER ("." IDENTIFIER)? "(" (argument_list)? ")"
argument_list ::= expression ("," expression)*

IDENTIFIER ::= [a-zA-Z_][a-zA-Z0-9_]*
STRING_LITERAL ::= '"' [^"]* '"'
REGEX_LITERAL ::= 'r"' [^"]* '"'
```

## 5. DAG 操作符 (v0.9.7+)

Nexa v0.9.7 引入了用于复杂拓扑编排的 DAG 操作符。

### 5.1 分叉操作符 (`|>>` 和 `||`)

将输入并行发送到多个 Agent：

```nexa
// |>> 等待所有结果返回
results = input |>> [Agent1, Agent2, Agent3];

// || 不等待（fire-and-forget）
input || [Logger, Analytics];
```

### 5.2 合流操作符 (`&>>` 和 `&&`)

将多个结果合并：

```nexa
// &>> 顺序合流
result = [Researcher, Analyst] &>> Reviewer;

// && 共识合流（需要 Agent 达成一致）
consensus = [Agent1, Agent2] && JudgeAgent;
```

### 5.3 条件分支操作符 (`??`)

根据条件选择执行路径：

```nexa
// 根据输入特征选择处理 Agent
result = input ?? UrgentHandler : NormalHandler;
```

### 5.4 复杂 DAG 拓扑

组合使用操作符构建复杂流程：

```nexa
// 分叉后合流
final = topic |>> [Researcher, Analyst] &>> Writer >> Reviewer;

// 多阶段并行处理
report = data |>> [Preprocess1, Preprocess2] &>> Aggregator >> Formatter;
```

## 6. 传统控制流 (v1.0.1-beta)

v1.0.1-beta 引入了确定性传统控制流，与语义控制流（semantic_if、loop...until）明确区分。

### 6.1 传统 if/else if/else 语句

使用确定性比较运算符进行条件判断：

```nexa
// 基本语法
if (condition) {
    // then block
} else if (another_condition) {
    // else if block
} else {
    // else block
}

// 示例：分数等级判断
score = 85;

if (score >= 90) {
    result = "优秀";
} else if (score >= 80) {
    result = "良好";
} else if (score >= 60) {
    result = "及格";
} else {
    result = "不及格";
}
```

**比较运算符**：
| 运算符 | 含义 |
|--------|------|
| `==` | 等于 |
| `!=` | 不等于 |
| `<` | 小于 |
| `>` | 大于 |
| `<=` | 小于等于 |
| `>=` | 大于等于 |

**逻辑运算符**：
- `and` - 逻辑与
- `or` - 逻辑或

### 6.2 for each 循环

遍历集合或数组：

```nexa
// 基本语法
for each item in collection {
    // 处理 item
}

// 带索引遍历
for each index, item in collection {
    // 使用 index 和 item
}

// 示例
for each item in data_list {
    processed = DataProcessor.run(item);
    print(processed);
}
```

### 6.3 while 循环

基于条件的循环：

```nexa
// 基本语法
while (condition) {
    // 循环体
}

// 示例
counter = 0;
while (counter < 5) {
    print(counter);
    counter = counter + 1;
}
```

### 6.4 break 和 continue

循环控制语句：

```nexa
// break - 立即终止循环
while (counter < 10) {
    if (counter == 5) {
        break;  // 当 counter == 5 时退出循环
    }
    counter = counter + 1;
}

// continue - 跳过当前迭代
for each num in numbers {
    if (num % 2 == 0) {
        continue;  // 跳过偶数
    }
    print(num);  // 只打印奇数
}
```

### 6.5 二元运算符

v1.0.1-beta 支持基本算术运算：

| 运算符 | 含义 | 示例 |
|--------|------|------|
| `+` | 加法 | `x + y` |
| `-` | 减法 | `x - y` |
| `*` | 乘法 | `x * y` |
| `/` | 除法 | `x / y` |
| `%` | 取模 | `x % y` |

```nexa
count = count + 1;
average = total / count;
remainder = num % 2;
```

### 6.6 与语义控制流的区别

| 特性 | 传统控制流 | 语义控制流 |
|------|-----------|-----------|
| 条件判断 | 确定性比较 | LLM 语义判断 |
| 语法 | `if (x > 5)` | `semantic_if "条件" against var` |
| 循环终止 | `while (x < 10)` | `loop...until(语义条件)` |
| 执行确定性 | 完全确定 | 依赖 LLM 输出 |

## 7. Python 逃生舱 (v1.0.1-beta)

当需要直接使用 Python 功能时，可以使用 `python!` 关键字嵌入原生 Python 代码。

### 7.1 基本语法

```nexa
python! """
# Python 代码
import math
result = math.sqrt(16)
print(result)
"""
```

### 7.2 使用场景

1. **复杂算法实现**：
```nexa
python! """
import math

def calculate_statistics(data):
    n = len(data)
    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / n
    return mean, math.sqrt(variance)

data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
mean, std = calculate_statistics(data)
print(f"Mean: {mean}, Std: {std}")
"""
```

2. **第三方库调用**：
```nexa
python! """
import os
import json

# 文件操作
files = os.listdir('.')
config = {"files": files}
print(json.dumps(config, indent=2))
"""
```

3. **性能关键代码**：
```nexa
python! """
# 快速数据处理
data = list(range(1000000))
filtered = [x for x in data if x % 2 == 0]
print(f"Filtered {len(filtered)} even numbers")
"""
```

### 7.3 安全设计

Python 逃生舱使用 `python!` 关键字和三引号定界符，避免了：
- Markdown 代码块冲突（不使用 ```）
- 大括号嵌套问题（不使用 {}）
- 清晰的边界标识

## 8. Intent-Driven Development (IDD) (v1.1)

Nexa 的 IDD 系统让需求文档变成可执行测试，形成"需求→实现→验证"的闭环。这是从 NTNT 语言学习的灵魂特性，融合了 Agent-native 验证，超越 NTNT 的 HTTP-only 模式。

### 8.1 @implements 注解

在 Nexa 源代码中使用 `@implements` 注解将 agent 链接到 intent feature：

```nexa
// @implements: feature.weather_bot
agent WeatherBot uses WeatherAPI implements WeatherReport {
    role: "Weather Assistant",
    prompt: "Provide weather information"
}
```

也支持 `@supports` 注解链接约束：

```nexa
// @supports: constraint.output_format
agent Formatter {
    role: "Format output"
}
```

### 8.2 .nxintent 文件

`.nxintent` 文件定义 Feature、Scenario 和 Glossary，描述期望行为：

```yaml
## Glossary

| Term | Means |
|------|-------|
| a user asks {question} | agent run with input {question} |
| the agent responds with {text} | output contains {text} |
| the response is valid | protocol check passes |

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

**术语类型**：
- **模式术语**：含 `{param}` 占位符，如 `they see {text}`
- **精确术语**：无占位符，如 `the response is valid`
- **展开术语**：映射到多个断言，如 `success response → ["status 2xx", "body contains 'ok'"]`

### 8.3 IAL 引擎

IAL (Intent Assertion Language) 是术语重写引擎，将自然语言断言递归解析为可执行测试：

```
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

### 8.4 CLI 命令

```bash
# 验证代码是否符合 intent
nexa intent-check weather_bot.nx

# 显示特性覆盖率
nexa intent-coverage weather_bot.nx

# 指定 intent 文件路径
nexa intent-check weather_bot.nx --intent weather_bot.nxintent

# 详细输出
nexa intent-check weather_bot.nx --verbose
```

### 8.5 Intent 声明语法

```nexa
// 声明意图
intent Bot shall "respond politely to user questions"

// 声明约束
intent Bot shall not "generate harmful content"

// 声明偏好
intent Bot prefers "concise responses over verbose ones"
```

**关键能力**：
- Intent 覆盖率测量：代码路径被 intents 覆盖的百分比
- Intent 验证：运行时检查 intent 满足情况
- 模糊 Intent 匹配：部分 intent 规范的近似匹配解析
