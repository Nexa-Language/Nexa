# Nexa Troubleshooting Guide

## Compilation Errors

### Error: "No terminal matches 'X' in the current parser context"

**Cause:** Syntax error — the parser encountered an unexpected token.

**Common triggers and fixes:**

| Trigger | Fix |
|---------|-----|
| `.nxs` file included as `.nx` | `.nxs` uses `config default{...}` format. Remove from include or rename to `.nx` with valid syntax. |
| Missing semicolon | Add `;` at end of statements inside `flow` blocks. |
| Unclosed braces | Check that every `{` has a matching `}`. |
| `python!` block outside a function | `python!` blocks are only valid inside `@tool fn` or `fn` bodies. |

**Debug workflow:**
1. Read the "Expected one of:" list in the error — it tells you what's valid at that position.
2. Check the line number and column in the error message.
3. Run `nexa validate <file.nx>` for a faster syntax-only check.

### Error: "Included file does not exist"

```
❌ Error: Included file 'tools.nx' does not exist at '/path/to/tools.nx'.
```

**Cause:** The `include` path is relative to the *source file's directory*, not
the current working directory.

**Fix:** Verify the path relative to the including `.nx` file. If `main.nx` is
at `project/main.nx` and does `include "tools.nx"`, then `project/tools.nx`
must exist.

### Error: "verify target not found" (V-001)

```
HarnessViolation: verify target not found
```

**Cause:** The variable in `verify X satisfies Y` is not defined in scope.

**Fix:** Ensure the variable is declared before the `verify` statement.

### Warning: "@tool fn without return type" (T-004)

```
HarnessViolation: @tool fn without return type — Agent may misinterpret output
```

**Cause:** The `@tool fn` declaration lacks a return type annotation.

**Fix:** Add `: string` (or appropriate type) to the function signature:
```nexa
@tool("description")
fn my_tool(param: string): string {  // ← add : string
```

### Warning: "Agent uses only 0 Harness dimensions" (X-002)

```
HarnessViolation: Agent uses only 0 Harness dimensions
```

**Cause:** An agent is declared without any Harness primitives in its flow.

**Fix:** This is informational. For production agents, wrap the agent call in
`autoloop` + `with_context` + `verify`. For simple one-shot agents, ignore.

---

## Runtime Errors

### Error: "ModuleNotFoundError: No module named 'src'"

**Cause:** Running the generated `.py` file from outside the Nexa project root.

**Fix:** The generated `.py` imports `from src.runtime.agent import NexaAgent`.
Run it from the Nexa project root directory, or add the project root to
`sys.path`:

```python
import sys
sys.path.insert(0, '/path/to/Nexa')
```

### Error: "API key not found" or "MODEL_NAME not configured"

**Cause:** `secrets.nxs` is missing or incorrectly formatted.

**Fix:** Ensure `secrets.nxs` exists in the same directory as the source `.nx`
file with valid `config default{...}` format:

```
config default{
    BASE_URL = "https://api.example.com/v1"
    API_KEY = "sk-..."
    MODEL_NAME = {
        "default": "your-model-name"
    }
}
```

### Error: "Tool 'X' not found"

**Cause:** The LLM requested a tool that isn't registered in `LOCAL_TOOLS`.

**Possible causes:**
1. The `@tool fn` wasn't compiled (check that the `.nx` file is included).
2. The tool function name doesn't match between `@tool fn name` and the LLM's
   tool call.
3. The `python!` block has a syntax error that prevents registration.

**Fix:** Rebuild with `nexa build --harness=warn` and check for T-003 errors.

### Error: "Type mismatch: expected string, got str"

**Cause:** Internal type checking mismatch between Nexa types and Python types.

**Fix:** This is usually harmless (a warning, not an error). It means the
runtime's type checker found `str` (Python type) when it expected `string`
(Nexa type). The Nexa compiler maps `string` → `str` correctly at codegen;
this warning can be ignored in most cases.

### Hang: Agent loop never terminates

**Cause:** `autoloop` without `exit_when` or `max_steps` too large.

**Fix:** Always set `max_steps` to a reasonable limit (10-50 for most tasks).
Add an `exit_when` condition for autonomous termination. Use `timeout` as a
safety net.

---

## Build/Packaging Errors

### Error: "pip install -e ." fails with dependency conflicts

**Cause:** System Python packages conflict with Nexa dependencies.

**Fix:** Use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Error: "nexa: command not found"

**Cause:** The `nexa` CLI wasn't installed, or the virtual environment isn't
activated.

**Fix:**
```bash
# Check if installed
pip show nexa-lang

# If not installed:
pip install -e .

# If using venv, activate it first:
source venv/bin/activate
```

---

## Design/Architecture Mistakes

### Mistake: Using `python!` for everything

**Symptom:** `.nx` files that are mostly `python!` blocks with minimal Nexa
syntax.

**Why it's wrong:** You lose the benefits of Nexa's agent-native abstractions
(semantic control flow, Harness validation, tool schema generation).

**Fix:** Use `python!` only for I/O, external API calls, and computation that
can't be expressed in Nexa. Let Nexa handle agent orchestration, tool binding,
and control flow.

### Mistake: One agent doing everything

**Symptom:** A single agent with a 500-word prompt handling research, analysis,
writing, and formatting.

**Why it's wrong:** LLMs perform better with focused prompts. A single complex
prompt produces worse results than a pipeline of specialized agents.

**Fix:** Break into Researcher → Analyst → Writer → Editor pipeline.

### Mistake: Skipping `verify`

**Symptom:** Agent output is sometimes empty, malformed, or wrong type, and
the program crashes downstream.

**Fix:** Add `verify result satisfies string;` after every agent call. It costs
almost nothing and catches a large class of failures.

---

## Quick Diagnostic Checklist

When something goes wrong, run through these in order:

- [ ] Is `nexa --version` working? If not, reinstall.
- [ ] Does `nexa validate <file.nx>` pass? Fix syntax errors first.
- [ ] Does `nexa build <file.nx>` succeed with `--harness=warn`? Address Harness violations.
- [ ] Does `python <file.py>` run? Check imports and secrets.nxs.
- [ ] Is `secrets.nxs` in the right directory? It must be next to the source .nx file.
- [ ] Are `include` paths relative to the source file? Not the CWD.
- [ ] Is the virtual environment activated?
- [ ] Does the model name in the agent match a key in secrets.nxs MODEL_NAME?