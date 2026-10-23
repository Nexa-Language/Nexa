<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa</h1>
  <p>Agent 原生语言与可靠运行时，供人和模型共同编写 .nx 程序。</p>
</div>

**中文** | [English](README_EN.md) · Python 3.10+ · AGPL-3.0-or-later

Nexa 3.0 **Open Programs** 让程序持有目标、实现、证据和修订。人和模型编写同一种 `.nx` 合同；编译器可以澄清目标、求解实现和执行验收，运行时在证据有效、权限满足时接纳并执行新版本。

## 3.0 的变化

- **编译包含求解**：`implementation open` 留下带类型与验收条件的目标；模型在预算内提出实现，OCI 执行器运行候选和固定检查。
- **完成有条件**：确定性检查、模型评审和人工授权分别记录。输入、策略、依赖或环境变化后重新核对证据；后续失败阻止旧成功继续授权。
- **程序持续修订**：源码版本、活动与检查点持久保存。旧活动固定原版本，新活动使用接纳后的修订；未知外部作用先核对再恢复。
- **准确授权应用**：仓库维护生成可审查补丁，授权绑定补丁、基线、作用范围和证据。写前日志及保留原文件支持并发编辑保护和中断恢复。
- **实现有条件复用**：本地 capsule 携带来源、许可、依赖和证据；接收任务核对条件并重验。
- **编译器协作演进**：作者 JSON-RPC 协议提供诊断、澄清和取消；诊断 advice pass 通过固定语料、C1/C2 锁定自举与授权后选择。

[3.0.0 发行说明](docs/release_notes/v3.0.0.md) · [使用指南](docs/spec/3.0/usage.md) · [语言合同](docs/spec/3.0/core.md) · [作者协议](docs/spec/3.0/author-protocol.md) · [2.4 迁移](docs/migration/2.4-to-3.0.md)

## 开始使用

需要 Python 3.10+。3.0 运行时支持 Linux/macOS，执行候选需要 Docker Engine 或 macOS 上的 Docker Desktop / Colima。在虚拟环境中安装 [3.0.0 Release](https://github.com/Nexa-Language/Nexa/releases/tag/v3.0.0) 的 wheel：

```sh
python -m pip install https://github.com/Nexa-Language/Nexa/releases/download/v3.0.0/nexa_lang-3.0.0-py3-none-any.whl
nexa --version
```

PyPI 的 `nexa-lang` 属于另一项目，请使用完整发行物 URL。将以下程序保存为 `answer.nx`：

```nexa
language "3.0"
program Answer {
    goal answer() -> Int {
        intent "Return 42"
        implementation value 42
    }
}
```

`nexa check answer.nx --json` 在离线环境中检查源码，不需要 Docker 或模型凭据。构建、运行与锁定重放见 [使用指南](docs/spec/3.0/usage.md)。将实现改为 `implementation open` 并配置检查和 provider 后，编译器可以求解目标。

开发环境与示例固定到同一 tag：

```sh
git clone --branch v3.0.0 --depth 1 https://github.com/Nexa-Language/Nexa.git
cd Nexa
uv sync --locked --all-extras
uv run nexa check examples/open_programs/sum.nx --json
```

[阿里云示例](examples/open_programs/aliyun.json) 通过环境变量绑定 endpoint 和凭据；已实测模型为 `qwen3.8-max-0902`。配置只存变量名。候选容器无宿主目录挂载、密钥和外网，模型调用由编译器统一计量。维护仓库从 [maintain.nx](examples/open_programs/maintain.nx) 开始。

## 2.4 兼容入口

没有 `language "3.0"` 的既有源码继续使用 2.4 编译路径。Agent、工具、Protocol 和 flow 仍可运行；公开 `src.*` API 保持兼容。首次配置旧入口的模型见 [开发指南](docs/development.md#configure-your-first-model)。

### 保留的运行时能力

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

3.0 候选及运行实现均在 OCI 中执行；工作区应用需要单独授权。Python 是参考运行时，Rust 保持 2.4 子集；支持的指令见 [能力说明](docs/runtime-v2.4.md#rust-能力子集)。2.4 入口中的普通 Python 工具在宿主进程运行；声明 sandbox 而未配置隔离执行器时，运行明确失败。WASM 功能需通过 `wasm` feature 启用。离线测试验证执行机制，真实 provider 的效果、成本和延迟单独评测。

3.0 测试、审查与真实模型记录见 [执行记录](plan/04-v1-open-programs-execution.md) 和 [实验报告](plan/evidence/2026-10-23-open-programs-experiment.md)。固定的 360 阶段实验中，Open Programs 为 73/90，适配后的 2.4 基线为 70/90；token、失败和方法修正均单独报告。性能实验使用 `benchmark` 标记，与正确性测试分开运行。

[示例清单](examples/manifest.json) 逐项登记了 67 个通过编译或合同检查的示例和 12 个保留的历史草案。模型、数据库或服务依赖的实际执行需要对应环境；统一编译门禁使用 `uv run pytest tests/test_examples.py -q`。

## 文档

- [3.0 使用与执行边界](docs/spec/3.0/usage.md)
- [3.0 迁移](docs/migration/2.4-to-3.0.md)
- [2.4 运行契约与迁移](docs/runtime-v2.4.md)
- [开发与分发](docs/development.md)
- [语法参考](docs/01_nexa_syntax_reference.md)
- [编译器架构](docs/02_compiler_architecture.md)
- [Harness 设计背景](docs/others/Harness_Agent.md)
- [版本记录](docs/release_notes/)
- [许可证](LICENSE)
