# Nexa 语言架构师记忆库 (MEMORY_BANK)

> **[Agent 核心指令]** 每次对话开始时，你必须首先读取并遵循此文件。每次完成重大修改后，你必须主动更新此文件中的【进度追踪】和【踩坑记录】。

## 1. 核心教条 (Core Tenets)
- **Think Big, Start Small:** 我们最终要构建基于 WASM 的 AVM (Agent Virtual Machine)，但目前 (v0.1) 只做 Python 转译器 (Transpiler)。
- **拒绝过度工程:** 不手写底层网络协议，全面拥抱现有的成熟 SDK（OpenAI Python SDK, Pydantic, Tenacity, Lark）。
- **确定性至上:** 将 LLM 的概率输出限制在极小范围内（如强制使用 Structured Output 约束 `semantic_if` 返回 `{matched: bool, confidence: float}`）。
- **多轮检查:** 在每个阶段结束时，必须进行至少两轮的代码审计和测试，确保生成的 Python 代码不仅正确，而且健壮（例如在 `semantic_if` 的实现中注入重试机制）。同时，你应该重复读入并更新此 MEMORY_BANK和其他有修改的文件，以便在后续阶段中避免重复犯错。
- **禁止懒惰:** 不允许在任何阶段中为了赶进度而牺牲代码质量或架构设计。每次提交的代码都必须是可审计、可测试、且符合生产级标准的。

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

## 5. 未来架构演进备忘录 (Transition to v0.5)
- **Boilerplate 的瓶颈：** 目前我们在 `code_generator.py` 中强塞了大段的 Python SDK 初始化和工具链代码。但随着 v0.5 将引入 **多 Agent 并发 (join)**、**Unix 风格管道 (`>>`)**、**全局/共享 Memory 管理** 等高级并发功能，仅靠字符串模板生成代码将会引发灾难级的代码爆炸和难以调试。
- **重构方向：** 下一个周期的首要任务是建设和抽离 `runtime/` 目录。Nexa 的 `code_generator` 应单纯只向外输出简单的 **DAG / Workflow 编排调用图**。对 `openai` 接口的访问拦截、`tenacity` 重试管理、`critic loop` 共识系统，必须封装沉淀进一套名为 `nexa.runtime` 的底层库支撑中。为进军 AVM 沙盒化铺路。

## 6. 项目生态与开源包装 (Open Source Ecosystem)
- 通过 setuptools 编写 setup.py 并注册 entry_points (nexa=src.cli:main)。
- 重新构筑史诗级 README.md 与开发者第一视角的 06_quick_start_guide.md。完成了 MVP 最终开源面貌的打包。
