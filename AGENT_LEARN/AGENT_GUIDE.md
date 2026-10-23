# Nexa 2.4 authoring guide

Nexa is an agent-native language. Humans and models use the same `.nx` source:
Agent definitions declare prompts, tools and limits; flows express control and
data dependencies. Python is the reference runtime. Use the Rust AVM only for
its [documented subset](../docs/runtime-v2.4.md#rust-能力子集).

## Author, compile, inspect, execute

```sh
uv sync --locked --all-extras
uv run nexa build program.nx
uv run nexa inspect program.nx --format json
uv run nexa validate program.nx --json
uv run nexa harness-check program.nx --harness strict --json
uv run nexa run program.nx
```

Compilation works without credentials. Model execution requires configured
provider credentials and a model. `build` uses compatibility warnings by default;
`--harness strict` makes Harness violations errors. Build output is a sibling
`.py` file. Fix diagnostics in the reported source file, including an included
module, then compile again. `inspect` describes the expanded module structure.

## Minimal executable program

```nexa
flow main {
    result = 23 + 19;
    print(result);
}
```

A flow returns its last assigned value implicitly. Empty and declaration-only
modules also compile. Includes resolve relative to their importing file, then
the bundled standard library. A file is included once; cycles are errors.

## Agent with an executable tool

```nexa
@tool("Add two integers")
fn add(a: int, b: int): int {
    python! """
return a + b
"""
}
agent Calculator uses add {
    prompt: "Use add to calculate the answer."
    timeout: 60
    max_tool_calls: 2
}
flow main {
    result = Calculator.run("What is 23 + 19?");
    verify result satisfies string;
}
```

Keep tools narrow and expose only the required ones. Arguments are checked
against JSON Schema. Writes and commands should declare `requires_approval: true`;
`risk_level: "high"` also requires approval. Local Python tools execute on the
host. `sandbox: true` requires an actual isolated executor and fails if missing.

Use `provider_api: "chat"`, `"responses"` or `"anthropic"` for the protocol.
Native provider state is retained by the runtime. Do not edit opaque reasoning
or signed thinking items. Structured output definitions are runtime-validated;
use the [working schema example](../examples/v2.1/02_structured_output.nx).

## Choose the appropriate execution interface

- `Agent.run(...)` carries a sequential conversation and returns its value.
- Python `Agent.execute(...)` creates an isolated run and returns status,
  messages, usage, events, pending approvals and the tool journal.
- `nexa agent FILE NAME TASK` runs a declared agent with SQLite checkpoints.
  Resume using `--resume RUN_ID --approve CALL_ID` or `--deny CALL_ID` after
  inspecting the exact tool and arguments. Keep the same workspace/source/config.
- `fork ... merge all/first/vote` runs independent sessions with bounded
  concurrency. `best` requires a numeric `score` in every branch result.
- `spawn` creates a flow-owned actor with an isolated ordered mailbox. `pass`
  queues another input; `await` closes and joins it. Await every spawned actor.

Approval waiting counts toward the original deadline. Interrupted tool results
can be unknown; reconcile the actual effect before resuming. Do not blindly
repeat an operation merely because its response was lost.

## Harness and validation rules

| Situation | Authoring action |
|---|---|
| An autoloop lacks a bound or exit observation | Supply `max_steps`, `timeout` and a meaningful `exit_when`; compare the final assigned text/status exactly |
| A verify predicate fails | Correct the result or predicate; execution stops at that statement |
| Output violates Protocol/schema | Correct the model/tool output; malformed data produces failure |
| Context exceeds its budget | Reduce input or complete earlier turns; native opaque state must remain intact |
| A fork uses best with string outputs | Use `all`/`first`/`vote`, or return explicit numeric scores |
| Intent check lacks an evaluator | Treat `skip`/`error` explicitly; configure the evaluator before claiming success |

`snapshot`/`restore` cover flow memory and Agent context. External filesystem and
service effects remain in the environment. `reflect` affects the next Agent
input; lifecycle hooks observe real model/tool boundaries.

Start from files listed under `compiled` in [examples/manifest.json](../examples/manifest.json).
`historical_drafts` records unsupported earlier syntax and missing dependencies.
Compilation checks and environment acceptance checks have separate roles:
verify file contents, subprocess results or other task outcomes after execution.

See [runtime and migration](../docs/runtime-v2.4.md),
[Nexa Code](../examples/Nexa-Code/README.md), and the
[versioned evaluation](../evals/README.md). Live model ability to generate and
repair Nexa programs remains a separate evaluation from offline runtime tests.
