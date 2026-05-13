# Nexa v2.0 — Vision and Architecture Blueprint

> **定位声明**: Nexa v2.0 是 **the first ever Harness Native Programming Language**。
> 正如 Rust 之于传统编程安全——通过所有权系统在编译期消灭内存错误，
> Nexa v2.0 之于 Agent 开发——通过 Harness 原语在语言层消灭 Agent 的不确定性失控。

---

## 1. 时代背景与核心矛盾

### 1.1 从 v1.x 到 v2.0 的范式跃迁

Nexa v1.x 的设计哲学是 **"Agent-Native DSL"**——将 LLM 调用和编排做成一等公民。这在 v1.3.7 中已经实现：`agent` 声明、`flow` 编排、`semantic_if`、`loop until`、DAG 操作符、契约式编程等。

但 v1.x 存在一个根本性的架构缺陷：**它只解决了"如何方便地调用 LLM"，却没有解决"如何让 LLM 的行为可控、可观测、可验证"**。

当前的 `NexaAgent` 本质上是一个 OpenAI client wrapper——它发送消息、接收回复、没有自主循环、没有上下文自动管理、没有错误自愈、没有执行沙箱。用 v1.x 写出的 Agent 无法像 Claude Code 或 Devin那样进行长周期的自主任务执行。

### 1.2 Harness Agent 的核心洞察

参考 `docs/others/Harness_Agent.md` 的核心公式：

> **Agent = Model + Harness**

模型提供概率性推理，Harness 提供确定性控制。当前 Nexa v1.x 只有 Model 层（LLM 调用），缺少 Harness 层。

Harness 的六元组定义 $H = (E, T, C, S, L, V)$：

| 元组分量 | 含义 | Nexa v1.x 状态 | Nexa v2.0 目标 |
|----------|------|---------------|---------------|
| **E** — Execution Loop | 执行循环引擎 | ❌ 无自主循环，仅单次 `agent.run()` | ✅ `autoloop` 原语，ReAct 循环内置 |
| **T** — Tool Registry | 工具注册表 | ⚠️ 手动 `tool` 声明 + JSON Schema | ✅ `@tool` 零成本绑定 + 自动 Schema 生成 |
| **C** — Context Manager | 上下文管理器 | ❌ 裸 `messages[]` 列表，无自动管理 | ✅ `with_context` 作用域 + 自动 eviction |
| **S** — State Store | 状态存储 | ⚠️ 简单 `MemoryManager` dict | ✅ COW 状态树 + 持久化快照 + KV/Vector 双存储 |
| **L** — Lifecycle Hooks | 生命周期钩子 | ❌ 无任何钩子机制 | ✅ `before_step`/`after_step`/`on_error` 钩子 |
| **V** — Evaluation Interface | 评估接口 | ⚠️ IAL 仅用于测试 | ✅ Harness 内置验收 + AST 静态护栏 |

### 1.3 Real Agent 的能力差距

参考 `docs/others/Real_Agent.md`，要开发出 Claude Code 级别的自主 Agent，需要五大核心能力：

| 能力维度 | Real Agent 要求 | Nexa v1.x 现状 | 差距 |
|----------|----------------|---------------|------|
| **核心原语** | Prompt-as-Code + 结构化输出 + 模型路由 | `agent { prompt: "..." }` 裸字符串 | 需要模板化 Prompt + 输出约束 + 动态路由 |
| **上下文管理** | Context Scoping + Auto-Eviction + 工作/长期记忆分离 | 裸 `messages[]` | 需要完整 Context Manager |
| **动作与环境** | 零成本 Tool + 沙箱 + HITL | 手动 `tool` 声明 + 无沙箱 | 需要自动 Tool + 沙箱 + 权限控制 |
| **Agentic 控制流** | ReAct Loop + Branch/Backtrack + Actor Model | `loop until` 仅语义循环 | 需要 `autoloop` + `fork/snapshot` + Actor |
| **容错与可观测** | AI Try-Catch + 思维轨迹 | 普通 `try/catch` | 需要 `try_agent` + Trace 系统 |

---

## 2. v2.0 架构设计哲学

### 2.1 三层设计原则

Nexa v2.0 的架构遵循三条不可妥协的原则：

**原则一：Harness 是语言的灵魂，不是库**

