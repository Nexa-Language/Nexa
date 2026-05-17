# Nexa Code — Harness Native AI Programming Assistant

**The first interactive AI coding assistant written in Nexa syntax**, compiled via `nexa build`, and executed as generated Python with autonomous tool use.

## Architecture

Nexa Code is structured as a multi-module Nexa project using `include`:

```
Nexa-Code/
  main.nx          ← Entry point: includes all modules + secrets
  tools.nx         ← @tool fn definitions (T-dimension)
  agent.nx         ← CodeAssistant agent definition
  flows.nx         ← REPL and oneshot flows (E, C, V dimensions)
  secrets.nxs      ← API configuration (not tracked in git)
  README.md        ← This file
  docs/
    architecture.md ← Architecture deep-dive
    usage.md        ← Usage guide
```

## Harness Dimensions

| Dimension | Primitive | Usage |
|-----------|-----------|-------|
| **E** (Execution) | `autoloop` | Interactive REPL loop |
| **T** (Tool) | `@tool fn` | 5 file/shell tools → OpenAI function calling |
| **C** (Context) | `with_context` | Conversation token management |
| **V** (Verify) | `verify ... satisfies` | Output quality check |

## Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with line numbers |
| `write_file` | Write content to file (auto-create dirs) |
| `search_files` | Grep pattern in code files |
| `list_directory` | List files/dirs with sizes |
| `shell_exec` | Execute shell commands (dangerous commands blocked) |

## Quick Start

### 1. Configure API

Create `secrets.nxs` in this directory:

```
config default{
    BASE_URL = "https://your-api-endpoint/v1"
    API_KEY = "your-api-key"
    MODEL_NAME = {
        "strong": "your-model-name"
    }
}
```

### 2. Build

```bash
nexa build examples/Nexa-Code/main.nx
```

### 3. Run

**Interactive REPL:**
```bash
python examples/Nexa-Code/main.py
```

**One-shot (non-interactive):**
```python
from examples.Nexa_Code import main as nexa_code
result = nexa_code.flow_nexa_code_oneshot("Read README.md and summarize it")
print(result)
```

## How It Works

The `@tool fn` declarations in `tools.nx` compile to two things:

1. **OpenAI function calling schema** — JSON schema describing each tool's name, description, and parameters
2. **Python implementation** — The `python!` block becomes the actual function body, registered in `LOCAL_TOOLS`

When the LLM decides to call a tool, the runtime:
- Receives `tool_calls` from the OpenAI API response
- Dispatches to `LOCAL_TOOLS[function_name]`
- Returns the tool result back to the LLM
- LLM generates the final answer

This is the **think → act → observe → answer** loop, powered by Nexa's Harness Runtime.

## Module Split Rationale

- **tools.nx** — Tools are reusable across different agents. Keep them separate for modularity.
- **agent.nx** — Agent definition is configuration (prompt, model). Easy to swap models or prompts.
- **flows.nx** — Flow logic (REPL, oneshot) is the orchestration layer. Independent of tools/agent.
- **main.nx** — Just includes. The "glue" that ties everything together.

This structure mirrors how real projects organize code: config, logic, orchestration, entry point.