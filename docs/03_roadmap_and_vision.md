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

## 阶段 2: v0.5 架构重构与标准库 (已完成 ✅)
**定位：** 解决复杂的智能体间协作、状态持久化与幻觉约束痛点。引入 `std.shell` 使系统获得操作系统级感知。
* **实现方式：** 依然基于 Python 运行时，但必须剥离 Boilerplate，建立独立的 `runtime/` 层。
* **核心特性：**
  * **管道与流式编排 (Pipeline & Intent Routing)：** 引入 Unix 风格的 `>>` 管道操作符，以及强大的 `match intent(...)` 意图多路路由结构。
  * **并发与共识机制 (Concurrency & Consensus)：** 添加 `join(...)` 原语实现并行发散-收敛；支持 `loop until` 的批评者模式 (Critic Pattern) 进行结果对齐。
  * **统一作用域内存体系 (Unified Memory System)：** 支持 `local`, `shared`, `persistent` 跨 Agent 数据看板，并提供上下文字动压缩 (Auto-summarization)。
  * **强类型约束与沙箱前奏 (Type Safety)：** 将 Pydantic 内化至 Schema 原生层以拦截幻觉，并在 Runtime 层建立轻量级沙箱探针。

## 阶段 3: v0.6 模块化与安全纪元 (已完成 ✅)
**定位：** 引领代码复用与原生安全防护。
* **核心特性：**
  * **密钥隔离 (.nxs)：** 原生剔除硬编码密钥，引入 `secret("KEY")` 运行时动态注入与只读加载环境。
  * **原生标准库与包导入 (.nxlib)：** 添加 `include` 关键字合并跨文件 AST，允许开发者构建定制化 Agent 插件并分发。

## 阶段 4: v0.8 认知架构与人机协同 (已完成 ✅)
**定位：** 强化类型安全、多模型治理与动态生态接入。
* **契约式编程 (Protocols)：** 强制的输出格式约束与自修正重试循环。
* **多模型动态路由：** 基于 `model:` 前缀跨厂模型分发及 API 多密钥路由隔离。
* **人类介入机制 (HITL)：** 新增 `std.ask_human` 系统级终端阻断能力，实现流授权。
* **语言特性补齐：** 在 Agent 声明层支持终端流式输出 (`stream`) 与跨会话本地记忆持久化 (`memory: "persistent"`)。
* **动态工具挂载：** 通过 `uses "SKILLS.md"` 实现从自然语言文档自动提取和编译 JSON Tool Schema 的机制。

## 阶段 5: v0.9 认知与治理增强 (Cognitive & Governance) 🌟
**定位：** 深化 Agent 的思考逻辑与安全性防护机制，补齐“完整编程语言”的深度。
* **双系统思维 (System 1 & System 2)：** 原生支持 `reflect { ... } until condition` 等语法，实现快思考与慢思考（Chain-of-Thought）的无缝切换。
* **状态机约束 (FSM Guardrails)：** 强制 Agent 状态转移路径，彻底避免黑盒中的执行死循环。
* **事件驱动与跨平台交互：** 支持 `whenever event_name -> action` 的异步事件监听语法设计，拓展除了顺序流以外的事件流。
* **自动缓存 (Memoization)：** 针对相同 Prompt 与工具（纯函数）组合的确定性输出，运行时自动短路返回。

## 阶段 6: v1.0 终极形态 (AVM & Ecosystem) 🚀
**定位：** 脱离单机 Python 生态依赖，打造分布式计算节点和包管理分发生态。
* **NxPM 包管理器：** 实现 `nxpm install`，无缝拉取云端 Agent 定义与社区公开库。
* **Rust WASM 沙盒：** 废弃脆弱的 Python 原生调用底座，基于 WebAssembly 重构虚拟执行层，彻底解决任意代码执行的安全性。
* **时光机调试 (Time-travel Debugging)：** 配合 AVM，实现快照回滚、内存重写与在任意执行节点的重新推理。
