# Nexa 2.4 本地交付证据

日期：2026-10-23，Asia/Singapore。环境：macOS 26.6.2 arm64、Python 3.12.13、rustc/cargo 1.97.1。依赖由 uv.lock 与 avm/Cargo.lock 锁定；Python 使用项目 `.venv`，Rust 使用临时 CARGO_HOME。基线 commit 为 `c1ec8af8e2151c293fce76da29469f24699a0c58`，功能分支为 `feat/nexa-runtime-modernization`。

本地代码、工具和确定性评测的验收已通过。代码未提交，当前源码与测试文件的 SHA-256 清单见 [验证快照](verification-snapshot.json)。真实模型服务、本地以外的 CI 矩阵和 PostgreSQL 集成另行验证。

## 最终检查

| 检查 | 命令或范围 | 结果 |
|---|---|---|
| Python 正确性 suite | `.venv/bin/pytest -q -rs -m 'not benchmark'` | **2130 passed / 5 skipped / 3 deselected**，16 warnings，140.79 s |
| Rust 默认 feature | `cargo test --manifest-path avm/Cargo.toml --locked --offline --lib --test conformance --test wasm_execution` | 135 library + 3 conformance + 2 WASM feature/metadata tests passed |
| Rust WASM feature | 上述命令加 `--features wasm` | 135 library + 3 conformance + 5 WASM tests passed |
| Python 静态检查 | CI 中 maintained files 清单，另检查 baseline 脚本及跨进程 fixture/test | Ruff、isort、ty 均通过 |
| Rust 格式与静态检查 | 修改文件执行 rustfmt；`cargo clippy --locked --offline --features wasm --lib --tests` | 命令退出 0；保留 27 项 lib-test warnings（23 duplicates） |
| 分发构建 | `uv build --offline --no-build-isolation` | sdist + wheel 2.4.0 构建成功；全套中的分发测试验证 sdist 重建及仓库外 CLI/stdlib |
| 示例清单 | 每个 supported `.nx` 走 `compile_file`，清单必须覆盖所有示例 | 63 compiled / 75 total；12 historical drafts 按文件记录原因 |
| 文档 smoke | README 中英文、AGENT_GUIDE、INSTALL_AND_HELLO_WORLD | 共 5 个完整 Nexa 代码块编译通过，Hello World 实际输出 `42` |
| 工作树检查 | `git diff --check` | 通过 |

5 个 skip 均来自 `test_database.py` 的 PostgreSQL 用例，原因是 `psycopg2 not installed`。3 个 deselected 是独立 COW/cache 性能实验。16 个 warnings 主要为历史 JWT fixture 的短密钥和被测试隔离器拦截的 OAuth DNS 尝试；本轮未发出真实模型请求。

日志：[Python suite](python-tests.log.txt)、[Rust 默认](rust-default-tests.log.txt)、[Rust WASM](rust-wasm-tests.log.txt)、[Clippy](rust-clippy.log.txt)、[Ruff](python-ruff.log.txt)、[isort](python-isort.log.txt)、[ty](python-ty.log.txt)、[分发](distribution-build.log.txt)。

## 关键行为验收

- 同一 `.nx` 通过 CLI、SDK、API 共用 include/AST/诊断路径；嵌套 Harness 和 include 文件保留源文件、行、列。
- Agent 运行覆盖工具暴露、参数校验、审批、预算、取消、文本/结构化/流式结果与上下文；原生协议 fixture 保留 Responses encrypted reasoning 和 Anthropic thinking 签名。
- 工具传输失败保留 `started`，停止模型继续循环。HTTP post/put/delete 覆盖 Timeout、ChunkedEncodingError、ContentDecodingError、IncompleteRead；shell 超时和真实 MCP 进程断连也进入未知结果路径。
- 真实子进程使用 `os._exit(73)` 注入两种窗口：外部文件写入后退出；完成结果落库后退出。新进程恢复时都只写入一次，未知结果需 reconcile 后继续。相关 8 项 checkpoint 测试通过，见 [跨进程日志](cross-process-recovery.log.txt)。
- 本地 MCP SDK server 实际执行 stdio 协商、分页、调用、业务错误、断连和关闭。HTTP transport 使用官方 SDK 实现，HTTP server 端到端尚未在本轮单独运行。
- 并行运行有界且结果有序；Actor 会话独立、邮箱有序、预算累计、并发上限与总生命周期次数分开；漏 await 的 flow 会取消并收束线程。
- WASM 实际运行 guest 代码，检验导出内存读写、状态保留、fuel 耗尽和畸形元数据；未启用 feature 时明确失败。

独立审查的 9 类实质发现全部修复。最后定向复核确认 HTTP 响应流异常场景均为副作用 1 次、模型调用 1 次、journal `started`、run `failed`；无该范围剩余 Important。

## Nexa Code 评测

版本化任务：`fix-addition-v1`。运行真正编译的 Nexa Code，在临时工作区读取错误实现、审批写入、实际修改、审批验证命令并运行子进程。完成状态为 `completed`，4 次模型 fixture 调用、3 次工具调用、2 次审批；文件内容和验证脚本输出均符合预期。

[评测 JSON](nexa-code-fixture-eval.json) 保存环境、模型字段、事件和 fixture usage。模型字段表示请求配置，provider_mode 为 `deterministic_fixture`；12 input / 8 output tokens 是 fixture 计数，用于验证预算记账。

## 本地 timing baseline

[Python](python-runtime-baseline.json)、[Rust](rust-runtime-baseline.json)、[环境](runtime-baseline-environment.json)。共同输入是 conformance corpus 的 3 个纯算术程序；每个预热 50 次，测量 1000 次，单并发，provider 调用为 0。机器为本次 arm64 macOS 主机；沙箱内 CPU 型号读取不可用。

| 用例 | Python median / p95（µs） | Rust debug median / p95（µs） |
|---|---:|---:|
| integer_precision | 0.542 / 0.584 | 3.708 / 4.083 |
| true_division | 0.500 / 0.542 | 1.625 / 1.750 |
| local_variables | 0.500 / 0.667 | 2.208 / 2.333 |

Python 测量编译后 flow 调用及其 scope；Rust 包含新解释器、bytecode clone/load 与执行。初始化/编译时间单独保存在 JSON 中。两者的测量边界不同，后续比较性能需统一工作负载和计时范围。实时模型网络开销、质量和费用尚未测量。

## 后续验收条件

真实 provider 需要固定 endpoint/model、凭据、预算和重复次数，分别评测执行 `.nx` 与根据文档生成/修复 `.nx`。Python 3.10/3.14 与 Linux 验证交由已配置的 CI；本轮本地仅验证 3.12。Rust 支持子集、宿主工具隔离和协作取消等使用边界见 [运行契约](../../docs/runtime-v2.4.md)。
