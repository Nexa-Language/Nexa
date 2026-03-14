# Nexa 路线图：从 MVP 到 AVM (Agent Virtual Machine)

Nexa 语言的演进路线严格遵循 "Think Big, Start Small" 的原则。我们的终极目标是创建一个原生且安全的智能体执行引擎，但我们将从简单的语法糖起步。

## 阶段 1: v0.1 MVP - Transpiler 模式 (当前)
**定位：** 验证语言的语法设计 (Syntax) 与开发者体验 (DX)。
* **实现方式：** Python 编写的 Source-to-Source 转译器，将 `.nx` 文件编译成标准的 Python 脚本。
* **核心特性：**
  * 原生关键字：`agent`, `tool`, `flow`
  * 流程控制：结构化输出加持的 `semantic_if`
* **运行时依赖：** OpenAI Python SDK、Pydantic。
* **局限性接受：** 无沙盒隔离，多轮对话依靠 Python 的内存 List，缺乏持久化和安全限制。

## 阶段 2: v0.5 - Agent-Native 原生并发协作与内置运行时
**定位：** 解决复杂的智能体间协作、状态持久化与幻觉约束痛点。
* **实现方式：** 依然基于 Python 运行时，但必须剥离 Boilerplate，建立独立的 `runtime/` 层。
* **核心特性：**
  * **管道与流式编排 (Pipeline & Intent Routing)：** 引入 Unix 风格的 `>>` 管道操作符，以及强大的 `match intent(...)` 意图多路路由结构。
  * **并发与共识机制 (Concurrency & Consensus)：** 添加 `join(...)` 原语实现并行发散-收敛；支持 `loop until` 的批评者模式 (Critic Pattern) 进行结果对齐。
  * **统一作用域内存体系 (Unified Memory System)：** 支持 `local`, `shared`, `persistent` 跨 Agent 数据看板，并提供上下文字动压缩 (Auto-summarization)。
  * **强类型约束与沙箱前奏 (Type Safety)：** 将 Pydantic 内化至 Schema 原生层以拦截幻觉，并在 Runtime 层建立轻量级沙箱探针。

## 阶段 3: v1.0 - The Rust AVM (智能体虚拟机)
**定位：** 脱离 Python 生态依赖，在系统层面定义何为 "Agent Native"。
* **实现方式：** 废弃 Python 转译。使用 Rust 从头构建全新的编译器与独立的 AVM (Agent Virtual Machine)。
* **核心特性：**
  * **WASM 工具沙盒：** 所有 `tool` 函数编译为 WebAssembly，由 AVM 沙盒执行。确保智能体执行外部工具时不会造成系统级安全风险（例如防止 `rm -rf /` 注入恶意执行）。
  * **KV / Vector 虚拟内存分页：** 颠覆传统的 Context Limit 概念。底层实现透明的 Memory Paging 机制，当智能体的长期记忆超出 LLM 的输入窗口时，AVM 像操作系统一样，透明地通过 Vector Data 查询页面（Pages），将其置换（Swap In/Out）到大模型的上下文中。
  * **全确定性断点 / 任意时刻重放 (Time-Travel Debugging)：** 由于所有的外部不确定性都在 WASM 边界执行，AVM 可以快照智能体的整个内部状态（State Hash），实现随时暂停、恢复、克隆。