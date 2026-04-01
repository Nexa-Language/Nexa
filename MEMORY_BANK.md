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

## 1.2 v1.0 Rust AVM + WASM 架构演进 (已完成 ✅)

### 核心目标
从 Python 脚本解释转译模式跨越至基于 Rust 编写的独立编译型 Agent Virtual Machine (AVM)。

### 实现阶段

#### Phase 1: 编译器前端 (Lexer + Parser) - 已完成 ✅
- [x] 创建 `avm/` 目录结构
- [x] 实现 Rust 词法分析器 (logos v0.14) - 支持所有 Nexa 语法
- [x] 实现 Rust 语法解析器 (递归下降) - 完整语法支持
- [x] 定义 Rust AST 类型 - 完整 AST 定义
- [x] 测试与 Python 解析器输出一致性 - 所有测试通过

#### Phase 2: 字节码编译器 - 已完成 ✅
- [x] 设计字节码指令集 - 50+ 指令
- [x] 实现 AST -> Bytecode 编译器 - 完整实现
- [x] 实现 BytecodeModule 序列化
- [x] 支持常量池、符号表、调试信息

#### Phase 3: AVM 运行时 - 已完成 ✅
- [x] 实现栈式虚拟机
- [x] 实现异步调度器 (Tokio)
- [x] 实现 Agent 运行时
- [x] 实现 LLM 客户端集成
- [x] 实现 Tool 执行器

#### Phase 4: WASM 沙盒 - 已完成 ✅
- [x] 集成 WASM 运行时 (wasmtime, 可选 feature)
- [x] 实现 WASI 接口支持
- [x] 实现资源限制和沙盒安全
- [x] 实现权限控制系统

#### Phase 5: FFI 集成 - 已完成 ✅
- [x] Python FFI (PyO3 绑定)
- [x] C FFI (完整 C API)
- [x] 82 个测试全部通过

#### Phase 6: 智能调度器增强 - 已完成 ✅
- [x] 优先级队列调度
- [x] 负载均衡策略 (RoundRobin/LeastLoaded/Adaptive)
- [x] DAG 拓扑排序与并行度分析
- [x] 资源分配优化
- [x] 14 个调度器测试通过

#### Phase 7: 向量虚存分页 - 已完成 ✅
- [x] ContextPager 核心实现
- [x] MemoryPage 页面管理
- [x] LRU/LFU/Hybrid 淘汰策略
- [x] 嵌入向量相似度搜索
- [x] 页面压缩与刷新
- [x] 14 个分页测试通过

### 测试统计
- **总测试数**: 110 个
- **通过率**: 100%
- **模块覆盖**: 编译器、字节码、运行时、WASM、FFI、调度器、分页器

### 性能目标
| 指标 | Python 转译器 | Rust AVM |
|------|--------------|----------|
| 编译时间 | ~100ms | ~5ms |
| 启动时间 | ~500ms | ~10ms |
| 内存占用 | ~100MB | ~10MB |
| 并发 Agents | ~100 | ~10000 |

详细规划见: `plans/v1.0_rust_avm_roadmap.md`

---

## 1.3 v1.0.1-beta 新增特性 (2026-03-31)

### 核心功能
- [x] **传统控制流：** 确定性的 if/else if/else、for each、while、break、continue 语句。
- [x] **Python 逃生舱：** 使用 `python! """..."""` 语法直接嵌入 Python 代码。
- [x] **二元运算符扩展：** 支持 +、-、*、/、% 算术运算。
- [x] **比较运算符：** 支持 ==、!=、<、>、<=、>= 比较运算。
- [x] **逻辑运算符：** 支持 and、or 逻辑运算。

### 实现细节
- **Parser 层修改：** `src/nexa_parser.py` - 新增 EBNF 规则
  - `traditional_if_stmt`: 传统 if/else if/else 语句
  - `foreach_stmt`: for each 循环
  - `while_stmt`: while 循环
  - `python_escape_stmt`: Python 逃生舱
  - `CMP_OP`: 比较运算符终端
  - `BINARY_OP`: 二元运算符终端

- **AST Transformer 层修改：** `src/ast_transformer.py` - 新增 AST 节点转换
  - `TraditionalIfStatement`: 传统 if 语句 AST
  - `ForEachStatement`: for each 循环 AST
  - `WhileStatement`: while 循环 AST
  - `PythonEscapeStatement`: Python 逃生舱 AST
  - `BinaryExpression`: 二元表达式 AST
  - `ComparisonExpression`: 比较表达式 AST

