# Development and verification

Nexa supports Python 3.10 and newer. The Python compiler and runtime are the
reference implementation for `.nx` programs. The Rust AVM is developed against
the documented 2.4 subset. Open Programs 3.0 supports Linux/macOS and requires
Docker Engine or Docker Desktop / Colima for candidate execution. Windows users
can run that runtime inside a Linux environment such as WSL2; native Windows
execution of the 3.0 controller is outside the supported platform set.

## Install a release

The 3.0.0 Python packages are distributed through [GitHub Releases](https://github.com/Nexa-Language/Nexa/releases/tag/v3.0.0). The `nexa-lang` PyPI name belongs to another project; install using the full artifact URL:

```sh
uv venv --python 3.12
uv pip install "nexa-lang[anthropic,terminal,mcp] @ https://github.com/Nexa-Language/Nexa/releases/download/v3.0.0/nexa_lang-3.0.0-py3-none-any.whl"
.venv/bin/nexa --version
```

On Windows, the entry point is `.venv\Scripts\nexa.exe`. An activated environment can use `python -m pip install` with the same direct reference. The release includes a wheel, source distribution, `SHA256SUMS`, and full repository source archives. Verify downloaded packages with `shasum -a 256 -c SHA256SUMS` (or `sha256sum -c SHA256SUMS` on Linux).

For the 3.0 language, save this as `answer.nx` and run `.venv/bin/nexa check answer.nx --json`:

```nexa
language "3.0"
program Answer {
    goal answer() -> Int {
        intent "Return 42"
        implementation value 42
    }
}
```

Offline checking needs neither Docker nor credentials. The [Open Programs guide](spec/3.0/usage.md) covers OCI setup, build and locked replay, Aliyun configuration, and repository maintenance. A wheel includes the compiler, runtime, standard library and schema exporter; examples, environment configurations and experiments are in the matching source archive or sdist.

Existing 2.4 syntax remains available. Save this as `hello.nx` and run `.venv/bin/nexa run hello.nx`; it prints `42` without a model connection:

```nexa
flow main {
    result = 23 + 19;
    print(result);
}
```

## Configure your first model

Open Programs uses an explicit JSON environment: see the [3.0 provider binding](spec/3.0/usage.md#绑定阿里云). The following `.nxs` setup applies to the retained 2.4 Agent/flow entry points.

For Chat Completions or Responses, create `model.nxs` beside your `.nx` program. Set the endpoint and model ID supplied by your provider:

```nxs
config default {
    BASE_URL = "https://your-provider.example/v1"
    MODEL_NAME = {
        "strong": "your-model-id",
        "weak": "your-model-id"
    }
}
```

Supply the credential through the `API_KEY` environment variable in your local shell or secret manager. The endpoint and model above are placeholders; replace both before making a model call. Nexa loads `.nxs` settings from the program's directory and its parents, with the nearest directory taking precedence. Keep credential files out of version control.

An agent without a model override selects `MODEL_NAME.strong` and uses Chat Completions by default. To use a Responses-compatible endpoint, add `provider_api: "responses"` inside its `agent` declaration. Set `model: "your-model-id"` there to override the configured model for one agent. Nexa 2.4 retains the legacy defaults (`minimax-m2.5`, `https://aihub.arcsysu.cn/v1`) when these settings are omitted; configure your chosen provider explicitly for the first run.

Native Anthropic uses the `anthropic` extra, `ANTHROPIC_API_KEY`, optional `ANTHROPIC_BASE_URL`, and an agent declaration with `provider_api: "anthropic"` and the provider's model ID. See the [protocol and budget contract](runtime-v2.4.md#模型协议) for further details.

## Develop from the release source

```sh
git clone --branch v3.0.0 --depth 1 https://github.com/Nexa-Language/Nexa.git
cd Nexa
uv sync --locked --all-extras
uv run nexa --version
uv run pytest -m "not benchmark"
uv build --no-build-isolation
```

The lockfile pins the development environment. `pip install -r requirements.txt`
remains available for existing workflows and installs the local project with its
terminal and Anthropic extras. Library installations can use `pip install .`;
the optional extras are `anthropic`, `terminal`, and `mcp`.

Tests run without provider credentials, with network sockets blocked, and with
temporary working and home directories. Test fixtures must supply their own
credentials and provider responses. Performance experiments are marked
`benchmark` and run separately with `uv run pytest -m benchmark`; timing results
are specific to the measured machine. A complete source distribution is tested
by rebuilding its wheel. The wheel is tested outside the checkout for version
reporting and bundled `.nx` standard-library resolution.

`src.compiler.compile_file` and `compile_source` are the shared compiler boundary.
The CLI, `src.nexa_sdk`, and `NexaRuntime` use this boundary. Includes are recursive,
resolved relative to the importing file first, and then against the bundled
`stdlib` package. A module is imported once per compilation; cycles report their
path chain. `.nxs` includes remain runtime configuration declarations. Generated
Python is syntax-checked before a successful compilation is returned. Harness
validation supports `warn` (the compatibility default), `strict`, and `off`.

The original codebase has existing typing debt (588 diagnostics in the initial
Python 3.12 audit). CI checks the maintained compiler and new runtime boundaries with ruff, isort,
and ty. The original audit count is recorded separately from passing checks.
See [runtime contracts](runtime-v2.4.md) for checkpoints, provider adapters,
approvals, context limits, and the Rust subset.

## Example inventory

`examples/manifest.json` lists each `.nx` file explicitly: 67 supported compilation or contract-check
cases and 12 historical drafts with their current failure reason. Run
`uv run pytest tests/test_examples.py -q` to check every supported file through the
shared compiler. The inventory test requires a status for every new example.
These checks cover compilation; examples needing models, databases, or servers
require their own configured execution environments. Historical drafts preserve
earlier syntax experiments and missing-module examples for reference.

## Local timing baseline

```sh
uv run python evals/runtime_baseline.py
cargo run --manifest-path avm/Cargo.toml --locked --example runtime_baseline
```

Both commands use the three arithmetic cases in the shared conformance corpus,
50 warm-up runs and 1,000 measured sequential runs, with zero provider calls.
Python measures an initialized compiled flow invocation, including its flow
scope. Rust measures interpreter creation, bytecode cloning/loading and execution;
the report identifies the debug/release build. Compilation/initialization time
is reported separately. Record hardware, OS and toolchain with the output.
These distinct boundaries provide reproducible backend baselines; cross-backend
speedup claims require a matched workload and measurement boundary.
