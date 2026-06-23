# Harness Native Runtime — Complete Reference

The Harness six-tuple H=(E,T,C,S,L,V) defines the safety and execution
guarantees for Nexa agents. Each dimension maps to language primitives
that compile to runtime components.

## Compile-Time Validation

The [`harness_validator.py`](../../src/harness_validator.py) runs at compile
time with three modes:

| Mode | CLI flag | Behavior |
|------|----------|----------|
| STRICT | `--harness=strict` | Violations are errors; compilation fails |
| WARN | `--harness=warn` (default) | Violations are warnings; compilation continues |
| OFF | `--harness=off` | Skip all Harness validation |

Each violation has a rule ID (e.g., `E-001`) and a suggestion for fixing it.

---

## E — Execution Dimension

**Primitives**: `autoloop`, `try_agent`, `step`

### `autoloop`

```nexa
autoloop max_steps: N, exit_when: "condition", timeout: T {
    // body
}
```

**Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `max_steps` | Yes | — | Maximum loop iterations (integer) |
| `exit_when` | No | `""` | Natural language exit condition |
| `timeout` | No | `300` | Total timeout in seconds |

**Validation rules:**

| Rule | Severity | Message |
|------|----------|---------|
| E-001 | error | autoloop without max_steps |
| E-002 | error | autoloop max_steps must be positive |
| E-003 | warning | autoloop without timeout may hang |
| E-004 | info | autoloop without exit_when (recommended) |

**Runtime component:** [`HarnessKernel`](../../src/runtime/harness_kernel.py)
manages loop state, counts iterations, and enforces the timeout.

### `try_agent` / `catch_correction`

```nexa
try_agent {
    result = Agent.run(task);
} catch_correction(e: ToolError) {
    reflect "Error handling strategy";
}
```

**Catchable error types:**
- `ToolError` — Tool execution failure
- `ModelError` — LLM API error
- `TimeoutError` — Operation timed out

**Runtime component:** The try/except is compiled to Python's native
`try:/except:` with the appropriate exception classes from
[`execution_engine.py`](../../src/runtime/execution_engine.py).

---

## T — Tool Dimension

**Primitives**: `@tool fn`, risk levels, approval gates

### `@tool fn`

```nexa
@tool("Human-readable description")
fn tool_name(param1: type1, param2: type2): return_type {
    python! """..."""
}
```

**Validation rules:**

| Rule | Severity | Message |
|------|----------|---------|
| T-001 | error | @tool fn must have a description |
| T-002 | error | @tool fn must have a return type |
| T-003 | error | @tool fn must contain a python! block |
| T-004 | warning | @tool fn description should be descriptive (>10 chars) |

**Runtime component:** [`ToolRegistry`](../../src/runtime/tool_registry.py)
manages tool schemas and dispatches tool calls. The compiler generates:

1. `__tool_<name>_schema` — JSON schema for OpenAI function calling
2. `def <name>(...)` — Python function implementation
3. Registration in `LOCAL_TOOLS` dict

**Tool dispatch flow:**

```
LLM returns tool_calls
  → execute_tool(name, args_json)
  → LOCAL_TOOLS[name](**json.loads(args_json))
  → Python function runs
  → result returned to LLM
```

---

## C — Context Dimension

**Primitives**: `with_context`

### `with_context`

```nexa
with_context max_tokens: N, strategy: sliding_window {
    // scoped block — context managed within
}
```

**Parameters:**

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `max_tokens` | No | `50000` | Token budget for the conversation |
| `strategy` | No | `sliding_window` | Context pruning strategy |

**Strategies:**
- `sliding_window` — Keep most recent messages, drop oldest
- `importance_weighted` — Prune low-importance messages first

**Validation rules:**

| Rule | Severity | Message |
|------|----------|---------|
| C-001 | warning | Agent without with_context may overflow token limit |
| C-002 | info | with_context max_tokens > model context limit |

**Runtime component:** [`ContextManager`](../../src/runtime/context_manager.py).
When the conversation exceeds `max_tokens`, the manager prunes older or
lower-importance messages.

---

## S — State Dimension

**Primitives**: `snapshot`, `restore`, `fork`

### `snapshot` / `restore`

```nexa
snap = snapshot();      // capture current state
// ... operations ...
restore(snap);           // rollback to captured state
```

State includes: conversation history, agent results, variable bindings.

**Runtime component:** [`StateStore`](../../src/runtime/state_store.py).
Uses Copy-on-Write (CoW) for efficient snapshots. Each snapshot is an
immutable copy of the state tree; restore replaces the current state.

### `fork` / `merge`

```nexa
fork {
    result_a = AgentA.run(task);
} and {
    result_b = AgentB.run(task);
}
final = merge(result_a, result_b);
```

**Runtime component:** [`ActorSystem`](../../src/runtime/actor_system.py).
Fork spawns parallel execution branches. Merge collects and combines results.

**Validation rules:**

| Rule | Severity | Message |
|------|----------|---------|
| S-001 | error | snapshot without restore (state leak) |
| S-002 | warning | fork without merge (dangling branches) |

---

## L — Lifecycle Dimension

**Primitives**: `reflect`, `before_step`, `after_step`

### Lifecycle Hooks in Agent Declaration

```nexa
agent MyAgent {
    prompt: "..."
    before_step: "Prepare for this step."
    after_step: "Verify the step output."
    reflect: "Analyze and improve."
}
```

### `reflect`

```nexa
reflect "Analyze the conversation and suggest improvements.";
```

The reflection instruction is injected into the LLM's context, asking it to
self-evaluate and adjust its strategy.

**Runtime component:** [`LifecycleHookManager`](../../src/runtime/lifecycle_hooks.py)
orchestrates hooks. Execution order:
1. `before_step` → 2. Agent.run() → 3. `after_step` → 4. `reflect` (periodic)

**Validation rules:**

| Rule | Severity | Message |
|------|----------|---------|
| L-001 | info | Agent with lifecycle hooks (good) |
| L-002 | warning | reflect without before/after_step (less effective) |

---

## V — Verification Dimension

**Primitives**: `verify ... satisfies`

### `verify`

```nexa
verify result satisfies string;           // type check
verify result satisfies "is non-empty";   // semantic check
```

**Runtime component:** [`EvaluationInterface`](../../src/runtime/evaluation_interface.py)
+ [`LLMRouter`](../../src/runtime/llm_router.py). Type checks are compile-time;
semantic checks use a judge LLM at runtime.

**Validation rules:**

| Rule | Severity | Message |
|------|----------|---------|
| V-001 | error | verify target not found |
| V-002 | warning | verify with semantic condition (costs LLM call) |

---

## Cross-Dimensional Validation

| Rule | Severity | Message |
|------|----------|---------|
| X-001 | warning | Agent with 0 Harness dimensions (unharnessed agent) |
| X-002 | warning | Agent uses only 0 Harness dimensions — recommend ≥3 |
| X-003 | info | Well-harnessed agent (≥4 dimensions) |

---

## CLI Integration

```bash
# Build with Harness validation (warning mode)
nexa build agent.nx --harness=warn

# Build with strict Harness (block on violations)
nexa build agent.nx --harness=strict

# Build without Harness validation
nexa build agent.nx --harness=off

# Validate only (no codegen)
nexa validate agent.nx --harness=strict
```

Violations are printed in format:
```
⚡ HarnessViolation(dimension=E, severity=warning, rule_id=E-003,
   message='autoloop without timeout may hang indefinitely',
   suggestion='Add: timeout: 300 (seconds)')