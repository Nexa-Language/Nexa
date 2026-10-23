<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa</h1>
  <p>Agent 原生语言与可靠运行时，供人和模型共同编写 .nx 程序。</p>
</div>

**中文** | [English](README_EN.md) · Python 3.10+ · AGPL-3.0-or-later

Nexa 将 Agent、工具、Protocol、上下文和执行流程写进同一种语言。Python 编译器将声明转为可执行程序，运行时负责模型协议、工具策略、预算、审批、状态恢复和事件记录。Rust AVM 通过共同语义测试推进能力子集。

## 开始使用

需要 Python 3.10+。在虚拟环境中安装 [2.4.0 Release](https://github.com/Nexa-Language/Nexa/releases/tag/v2.4.0) 的 wheel：

```sh
python -m pip install https://github.com/Nexa-Language/Nexa/releases/download/v2.4.0/nexa_lang-2.4.0-py3-none-any.whl
nexa --version
```

PyPI 的 `nexa-lang` 属于另一项目，请使用上面的完整发行物 URL。编译与纯计算无需模型凭据；从 [安装与 Hello World](AGENT_LEARN/INSTALL_AND_HELLO_WORLD.md) 开始。

开发环境与示例固定到同一 tag：

```sh
git clone --branch v2.4.0 --depth 1 https://github.com/Nexa-Language/Nexa.git
cd Nexa
uv sync --locked --all-extras
uv run nexa --version
uv run nexa build examples/v2.0/07_verify.nx
```

运行模型前按 [首次模型配置](docs/development.md#configure-your-first-model) 设置项目的 endpoint、model ID 和凭据。凭据只在实际调用时读取。使用 `uv run nexa run FILE.nx` 执行 flow。

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

## 2.4 升级

- **统一编译**：CLI、SDK、嵌入式 API 共用递归 include、AST 规范化、Harness 诊断和生成物语法检查；wheel 包含标准库资源。
- **统一执行**：文本、Protocol、流式输出与精确缓存共用 AgentRunner。`execute()` 返回独立 RunState，`run()` 保留连续会话。
- **原生协议**：Chat Completions、Responses、Anthropic；保留工具调用、usage 和原生 reasoning / thinking 状态。
- **工具策略**：工具暴露集、JSON Schema、显式审批和实际 sandbox 状态共用检查入口。工具调用预算按实际调用计数。
- **持久化**：SQLite checkpoint、revision 冲突检测、工具执行日志与大输出 artifact。未知副作用结果须核实后恢复。
- **连续任务**：`continue_run()` 保留已结算历史及原生 provider 状态，为新一轮创建独立预算、期限、审批和可追踪的 run_id。
- **执行约束**：模型及工具预算、超时、协作取消、有界并行、上下文限额和稳定结果顺序。
- **可核验结果**：`.nxintent` 区分 pass、fail、skip、error；`verify` 失败终止当前成功路径。
- **MCP 与 Rust**：官方 MCP SDK 的真实 stdio/HTTP 连接；Rust 共同语义用例，以及 Wasmtime 48 LTS 的实际执行与资源限制。

发行物、验证范围与兼容变化见 [2.4.0 发行说明](docs/release_notes/v2.4.0.md)，完整行为见 [运行契约与迁移](docs/runtime-v2.4.md)。

## 长任务与审批

```sh
uv run nexa agent examples/Nexa-Code/main.nx CodeAssistant "Fix the failing test" --timeout 900
# 核对返回的 pending_calls，再批准指定调用：
uv run nexa agent examples/Nexa-Code/main.nx CodeAssistant --resume RUN_ID --approve CALL_ID
```

结果包含 run_id、status、output、error、usage 和待审批调用。默认 checkpoint 位于 `.nexa/runs.sqlite3`。拒绝调用使用 `--deny CALL_ID`。恢复会检查程序、provider、工作目录与预算的一致性。

[Nexa Code](examples/Nexa-Code/README.md) 使用同一运行时完成文件读取、审批修改和执行验证。离线评测任务位于 [evals/tasks](evals/tasks)，真实模型评测需要另外配置凭据与预算。

## Python API

```python
from src.runtime.agent import NexaAgent
from src.runtime.checkpoints import SQLiteCheckpointStore
from src.runtime.run_state import RunConfig

agent = NexaAgent("Analyst", prompt="Explain the evidence")
store = SQLiteCheckpointStore(".nexa/runs.sqlite3")
state = agent.execute("Analyze this result", config=RunConfig(timeout=120), save=store.save)
print(state.status, state.output)
```

`src.nexa_sdk.compile()` / `run()` 提供 `.nx` 编译与执行接口。公开的 `src.*` 导入路径保持兼容。

## 验证与能力边界

```sh
uv run pytest -m "not benchmark"
uv build --no-build-isolation
cargo test --manifest-path avm/Cargo.toml --locked --lib --test conformance --test wasm_execution
cargo test --manifest-path avm/Cargo.toml --locked --features wasm --lib --test conformance --test wasm_execution
```

Python 是参考运行时；Rust 支持的指令见 [能力说明](docs/runtime-v2.4.md#rust-能力子集)。普通 Python 工具在宿主进程运行；声明 sandbox 而未配置隔离执行器时，运行明确失败。WASM 功能需通过 `wasm` feature 启用。离线测试验证执行机制，真实 provider 的效果、成本和延迟单独评测。

当前测试与升级记录见 [实施清单](plan/01-v1-execution.md) 和 [证据目录](plan/evidence)。性能实验使用 `benchmark` 标记，与正确性测试分开运行。

[示例清单](examples/manifest.json) 逐项登记了 63 个通过编译检查的示例和 12 个保留的历史草案。模型、数据库或服务依赖的实际执行需要对应环境；统一编译门禁使用 `uv run pytest tests/test_examples.py -q`。

## 文档

- [运行契约与迁移](docs/runtime-v2.4.md)
- [开发与分发](docs/development.md)
- [语法参考](docs/01_nexa_syntax_reference.md)
- [编译器架构](docs/02_compiler_architecture.md)
- [Harness 设计背景](docs/others/Harness_Agent.md)
- [版本记录](docs/release_notes/)
- [许可证](LICENSE)