> Rust 的所有权不是 `std::own` 库，而是 `let`/`move`/`borrow` 语法。
> Nexa 的 Harness 不是 `nexa.harness` 模块，而是 `autoloop`/`with_context`/`@tool`/`try_agent` 语法。

这意味着 Harness 的核心约束必须在编译期通过 AST 分析强制执行，而非运行时可选启用。

**原则二：确定性主干 + 非确定性分支**

> Harness 提供确定性主干（执行循环、上下文边界、安全护栏），
> Model 提供非确定性分支（推理、选择、生成）。
> 编译器验证主干，运行时包容分支。

**原则三：渐进式 Harness 强度**

> 类似 Rust 的 `unsafe` 块，Nexa 提供 `unharnessed` 块。
> 默认所有 Agent 代码受 Harness 保护；
> 开发者可在明确标注的 `unharnessed` 块中绕过特定约束。

### 2.2 与 v1.x 的关系：演进而非推翻

v2.0 不是从零开始。v1.x 已有的优秀设计将被保留并增强：

| v1.x 保留设计 | v2.0 增强方向 |
|--------------|-------------|
| `agent` 声明 | 增加 `autoloop`/`context_policy`/`lifecycle` 子声明 |
| `tool` 声明 | 增加 `@tool` 注解式零成本绑定 |
| `protocol` 声明 | 增加为结构化输出约束的运行时强制 |
| `flow` 编排 | 增加为 Harness Execution Loop 的声明式入口 |
| `semantic_if` | 保留，作为 Harness 评估接口的一部分 |
| `loop until` | 保留，但增加 `autoloop` 作为更强大的替代 |
| DbC 契约 | 增强为 Harness Lifecycle Hooks 的前置/后置条件 |
| COW 状态 | 增强为 Harness State Store 的核心实现 |
| DAG 操作符 | 增强为 Harness 多 Agent 编排的基础 |
| AVM | 从"未来目标"变为 v2.0 的核心执行引擎 |

**需要抛弃的 v1.x 设计：**

| v1.x 设计 | 抛弃原因 | v2.0 替代 |
|----------|---------|----------|
| 裸 `messages[]` 上下文 | 无自动管理，导致 OOM | `ContextManager` + `with_context` 作用域 |
| `agent.run()` 单次调用 | 无法自主循环 | `autoloop` + `agent_loop` 内置循环 |
| 手动 `tool` JSON Schema | 繁琐且易错 | `@tool` 自动 Schema 生成 |
| Python 转译为唯一后端 | 性能瓶颈 + 无沙箱 | AVM 字节码为首要后端 |
| `MemoryManager` 简单 dict | 无分层无持久化 | COW + KV + Vector 三层存储 |

---

## 3. v2.0 总体架构蓝图

### 3.1 架构全景图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Nexa v2.0 — Harness Native Architecture              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Layer 1: Language Frontend                     │   │
│  │  .nx 源码 → Lark Parser → AST Transformer → Harness Validator   │   │
│  │  (新增: Harness AST 节点 + 静态护栏分析 + 编译期约束检查)         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ↓                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Layer 2: Compiler Middle-end                   │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐  │   │
│  │  │ Python Backend   │  │ AVM Bytecode     │  │ WASM Backend   │  │   │
│  │  │ (兼容 v1.x)      │  │ Backend (主目标)  │  │ (Tool 沙箱)    │  │   │
│  │  └─────────────────┘  └──────────────────┘  └────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ↓                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Layer 3: Harness Runtime                       │   │
│  │                                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │              H = (E, T, C, S, L, V) — 六元组实现             │ │   │
│  │  │                                                             │ │   │
│  │  │  E ┌──────────┐  T ┌──────────┐  C ┌───────────────────┐  │ │   │
│  │  │    │ Execution│    │ Tool     │    │ Context           │  │ │   │
│  │  │    │ Loop     │    │ Registry │    │ Manager           │  │ │   │
│  │  │    │ Engine   │    │ + Sandbox│    │ + Eviction        │  │ │   │
│  │  │    └──────────┘    └──────────┘    └───────────────────┘  │ │   │
│  │  │                                                             │ │   │
│  │  │  S ┌──────────┐  L ┌──────────┐  V ┌───────────────────┐  │ │   │
│  │  │    │ State    │    │ Lifecycle│    │ Evaluation        │  │ │   │
│  │  │    │ Store    │    │ Hooks    │    │ Interface         │  │ │   │
│  │  │    │ COW+KV   │    │ + Guards │    │ + AST Validator   │  │ │   │
│  │  │    └──────────┘    └──────────┘    └───────────────────┘  │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                                                                    │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐ │   │
│  │  │ LLM Router     │  │ Actor System   │  │ Trace & Observability│ │   │
│  │  │ (Model-Agnostic)│  │ (Multi-Agent)  │  │ (思维轨迹追踪)       │ │   │
│  │  └────────────────┘  └────────────────┘  └────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Harness 六元组在语言中的映射