- **Code Generator 层修改：** `src/code_generator.py` - 新增代码生成
  - 生成 Python if/elif/else 语句
  - 生成 Python for/in 循环
  - 生成 Python while 循环
  - 生成原生 Python 代码块

### 已知问题
- **else-if 链解析：** Earley 解析器在处理连续 else-if 时存在歧义问题，当前版本建议使用单一 if-else 或嵌套 if 结构。

### 文件变更
- `src/nexa_parser.py` - Parser 层
- `src/ast_transformer.py` - Transformer 层
- `src/code_generator.py` - Code Generator 层
- `docs/01_nexa_syntax_reference.md` - 语法文档
- `examples/16_native_controls_and_python.nx` - 示例文件

---

## 1.4 v1.0.x 已完成特性

### v1.0.4-beta: Python SDK COW Agent 状态 - 新增 ✅
- [x] **COW Agent State (Python SDK)：** `src/runtime/cow_state.py` - Python SDK 的 COW 实现
  - `CowAgentState` 类：O(1) clone() 实现
  - 支持 Tree-of-Thoughts 模式的多分支独立上下文
  - 性能测试：700x 加速比 (10K 数据)
- [x] **NexaAgent.clone() 重构：** 使用 COW 状态管理
  - `clone()`: O(1) COW 克隆
  - `clone_deep()`: O(n) 深拷贝（用于对比测试）
  - `get_cow_stats()`: 获取 COW 性能统计
- [x] **真实性能测试：** 删除模拟测试，使用真实运行时组件
  - `tests/test_real_cow_performance.py`: COW 性能测试
  - `tests/test_real_cache_hit_rate.py`: 缓存命中率测试
  - `avm/benches/paper_performance_bench.rs`: Rust AVM 基准测试
- [x] **WASM 默认配置：**
  - 内存限制：16MB（匹配论文声称）
  - 超时时间：30s

### v1.0.3-beta: Key Findings 实现 - 新增 ✅
- [x] **COW Memory (Copy-on-Write)：** `avm/src/vm/cow_memory.rs` - O(1) 状态分支快照
  - 论文声称：0.1ms vs 20,178ms (deep copy)，200,000x 性能提升
  - 支持 Tree-of-Thoughts 模式的多分支独立上下文
- [x] **Work-Stealing Scheduler：** `avm/src/vm/scheduler.rs` - Actor-based 并发调度
  - 支持工作窃取负载均衡
  - 多 Worker 并行任务执行
  - 负载均衡效率统计
- [x] **综合测试：** `test_tree_of_thoughts_with_cow_and_workstealing` - COW + Work-Stealing 联合测试

### v1.0.2-beta: Semantic Types (语义类型) - 新增 ✅
- [x] **语义类型语法：** `type Name = base_type @ "constraint"` - 支持带语义约束的类型定义
- [x] **Parser 层支持：** 新增 `type_decl`, `semantic_type`, `base_type`, `inner_type` EBNF 规则
- [x] **Transformer 层支持：** 处理 `TypeDeclaration`, `SemanticType`, `BaseType`, `GenericType`, `CustomType` AST 节点
- [x] **Code Generator 层支持：** 生成 Pydantic BaseModel 类，包含语义约束验证器
- [x] **歧义树处理：** 实现 `_ambig` 方法优先选择内置类型分支
- [x] **测试覆盖：** 创建 `tests/test_paper_features.py` 验证所有论文特性

### v1.0.1-beta: 传统控制流 & Python 逃生舱
- [x] **传统 if/else if/else 语句** - 确定性条件分支
- [x] **for each 循环** - 数组/集合遍历
- [x] **while 循环** - 确定性条件循环
- [x] **break/continue 语句** - 循环控制
- [x] **二元运算符扩展** - 支持加减乘除取模 (+, -, *, /, %)
- [x] **Python 逃生舱** - `python! """..."""` 内嵌 Python 代码

### v1.0.0
- [x] **Agent 友好文档：** `docs/NEXA_AGENT_GUIDE.md` - 语法速查表、代码模板、Agent写Agent指南。（v1.0 实现）
- [x] **Python SDK：** `src/nexa_sdk.py` - `nexa.run()`, `nexa.Agent()`, `nexa.compile()` 等 API。（v1.0 实现）
- [x] **调试器：** `src/runtime/debugger.py` - 断点、变量监视、单步执行、事件日志。（v1.0 实现）
- [x] **性能分析器：** `src/runtime/profiler.py` - Token消耗、执行时间追踪、性能报告。（v1.0 实现）
- [x] **标准库：** `src/runtime/stdlib.py` - HTTP请求、文件操作、JSON处理、加密、时间日期等内置工具。（v1.0 实现）

