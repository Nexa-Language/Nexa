# Nexa 语法参考手册 (v0.9-alpha)

本手册涵盖了 Nexa 语言从基础语法到 v0.9-alpha 引入的全部高级特性，包括智能体声明、路由协作、语义分支、测试断言及 MCP 扩展。所有符合本手册规范的代码皆可由 Nexa Compiler 直接转译并在 Nexa Runtime 中执行。

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

flow_stmt ::= assignment_stmt | expr_stmt | semantic_if_stmt | loop_stmt | match_stmt | assert_stmt

assignment_stmt ::= IDENTIFIER "=" expression ";"
expr_stmt ::= expression ";"
assert_stmt ::= "assert" STRING_LITERAL "against" IDENTIFIER ";"

semantic_if_stmt ::= "semantic_if" STRING_LITERAL ["fast_match" REGEX_LITERAL] "against" IDENTIFIER "{" flow_stmt* "}" ("else" "{" flow_stmt* "}")?
loop_stmt ::= "loop" "{" flow_stmt* "}" "until" "(" STRING_LITERAL ")"
match_stmt ::= "match" IDENTIFIER "{" match_branch+ ("_" "=>" expression)? "}"
match_branch ::= "intent" "(" STRING_LITERAL ")" "=>" expression ","

expression ::= pipeline_expr
pipeline_expr ::= base_expr (">>" IDENTIFIER)*
base_expr ::= method_call | STRING_LITERAL | IDENTIFIER

method_call ::= IDENTIFIER "." IDENTIFIER "(" (argument_list)? ")"
argument_list ::= expression ("," expression)*

IDENTIFIER ::= [a-zA-Z_][a-zA-Z0-9_]*
STRING_LITERAL ::= '"' [^"]* '"'
REGEX_LITERAL ::= 'r"' [^"]* '"'
```
