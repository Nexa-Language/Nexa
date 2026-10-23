<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa</h1>
  <p>An agent-native language and reliable runtime for humans and models authoring .nx programs.</p>
</div>

[中文](README.md) | **English** · Python 3.10+ · AGPL-3.0-or-later

Nexa expresses agents, tools, protocols, context, and control flow in one language. Its Python compiler produces executable programs; its runtime owns provider protocols, tool policy, budgets, approvals, checkpoints, and events. The Rust AVM grows against a shared semantic test suite.

## Getting started

With Python 3.10+ in an activated virtual environment, install the wheel from the [2.4.0 release](https://github.com/Nexa-Language/Nexa/releases/tag/v2.4.0):

```sh
python -m pip install https://github.com/Nexa-Language/Nexa/releases/download/v2.4.0/nexa_lang-2.4.0-py3-none-any.whl
nexa --version
```

The `nexa-lang` name on PyPI belongs to another project. Use the full release URL above. Compilation and pure computation work without provider credentials. See the [installation guide](docs/development.md#install-a-release).

For development and examples, check out the matching tag:

```sh
git clone --branch v2.4.0 --depth 1 https://github.com/Nexa-Language/Nexa.git
cd Nexa
uv sync --locked --all-extras
uv run nexa --version
uv run nexa build examples/v2.0/07_verify.nx
```

Follow [first-model setup](docs/development.md#configure-your-first-model) to configure your endpoint, model ID and credential before making model calls. Compilation works without credentials. Run flows with `uv run nexa run FILE.nx`.

```nexa
@tool("Add two integers")
fn add(a: int, b: int): int {
    python! """
return a + b
"""
}
agent Calculator uses add {
    prompt: "Use the add tool to calculate the answer."
    timeout: 60
    max_tool_calls: 2
}
flow main {
    result = Calculator.run("What is 23 + 19?");
    verify result satisfies string;
    print(result);
}
```

## Version 2.4

- One compiler boundary for CLI, SDK, and embedded API: recursive includes, normalized AST, Harness diagnostics, and Python syntax validation. Distributions include the `.nx` standard library.
- One AgentRunner for text, Protocol, streaming, and exact-cache results. `execute()` creates an isolated RunState; `run()` retains a serialized conversation.
- Native Chat Completions, Responses, and Anthropic adapters preserve tool calls, usage, and opaque reasoning or signed thinking state.
- Tool exposure, JSON Schema validation, explicit approvals, and truthful isolation status share one dispatch boundary.
- Versioned SQLite checkpoints use optimistic concurrency and a tool journal. Completed tool results are reused; uncertain side effects require operator reconciliation.
- `continue_run()` starts a new turn from settled history, retaining native provider state with fresh budgets, deadlines and approvals, linked by parent and session identifiers.
- Bounded parallel execution, cancellation signals, deadlines, call and token budgets, and bounded tool-output artifacts.
- IAL checks distinguish pass, fail, skip, and error. Failed `verify` statements stop the success path.
- Official MCP SDK connections, shared Python/Rust fixtures, and real Wasmtime 48 LTS execution with resource limits.

See the [2.4.0 release notes](docs/release_notes/v2.4.0.md) for artifacts and verification scope, and the [runtime contract and migration guide](docs/runtime-v2.4.md) for detailed behavior.

## Durable agent execution

```sh
uv run nexa agent examples/Nexa-Code/main.nx CodeAssistant "Fix the failing test" --timeout 900
# Inspect pending_calls, then approve the specific call:
uv run nexa agent examples/Nexa-Code/main.nx CodeAssistant --resume RUN_ID --approve CALL_ID
```

Use `--deny CALL_ID` to reject a tool call and `--checkpoint PATH` to select a database. The default is `.nexa/runs.sqlite3`. Exit codes are 0 for completion, 2 for approval, and 1 for other stopped states. Source, provider, workspace and budgets must match when resuming. Deadlines include approval waiting time.

```python
from src.runtime.agent import NexaAgent
from src.runtime.checkpoints import SQLiteCheckpointStore
from src.runtime.run_state import RunConfig

agent = NexaAgent("Analyst", prompt="Explain the evidence")
store = SQLiteCheckpointStore(".nexa/runs.sqlite3")
state = agent.execute("Analyze this result", config=RunConfig(timeout=120), save=store.save)
print(state.status, state.output)
```

The existing `src.nexa_sdk.compile()` / `run()` and public `src.*` import paths remain available. Provider API selection accepts `chat`, `responses`, and `anthropic`; native Anthropic uses `ANTHROPIC_API_KEY` and optional `ANTHROPIC_BASE_URL`.

## Development and verification

```sh
uv run pytest -m "not benchmark"
uv build --no-build-isolation
cargo test --manifest-path avm/Cargo.toml --locked --lib --test conformance --test wasm_execution
cargo test --manifest-path avm/Cargo.toml --locked --features wasm --lib --test conformance --test wasm_execution
```

Python is the reference runtime. Rust supports an explicit subset, returning errors for unsupported instructions. Python tools execute on the host; requesting a sandbox without an isolated executor fails. WASM execution requires the `wasm` feature. Cancellation of arbitrary Python handlers is cooperative. Context limits use a conservative UTF-8 byte bound; native provider history is retained and oversized requests fail explicitly.

Offline provider fixtures verify runtime behavior. Real-provider quality, cost, and latency require a separately configured evaluation. [Nexa Code](examples/Nexa-Code/README.md) and the versioned [evaluation tasks](evals/tasks) exercise actual file edits and subprocess verification in temporary workspaces.

The [example manifest](examples/manifest.json) records 63 compilation cases and 12 historical drafts with explicit failure reasons. `uv run pytest tests/test_examples.py -q` checks every supported file. Execution of examples with model, database or server dependencies requires the corresponding environment.

- [Development guide](docs/development.md)
- [Runtime contract](docs/runtime-v2.4.md)
- [Syntax reference](docs/01_nexa_syntax_reference.md)
- [Compiler architecture](docs/02_compiler_architecture.md)
- [Implementation record](plan/01-v1-execution.md)
- [License](LICENSE)
