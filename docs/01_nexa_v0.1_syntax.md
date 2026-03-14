# Nexa v0.1 MVP 语法规范 (内部审计修订版)

## 1. 设计哲学：极简与务实 (Think Big, Start Small)
在 v0.1 (MVP) 阶段，Nexa 语言作为一门 **智能体原生 (Agent-Native)** 的编程语言，将放弃复杂的面向对象或函数式抽象，仅围绕 AI 应用的本质进行建模。我们追求语法的严谨性与确定性，确保每个语言构造都能无缝转译为当前成熟的 Python SDK 代码。

## 2. 核心一等公民 (First-Class Citizens)

Nexa 仅定义 3 个核心关键字来组织代码结构：

1. **`tool` (工具挂载):** 定义智能体可以调用的外部能力。在 v0.1 中，直接映射到 Python 函数与 JSON Schema。
2. **`agent` (智能体声明):** 声明一个独立的大模型实例的上下文与性格，并显式指定它可以访问的一组 `tool`。
3. **`flow` (执行主流程):** 编排多个 agent 和普通逻辑的控制流，代表程序的具体执行过程。

## 3. 原生语义分支：`semantic_if`

传统编程的 `if (a > b)` 无法处理自然语言的模糊判断。Nexa 提供原生的 `semantic_if`，实现在非结构化文本上的“条件逻辑分支”。

### 语法示例
```nexa
semantic_if "包含具体的日期和地点" against user_input {
    // 满足条件时执行
} else {
    // 不满足条件时执行
}
```

### 底层实现机制 (Transpiler 映射与防幻觉)
在转译为 Python 脚本时，编译器会利用大模型的 **Structured Outputs (严格 JSON Schema)**。
此外，为了保证工业级健壮性（API 请求超时、返回无效 JSON、格式解析错误），Nexa 转译器会自动在生成的 `__nexa_semantic_eval` 辅助函数中注入**重试 (Retry) 和降级 (Fallback) 机制**。在达到最大重试次数后，默认会降级（例如配置为 `False`，使得流程可控）。

## 4. EBNF 极简语法定义 (严格工程版)

为了消除分号冲突、表达式与语句混淆，以及处理变量传递，下述 EBNF 区分了 Statement 和 Expression，并清晰定义了字面量结构。

```ebnf
program ::= script_stmt*

script_stmt ::= tool_decl | agent_decl | flow_decl

// === Tool ===
tool_decl ::= "tool" IDENTIFIER "{" tool_body "}"
tool_body ::= "description:" STRING_LITERAL "," "parameters:" json_object
json_object ::= "{" (json_pair ("," json_pair)*)? "}"
json_pair ::= STRING_LITERAL ":" STRING_LITERAL

// === Agent ===
agent_decl ::= "agent" IDENTIFIER ("uses" identifier_list)? "{" agent_body "}"
identifier_list ::= IDENTIFIER ("," IDENTIFIER)*
agent_body ::= "prompt:" STRING_LITERAL

// === Flow & Statements ===
flow_decl ::= "flow" IDENTIFIER "{" flow_stmt* "}"

flow_stmt ::= assignment_stmt | expr_stmt | semantic_if_stmt

assignment_stmt ::= IDENTIFIER "=" expression ";"
expr_stmt ::= expression ";"

semantic_if_stmt ::= "semantic_if" STRING_LITERAL "against" IDENTIFIER "{" flow_stmt* "}" ("else" "{" flow_stmt* "}")?

// === Expressions ===
expression ::= method_call | STRING_LITERAL | IDENTIFIER

method_call ::= IDENTIFIER "." IDENTIFIER "(" (argument_list)? ")"
argument_list ::= expression ("," expression)*

// === Lexical Tokens ===
IDENTIFIER ::= [a-zA-Z_][a-zA-Z0-9_]*
STRING_LITERAL ::= '"' [^"]* '"'
// 单行注释忽略: // .*
// 多行注释忽略: /* .*? */
```
说明：
- 修复了此前嵌套调用的歧义。
- 引入了 `expression` 规则，使得方法调用的参数可以混用 `STRING_LITERAL`（硬编码字符串）和 `IDENTIFIER`（变量引用）。
- 明确了 `parameters` 为基础键值对映射，便于轻量级解析。