## 1.4 v0.9.x 已完成特性
- [x] **复杂拓扑 DAG 支持：** 扩展 `>>` 运算符，支持分叉、合流等高阶数据流转编排。（v0.9.7-rc 实现）
- [x] **原生异常处理：** 引入 `try/catch` 语法块，允许开发者在脚本层捕获运行时异常。
- [x] **运行时动态反射：** 支持在执行期动态生成新 Agent 实例或动态重载 Model 配置。
- [x] **RBAC 权限访问控制：** 为不同 Agent 或流定义安全角色，确保工具调用的最小权限原则。（v0.9.7-rc 实现）
- [x] **Open-CLI 深度接入：** 原生集成类似 `spectreconsole/open-cli` 的宿主命令行交互标准。（v0.9.7-rc 实现）
- [x] **编程语言层面的缓存机制：** 语义缓存、多级缓存。（v0.9.7-rc 实现）
- [x] **上下文压缩工具 compactor：** 原生上下文压缩。（v0.9.7-rc 实现）
- [x] **长久记忆文件系统：** CLAUDE.md 风格长期记忆。（v0.9.7-rc 实现）
- [x] **基于知识图谱的记忆管理：** 结构化记忆存储和查询。（v0.9.7-rc 实现）
- [x] **长期记忆后端支持：** SQLite、向量后端。（v0.9.7-rc 实现）

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

## 版本 v0.9.7-rc (The Enterprise & Cognitive Era)
### 核心特性
- **复杂拓扑 DAG 支持**:
  - 新增 DAG 操作符：`|>>` (分叉)、`&>>` (合流)、`??` (条件分支)。
  - `src/runtime/dag_orchestrator.py`: 实现 `dag_fanout`, `dag_merge`, `dag_branch`, `dag_parallel_map` 等核心函数。
  - 支持分叉(Fan-out)、合流(Fan-in)、条件分支、并行执行等高阶数据流转编排。
  - 示例：`examples/15_dag_topology.nx`。

- **增强缓存机制**:
  - `src/runtime/cache_manager.py`: 多级缓存系统（内存 L1 + 磁盘 L2）。
  - 语义缓存：基于输入相似度的智能匹配，减少重复 Token 消耗。
  - TTL 支持、缓存统计、缓存预热、LRU 驱逐策略。

- **上下文压缩工具 (Compactor)**:
  - `src/runtime/compactor.py`: 智能压缩对话历史。
  - 支持激进压缩（LLM 摘要）和渐进式压缩（分段处理）。
  - 实体提取、决策追踪、知识保留。

- **长期记忆系统**:
  - `src/runtime/long_term_memory.py`: CLAUDE.md 风格的持久化记忆。
  - 分类管理：经验、教训、知识、偏好。
  - Markdown 格式存储，易于阅读和编辑。
  - 自动学习：从对话中提取有价值信息。

- **知识图谱记忆管理**:
  - `src/runtime/knowledge_graph.py`: 结构化知识存储和推理。
  - 实体管理、关系推理、路径查询。
  - 支持从文本中自动提取知识三元组。
  - DOT 格式导出（用于可视化）。

- **长期记忆后端**:
  - `src/runtime/memory_backend.py`: 大规模记忆存储支持。
  - SQLite 后端：本地持久化，全文搜索 (FTS)。
  - 向量后端：语义相似度搜索。
  - 分层存储：内存 + 磁盘混合。

- **RBAC 权限控制**:
  - `src/runtime/rbac.py`: 角色基础的访问控制系统。
  - 预定义角色：admin、agent_standard、agent_readonly 等。
  - 工具访问控制、审计日志。
  - 权限装饰器：`@require_permission`。

- **Open-CLI 深度接入**:
  - `src/runtime/opencli.py`: 交互式命令行系统。
  - 富文本输出：颜色、表格、进度条。
  - 内置命令：run、build、test、agent、memory、cache、config。
  - 脚本执行支持。

- **架构演进规划**:
  - `docs/05_architecture_evolution.md`: 详细技术蓝图。
  - Rust AVM 底座设计、WASM 安全沙盒规划。
  - 可视化 DAG 编辑器、智能调度器。
  - 向量虚存分页设计。

### 新增文件
- `src/runtime/dag_orchestrator.py` - DAG 编排器
- `src/runtime/cache_manager.py` - 智能缓存管理器
- `src/runtime/compactor.py` - 上下文压缩器
- `src/runtime/long_term_memory.py` - 长期记忆系统
- `src/runtime/knowledge_graph.py` - 知识图谱
- `src/runtime/memory_backend.py` - 记忆后端
- `src/runtime/rbac.py` - RBAC 权限控制
- `src/runtime/opencli.py` - Open-CLI 系统
- `docs/05_architecture_evolution.md` - 架构演进规划
- `examples/15_dag_topology.nx` - DAG 拓扑示例

