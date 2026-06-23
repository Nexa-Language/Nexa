---
name: nexa-lang
description: >
  Write, compile, run, test, and debug Nexa programs. Nexa is the first
  Harness Native Agent Language — compile .nx scripts to Python via
  `nexa build`, then execute with full autonomous agent capabilities
  including tool calling, semantic control flow, and Harness Native
  Runtime (E,T,C,S,L,V). Use this skill when asked to create or modify
  .nx files, install Nexa, run `nexa build` or `nexa run`, declare
  agents/tools/flows, write @tool functions, use autoloop/with_context/
  snapshot/verify/reflect primitives, or build any AI agent application
  with Nexa syntax — even if the user doesn't mention Nexa by name but
  describes "building an AI agent with a DSL that compiles to Python."
  Also covers v2.2.1 Context-as-Structure (context { } block), v2.3.1
  Terminal UI (std.ui DSL), and @tool edit_file for diff-style edits.
license: AGPL-3.0
compatibility: Requires Python 3.10+, pip, git. The `nexa` CLI must be
  installed from source (pip install -e .) or pip install nexa-lang.
metadata:
  author: Nexa Core Team
  version: "2.3.1"
---

# Nexa Language — Agent Skill

## What is Nexa?

Nexa is a domain-specific language that compiles `.nx` scripts to Python. Its
three design goals:

1. **Agent-native syntax** — `agent`, `tool`, `flow`, `match intent`, and
   `semantic_if` are first-class keywords, not library wrappers.
2. **Harness Native Runtime (v2.0)** — Six-tuple H=(E,T,C,S,L,V) as language
   primitives: `autoloop`, `@tool`, `with_context`, `snapshot/restore`,
   lifecycle hooks, and `verify`.
3. **Zero-boilerplate tool calling** — `@tool fn` compiles to OpenAI function
   calling schemas + Python implementations automatically.

An `.nx` file is compiled by `nexa build` into a standalone Python file. No
Nexa runtime needed at execution time (though the Harness Runtime is imported).

## Installation

The `nexa` CLI is a Python package installed from the GitHub repository:

```bash
git clone https://github.com/Nexa-Language/Nexa.git
cd Nexa
pip install -r requirements.txt
pip install -e .
```

Verify:

```bash
nexa --version
# → nexa 2.3.1
```

The CLI binary is `nexa` (entry point: `src/cli.py`). Available subcommands:

| Command | Purpose |
|---------|---------|
| `nexa build <file.nx>` | Compile .nx → .py |
| `nexa run <file.nx>` | Build and execute immediately |
| `nexa inspect <file.nx>` | Show compiled AST or IR |
| `nexa validate <file.nx>` | Validate syntax only (no codegen) |
| `nexa lint <file.nx>` | Check for common issues |

## Core Workflow: Write → Build → Run

### Minimal Example

Create `hello.nx`:

```nexa
agent Greeter {
    prompt: "You are a friendly greeter. Respond warmly."
}

flow main {
    result = Greeter.run("Say hello in three different languages.");
    print(result);
}
```

Build and run:

```bash
nexa build hello.nx          # → hello.py
python hello.py              # execute
# or: nexa run hello.nx      # build + run in one step
```

## Nexa Syntax Essentials

### The Three Pillars

Every Nexa program consists of three declaration types:

**`agent`** — LLM-backed agent with model, prompt, and optional tools:

```nexa
agent Analyst {
    prompt: "You are a data analyst. Be precise."
    model: "deepseek-chat"        # optional; defaults from secrets.nxs
}
```

**`@tool fn`** (v2.0) — Compiles to OpenAI function calling schema:

```nexa
@tool("Search the web for information")
fn web_search(query: string): string {
    python! """
# Python code that executes when the LLM calls this tool
import requests
return requests.get(f"https://api.example.com/search?q={query}").text
"""
}
```

**`flow`** — Orchestration entry point. Every `.nx` file must have at least one
`flow main` or be included by another file that does.

```nexa
flow main {
    answer = Analyst.run("Analyze quarterly trends");
    print(answer);
}
```

### Agent Invocation

Agents are invoked with `.run(prompt)`:

```nexa
result = MyAgent.run("your prompt here");
```

The pipeline operator `>>` chains outputs:

```nexa
summary = raw_data >> Analyst >> Formatter;
```

### Semantic Control Flow

`semantic_if` uses a judge LLM to evaluate natural language conditions:

```nexa
semantic_if "The response contains harmful content" against response {
    SafetyAgent.run("Flag this content.");
} else {
    print("Content is safe.");
}
```

`match intent` routes user input to agents based on semantic matching:

```nexa
match intent user_input {
    "financial query" => FinanceAgent;
    "technical question" => TechSupportAgent;
    default => GeneralAgent;
}
```

### Traditional Control Flow (v1.3+)

