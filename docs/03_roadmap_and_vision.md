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

- [ ] **复杂拓扑 DAG 支持：** 扩展 `>>` 运算符，支持分叉、合流等高阶数据流转编排。
- [x] **原生异常处理：** 引入 `try/catch` 语法块，允许开发者在脚本层捕获运行时异常。
- [ ] **Rust AVM 底座：** 从 Python 脚本解释转译模式跨越至基于 Rust 编写的独立编译型 Agent Virtual Machine (AVM)。
- [ ] **WASM 安全沙盒：** 在 AVM 中引入 WebAssembly，对外部 `tool` 执行提供强隔离与跨平台兼容性。
- [ ] **可视化 DAG 编辑器：** 提供基于 Web 的节点拖拽界面，支持逆向生成 Nexa 代码。
- [ ] **智能调度器 (Smart Scheduler)：** 在 AVM 层基于系统负载、Agent 优先级动态分配并发资源。
- [ ] **向量虚存分页 (Context Paging)：** AVM 接管内存，自动执行对话历史的向量化置换与透明加载。
- [x] **运行时动态反射：** 支持在执行期动态生成新 Agent 实例或动态重载 Model 配置。
- [ ] **RBAC 权限访问控制：** 为不同 Agent 或流定义安全角色，确保工具调用的最小权限原则。
- [ ] **Open-CLI 深度接入：** 原生集成类似 `spectreconsole/open-cli` 的宿主命令行交互标准。

### 社区生态与学术
1. **开源贡献**：建立开放的贡献流程和代码审查机制。
2. **理论基础论文**：分享非确定性计算的确定性控制流、基于模型的 `loop ... until` 与原生 `semantic_if` 等。
