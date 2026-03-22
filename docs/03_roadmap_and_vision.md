# Nexa 路线图：从 MVP 到 AVM (Agent Virtual Machine)

Nexa 语言的演进路线严格遵循 "Think Big, Start Small" 的原则。我们的终极目标是创建一个原生且安全的智能体执行引擎。

## 阶段 1-4: v0.1 到 v0.8.x (已完成 ✅)
覆盖了 MVP 转译器、管道操作、架构重构、安全模块 (.nxs/.nxlib)、契约式编程 (Protocols)、多模型路由、持久化记忆及 Markdown 动态工具体系编排。

## 阶段 5: v0.9-alpha 认知与治理增强 (已完成 ✅)
- [x] 原生支持声明 `uses mcp:"..."` 来引入外部服务，形成一个真正的工具生态系统。
- [x] 基于正则的 Heuristic Fast-Path `semantic_if ... fast_match`。
- [x] 导入 python 运行时：增强 SDK Interop，允许动态通过 `importlib` 加载底层框架。
- [x] 提供 `test` 子类，可以进行各种测试，比如代理连通性测试。

## 阶段 6: v1.0+ 架构演进待办池 (Feature Backlog) 🚀
以下内容已在主创团队决议后纳入 v1.0 乃至更长远的未来视界：

- [x] **复杂拓扑 DAG 支持：** 扩展 `>>` 运算符，支持分叉、合流等高阶数据流转编排。（v0.9.6-rc 实现）
- [x] **原生异常处理：** 引入 `try/catch` 语法块，允许开发者在脚本层捕获运行时异常。
- [x] **Rust AVM 底座：** 从 Python 脚本解释转译模式跨越至基于 Rust 编写的独立编译型 Agent Virtual Machine (AVM)。（v1.0 实现，110个测试通过）
- [x] **WASM 安全沙盒：** 在 AVM 中引入 WebAssembly，对外部 `tool` 执行提供强隔离与跨平台兼容性。（v1.0 实现，wasmtime 集成）
- [ ] **可视化 DAG 编辑器：** 提供基于 Web 的节点拖拽界面，支持逆向生成 Nexa 代码。（架构规划已完成）
- [x] **智能调度器 (Smart Scheduler)：** 在 AVM 层基于系统负载、Agent 优先级动态分配并发资源。（v1.0 基础实现）
- [x] **向量虚存分页 (Context Paging)：** AVM 接管内存，自动执行对话历史的向量化置换与透明加载。（v1.0 基础实现）
- [x] **运行时动态反射：** 支持在执行期动态生成新 Agent 实例或动态重载 Model 配置。
- [x] **RBAC 权限访问控制：** 为不同 Agent 或流定义安全角色，确保工具调用的最小权限原则。（v0.9.6-rc 实现）
- [x] **Open-CLI 深度接入：** 原生集成类似 `spectreconsole/open-cli` 的宿主命令行交互标准。（v0.9.6-rc 实现）
- [x] **编程语言层面的缓存机制：** 因为agent本身的特点，同一次对话里面会有很大一部分input是重复的，设计一个原生的缓存机制可以极大提升效率。（v0.9.6-rc 实现：语义缓存、多级缓存）
- [x] **上下文压缩工具compactor：** 设计一个原生的上下文压缩工具，能够在不丢失关键信息的前提下压缩对话历史，提升模型处理长上下文的能力。（v0.9.6-rc 实现）
- [x] **一个长久记忆文件：** 参考AReal的CLAUDE.md的设计，设计一个长期记忆文件，能够记录agent的长期记忆和经验教训，供未来的agent参考和学习。（v0.9.6-rc 实现）
- [x] **基于知识图谱的记忆管理：** 设计一个基于知识图谱的记忆管理系统，能够将agent的记忆以结构化的方式存储和查询，提升agent的推理能力和知识整合能力。（v0.9.6-rc 实现）
- [x] **长期记忆后端支持：** 设计一个长期记忆后端，能够支持大规模的记忆存储和高效的查询，满足agent在复杂任务中的记忆需求。（v0.9.6-rc 实现：SQLite、向量后端）

## 其他的一些想法

- [x] **让agent学会写agent：** 提供一个专门的Agent友好的Nexa文档 `docs/NEXA_AGENT_GUIDE.md`，包含语法速查表、代码模板、最佳实践。（v1.0 实现）
- [x] **Python 实时引用 Nexa 库/接口：** `src/nexa_sdk.py` 提供 `nexa.run()`, `nexa.Agent()`, `nexa.compile()` 等 API。（v1.0 实现）
- [x] **调试器支持：** `src/runtime/debugger.py` 提供断点、变量监视、单步执行。（v1.0 实现）
- [x] **性能分析器：** `src/runtime/profiler.py` 提供 Token 消耗、执行时间追踪、性能报告。（v1.0 实现）
- [x] **标准库扩展：** `src/runtime/stdlib.py` 提供 HTTP请求、文件操作、JSON处理、加密、时间日期等内置工具。（v1.0 实现）
- [ ] **包管理器

### 社区生态与学术
1. **开源贡献**：建立开放的贡献流程和代码审查机制。
2. **理论基础论文**：分享非确定性计算的确定性控制流、基于模型的 `loop ... until` 与原生 `semantic_if` 等。
