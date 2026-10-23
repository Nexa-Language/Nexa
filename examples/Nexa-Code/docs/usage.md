# Nexa Code — Usage Guide

Nexa 2.4.0 uses the durable `nexa agent` entry point for tasks that edit files or run
commands. Follow the [tagged-source setup](../README.md#运行), then configure your
endpoint, model and credential using the [first-model guide](../../../docs/development.md#configure-your-first-model).

## Start a task

Change to the workspace to edit, then invoke the installed CLI:

```sh
/path/to/Nexa/.venv/bin/nexa agent /path/to/Nexa/examples/Nexa-Code/main.nx CodeAssistant "Fix the failing tests" --timeout 900
```

The current directory is the tool workspace. Read, search and directory-listing
tools are read-only. Writing files and executing commands pause the run with
`status: waiting_approval`; the JSON result contains the run ID and pending calls.

## Approve, deny and resume

Inspect the pending tool name and complete arguments, then approve that call:

```sh
/path/to/Nexa/.venv/bin/nexa agent /path/to/Nexa/examples/Nexa-Code/main.nx CodeAssistant --resume RUN_ID --approve CALL_ID
```

Use `--deny CALL_ID` to reject it. Resume from the same workspace with the same
source and provider configuration. `--checkpoint PATH` selects a SQLite file;
the default is `.nexa/runs.sqlite3`. The original timeout includes time spent
waiting for approval. Exit codes are 0 for completion, 2 for pending approval,
and 1 for failure, cancellation or exhausted budgets.

A transport failure after dispatch leaves the tool result unknown. Verify the
actual file/service state and reconcile it with `SQLiteCheckpointStore.resolve_tool`
before resuming. Completed journal entries reuse their stored results.

## Tools and verification

File tools validate resolved paths against the workspace and reject sensitive
paths. Writes are atomic. `shell_exec` runs a parsed argument list without a
shell, in the host environment, with a 30-second timeout. Approval authorizes the
actual command; commands can have effects beyond the file-tool path checks.

Run `uv run pytest tests/test_nexa_code_eval.py -q` from the Nexa repository for a
reproducible temporary-workspace evaluation. It uses scripted model responses,
real file tools, two approvals and a real verification subprocess. See the
[evaluation guide](../../../evals/README.md) for report fields and live-provider
measurements.

The older REPL flows remain in `flows.nx`. Use the durable entry point above for
approval and checkpoint recovery. Full contracts are in the
[2.4 migration guide](../../../docs/runtime-v2.4.md).
