# Nexa 编译器与运行时架构 (v0.9-alpha)

在 v0.9-alpha 阶段，Nexa 的底层链路经历了颠覆性重构。它不再像最初版本那样仅作为粗糙的文本生成器（Boilerplate Injector），而是跨越到了完备的 **AST 转译 + 原生 Python SDK 交互 (NexaRuntime)** 模式，并在底层集成了高速匹配机制与 MCP 支持。

## 1. 前端阶段 (Frontend Lex & Parse)

Nexa 前端依然基于 `Lark` 框架解析词法与语法，保障开发者撰写规则的灵活性（Start Small 策略）。Lark 利用 Earley 算法，能够迅速完成由上下文无关文法（CFG）到 Python 内部类结构的转化。

转译后的 AST 设计在 v0.9-alpha 极大分离了状态管理和表达式层级：
在处理类似于 `test "demo"` 或 `mcp:"..."` 的指令时，前端生成的 AST 会产生专门的 `TestDeclaration` 以及 `ToolMCPConfig` 节点。

## 2. 后端生成与 Python SDK Interop

过去，Nexa 会直接将所有依赖的庞大 LLM 客户端代码通过强行粘贴字符串的方式打在生成的代码头部。
自 v0.9-alpha 起，转译引擎彻底废弃了这种 “Boilerplate Injection” 黑魔法，转而使用更加现代化的 **SDK Interop** 模式与 `importlib` 动态模块加载技术。

生成的代码将会通过 `importlib` 调用位于 `src.api.NexaRuntime` 下的标准运行时对象：

```python
# 生成的模块结构示意
from src.api.nexa_runtime import NexaRuntime

runtime = NexaRuntime()
bot = runtime.create_agent("FinancialAnalyst", model="claude-3.5-sonnet")
```
这种设计让底层 Python API 继续被标准 IDE 生态复用，使得我们可以针对 NexaRuntime 进行独立的单元测试与 Mocking 注入。

## 3. Fast-Path 启发式评估 (Heuristic Fast-Path)

针对 `semantic_if` 的昂贵网络 I/O，Nexa 编译器在代码生成过程中加入了 `Fast-Path` 降级支持：

当遇到 `semantic_if ... fast_match r"..."` 时，生成的 Python 后端代码首先使用 `re.search` 执行本地 CPU 正则匹配。如果在 O(1) 性能下就确定能捕捉特征要素，便会阻止向 `gpt-4o-mini` 发起的结构化断言调用（Structured Output Request），极大降低了系统的 Token 损耗。

## 4. MCP 原生集成策略

在解析 `tool { mcp: "..." }` 时，编译器不会生成普通的 Python Native 工具适配器。它将直接为目标 URI 编译出一条专属的异步通信管线协议（JSON-RPC based on Model Context Protocol）。
在执行期，NexaRuntime 接管该 URI 连接并映射为 Agent 可视的动态函数声明，无缝适配 Claude Desktop 甚至更广泛的生态标准。
