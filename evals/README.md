# Versioned agent evaluations

`tasks/fix-addition-v1.json` defines a reproducible filesystem task and its acceptance conditions. `tests/test_nexa_code_eval.py` executes the actual Nexa Code program in a temporary workspace, replaces only the model API boundary, approves individual calls, and runs the resulting code in a subprocess.

Run with `uv run pytest tests/test_nexa_code_eval.py -q`. The test writes `eval-report.json` next to its temporary checkpoint, recording task version, Python version, provider mode, model, status, model/tool counts, fixture usage, elapsed time, and events. Correctness requires the expected file contents and a successful verification subprocess.

For a real-provider run, materialize the task files in a separate workspace and invoke `nexa agent /absolute/path/to/examples/Nexa-Code/main.nx CodeAssistant TASK --timeout 900`. Inspect each pending call before approval. Preserve the SQLite checkpoint and record the actual provider/model configuration and environment alongside the acceptance result. Offline fixture token numbers must not be used as measured model cost.

`tests/fixtures/conformance/programs.json` separately defines language semantics shared by the Python and Rust tests.

For a local timing baseline, run `uv run python evals/runtime_baseline.py` and
`cargo run --manifest-path avm/Cargo.toml --locked --example runtime_baseline`.
Both use the three non-model corpus cases, 50 warm-ups, 1,000 measured runs and
one worker. Reports state their different measurement boundaries and build mode;
record them with hardware/toolchain details. Baseline outputs from this upgrade
are kept in `plan/evidence/*runtime-baseline*.json`.
