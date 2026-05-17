# Nexa Code — Usage Guide

## Prerequisites

- Python 3.10+
- Nexa compiler (`nexa build`)

## Setup

### 1. Configure API Secrets

Create `secrets.nxs` in the `Nexa-Code/` directory:

```
config default{
    BASE_URL = "https://your-api-endpoint/v1"
    API_KEY = "your-api-key"
    MODEL_NAME = {
        "strong": "your-model-name"
    }
}
```

This file is gitignored — never commit API keys.

### 2. Build

```bash
cd /path/to/nexa
python src/cli.py build examples/Nexa-Code/main.nx
```

This compiles all included modules (tools.nx, agent.nx, flows.nx, secrets.nxs) into a single `main.py`.

### 3. Run Interactive REPL

```bash
python examples/Nexa-Code/main.py
```

```
╔════════════════════════════════════════════════╗
║          Nexa Code v2.0.0                     ║
║   The First Harness Native AI Coding Agent    ║
╚════════════════════════════════════════════════╝
Type your request, or /exit to quit.

nexa-code>
```

### REPL Commands

| Command | Description |
|---------|-------------|
| `/exit` | Exit the REPL |
| `/help` | Show available commands |
| `/clear` | Clear conversation context |
| `/tools` | List available tools |
| `/snap` | Save conversation snapshot |
| `/restore` | Restore from snapshot |

### Example Interactions

```
nexa-code> Read the VERSION file and tell me the version.
> [CodeAssistant received]: Read the VERSION file...
[CodeAssistant requested TOOL CALL]: read_file -> {"path": "VERSION"}
    [ToolRegistry] Execution result: File: VERSION | 2.0.0
< [CodeAssistant replied]: This project is version 2.0.0.

nexa-code> List all python files in src/runtime/
> [CodeAssistant requested TOOL CALL]: shell_exec -> {"command": "ls src/runtime/*.py"}
    [ToolRegistry] Execution result: agent.py, context_manager.py, ...
< [CodeAssistant replied]: There are 47 Python files in src/runtime/
```

## One-shot Mode

For scripting or CI pipelines, use the oneshot flow:

```python
import importlib.util, sys
sys.path.insert(0, '/path/to/nexa')

spec = importlib.util.spec_from_file_location(
    'nexa_code', 'examples/Nexa-Code/main.py'
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Execute a single task
result = mod.flow_nexa_code_oneshot(
    "Check if tests/test_integration.py has any failing tests"
)
print(result)
```

## Adding Custom Tools

1. Edit `tools.nx` and add a new `@tool fn`:

```nexa
@tool("Get current git status")
fn git_status(path: string): string {
    python! """
import subprocess, os
result = subprocess.run(["git", "status", "--short"],
    cwd=path, capture_output=True, text=True, timeout=10)
return result.stdout if result.stdout else "(clean)"
"""
}
```

2. Rebuild:

```bash
python src/cli.py build examples/Nexa-Code/main.nx
```

3. The new tool is automatically registered in `LOCAL_TOOLS` and included in the OpenAI function calling schemas — the LLM will discover it automatically.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full compiler pipeline, data flow, and module design.

## Limitations

- **No multi-file edit**: The agent operates on one file at a time
- **10-second grep timeout**: `search_files` has a 10s timeout
- **30-second shell timeout**: `shell_exec` has a 30s timeout
- **Dangerous command filter**: Blocks `rm -rf`, `chmod 777`, `dd`, `mkfs`

## Security

- `shell_exec` blocks dangerous commands via a pattern match filter
- `secrets.nxs` is gitignored and never committed
- API keys are loaded at runtime from `secrets.nxs`, never hardcoded