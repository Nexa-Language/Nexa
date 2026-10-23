# Nexa 2.4 升级实施记录

设计依据：[已批准的升级方案](00-v1-nexa-modernization.md)。用户已确认「Agent 原生语言与可靠运行时」及 Python 优先路线。

当前状态：M0–M3 的本地实现与离线验收已完成，M4 的 Nexa Code 文件操作评测已完成，M5 的 Rust 语义子集与 WASM 已完成。本轮未调用真实模型服务，M4 的模型执行/编写 `.nx` 质量、费用和网络延迟评测待配置 provider 与预算后进行。最终检查数字与日志见 [交付证据](evidence/2026-10-23-verification.md)。

代码基线：`c1ec8af8e2151c293fce76da29469f24699a0c58`（2.3.1）。本地版本：2.4.0。分支：`feat/nexa-runtime-modernization`。改动保留在工作区，未提交、推送或发布。

## 实现与验收映射

| 阶段 | 实际交付 | 主要行为证据 |
|---|---|---|
| M0 工程基线 | pyproject、uv.lock、wheel/sdist 资源、延迟 provider 初始化、隔离测试、Python/Rust CI | `test_packaging.py` 从 sdist 重建 wheel，在仓库外加载分发包并编译包内标准库 |
| M1 编译 | CLI/SDK/API 共用加载、递归 include、AST、Harness 检查及生成 Python 语法检查；inspect/validate 同源；源码行列定位 | `test_compiler_integration.py`、`test_examples.py`；嵌套与 include 诊断、循环导入、声明模块、63 个示例逐文件编译 |
| M2 单 Agent | RunState/AgentRunner、预算与终态、取消、Chat/Responses/Anthropic、工具暴露/参数/审批、context/cache/trace 与 Harness lowering | `test_agent_execution.py`、`test_native_providers.py`、`test_harness_execution.py`、`test_tool_policy.py`、`test_review_regressions.py` |
| M3 长任务 | SQLite revision、跨进程恢复、工具 journal、artifact、官方 MCP SDK、有界并发与 flow Actor 生命周期 | `test_checkpoints.py`、`test_mcp_execution.py`、`test_parallel_runs.py`；副作用窗口、协议断连、分页、消息隔离、取消与资源回收 |
| M4 应用与评测 | `nexa agent` 审批/恢复入口、Nexa Code 工作区工具、版本化修复任务、双语 README 与迁移文档 | `test_nexa_code_eval.py`：真实文件读取、审批、写入、子进程检查；4 次 fixture 模型调用、3 次工具调用 |
| M5 Rust | Agent opcode、整数精度/变量/返回/跳转、显式拒绝不支持能力、共同语义 fixture、Wasmtime 48 LTS | 135 项库测试、3 项 conformance 测试；默认 2 项/WASM 5 项集成测试；真实 guest memory、fuel、状态保留及畸形元数据 |

维护中的 Python 边界通过 Ruff、isort、ty；Rust 修改文件经 rustfmt，Clippy 执行通过且保留旧代码 warning。CI 配置 Python 3.10/3.12/3.14，本地执行环境是 Python 3.12.13。全仓旧类型债务原始为 588 项 diagnostics，后续按模块迁移。

## 关键设计决定

- Python 为语义参考实现；Rust 以明确子集和共同用例推进。工具、完整 Harness 与原生 provider 状态留在 Python 路径。
- `run()` 保留有序连续会话；`execute()` 返回独立 RunState。并行执行与 Actor 使用独立会话；同一个定义可被复用。
- RunState schema 为 1，保存模型与工具计数、usage、provider items、审批、工具 journal、事件、定义/工作区标识。恢复保留原预算与墙钟期限。
- 工具执行前记录 `started`，确认结果后落库。超时、断连与响应流失败保留未知状态；人工核实后 reconcile，已确认结果可重用。
- 审批仅接受布尔值。`sandbox: true` 在没有隔离执行器时失败，执行记录反映实际隔离状态。
- Responses/Anthropic 保留 opaque reasoning/thinking 状态；上下文预算也计算这些内容。精确响应缓存限定为无工具的 Chat，并基于真正发送的上下文建立键。
- Harness 的 autoloop 精确比较退出状态；verify 失败终止；snapshot 恢复内存和会话；外部副作用留在真实环境中。
- Actor 邮箱按顺序消费，共享该 Actor 的调用预算与期限。最多 8 个活跃 Actor，flow 返回前要求 await；退出时等待线程收束。
- 历史示例采用显式清单：63 个支持编译，12 个草案记录原因。保留现有语法入口与旧 flow 隐式末赋值返回约定。
- `stdlib` 继续作为同目录 data package 分发，避免重复维护 `.nx` 资源。公开 `src.*` API 与已有入口保留。

