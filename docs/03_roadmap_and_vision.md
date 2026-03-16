# Nexa 路线图：从 MVP 到 AVM (Agent Virtual Machine)

Nexa 语言的演进路线严格遵循 "Think Big, Start Small" 的原则。我们的终极目标是创建一个原生且安全的智能体执行引擎。

## 阶段 1-4: v0.1 到 v0.8.x (已完成 ✅)
覆盖了 MVP 转译器、管道操作、架构重构、安全模块 (.nxs/.nxlib)、契约式编程 (Protocols)、多模型路由、持久化记忆及 Markdown 动态工具体系编排。

## 阶段 5: v0.9 认知与治理增强 (Cognitive & Governance)
* **双系统思维 (System 1 & System 2)：** 原生支持 `reflect { ... } until condition` 等语法。
* **状态机约束 (FSM Guardrails)：** 强制 Agent 状态转移路径，杜绝死循环。
* **事件驱动与跨平台交互：** `whenever event_name -> action` 异步事件监听。

## 阶段 6: v1.0 全景路线图确立 (The Ultimate AVM) 🚀
v1.0 版本将着重打造完整的 AI 原生体系，核心包含以下 6 个全新架构维度设计规划：

### 1. Memory/Context (上下文与长驻记忆体系)
统一支持 `local`, `shared`, `persistent` 的分级缓存控制机制。在 v1.0 中将引入向量数据库内建接入或原生 RAG 挂载点，提供透明的自动上下文压缩 (Auto-summarization) 与海量会话找回能力。

### 2. Resilience/Fallback (容错与灾备降级)
提出原生的 `fallback` 关键字层。Agentic Workflow 中经常面临 API 宕机、解析失败或死循环。通过 `action_a fallback action_b` 原语，使流程在发生 `Exception` 时，无缝安全地退化到备用流程或提示降级。

### 3. Observability/Tracing (执行观测与时空穿梭)
抛弃粗糙的终端抓取，引入系统级的 AST 执行切面 (AOP)。将每一步 Agent 思考流、工具调用与上下文变更进行结构化打点 (Log/Trace)。支持 "Time-travel Debugging"，允许开发者在沙盒里回滚断点，从特定的历史树节点重新启发推理。

### 4. Event-driven/Async (异步事件总线)
支持 `emit` 和 `on` 关键字。当爬虫工具发现新数据，或者外部 Webhook 到达时，通过异步消息泵直接唤醒沉睡的 Agent 进行并行消化，脱离单调的线性 `flow` 束缚。

### 5. Multi-Modal (多模态感知内化)
不再将视觉、音频视为二等公民。引入内建的视觉处理语法如 `img("some_file.jpg")`，并将在编译器层面自动拦截并展开成多模态 LLM 能够识别的 Base64 Payload。为具备"世界感知"能力的机器人奠定基础设施。

### 6. MCP Ecosystem (工具生态自治)
全面整合 Model Context Protocol。引入 `nxpm` 甚至直接复用生态中海量的只读/可写 Server 集成。让 Nexa 代码里一个简短的 `uses mcp:"github"` 或者 `uses mcp:"sqlite"` 就能将全世界的服务变成函数的本地执行端点点。