这是 Nexa v2.0 最核心的设计决策——Harness 的每个元组分量都对应一个语言级原语：

| Harness 元组 | 语言原语 | 语法示例 | 编译期行为 |
|-------------|---------|---------|----------|
| **E** — Execution Loop | `autoloop` | `autoloop max_steps: 50 { step(); }` | 验证 exit condition 存在 |
| **T** — Tool Registry | `@tool` | `@tool fn grep(pattern: string): string { ... }` | 自动生成 JSON Schema + 注入上下文 |
| **C** — Context Manager | `with_context` | `with_context max_tokens: 100k { ... }` | 验证 eviction 策略存在 |
| **S** — State Store | `snapshot`/`restore` | `snap = snapshot(); restore(snap);` | 验证快照点在合法作用域内 |
| **L** — Lifecycle Hooks | `before`/`after`/`on_error` | `before_step { log(state); }` | 验证钩子不修改 Harness 状态 |
| **V** — Evaluation | `verify`/`assert_harnessed` | `verify result satisfies Protocol;` | AST 级静态检查 + 运行时验收 |

### 3.3 新增核心语法概览

```nexa
// ═══════════════════════════════════════════════════════════
// Nexa v2.0 — Harness Native 核心语法演示
// ═══════════════════════════════════════════════════════════

// 1. @tool — 零成本工具绑定 (Harness T)
@tool("Search for a pattern in the codebase")
fn grep(pattern: string, path: string = "."): string {
    return std.shell.exec("grep -rn #{pattern} #{path}");
}

@tool("Edit a specific file")
fn edit_file(path: string, search: string, replace: string): bool {
    return std.fs.edit(path, search, replace);
}

// 2. agent + autoloop — 自主执行循环 (Harness E + L)
agent BugFixer(issue: string) {
    system `
        You are an expert software engineer.
        Fix: #{issue}
    `
    
    // Harness C — 上下文策略
    context_policy {
        max_tokens: 100000,
        on_overflow: summarize_early_observations
    }
    
    // Harness L — 生命周期钩子
    before_step { trace.log("starting step", step_count); }
    after_step  { trace.log("completed step", step_count); }
    on_error    { trace.capture(error); }
    
    // Harness E — 自主循环
    autoloop max_steps: 50 exit_when: "issue is resolved" {
        // Harness V — AI 专属容错
        try_agent {
            step();  // 思考 → 选工具 → 观察
        } catch_correction(e: ToolError) {
            reflect `Tool failed: #{e.message}. Adjust and retry.`
        }
    }
}

// 3. with_context — 上下文作用域 (Harness C)
with_context max_tokens: 50000 strategy: sliding_window {
    result = BugFixer.run("Fix NullPointerException in auth.js");
}

// 4. fork/snapshot — 并行探索与回溯 (Harness S)
snap = snapshot();  // 保存当前状态
fork [
    path_a = BugFixer.run("Approach A: fix null check"),
    path_b = BugFixer.run("Approach B: add try-catch")
] merge best;
// 如果两条路径都失败，回溯到快照点
restore(snap) if path_a.failed and path_b.failed;

// 5. verify — Harness 验收 (Harness V)
verify result satisfies AnalysisReport;
verify result.code_compiles();
verify result.tests_pass();

// 6. unharnessed — 绕过 Harness 约束的显式标注
unharnessed {
    // 这里可以执行不受 Harness 保护的危险操作
    // 编译器会发出警告，运行时会记录到 trace
    std.shell.exec("rm -rf /tmp/test_build");
}
```

### 3.4 编译期 Harness 验证流程

```
.nx 源码
    │
    ↓ Lark Parser
Parse Tree
    │
    ↓ AST Transformer (新增 Harness AST 节点)
