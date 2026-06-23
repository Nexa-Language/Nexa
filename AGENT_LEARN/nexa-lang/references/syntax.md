# Nexa Syntax Reference

## Declaration Types

Nexa has five core declaration types at the top level. Each `.nx` file is a
sequence of zero or more declarations plus optionally one or more `flow`
blocks.

### `agent` — LLM Agent Declaration

```nexa
agent AgentName {
    prompt: "..."
    model: "model-name"         // optional; default from secrets.nxs
}
```

With tools (v1.x legacy syntax, use @tool for v2.0+):

```nexa
agent Accountant uses calculate_tax, AuditLog {
    prompt: "You are an expert accountant."
}
```

With Harness lifecycle hooks (v2.0):

```nexa
agent MyAgent {
    prompt: "You are a helpful assistant."
    model: "glm-5"
    after_step: "Verify the output is concise and accurate."
    reflect: "Review the conversation and improve future responses."
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | System prompt for the LLM |
| `model` | string | No | Model name, resolved via secrets.nxs MODEL_NAME |
| `role` | string | No | Legacy role description (deprecated, use prompt) |
| `after_step` | string | No | (v2.0 L-dimension) Instruction injected after each step |
| `reflect` | string | No | (v2.0 L-dimension) Self-reflection instruction |

### `@tool fn` — Function-Tool Declaration (v2.0)

```nexa
@tool("Description of what this tool does")
fn tool_name(param1: type1, param2: type2): return_type {
    python! """
# Python implementation
"""
}
```

The `@tool("description")` annotation compiles to:
1. An OpenAI function calling JSON schema
2. A Python function registered in `LOCAL_TOOLS`

Parameter types are Nexa type names: `string`, `number`, `boolean`.

**Requirements:**
- Must have a return type (`: string` or other)
- Must contain exactly one `python! """..."""` block as the body
- The function name is used as the tool name in the LLM API

### `tool` — Legacy Tool Declaration (v1.x)

```nexa
tool ToolName {
    description: "What this tool does"
    parameters: {"param1": "string", "param2": "number"}
}
```

With MCP binding:

```nexa
tool SearchMCP {
    mcp: "github.com/nexa-ai/search-mcp"
}
```

### `protocol` — Output Schema Declaration

```nexa
protocol Report {
    title: "string",
    sentiment: "string",
    confidence: "number"
}
```

Compiles to a Pydantic model. Agents can `implement` protocols:

```nexa
agent Analyst implements Report {
    prompt: "Output structured analysis."
}
```

### `flow` — Execution Flow

The `flow` block is where orchestration happens. It's the equivalent of a
`main()` function.

```nexa
flow main {
    // sequential execution
    step1 = Agent1.run("prompt");
    step2 = Agent2.run(step1);
    print(step2);
}
```

**Naming:** The entry point must be `flow main`. Additional flows can have
arbitrary names and be called from `main`.

## Agent Invocation

### `.run(prompt)` — Invoke an Agent

```nexa
result = AgentName.run("your prompt text");
```

The prompt can be a string literal or a variable:

```nexa
query = input("Enter question: ");
answer = Bot.run(query);
```

### Pipeline Operator `>>`

Chains the output of one agent/tool as input to the next:

```nexa
final = raw_data >> Analyst >> Formatter >> Publisher;
```

Equivalent to:

```nexa
step1 = Analyst.run(raw_data);
step2 = Formatter.run(step1);
final = Publisher.run(step2);
```

## Semantic Control Flow

### `semantic_if`

Evaluates a natural language condition using a judge LLM:

```nexa
semantic_if "natural language condition" against variable {
    // true branch
} else {
    // false branch
}
```

The `else` branch is optional. Nested `semantic_if` is supported.

**How it works:** A small judge LLM evaluates the condition against the
variable's content. The result is a boolean. The runtime uses exponential
backoff retry for robustness.

### `match intent`

Routes user input to agents based on semantic matching:

```nexa
match intent user_input {
    "financial analysis" => FinanceAgent;
    "code review" => CodeReviewAgent;
    "weather forecast" => WeatherAgent;
    default => GeneralAgent;
}
```

The `default` arm is required. Each arm's label is a natural language
description that is semantically matched against the input.

## Deterministic Control Flow (v1.3+)

### `if` / `else if` / `else`

Standard conditional branching with deterministic expressions:

```nexa
if (count > 10) {
    result = LargeBatchAgent.run(data);
} else if (count > 0) {
    result = SmallBatchAgent.run(data);
} else {
    print("No data to process.");
}
```

Supported comparison operators: `==`, `!=`, `<`, `>`, `<=`, `>=`.
Supported arithmetic: `+`, `-`, `*`, `/`, `%`.

### `for each`

```nexa
for each item in items {
    result = Processor.run(item);
}
```

### `while`

```nexa
while (retry_count < 3) {
    result = Agent.run(query);
    if (result != "") { break; }
    retry_count = retry_count + 1;
}
```

## Python Escape Hatch

### `python! """..."""` Block

Embeds arbitrary Python code. The block is inserted verbatim into the generated
output with the caller's indentation.

```nexa
fn compute_score(a: number, b: number): number {
    python! """
import math
return math.sqrt(a * a + b * b)
"""
}
```

**Nexa type mapping to Python:**
| Nexa type | Python type |
|-----------|-------------|
| `string` | `str` |
| `number` | `float` |
| `boolean` | `bool` |

### `print(...)` and `input(...)`

Built-in functions that compile to Python's `print()` and `input()`:

```nexa
print("Hello, " + name);
user_input = input("Enter: ");
```

### `exit(code)`

```nexa
exit(0);  // successful exit
exit(1);  // error exit
```

## v2.0 Harness Primitives

### `autoloop` — E-dimension

```nexa
autoloop max_steps: N, exit_when: "condition", timeout: T {
    // loop body
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `max_steps` | number | Yes | Maximum iterations |
| `exit_when` | string | No | Natural language exit condition |
| `timeout` | number | No | Timeout in seconds |

### `with_context` — C-dimension

```nexa
with_context max_tokens: N, strategy: sliding_window {
    // scoped block
}
```

Manages the conversation token budget using a sliding window strategy.

### `snapshot` / `restore` — S-dimension

```nexa
snap = snapshot();        // save current state
// ... risky operations ...
restore(snap);            // rollback to saved state
```

### `try_agent` / `catch_correction` — E+L-dimension

```nexa
try_agent {
    result = Agent.run(task);
} catch_correction(e: ToolError) {
    reflect "Error: tool failed. Retry with fallback.";
}
```

Catchable error types: `ToolError`, `ModelError`, `TimeoutError`.

### `verify` — V-dimension

```nexa
verify expression satisfies type;
// or with natural language condition:
verify expression satisfies "property description";
```

### `reflect` — L-dimension

```nexa
reflect "Analyze the conversation and suggest improvements.";
```

### `fork` / `merge` — Actor dimension

```nexa
// Branch into parallel execution paths
fork {
    result_a = AgentA.run(task);
} and {
    result_b = AgentB.run(task);
}

// Merge results
final = merge(result_a, result_b);
```

## Module System

### `include`

Includes another `.nx` file's declarations into the current compilation unit:

```nexa
include "tools.nx";
include "agents/analyzer.nx";
include "secrets.nxs";      // .nxs files are skipped by compiler
```

**Rules:**
- Paths are relative to the including file's directory.
- `.nxs` files are silently skipped (they contain secrets config, not Nexa code).
- Include order matters: declarations from included files are merged before
  the current file's declarations.
- Circular includes are not detected — avoid them.

## Secrets Configuration (`.nxs`)

`.nxs` files use a special format for API keys and model configuration:

```
config default{
    BASE_URL = "https://api.example.com/v1"
    API_KEY = "sk-..."
    MODEL_NAME = {
        "strong": "model-strong",
        "weak": "model-weak"
    }
}
```

**Important:** This is NOT standard Nexa syntax and cannot contain Nexa
declarations. The `config default{...}` block is parsed by
`src/runtime/secrets.py` using line-by-line regex matching.

## Test Declarations

```nexa
test "description of the test case" {
    result = MyAgent.run("input");
    assert result != "";
}
```

## Comment Syntax

```nexa
// Single-line comment

/*
   Multi-line comment
*/