Standard deterministic constructs are supported:

```nexa
if (x > 0) {
    result = Agent.run("positive case");
} else if (x == 0) {
    result = Agent.run("neutral case");
} else {
    result = Agent.run("negative case");
}

for each item in items {
    Agent.run(item);
}
```

### @tool edit_file (v2.3.1) — Diff-style file editing

```nexa
@tool("Edit a file by replacing old_text with new_text")
fn edit_file(path: string, old_text: string, new_text: string): string {
    python! """
content = open(path).read()
new_content = content.replace(old_text, new_text)
open(path, 'w').write(new_content)
return f"Edited {path}"
"""
}
```

### Python Escape Hatch

Use `python! """..."""` to embed arbitrary Python:

```nexa
fn calculate(x: number, y: number): number {
    python! """
import math
return x * math.log(y + 1)
"""
}
```

### Include Mechanism

Multi-file projects use `include`:

```nexa
include "tools.nx";
include "agent.nx";
include "flows.nx";
```

Includes are resolved relative to the source file's directory. The compiler
merges all included bodies into a single output `.py` file.

## Harness Native Runtime (v2.0)

The six-tuple H=(E,T,C,S,L,V) provides language-level primitives for
autonomous agent behavior:

| Dim | Primitive | Syntax | What it does |
|-----|-----------|--------|--------------|
| E | `autoloop` | `autoloop max_steps: N { ... }` | Autonomous execution loop |
| T | `@tool fn` | `@tool("desc") fn name(...): type { ... }` | Compile-time tool schema generation |
| C | `with_context` | `with_context max_tokens: N { ... }` | Sliding window context management |
| S | `snapshot` | `snap = snapshot(); restore(snap);` | State checkpoint and recovery |
| L | `reflect` | `reflect "string";` | Introspective self-correction |
| V | `verify` | `verify expr satisfies type;` | Compile + runtime output validation |

See [`references/harness.md`](references/harness.md) for full API and
configuration options for each dimension.

### Minimal Harness Example

```nexa
flow harness_example {
    autoloop max_steps: 10, exit_when: "task complete", timeout: 300 {
        with_context max_tokens: 50000, strategy: sliding_window {
            snap = snapshot();
            try_agent {
                result = MyAgent.run("Do the task");
            } catch_correction(e: ToolError) {
                reflect "Error occurred. Retrying with different approach.";
            }
            verify result satisfies string;
        }
    }
}
```

## v2.2.1: Context-as-Structure

Agent declarations can include a `context { }` block that defines context
behavior (source, sink, input_schema, output_schema, inherit):

```nexa
agent Researcher {
    model: "deepseek-chat"
    context {
        source: upstream
        sink: downstream
        output_schema: ResearchOutput
        inherit: [messages, artifacts]
    }
    prompt: "..."
}
```

The Harness Validator checks pipeline compatibility (C-004 rule): if
`A >> B` and A's output_schema ≠ B's input_schema, compilation fails.

## v2.3.1: Terminal UI (std.ui DSL)

Rich-based terminal rendering with markdown, syntax highlighting, and
spinner animations:

```nexa
flow main {
    std.ui.banner("My App");
    std.ui.markdown("# Hello\n\nThis is **bold**.");
    std.ui.thinking("Analyzing...", 1.0);
    std.ui.agent_reply("Agent", "Reply as **markdown**");
}
```

Requires `pip install rich prompt_toolkit`.

## Common Patterns

### Pattern: Weather Bot (tool + agent + flow)

```nexa
@tool("Get current weather for a city")
fn get_weather(city: string): string {
    python! """
# In production, call a real weather API
data = {"Beijing": "Sunny, 25°C", "Shanghai": "Cloudy, 22°C"}
return data.get(city, f"No data for {city}")
"""
}

agent WeatherBot {
    prompt: "You are a weather assistant. Use the get_weather tool to answer."
    model: "deepseek-chat"
}

flow main {
    city = input("Enter city: ");
    report = WeatherBot.run(f"What is the weather in {city}?");
    print(report);
}
```

### Pattern: Multi-Agent Pipeline

```nexa
agent Researcher { prompt: "Research the topic thoroughly." }
agent Writer { prompt: "Write a clear, concise article based on research." }
agent Editor { prompt: "Edit for clarity, grammar, and style." }

flow main {
    topic = "quantum computing basics";
    research = Researcher.run(topic);
    draft = research >> Writer;
    final = draft >> Editor;
    print(final);
}
```

For detailed patterns and anti-patterns, see
[`references/patterns.md`](references/patterns.md).

## Gotchas

- **`.nx` vs `.nxs`**: `.nx` files are Nexa source code. `.nxs` files use a
  different format (`config default{...}`) for secrets/API keys. The compiler
  skips `.nxs` files in `include` processing — they are handled at runtime by
  `src/runtime/secrets.py`. Never write Nexa syntax in a `.nxs` file.

