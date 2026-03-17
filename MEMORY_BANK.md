# Nexa 语言架构师记忆库 (MEMORY_BANK)

> **[Agent 核心指令]** 每次对话开始时，你必须首先读取并遵循此文件。每次完成重大修改后，你必须主动更新此文件中的【进度追踪】和【踩坑记录】。

## 1. 核心教条 (Core Tenets)
- **Think Big, Start Small:** 我们最终要构建基于 WASM 的 AVM (Agent Virtual Machine)，但目前 (v0.1) 只做 Python 转译器 (Transpiler)。
- **拒绝过度工程:** 不手写底层网络协议，全面拥抱现有的成熟 SDK（OpenAI Python SDK, Pydantic, Tenacity, Lark）。
- **确定性至上:** 将 LLM 的概率输出限制在极小范围内（如强制使用 Structured Output 约束 `semantic_if` 返回 `{matched: bool, confidence: float}`）。
- **多轮检查:** 在每个阶段结束时，必须进行至少两轮的代码审计和测试，确保生成的 Python 代码不仅正确，而且健壮（例如在 `semantic_if` 的实现中注入重试机制）。同时，你应该重复读入并更新此 MEMORY_BANK和其他有修改的文件，以便在后续阶段中避免重复犯错。
- **禁止懒惰:** 不允许在任何阶段中为了赶进度而牺牲代码质量或架构设计。每次提交的代码都必须是可审计、可测试、且符合生产级标准的。

## 1.1 文档维护标准作业程序 (Doc SOP)
我们将通过以下严苛的约束纪律来维护所有的文档资产，确保任何代码的下潜都能完美投射至系统级知识库中：
- **触发条件 A (语法新增/修改)：** 必须同步更新 `docs/01_nexa_syntax_reference.md` 中的 EBNF 规则和代码示例。
- **触发条件 B (编译器/运行时底层变动)：** 必须同步更新 `docs/02_compiler_architecture.md` 中的 AST 结构映射或 Runtime 执行逻辑。
- **触发条件 C (新特性发布/里程碑达成)：** 必须在 `MEMORY_BANK.md` 的版本迭代记录中追加条目，并将 `docs/03_roadmap_and_vision.md` 中对应的 `[ ]` 修改为 `[x]`。同时更新 `README.md` 的特性矩阵。

## 1.2 v1.0+ 架构演进待办池 (Feature Backlog)
以下内容已在主创团队决议后纳入：
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

## 2. 架构设计锚点 (Architecture Anchors)
- **Parser 选型:** Python `Lark` 库 (Earley 算法)。前端必须具备可视化终端报错能力。
- **AST 设计原则:** 严格区分 `Statement` (无返回值，如 flow, agent 声明) 和 `Expression` (有返回值，如 string, method_call)。加入了嵌套 `block` 层级以正确解析条件分支的子作用域。
- **代码生成目标:** 必须生成带有重试容错机制的健壮 Python 脚本，具体参考 `04_generated_python_reference.py`，Visitor 模式遍历生成代码。

## 3. 进度追踪 (Progress Tracker)
- [x] 确立 Nexa v0.1 MVP 宏观路线图。
- [x] 完成核心语法的 EBNF 定义。
- [x] 确立 Transpiler 后端目标代码 Reference (Python)。
- [x] 使用 Lark 编写前端解析器 (Lexer & Parser) 并在 Python 中打印出 AST。
- [x] 编写 AST 到 Python 的代码生成器 (Code Generator / Visitor 模式)。
- [x] NEXA MVP Code Generator 编写与真实 VENV 联调完成。
- [x] Nexa CLI 命令行工具封装 (`nexa build` / `nexa run`) -> **Nexa v0.1 MVP 正式完成！**