## 审查与修复记录（2026-10-23）

最终独立审查检查实际编译/运行边界、恢复窗口、并发、provider 协议和 WASM。以下发现均已修复并纳入回归：

1. 字符串 `"false"` 被当作审批通过；改为严格布尔检查。
2. 工具传输失败被记录为成功/可继续；统一传播未知结果，覆盖 Requests 超时、响应流异常、urllib/http.client、shell 和 MCP。
3. 恢复未绑定工作目录；RunState 保存并验证规范化路径。
4. inspect/validate 未复用 include 解析；接入共享前端。
5. 无实际 upstream 输入时丢失原生会话状态；按真实上下文重置条件处理。
6. 缓存使用裁剪前历史、命中绕过预算；改为有效上下文和命中前校验。
7. opaque provider items 未计入上下文预算；纳入保守预算。
8. Responses refusal 未形成失败；统一拒绝终态。
9. WASM host memory API 与 guest memory 脱节；使用实际导出内存和持久实例。

同一审查还复核 Actor 会话隔离、总生命周期内反复 spawn、漏 await 的取消和线程回收。最后 HTTP 响应流异常定向复核已关闭 Important：副作用 1 次、模型调用 1 次、journal 保持 `started`，run 停止。

## 基线与实施过程

- 原始 Python suite：1973 passed / 3 failed / 5 skipped，102.30 s。失败集中在 std.time.now 零参数生成与 std.code/std.ui 注册；已修复实际入口。
- 原始 Rust 库 suite：135 passed。依赖通过项目级缓存安装，保留 Cargo.lock，CI 使用 `--locked`。
- 旧 sdist 缺少 requirements/VERSION/stdlib，wheel 版本回退；新的分发回归先复现失败，再验证修复。
- 原测试曾在工作目录写入 tracked 示例；测试现在使用临时 cwd/home、无 provider 凭据和默认网络阻断。旧 parser 测试吞异常的 skip 已移除。
- 语法兼容修复过程中发现 Python 字符串把 `\b` 转成退格，关键字边界失效；改为真实边界，并保留历史软关键字。新增显式 print lowering、转义字符串和空参数 flow 回归。
- 以逐文件示例测试替换「超过半数能解析即可」的门槛；每个新增示例必须进入显式状态清单。
- 本地 timing baseline 使用共同的 3 个纯算术程序，每个预热 50 次、测量 1000 次、单并发、0 次 provider 请求。Python 与 Rust 的测量边界分别写入 JSON，Rust 为 debug 构建；不据此计算跨后端加速比。

## 剩余验收与能力边界

- 待真实 provider 评测：鉴权、服务端兼容、执行/生成/修复 `.nx` 的质量、token、费用和延迟。本轮只使用 SDK 类型与确定性 provider fixture。
- CI 的 Python 3.10/3.14 与 Linux 环境尚未在此本地任务执行；PostgreSQL 可选驱动缺失的 5 项测试保持 skip。
- Rust 暂不支持工具执行、完整 Harness、WASI imports 和引用类型参数；不支持的指令明确报错。
- Python 工具在宿主执行，取消依赖工具协作；持久审批使用 execute/CLI，Actor 状态限于当前 flow。
- 历史 COW/cache 性能实验与 12 个草案保留独立状态；模型性能和历史论文指标尚待匹配条件的实验。