- **`@tool fn` must have a return type**: The compiler emits a warning if a
  `@tool fn` lacks an explicit return type. Always add `: string` or the
  appropriate type.

- **`python!` blocks use the caller's indent**: The Python code inside
  `python! """..."""` is embedded as-is. Any `import` statements inside
  are re-executed on each call — put expensive imports at module level.

- **`include` paths are relative to the source file**: When `main.nx` does
  `include "tools.nx"`, the path is resolved relative to `main.nx`'s directory.

- **`nexa build` vs `nexa run`**: `build` only compiles; `run` compiles then
  executes. For CI testing, use `build` and run the generated `.py` separately.

- **Agent names are case-sensitive**: `MyAgent` and `myAgent` are different.
  Follow PascalCase convention.

- **`flow main` is the entry point**: If no `flow main` exists, the generated
  `.py` has no `if __name__ == "__main__"` block. It can still be imported.

- **`secrets.nxs` format**: Uses `config default{ KEY = "value" }` syntax.
  This is NOT standard Nexa syntax — it's parsed by `src/runtime/secrets.py`
  using a simple line-by-line parser. Do not add comments with `//` inside
  the config block (the parser doesn't strip them).

- **LLM model resolution**: The `model: "glm-5"` field in an agent declaration
  is resolved through `secrets.nxs`'s `MODEL_NAME` mapping. If the model name
  isn't in the mapping, the runtime falls back to the raw string.

## Workflow Checklists

### Writing a New .nx File

Progress:
- [ ] Step 1: Identify the agents needed (names, prompts, models, tools)
- [ ] Step 2: Declare `@tool fn` for any external capabilities (API calls, file I/O, shell)
- [ ] Step 3: Declare `agent` blocks with prompts and tool bindings
- [ ] Step 4: Write `flow main` as the orchestration entry point
- [ ] Step 5: Add Harness primitives (autoloop, with_context, verify) for robustness
- [ ] Step 6: Run `nexa build <file.nx>` and fix any compilation errors
- [ ] Step 7: Run `python <file.py>` to test

### Debugging a Compilation Error

Progress:
- [ ] Step 1: Read the error message — it includes line number and expected tokens
- [ ] Step 2: Check the specific line for syntax issues (missing semicolons, braces, keywords)
- [ ] Step 3: Run `nexa validate <file.nx>` for a syntax-only check (faster than full build)
- [ ] Step 4: If the error mentions "include", verify the included file exists and parses
- [ ] Step 5: For `python!` block errors, check the Python code independently
- [ ] Step 6: Rebuild after each fix — do not batch fixes

### Building an Autonomous Agent (ReAct Loop)

Progress:
- [ ] Step 1: Define tools as `@tool fn` with descriptions the LLM can understand
- [ ] Step 2: Create an agent that references those tools in its prompt
- [ ] Step 3: Wrap the call in `autoloop` (E-dimension) with a max_steps limit
- [ ] Step 4: Add `with_context` (C-dimension) to manage token budget
- [ ] Step 5: Add `snapshot/restore` (S-dimension) for error recovery
- [ ] Step 6: Add `verify` (V-dimension) to validate outputs
- [ ] Step 7: Test with a simple task before scaling up

## Testing

Nexa uses `pytest` for its test suite. To run tests:

```bash
# All tests
python -m pytest tests/ -x -q

# Specific test file
python -m pytest tests/test_integration.py -x -q

# Harness-specific tests
python -m pytest tests/test_harness_validator.py tests/test_execution_engine.py
```

To test a compiled `.nx` file, run it as a Python script and check the output:

```bash
nexa build my_agent.nx
python my_agent.py 2>&1 | grep "expected output pattern"
```

## Reference Files

Load these on demand when more detail is needed:

| File | When to load |
|------|-------------|
| [`references/syntax.md`](references/syntax.md) | Full syntax reference for all constructs |
| [`references/harness.md`](references/harness.md) | Complete Harness API with all configuration options |
| [`references/patterns.md`](references/patterns.md) | Proven patterns and anti-patterns with examples |
| [`references/v2.1-agent-properties.md`](references/v2.1-agent-properties.md) | v2.1 new agent properties (stream, output_format, output_schema, max_tool_calls, tool_call_strategy) |
| [`references/troubleshooting.md`](references/troubleshooting.md) | Common error messages, causes, and fixes |

## Scripts

- [`scripts/validate-nexa.sh`](scripts/validate-nexa.sh) — Quick validation:
  checks that `nexa` CLI is installed, Python version is 3.10+, and compiles
  a test `.nx` file to verify the toolchain works end-to-end.

## Assets

- [`assets/template.nx`](assets/template.nx) — Minimal Nexa project template
  with one tool, one agent, and one flow. Copy and customize.