## 4. 踩坑记录与教训 (Lessons Learned)
- **EBNF 歧义陷阱:** 早期设计没有区分表达式和语句，导致 `result = Researcher.run()` 和独立调用无法共存，且变量传递逻辑断层。已通过重写 EBNF 的 `assignment_stmt` 和 `expr_stmt` 解决。在后续手写 Parser 时需严格遵循当前 EBNF。
- **Lark 中的 Block/Scope 解析:** 在定义 `semantic_if_stmt` 时，如果没有独立的 `block: "{" flow_stmt* "}"` 规则，解析出的 args 将被拍平为一个长列表，使得无法区分 `consequence` 与 `alternative` (else) 中究竟包含了几个语句。引入独立的 `block` 后逻辑非常平滑地映射成了字典。
- **严厉的反思 (测试态度纪律):** 绝对不能在测试块中取巧只打印 success。必须强制使用 `tree.pretty()` 打印完整的 Tree 和 JSON 并在终端中肉眼校验！这才能防止出现空指针或解析遗漏。CLI 脚本在终端的输出排版同样是一种尊严，没有任何隐藏静默的权力。绝对不能在测试块中取巧只打印 success，必须强制打印完整的 Tree 和 JSON 并在终端中肉眼校验，防止出现空指针或解析遗漏。

## 5. 版本迭代记录 (Version History Log)

### v0.9.5-beta (The Exception & Reflection Era)
- **核心特性：** 重写了 `secrets.nxs` 的底层解析引擎以支持复杂字典结构环境变量映射；引入了全链条的基于 `try/catch` 闭包嵌套的原生异常捕获机制；在 Agent 实例级提供了 `.clone(new_name=..., **kwargs)` 实时热加载与动态反射方法。
- **底层修复：** 修复了语法树将 `img()` 以及 `secret()` 解析为通用函数时无法正确向 Python AST 转译并阻断流程的问题；明确了 `fallback` 关键字惰性求值 lambda 的正确翻译层映射。

### v0.5 编排时代 (The Orchestration Era)
- **核心特性：** 实现了真正的运行时模块（`src.runtime.*`），支持智能体协同编排、LLM 推理、路由和记忆状态管理。
- **AST/Runtime 变更细节：** 
  - 完全重写了 Lark EBNF 语法 (`nexa_parser.py` 和 `ast_transformer.py`)，正确映射 `match intent`、管道 `>>`、`loop until` 以及 `join` 并发组合。
  - 重构了 `code_generator.py`，将原本静态的字符串拼接转换为智能的 DAG（有向无环图）生成逻辑，与 Python Runtime 无缝桥接。
  - 构建了原生 Python 沙盒环境集 (`tools_registry.py`) 以支持工具调用。增强了 `agent.py`，能够递归解析 `tool_calls` 并调用本地函数执行后原生追加上下文。
- **踩坑记录：** 解决了 AST Payload 翻译时关于字典键值对和作用域映射 (`locals()`) 的诸多前沿解析错误。修复了通过 AST 向 `Agent.run()` 方法中依次正确传递多变量参数导致的上下文丢失问题。

### v0.6 模块化与安全时代 (Modularity and Safety)
- **核心特性：** 推出了基于 `.nxs` 的密钥注入机制与基于 `.nxlib` 的代码模块化复用机制。
- **AST/Runtime 变更细节：**
  - 在 `src/runtime/secrets.py` 中实现了原生 `secret("KEY")` 特性，避免了代码库中硬编码敏感鉴权信息。
  - 扩充了抽象语法树规则，首创了 `include "xx.nxlib"` 规则。只需在脚本文本顶部挂载，即可利用深度字典合并预处理多级 AST 树结构。

### v0.7 基础标准库扩容 (Standard Library Expansion)
- **核心特性：** 原生支持文件 I/O (`fs`)、网络请求 (`http`) 及时间系统 (`time`) 的 `std` 标准库。
- **AST/Runtime 变更细节：** 
  - 构建了 `src/runtime/stdlib.py`，包含具体的物理映射工具 (`std_fs_read_file` 等)。
  - 增强了 `code_generator.py` 的通配符映射，让 `uses std.fs` 能够自动下钻加载库中的关联子函数。