Enhanced AST
    │
    ↓ Harness Validator (新增编译期检查)
    │
    ├── ✅ 检查1: 每个 autoloop 必须有 exit_when 或 max_steps
    ├── ✅ 检查2: 每个 @tool 函数必须有 description 注解
    ├── ✅ 检查3: 每个 with_context 必须有 eviction 策略
    ├── ✅ 检查4: 每个 try_agent 必须有 catch_correction
    ├── ✅ 检查5: 高危操作必须在 unharnessed 块中
    ├── ✅ 检查6: verify 语句的目标必须是已声明类型
    ├── ✅ 检查7: snapshot/restore 必须在合法作用域内
    ├── ✅ 检查8: lifecycle hooks 不能修改 Harness 内部状态
    │
    ↓ (验证通过)
    │
    ├──→ Python Backend (兼容模式)
    ├──→ AVM Bytecode Backend (主目标)
    └──→ WASM Backend (Tool 沙箱)
```

---

## 4. v1.x → v2.0 架构差距分析

### 4.1 编译器层面差距

| 维度 | v1.x | v2.0 需要 | 改动量 |
|------|------|----------|--------|
| Parser 语法规则 | ~30 条核心规则 | ~50 条（新增 Harness 原语） | **中** |
| AST Transformer | ~60 个 handler | ~90 个（新增 Harness 节点） | **中** |
| Harness Validator | ❌ 不存在 | ✅ 全新模块，8+ 条验证规则 | **大** |
| Code Generator | Python-only BOILERPLATE | 多后端（Python + AVM + WASM） | **大** |
| 类型系统 | 渐进式，运行时可选 | Harness 强制 + 渐进式可选 | **中** |

### 4.2 运行时层面差距

| 维度 | v1.x | v2.0 需要 | 改动量 |
|------|------|----------|--------|
| Execution Loop | ❌ 无 | ✅ `autoloop` ReAct 循环引擎 | **大** |
| Context Manager | ❌ 裸 messages[] | ✅ 自动 eviction + 作用域 | **大** |
| Tool Registry | 手动声明 | ✅ `@tool` 自动绑定 + Schema | **中** |
| State Store | 简单 dict | ✅ COW + KV + Vector + 快照 | **大** |
| Lifecycle Hooks | ❌ 无 | ✅ before/after/on_error 钩子 | **中** |
| Evaluation | IAL 仅测试 | ✅ Harness 内置验收 + AST 检查 | **大** |
| Sandbox | ❌ 无 | ✅ WASM 沙箱 + 权限控制 | **大** |
| LLM Router | 固定 model 字符串 | ✅ 动态路由 + 能力声明 | **中** |
| Actor System | ❌ 无 | ✅ spawn/message/pass 模型 | **大** |
| Trace | ❌ 无 | ✅ 思维轨迹 + 可观测性 | **大** |

### 4.3 AVM 层面差距

| 维度 | v1.x AVM | v2.0 AVM 需要 | 改动量 |
|------|---------|-------------|--------|
| 字节码指令集 | ~30 条基础指令 | ~80 条（新增 Harness 指令） | **大** |
| VM Interpreter | 简单栈式 | ✅ Harness-aware 解释器 | **大** |
| Scheduler | 基础优先级调度 | ✅ DAG + Work-Stealing + Actor | **中** |
| Context Pager | 已有基础 | ✅ 增强为 Harness Context Manager | **中** |
| COW Memory | 已有基础 | ✅ 增强为 Harness State Store | **中** |
| Tool Registry | 基础 | ✅ 增强为 Harness Tool + Sandbox | **中** |
| WASM Sandbox | 框架存在 | ✅ 完整实现 + 资源限制 | **中** |

---

## 5. v2.0 核心创新点总结

### 5.1 语言层创新

1. **`autoloop` — 自主执行循环原语**: 将 ReAct 循环从 Python 胶水代码提升为语言关键字，编译器强制验证退出条件
2. **`@tool` — 零成本工具绑定**: 函数注解自动生成 JSON Schema，消除手动声明负担
3. **`with_context` — 上下文作用域**: 将 Context Window 管理从运行时技巧提升为语言级作用域，编译器强制验证 eviction 策略
4. **`try_agent` / `catch_correction` — AI 专属容错**: 将 LLM 错误自愈从 try-catch 异常处理提升为"错误反馈→模型重试"的闭环
5. **`snapshot` / `restore` / `fork` — 状态分支与回溯**: 将 Tree-of-Thoughts 从算法技巧提升为语言原语
6. **`verify` — Harness 验收**: 将验收标准从测试框架提升为编译期+运行时双重强制
7. **`unharnessed` — 显式约束绕过**: 类似 Rust `unsafe`，允许在明确标注处绕过 Harness 保护

### 5.2 运行时创新

1. **Harness Execution Engine**: 六元组 $H = (E, T, C, S, L, V)$ 的完整运行时实现
2. **Context Manager with Auto-Eviction**: 滑动窗口 + 智能摘要 + 工具输出卸载的三层压缩
3. **WASM Tool Sandbox**: 工具执行在 WASM 微沙箱中，资源受限 + 网络隔离
4. **Actor-based Multi-Agent**: spawn/message/pass 模型，取代简单的 ThreadPoolExecutor
5. **Trace & Observability System**: 每步推理、工具调用、终端输出自动记录为可可视化决策树

### 5.3 编译器创新

1. **Harness Validator**: 编译期强制检查 Harness 约束的完整性
2. **Multi-Backend Code Generation**: Python（兼容）+ AVM Bytecode（主目标）+ WASM（Tool 沙箱）
3. **AST-level Security Scanning**: 在 AST 转换阶段进行安全护栏检查，而非运行时正则匹配

---

## 6. 与竞品的差异化定位

| 竞品 | 定位 | Nexa v2.0 差异化 |
|------|------|-----------------|
| **Claude Code** | 单一产品，非语言 | Nexa 是语言，任何人可以用 Nexa 写出自己的 Claude Code |
| **Devin / OpenDevin** | Python + Docker 胶水 | Nexa 的 Harness 是语言级原语，不需要胶水代码 |
| **LangGraph** | Python 库 | Nexa 的编排是编译期验证的，不是运行时可选的 |
| **AutoGPT / BabyAGI** | Python 脚本 | Nexa 有上下文自动管理、错误自愈、状态快照 |
| **Mastra / Atomic Agents** | TS/Python 框架 | Nexa 是 DSL，框架逻辑沉淀为语法关键字 |
| **Rust** | 系统语言 | Nexa 借鉴 Rust 的"编译期消灭错误"哲学，但面向 Agent 不确定性 |

**核心差异化一句话**:

> 其他所有方案都在用通用语言写胶水代码来管理 Agent 的不确定性；
> Nexa v2.0 把这种管理沉淀为语言的底层关键字，编译器帮你消灭 Harness 缺失导致的失控。

---

## 7. 风险与挑战

### 7.1 技术风险

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| AVM 字节码后端开发周期长 | v2.0 交付延迟 | Python 后端先行，AVM 渐进迁移 |
| Harness Validator 规则过严 | 开发者体验变差 | `unharnessed` 块 + 渐进式强度 |
| WASM 沙箱性能开销 | Tool 执行变慢 | 预热池 + 热路径 bypass |
| LLM Router 动态路由不稳定 | Agent 行为不一致 | 确定性 fallback + 人类确认断点 |
| 语法膨胀过快 | Parser 维护困难 | 模块化语法扩展 + exclusion keyword |

### 7.2 生态风险

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| v1.x 用户迁移成本 | 社区分裂 | v2.0 Python 后端兼容 v1.x 语法 |
| 开发者学习曲线 | 采用率低 | 渐进式 Harness：从 `unharnessed` 开始 |
| AVM 工具链不成熟 | 开发调试困难 | 先用 Python 后端开发，AVM 仅用于生产部署 |

---

## 8. 下一步：详细规划文档索引

本蓝图是 v2.0 规划的总纲。以下四个文档分别从不同维度展开详细设计：

| 文档 | 维度 | 核心内容 |
|------|------|---------|
| [`02_Language_Design_Specification.md`](02_Language_Design_Specification.md) | 语言设计 | 新增语法的完整规范、类型系统、语义定义 |
| [`03_Harness_Native_Runtime_Architecture.md`](03_Harness_Native_Runtime_Architecture.md) | 运行时架构 | 六元组实现细节、Context Manager、Sandbox、Actor |
| [`04_Compiler_and_Toolchain_Redesign.md`](04_Compiler_and_Toolchain_Redesign.md) | 编译器与工具链 | Harness Validator、多后端 Code Gen、AVM 字节码设计 |
| [`05_Implementation_Roadmap.md`](05_Implementation_Roadmap.md) | 实施路线图 | 分阶段交付计划、里程碑、依赖关系 |