### AST/Runtime 变更细节
- 更新 `nexa_parser.py` 语法，支持 DAG 操作符。
- 扩展 `ast_transformer.py`，新增 DAG 表达式节点类型。
- 增强 `code_generator.py`，生成 DAG 调用代码。
- 更新 `agent.py`，集成新的缓存管理器。

### 踩坑记录
- DAG 操作符解析需要处理多种操作符优先级。
- 知识图谱实体合并时需要正确处理同名实体。

---

## 版本 v0.9.6-rc
### 核心特性
- **Secrets引擎重构**:
  - `secrets.nxs` 引入基于 AST 与 Regex 的混合块解析模型。
  - 支持 `property_access` 链式调用（譬如 `secrets.default.MODEL_NAME["strong"]`）。
  - 在语言层正式将 `include` 与 `uses` 进行规范，支持 `uses "secrets.nxs"` 直通底层密钥管理。
- **上下文治理体系** (Context Governance):
  - **静态高速缓存** (`cache: true`): 利用 `hashlib.md5` 提供调用签名，并在 `.nexa_cache/llm_cache.json` 中全量命中 LLM 缓存输出，极大减少重复Token请求计费。
  - **滑动窗口重写与压缩** (`max_history_turns`): 利用独立的轻量级大语言模型(譬如`gpt-4o-mini` 或 `deepseek-chat`)进行上下文无损合并与浓缩总结，大幅提升多轮长时对话能力。
  - **长图记忆植入** (`experience`): 主动读取并拉取 `.md` 知识库内容，合并注入 `system_prompt` 后段作为背景补充参数。
  
### 未来规划与已知局限
- 目前 `uses "secrets.nxs"` 属于语言层的特殊保留字路径，尚未做到全对象模块化的引用导入，计划后续全面收敛为 `Module.Variable` 体系。
- LLM 缓存系统暂未处理 `stream=True` 的全链路缓存异步回放，后续可扩展异步缓存发射器。

---

## 版本 v1.0.x 文档示例验证与语法同步 (Documentation Validation & Syntax Sync)
### 核心工作
- **文档示例全覆盖测试**: 从 `~/proj/nexa-docs` 提取所有文档中的 Nexa 示例代码，共 42 个示例：
  - Part 1 基础语法示例 (6 个)
  - Part 2 高级特性示例 (6 个)
  - Part 3 协议扩展示例 (5 个)
  - Part 4 标准库示例 (4 个)
  - Quickstart 快速入门示例 (10 个)
  - Reference Manual 参考手册示例 (11 个)
  
- **Python 编译器语法修复**:
  - `src/nexa_parser.py`: 新增 agent decorator 语法 (`@limit`, `@timeout`, `@retry`, `@temperature`)
  - `src/nexa_parser.py`: 新增 MCP/Python tool body 语法 (`mcp: "..."`, `python: "..."`)
  - `src/nexa_parser.py`: 新增 DAG `||` 和 `&&` 操作符 (`dag_fire_forget`, `dag_consensus`)
  - `src/nexa_parser.py`: 新增复杂 DAG 拓扑规则 (`dag_chain_tail`)
  - `src/ast_transformer.py`: 添加 `tool_body_mcp`, `tool_body_python`, `agent_decorator` 转换方法
  - `src/code_generator.py`: 更新工具生成逻辑支持 MCP/Python 声明

- **Rust AVM Lexer 同步**:
  - `avm/src/compiler/lexer.rs`: 新增 token 类型 (`Mcp`, `Python`, `Print`, `Join`, `Std`, `Img`, `Limit`, `Timeout`, `Retry`, `Temperature`)
  - `avm/src/compiler/lexer.rs`: 新增 `Regex(String)` 和 `Float(f64)` 字面量支持
  - 更新 `Token::name()` 和 `Display` trait 实现

### 测试结果
- **Python 测试**: 42/42 示例通过 (100%)
- **Rust AVM 测试**: 110/110 测试通过 (100%)

### 踩坑记录
- Agent decorator 需要使用 `@v_args(inline=False)` 来正确处理参数
- DAG `||` 操作符需要单独的语法规则处理标识符列表
- 复杂 DAG 拓扑需要 `dag_chain_tail` 规则来正确终止链式表达式
- Rust lexer 新增 token 必须同步更新 `Token::name()` match 语句