- **踩坑记录：** Minimax 对 Schema 格式有着极为苛刻的要求；为了消除模型被拒现象，对工具层 Schema 解析器去除了所有外部不符合 OpenAI 严格格式的包装器。

### v0.8 协议约束与沙盒架构演进 (Architecture Changes)
- **核心特性：** 新增 `protocol` 协议声明输出约束，多模型服务商动态路由分发机制，并开启了原生的 Human-in-the-loop 支持。
- **AST/Runtime 变更细节：**
  - 将 Nexa 脚本内声明的结构体转化为 Python Pydantic 实体类拦截返回机制，并通过 OpenAI Response Format JSON Schema 强行规范数据输出，内置失败自动重试恢复逻辑。
  - 将 `.model` 属性解析器拆分为 `provider/model_name` 双轨制引擎。配合 `secrets.py` 中的 `OPENAI_`, `MINIMAX_`, `DEEPSEEK_` 前缀实现了灵活的模型接入支持。
  - 设计了使用 `sys.stdin.readline` 的阻塞式 `std.ask_human` 系统并处理了多测试层的输入刷写问题。
  - **v0.8.1：** 支持原生 Markdown 工具库导入解析 (通过提取 `## Tool: <name>` 下置 JSON 解析)，完善了单智能体 `persistent` 本地 JSON 的会话存储和 `stream` 终端流式打印。

#### v0.8.2 多模态视觉与韧性执行 (Multi-modal & Resilience) 
- **核心特性：** 实现了多模态内建引擎 `img` 及处理执行层崩溃流的引擎级容错兜底关键字 `fallback`。
- **AST/Runtime 变更细节：**
  - 实现了 `fallback` 的核心 Python Runtime 函数（注入双重回调以完成容错兜底拦截），并修补了 AST Lark 引擎对原版 `Tree` 的子节点直接暴串导致的崩溃错误。
  - 重设了 `ast_transformer.py` 下的 `method_call` 和 `FunctionCallExpression` 逻辑以支持裸函数如 `img("...", args)` 和 `print(xx)` 的调用解析。
  - **踩坑记录：** 嵌套解包导致的 JSON 序列化报错；必须深层抽取 `.children` 数据才可保证 AST 的正确输出。

### v0.9-alpha 测试引擎、宿主互操作与原生扩展 (Test Framework, Interop & Native MCP)
- **核心特性：**
  - **原生测试框架 (Test Framework)：** 引入 `test` 与 `assert` 一等公民语法，支持批量隔离测试与独立断言。配合 `nexa test` CLI 提供沉浸式通过报告。
  - **宿主互操作性 (Python SDK Interop)：** 构建 `src.api.NexaRuntime` 允许外部 Python 系统 (如 FastAPI 等 Web 框架) 将 `.nx` 作为无头脚本通过 `run_script()` 加载执行，实现应用系统对 Agent 业务流的双向调用与入参注入 (`importlib` 动态模块桥接)。
  - **MCP 原生接入 (Native MCP Uses)：** 解析层新增 `mcp:"<uri>"` 语法定义，允许智能体直接读取远程/本地方言协议的 JSON 快速转化为内部 Tools Schema，极大扩展后端沙盒生态能力边界。
  - **语义阻断 (Heuristic Fast-Path)：** `semantic_if` 追加了基于正则表达式的局部匹配短路能力 (`fast_match`)，在拦截常规意图时直接绕过底层模型调用，显著优化并发性能并降低 token 消耗。
- **AST/Runtime 变更细节：**
  - 修补 Lark 解析器的 `use_identifier` 及 `semantic_if_stmt` 增加可选字面量支持。代码生成器配合追加对应解析链并完成动态函数映射 (`fetch_mcp_tools`, `__nexa_inputs__` 等)。
