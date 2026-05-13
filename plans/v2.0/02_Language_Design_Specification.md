# Nexa v2.0 — Language Design Specification

> 本文档定义 Nexa v2.0 的完整语言规范，包括新增 Harness 原语的语法、语义、类型系统演进，以及与 v1.x 的兼容性映射。

---

## 1. 设计原则

### 1.1 Harness Native 语法设计三定律

**定律一：Harness 原语必须是关键字，不是库函数**

```
❌ harness.autoloop(agent, max_steps=50)  // 库调用——可选、可绕过
✅ autoloop max_steps: 50 { step(); }     // 关键字——编译期强制验证
```

**定律二：每个 Harness 原语必须有编译期验证规则**

```
autoloop max_steps: 50 { step(); }
// 编译器验证: exit_when 或 max_steps 必须存在
// 编译器验证: 循环体内必须有 step() 或等效推进语句
```

**定律三：Harness 约束可以被显式绕过，但绕过必须被标注**

```
unharnessed {
    std.shell.exec("rm -rf /tmp/build");  // 编译器发出 WARNING
}
// 类似 Rust unsafe {}，但语义是"此处不受 Harness 保护"
```

### 1.2 语法演进策略

v2.0 采用**增量式语法演进**而非推翻式重设计：

- v1.x 所有语法保持有效（兼容模式）
- v2.0 新增语法作为**增强层**叠加在 v1.x 之上
- 编译器通过 `--harness=strict|warn|off` 标志控制 Harness 验证强度
- 默认 `--harness=warn`：v1.x 代码可编译但发出 Harness 缺失警告

---

## 2. 新增语法规范

### 2.1 `@tool` — 零成本工具绑定 (Harness T)

#### 2.1.1 语法定义

```ebnf
tool_annotation ::= "@tool" "(" STRING_LITERAL ")" tool_fn_def
tool_fn_def     ::= "fn" IDENTIFIER "(" param_list ")" [":" type_expr] block
param_list      ::= param ("," param)*
param           ::= IDENTIFIER ":" type_expr ["=" default_value]
default_value   ::= STRING_LITERAL | INT | FLOAT | BOOL
type_expr       ::= "string" | "int" | "float" | "bool" | "list" | "dict" | IDENTIFIER
```

#### 2.1.2 语义定义

`@tool` 注解将一个普通函数声明为 Harness Tool，编译器自动执行以下操作：

1. **Schema 生成**: 从函数签名 + description 字符串自动生成 JSON Schema
2. **上下文注入**: 将 Schema 自动注入到使用该 tool 的 agent 的 LLM 上下文
3. **权限标注**: 根据 `@tool` 的 `risk_level` 参数（默认 `low`）标注安全等级
4. **沙箱路由**: `risk_level=high` 的 tool 在 WASM 沙箱中执行

#### 2.1.3 示例

```nexa
// 基础 @tool
@tool("Search for a pattern in the codebase")
fn grep(pattern: string, path: string = "."): string {
    return std.shell.exec("grep -rn #{pattern} #{path}");
}

// 高风险 @tool — 需要 HITL 确认
@tool("Execute a shell command", risk_level: "high", requires_approval: true)
fn shell_exec(command: string): string {
    return std.shell.exec(command);
}

// 结构化输出 @tool
@tool("Parse a JSON config file")
fn parse_config(path: string): dict {
    return std.fs.read_json(path);
}
```

#### 2.1.4 编译期验证规则

| 规则 ID | 验证内容 | 错误级别 |
|---------|---------|---------|
| T-001 | `@tool` 函数必须有 description 字符串 | ERROR |
| T-002 | `@tool` 函数参数必须有类型标注 | WARN |
| T-003 | `risk_level=high` 的 tool 必须标注 `requires_approval` | ERROR |
| T-004 | `@tool` 函数不能有 `@unharnessed` 内部调用 | ERROR |

#### 2.1.5 与 v1.x `tool` 声明的兼容映射

```nexa
// v1.x 语法 (仍然有效)
tool Calculator {
    description: "Perform basic math operations",
    parameters: {"expression": "string"}
}

// v2.0 等价语法 (推荐)
@tool("Perform basic math operations")
fn calculator(expression: string): string {
    // 实现
}
```

编译器在 `--harness=warn` 模式下，遇到 v1.x `tool` 声明时发出：
> "WARNING: v1.x `tool` declaration lacks Harness binding. Consider migrating to `@tool` annotation."

---

### 2.2 `autoloop` — 自主执行循环 (Harness E)

#### 2.2.1 语法定义

```ebnf
autoloop_stmt ::= "autoloop" autoloop_config "{" autoloop_body "}"
autoloop_config ::= ["max_steps:" INT] ["exit_when:" STRING_LITERAL] ["timeout:" INT]
autoloop_body ::= autoloop_step | try_agent_stmt | lifecycle_hook_stmt | flow_stmt
autoloop_step ::= "step" "(" ")" ";"
```

#### 2.2.2 语义定义

`autoloop` 实现 ReAct (Reason-Act-Observe-Reflect) 循环的完整生命周期：

```
autoloop 执行流程:
  ┌─────────────────────────────────────────────┐
  │  1. Reason:  LLM 分析当前状态，决定下一步     │
  │  2. Act:     选择并执行一个 Tool               │
  │  3. Observe: 收集 Tool 执行结果                │
  │  4. Reflect: 评估结果，决定是否继续             │
  │                                              │
  │  退出条件:                                    │
  │  - exit_when 语义条件满足 (LLM 判定)           │
  │  - max_steps 达到上限                          │
  │  - timeout 超时                               │
  │  - 不可恢复错误                                │
  └─────────────────────────────────────────────┘
```

每个 `step()` 调用触发一次完整的 Reason→Act→Observe→Reflect 循环。Harness 运行时负责：

- 自动管理上下文窗口（调用 Context Manager）
- 自动记录思维轨迹（调用 Trace System）
- 自动执行 lifecycle hooks（before_step / after_step / on_error）
- 自动检查验收条件（调用 Evaluation Interface）

#### 2.2.3 示例

```nexa
agent BugFixer(issue: string) {
    system `You are an expert engineer. Fix: #{issue}`
    
    context_policy {
        max_tokens: 100000,
        on_overflow: summarize_early_observations
    }
    
    autoloop max_steps: 50 exit_when: "issue is resolved" timeout: 300 {
        try_agent {
            step();
        } catch_correction(e: ToolError) {
            reflect `Tool failed: #{e.message}. Adjust and retry.`
        }
    }
}
```

#### 2.2.4 编译期验证规则

| 规则 ID | 验证内容 | 错误级别 |
|---------|---------|---------|
| E-001 | `autoloop` 必须有 `max_steps` 或 `exit_when` | ERROR |
| E-002 | `autoloop` 循环体内必须有 `step()` 调用 | ERROR |
| E-003 | `autoloop` 必须在 `agent` 声明内部 | ERROR |
| E-004 | `autoloop` 的 `exit_when` 不能为空字符串 | ERROR |
| E-005 | `max_steps` 上限建议不超过 200 | WARN |

#### 2.2.5 与 v1.x `loop until` 的兼容映射

```nexa
// v1.x 语法 (仍然有效，但无 Harness 保护)
loop {
    feedback = Critic.run(poem);
    poem = Editor.run(poem, feedback);
} until ("Poem is perfect")

// v2.0 等价语法 (推荐，有 Harness 保护)
autoloop max_steps: 20 exit_when: "Poem is perfect" {
    try_agent {
        feedback = Critic.run(poem);
        poem = Editor.run(poem, feedback);
    } catch_correction(e) {
        reflect `Error: #{e}. Try different approach.`
    }
}
```

---

### 2.3 `with_context` — 上下文作用域 (Harness C)

#### 2.3.1 语法定义

```ebnf
with_context_stmt ::= "with_context" context_config "{" flow_stmt* "}"
context_config ::= context_param ("," context_param)*
context_param ::= "max_tokens" ":" INT
               | "strategy" ":" eviction_strategy
               | "preserve_recent" ":" INT
               | "on_overflow" ":" overflow_action
eviction_strategy ::= "sliding_window" | "lru" | "importance_weighted"
overflow_action ::= "summarize_early_observations"
                 | "drop_early_observations"
                 | "compress_tool_outputs"
                 | IDENTIFIER  // 自定义策略函数名
```

#### 2.3.2 语义定义

`with_context` 创建一个上下文作用域，在该作用域内：

1. 所有 LLM 交互自动累积到当前上下文
2. 当 Token 数量逼近 `max_tokens` 时，自动触发 `on_overflow` 策略
3. 跳出作用域后，上下文自动隔离或压缩
4. 作用域可以嵌套，内层作用域继承外层上下文

#### 2.3.3 示例

```nexa
// 基础上下文作用域
with_context max_tokens: 50000 strategy: sliding_window {
    result = BugFixer.run("Fix auth bug");
}

// 嵌套上下文作用域
with_context max_tokens: 100000 strategy: importance_weighted {
    // 外层：大窗口，重要性加权淘汰
    research = Researcher.run(topic);
    
    with_context max_tokens: 20000 strategy: lru {
        // 内层：小窗口，LRU 淘汰——用于子任务
        summary = Summarizer.run(research);
    }
    // 内层上下文已压缩，外层不受影响
}

// 自定义 overflow 策略
fn my_compactor(messages: list): list {
    // 自定义压缩逻辑
    return compacted;
}

with_context max_tokens: 80000 on_overflow: my_compactor {
    result = Agent.run(task);
}
```

#### 2.3.4 编译期验证规则

| 规则 ID | 验证内容 | 错误级别 |
|---------|---------|---------|
| C-001 | `with_context` 必须指定 `max_tokens` | ERROR |
| C-002 | `with_context` 必须指定 `strategy` 或 `on_overflow` | ERROR |
| C-003 | `max_tokens` 值应在 1000-200000 范围内 | WARN |
| C-004 | 自定义 `on_overflow` 函数必须接受 `list` 参数并返回 `list` | ERROR |

---

### 2.4 `try_agent` / `catch_correction` — AI 专属容错 (Harness E+L)

#### 2.4.1 语法定义

```ebnf
try_agent_stmt ::= "try_agent" "{" flow_stmt* "}"
                   "catch_correction" "(" error_binding ")" "{" correction_body "}"

error_binding ::= IDENTIFIER ":" error_type
error_type ::= "ToolError" | "FormatError" | "TimeoutError" | "ModelError" | IDENTIFIER

correction_body ::= "reflect" STRING_LITERAL ";"
                  | flow_stmt*
```

#### 2.4.2 语义定义

`try_agent` / `catch_correction` 与传统 `try/catch` 的根本区别：

| 维度 | 传统 `try/catch` | `try_agent` / `catch_correction` |
|------|-----------------|-------------------------------|
| 捕获对象 | 程序异常 | LLM/Tool 执行错误 |
| 处理方式 | 走向失败逻辑 | 将错误反馈给 LLM，触发自纠错 |
| 循环关系 | 单次捕获 | 内嵌在 `autoloop` 中，自动重试 |
| 上下文影响 | 无 | 错误信息自动注入 LLM 上下文 |

执行流程：

```
try_agent {
    step();  // Reason → Act → Observe
}
catch_correction(e: ToolError) {
    reflect `Error: #{e.message}. Adjust.`
    // reflect 的内容被自动注入到 LLM 的下一轮对话中
    // LLM 基于错误信息调整策略，在下一个 step() 中重试
}
```

#### 2.4.3 示例

```nexa
autoloop max_steps: 30 exit_when: "task completed" {
    try_agent {
        step();
    } catch_correction(e: ToolError) {
        reflect `The tool call failed with: #{e.message}. Please adjust your arguments and try again.`
    } catch_correction(e: FormatError) {
        reflect `The output format was incorrect. Expected JSON but got: #{e.raw_output}. Please output valid JSON.`
    }
}
```

#### 2.4.4 编译期验证规则

| 规则 ID | 验证内容 | 错误级别 |
|---------|---------|---------|
| EC-001 | `try_agent` 必须有至少一个 `catch_correction` 分支 | ERROR |
| EC-002 | `catch_correction` 的 error_type 必须是已定义的错误类型 | WARN |
| EC-003 | `reflect` 字符串必须引用 `e.message` 或 `e.raw_output` | WARN |

---

### 2.5 `snapshot` / `restore` / `fork` — 状态分支与回溯 (Harness S)

#### 2.5.1 语法定义

```ebnf
snapshot_stmt ::= "snapshot" [":" IDENTIFIER] ";"
restore_stmt  ::= "restore" "(" IDENTIFIER ")" ["if" expression] ";"
fork_stmt     ::= "fork" "[" fork_branch ("," fork_branch)* "]" merge_clause ";"
fork_branch   ::= [IDENTIFIER "="] expression
merge_clause  ::= "merge" merge_strategy
merge_strategy ::= "best" | "first_success" | "vote" | "consensus" | IDENTIFIER
```

#### 2.5.2 语义定义

这三个原语共同实现 Tree-of-Thoughts 模式：

- **`snapshot`**: 保存当前 Agent 的完整状态（COW O(1) 快照），包括上下文、消息历史、工具状态
- **`fork`**: 从当前状态并行派生多个子 Agent，每个子 Agent 独立执行
- **`restore`**: 回溯到某个快照点，丢弃当前状态

#### 2.5.3 示例

```nexa
// 基础回溯模式
snap = snapshot();
result = Agent.run("Try approach A");
restore(snap) if result.failed;
result = Agent.run("Try approach B");

// 并行探索模式
fork [
    path_a = Agent.run("Fix via null check"),
    path_b = Agent.run("Fix via try-catch"),
    path_c = Agent.run("Fix via type guard")
] merge best;

// 嵌套快照——深度回溯
snap1 = snapshot();
result1 = Agent.run("Step 1");
snap2 = snapshot();
result2 = Agent.run("Step 2");
restore(snap2) if result2.partially_failed;  // 回到 Step 2 之前
restore(snap1) if result2.completely_failed;  // 回到 Step 1 之前
```

#### 2.5.4 编译期验证规则

| 规则 ID | 验证内容 | 错误级别 |
|---------|---------|---------|
| S-001 | `restore` 的目标必须是已定义的 `snapshot` 变量 | ERROR |
| S-002 | `snapshot` 必须在 `agent` 或 `autoloop` 作用域内 | ERROR |
| S-003 | `fork` 的每个分支必须是有效的 Agent 调用 | WARN |
| S-004 | `fork` 的 `merge` 策略必须是已定义的策略 | WARN |

---

### 2.6 `verify` — Harness 验收 (Harness V)

#### 2.6.1 语法定义

```ebnf
verify_stmt ::= "verify" expression "satisfies" type_expr ";"
              | "verify" expression "." method_name "(" ")" ";"
              | "verify" STRING_LITERAL "against" expression ";"
```

#### 2.6.2 语义定义

`verify` 是 Harness 的验收接口，在两个层面执行：

1. **编译期**: AST 级静态检查——验证目标类型存在、方法签名匹配
2. **运行期**: 实际执行验收——调用 Evaluation Interface 检查结果合规性

`verify` 与 v1.x `assert` 的区别：

| 维度 | v1.x `assert` | v2.0 `verify` |
|------|-------------|-------------|
| 执行时机 | 仅运行时 | 编译期 + 运行时 |
| 检查方式 | 语义评估（LLM） | 类型合规 + 语义评估 |
| 失败处理 | 打印警告 | 触发 Harness 纠错循环 |
| 作用范围 | 仅在 `test` 块内 | 在任何 `flow`/`autoloop` 内 |

#### 2.6.3 示例

```nexa
// 类型验收
result = Agent.run(task);
verify result satisfies AnalysisReport;

// 方法验收
verify result.code_compiles();
verify result.tests_pass();

// 语义验收 (保留 v1.x assert 语义)
verify "contains actionable recommendations" against result;
```

#### 2.6.4 编译期验证规则

| 规则 ID | 验证内容 | 错误级别 |
|---------|---------|---------|
| V-001 | `verify satisfies` 的目标必须是已声明的 `protocol` 或 `struct` | ERROR |
| V-002 | `verify` 的方法调用必须是已定义的验收方法 | WARN |
| V-003 | `verify` 语句应在 `autoloop` 或 `flow` 内部 | WARN |

---

### 2.7 `unharnessed` — 显式约束绕过

#### 2.7.1 语法定义

```ebnf
unharnessed_stmt ::= "unharnessed" ["(" reason_string ")"] "{" flow_stmt* "}"
reason_string ::= STRING_LITERAL
```

#### 2.7.2 语义定义

`unharnessed` 块内的代码不受 Harness 保护：

- 不受 `with_context` Token 限制
- 不受 `@tool` Schema 约束
- 不受 Lifecycle Hooks 拦截
- 不受 Sandbox 执行限制

但所有 `unharnessed` 操作会被记录到 Trace System，并标记为 `UNHARNESSED`。

#### 2.7.3 示例

```nexa
// 合理使用: 开发调试
unharnessed("debug: need raw shell access for testing") {
    std.shell.exec("rm -rf /tmp/test_build");
}

// 不合理使用: 生产代码绕过安全
unharnessed("bypass approval for speed") {
    std.shell.exec("rm -rf /var/log/app");  // 编译器发出 STRONG WARNING
}
```

#### 2.7.4 编译期验证规则

| 规则 ID | 验证内容 | 错误级别 |
|---------|---------|---------|
| U-001 | `unharnessed` 必须有 reason_string 说明 | WARN |
| U-002 | `unharnessed` 块内不能有 `snapshot`/`restore` 操作 | ERROR |
| U-003 | `unharnessed` 块内不能定义新的 `@tool` | ERROR |
| U-004 | `unharnessed` 块不应出现在 `autoloop` 的 `try_agent` 内 | WARN |

---

### 2.8 `reflect` — 反思注入原语

#### 2.8.1 语法定义

```ebnf
reflect_stmt ::= "reflect" STRING_LITERAL ";"
```

#### 2.8.2 语义定义

`reflect` 将一段自然语言反思注入到当前 Agent 的 LLM 上下文中，作为下一轮推理的输入。它不是普通的字符串赋值，而是：

1. 自动包装为 `assistant` 角色消息
2. 自动追加到 `messages[]` 末尾
3. 在 Trace 中标记为 `REFLECTION` 类型

#### 2.8.3 示例

```nexa
try_agent {
    step();
} catch_correction(e: ToolError) {
    reflect `The grep command failed because the pattern was invalid regex.
             Try using a simpler search term like "NullPointerException" instead.`
}
```

---

### 2.9 `spawn` / `pass` / `await` — Actor 模型原语

#### 2.9.1 语法定义

```ebnf
spawn_stmt ::= "spawn" IDENTIFIER "(" argument_list ")" [":" IDENTIFIER] ";"
pass_stmt  ::= "pass" expression "to" IDENTIFIER ";"
await_stmt ::= "await" IDENTIFIER ";"
message_stmt ::= "receive" "(" ")" [":" type_expr] ";"
```

#### 2.9.2 语义定义

基于 Actor Model 的多 Agent 编排：

- **`spawn`**: 创建一个子 Agent 实例，返回 Actor handle
- **`pass`**: 向 Actor 发送消息（异步）
- **`await`**: 等待 Actor 返回结果（同步阻塞）
- **`receive`**: Actor 内部接收消息

#### 2.9.3 示例

```nexa
// 主 Agent 派生子 Agent
code_reader = spawn CodeReader("Read the entire codebase");
test_runner = spawn TestRunner("Run all unit tests");

// 向子 Agent 发送消息
pass "Focus on auth module" to code_reader;

// 等待子 Agent 结果
code_analysis = await code_reader;
test_results = await test_runner;

// 子 Agent 内部接收消息
agent CodeReader(task: string) {
    loop {
        msg = receive(): string;
        analysis = analyze(msg, task);
        pass analysis to parent;
    } until ("analysis complete")
}
```

#### 2.9.4 编译期验证规则

| 规则 ID | 验证内容 | 错误级别 |
|---------|---------|---------|
| A-001 | `spawn` 的目标必须是已声明的 `agent` | ERROR |
| A-002 | `pass` 的目标必须是已 `spawn` 的 Actor | ERROR |
| A-003 | `await` 的目标必须是已 `spawn` 的 Actor | ERROR |
| A-004 | `receive` 必须在 `agent` 声明内部 | ERROR |

---

### 2.10 `context_policy` — Agent 级上下文策略声明

#### 2.10.1 语法定义

```ebnf
context_policy_decl ::= "context_policy" "{" context_param* "}"
```

#### 2.10.2 语义定义

在 `agent` 声明内部定义上下文管理策略，作为 `with_context` 的声明式替代。当 agent 进入 `autoloop` 时，自动应用此策略。

#### 2.10.3 示例

```nexa
agent BugFixer(issue: string) {
    system `Fix: #{issue}`
    
    context_policy {
        max_tokens: 100000,
        strategy: importance_weighted,
        on_overflow: summarize_early_observations,
        preserve_recent: 3
    }
    
    autoloop max_steps: 50 exit_when: "issue resolved" {
        step();
    }
}
```

---

### 2.11 Lifecycle Hooks — 生命周期钩子声明

#### 2.11.1 语法定义

```ebnf
lifecycle_hook ::= "before_step" "{" flow_stmt* "}"
                 | "after_step" "{" flow_stmt* "}"
                 | "on_error" "(" error_binding ")" "{" flow_stmt* "}"
                 | "before_tool" "(" tool_name ")" "{" flow_stmt* "}"
                 | "after_tool" "(" tool_name ")" "{" flow_stmt* "}"
```

#### 2.11.2 语义定义

Lifecycle Hooks 是 Harness 的控制论调节器——前馈控制指南（before_*）和反馈控制传感器（after_* / on_error）。

- **`before_step`**: 在每个 autoloop step 之前执行
- **`after_step`**: 在每个 autoloop step 之后执行
- **`on_error`**: 在错误发生时执行
- **`before_tool`**: 在特定 tool 调用之前执行（可用于权限检查）
- **`after_tool`**: 在特定 tool 调用之后执行（可用于结果验证）

#### 2.11.3 示例

```nexa
agent BugFixer(issue: string) {
    system `Fix: #{issue}`
    
    before_step {
        trace.log("Step #{step_count} starting");
        trace.snapshot_context();
    }
    
    after_step {
        trace.log("Step #{step_count} completed");
        verify result.code_compiles();
    }
    
    on_error(e) {
        trace.capture(e);
        trace.log("Error at step #{step_count}: #{e.message}");
    }
    
    before_tool(shell_exec) {
        // 高风险工具调用前记录
        trace.log("About to execute shell command");
    }
    
    autoloop max_steps: 50 exit_when: "resolved" {
        try_agent { step(); }
        catch_correction(e) { reflect `Error: #{e.message}`; }
    }
}
```

---

## 3. 类型系统演进

### 3.1 v1.x → v2.0 类型系统对比

| 维度 | v1.x | v2.0 |
|------|------|------|
| 基础类型 | `string`/`number`/`bool` (语义类型) | `string`/`int`/`float`/`bool`/`list`/`dict` |
| 类型检查 | 渐进式，运行时可选 (STRICT/WARN/FORGIVING) | Harness 强制 + 渐进式可选 |
| 类型来源 | `type` 声明 + `protocol` 声明 | `type` + `protocol` + `struct` + `enum` + `@tool` 返回类型 |
| 错误传播 | `?` operator + `otherwise` | `?` + `otherwise` + `try_agent` + `catch_correction` |
| Option/Result | `NexaOption`/`NexaResult` 运行时 | `Option<T>`/`Result<T, E>` 类型级 |

### 3.2 新增类型构造

#### 3.2.1 `Option<T>` 和 `Result<T, E>`

```nexa
// Option 类型 — 可能不存在
type MaybeInt = Option<int>
let x: MaybeInt = Some(42)
let y: MaybeInt = None

// Result 类型 — 可能失败
type ParseResult = Result<AnalysisReport, FormatError>
let r: ParseResult = Ok(report)
let r: ParseResult = Err(FormatError("invalid JSON"))

// ? 操作符 — 错误传播
let value = parse(input)?;  // 如果 parse 返回 Err，提前退出
```

#### 3.2.2 Harness 类型标注

```nexa
// @tool 函数的返回类型自动成为 Harness 验收类型
@tool("Parse config")
fn parse_config(path: string): Result<Config, FormatError> {
    // ...
}

// verify 使用这些类型
result = parse_config("app.json");
verify result satisfies Config;  // 编译期检查 Config 类型存在
```

### 3.3 Harness 类型验证层级

```
┌─────────────────────────────────────────────────────────┐
│                  Harness Type Verification                 │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Level 0 — Structural (编译期)                            │
│  ├── 类型签名完整性检查                                    │
│  ├── @tool 参数/返回类型存在性检查                         │
│  └── verify 目标类型存在性检查                             │
│                                                           │
│  Level 1 — Contractual (编译期 + 运行期)                  │
│  ├── requires/ensures 契约检查                             │
│  ├── protocol 字段合规性检查                               │
│  └── Option/Result 类型匹配检查                           │
│                                                           │
│  Level 2 — Semantic (运行期)                              │
│  ├── 语义条件评估 (semantic_if / exit_when)               │
│  ├── 自然语言验收 (verify "..." against)                  │
│  └── LLM 输出格式合规性 (structured output)               │
│                                                           │
│  Level 3 — Behavioral (运行期 + Trace)                    │
│  ├── Agent 行为轨迹合规性                                  │
│  ├── Tool 调用序列合规性                                   │
│  └── 上下文使用效率评估                                    │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 完整 v2.0 EBNF 语法（增量部分）

以下仅列出 v2.0 新增的语法规则，与 v1.x 共有的规则参见 `docs/01_nexa_syntax_reference.md`。

```ebnf
// ═══════════════════════════════════════════════════════════
// Nexa v2.0 — Harness Native 新增语法规则
// ═══════════════════════════════════════════════════════════

// 顶层声明扩展
script_stmt ::= ...  // v1.x 所有规则
              | tool_annotation      // @tool 零成本绑定
              | harness_agent_decl   // Harness 增强型 agent

// @tool 注解式工具声明
tool_annotation ::= "@tool" "(" STRING_LITERAL ["," tool_config] ")" tool_fn_def
tool_config ::= "risk_level" ":" risk_level_value
             | "requires_approval" ":" BOOL
             | "sandbox" ":" BOOL
risk_level_value ::= "low" | "medium" | "high"

tool_fn_def ::= "fn" IDENTIFIER "(" [param_list] ")" [":" type_expr] block

// Harness 增强型 agent 声明
harness_agent_decl ::= "agent" IDENTIFIER "(" [param_list] ")" "{" agent_harness_body "}"

agent_harness_body ::= agent_body                  // v1.x agent body
                    | context_policy_decl           // Harness C
                    | lifecycle_hook                // Harness L
                    | autoloop_stmt                 // Harness E
                    | autoloop_stmt                 // 可有多个 autoloop

// autoloop — 自主执行循环
autoloop_stmt ::= "autoloop" autoloop_config "{" autoloop_body "}"
autoloop_config ::= ["max_steps:" INT] ["exit_when:" STRING_LITERAL] ["timeout:" INT]
autoloop_body ::= (try_agent_stmt | lifecycle_hook_stmt | flow_stmt)*

// with_context — 上下文作用域
with_context_stmt ::= "with_context" context_config "{" flow_stmt* "}"

// try_agent / catch_correction — AI 专属容错
try_agent_stmt ::= "try_agent" "{" flow_stmt* "}"
                   ("catch_correction" "(" error_binding ")" "{" correction_body "}")+

// snapshot / restore / fork — 状态分支与回溯
snapshot_stmt ::= [IDENTIFIER "="] "snapshot" ";"
restore_stmt ::= "restore" "(" IDENTIFIER ")" ["if" expression] ";"
fork_stmt ::= "fork" "[" fork_branch ("," fork_branch)* "]" "merge" merge_strategy ";"

// verify — Harness 验收
verify_stmt ::= "verify" expression "satisfies" type_expr ";"
              | "verify" expression "." IDENTIFIER "(" ")" ";"
              | "verify" STRING_LITERAL "against" expression ";"

// reflect — 反思注入
reflect_stmt ::= "reflect" STRING_LITERAL ";"

// unharnessed — 显式约束绕过
unharnessed_stmt ::= "unharnessed" ["(" STRING_LITERAL ")"] "{" flow_stmt* "}"

// spawn / pass / await / receive — Actor 模型
spawn_stmt ::= [IDENTIFIER "="] "spawn" IDENTIFIER "(" [argument_list] ")" ";"
pass_stmt ::= "pass" expression "to" IDENTIFIER ";"
await_stmt ::= "await" IDENTIFIER ";"
receive_stmt ::= "receive" "(" ")" [":" type_expr] ";"

// context_policy — Agent 级上下文策略
context_policy_decl ::= "context_policy" "{" context_param* "}"

// lifecycle hooks — 生命周期钩子
lifecycle_hook ::= "before_step" "{" flow_stmt* "}"
                 | "after_step" "{" flow_stmt* "}"
                 | "on_error" "(" error_binding ")" "{" flow_stmt* "}"
                 | "before_tool" "(" IDENTIFIER ")" "{" flow_stmt* "}"
                 | "after_tool" "(" IDENTIFIER ")" "{" flow_stmt* "}"

// 类型系统扩展
type_expr ::= ...  // v1.x 所有规则
            | "Option" "<" type_expr ">"       // Option<T>
            | "Result" "<" type_expr "," type_expr ">"  // Result<T, E>
            | "Actor" "<" type_expr ">"        // Actor<T>

// 错误类型
error_type ::= "ToolError" | "FormatError" | "TimeoutError" 
             | "ModelError" | "ContextOverflowError" | IDENTIFIER
```

---

## 5. v1.x → v2.0 语法迁移映射

### 5.1 完整映射表

| v1.x 语法 | v2.0 推荐语法 | 迁移难度 | 说明 |
|----------|-------------|---------|------|
| `tool X { description: "...", parameters: {...} }` | `@tool("...") fn x(...): T { ... }` | **低** | 自动 Schema 生成 |
| `agent X uses Y { prompt: "..." }` | `agent X(...) { system "..."; context_policy {...}; autoloop {...} }` | **中** | 增加 Harness 子声明 |
| `flow main { A.run() >> B }` | `flow main { with_context {...} { A.run() >> B } }` | **低** | 包裹 with_context |
| `loop { ... } until ("...")` | `autoloop exit_when: "..." { try_agent { step(); } catch_correction(e) { ... } }` | **中** | 增加 Harness 保护 |
| `try { ... } catch (e) { ... }` | `try_agent { ... } catch_correction(e: T) { reflect "..."; }` | **中** | AI 专属容错 |
| `semantic_if "..." against x { ... }` | 保持不变 | **无** | v1.x 语法继续有效 |
| `match intent { ... }` | 保持不变 | **无** | v1.x 语法继续有效 |
| `assert "..." against x;` | `verify "..." against x;` | **低** | 语义增强 |
| `protocol X { ... }` | 保持不变 + `verify result satisfies X;` | **低** | 增加 Harness 验收 |
| `requires/ensures/invariant` | 保持不变 + lifecycle hooks | **低** | 增强为 Harness L |
| `A |>> [B, C]` | `fork [B.run(x), C.run(x)] merge best;` | **中** | 更显式的 Harness S |
| `[A, B] &>> C` | 保持不变 或 `fork [A, B] merge consensus >> C` | **低** | 两种风格并存 |

### 5.2 渐进式迁移策略

v2.0 支持三种迁移模式：

**模式一：纯 v1.x 兼容（`--harness=off`）**
- 所有 v1.x 代码无需修改即可编译运行
- 不执行任何 Harness 验证
- 适用于：快速迁移、原型验证

**模式二：渐进式 Harness（`--harness=warn`）**
- v1.x 代码可编译，但发出 Harness 缺失警告
- 例如：`agent` 没有 `context_policy` → WARNING
- 例如：`loop until` 没有 `try_agent` → WARNING
- 适用于：逐步增强现有代码

**模式三：完整 Harness（`--harness=strict`）**
- 所有 Harness 验证规则以 ERROR 级别执行
- v1.x 代码必须迁移到 v2.0 语法才能编译
- 适用于：生产部署、安全敏感场景

---

## 6. 语义定义补充

### 6.1 `step()` 的完整语义

`step()` 是 `autoloop` 内的核心推进语句，一次 `step()` 调用执行完整的 ReAct 循环：

```
step() 执行流程:
  1. [Reason]   LLM 分析当前上下文，生成思考过程
  2. [Plan]     LLM 决定下一步行动（选择 Tool + 参数）
  3. [Act]      Harness 执行选定的 Tool
                ├── before_tool hook 拦截
                ├── Tool 在 Sandbox 中执行（如果 risk_level=high）
                ├── after_tool hook 拦截
  4. [Observe]  收集 Tool 执行结果
                ├── 结果注入上下文
                ├── Context Manager 检查 Token 溢出
  5. [Reflect]  LLM 评估结果，决定是否继续
                ├── exit_when 条件检查
                ├── verify 验收检查
  6. [Trace]    记录完整 step 轨迹
```

### 6.2 `reflect` 与上下文注入

`reflect` 语句的运行时行为：

```python
# reflect 的内部实现（概念性）
def nexa_reflect(agent: NexaAgent, reflection_text: str):
    # 1. 包装为 assistant 角色消息
    message = {
        "role": "assistant",
        "content": reflection_text,
        "_nexa_meta": {"type": "REFLECTION", "step": agent.step_count}
    }
    # 2. 追加到上下文
    agent.messages.append(message)
    # 3. 记录到 Trace
    trace.record("REFLECTION", reflection_text, step=agent.step_count)
```

### 6.3 `fork` 的并行执行语义

`fork` 语句的运行时行为：

```python
# fork 的内部实现（概念性）
def nexa_fork(agent: NexaAgent, branches: List[Callable], merge_strategy: str):
    # 1. 为每个分支创建 COW 快照
    snapshots = [agent.cow_state.clone() for _ in branches]
    
    # 2. 并行执行每个分支
    results = parallel_execute(branches, snapshots)
    
    # 3. 根据策略合并结果
    if merge_strategy == "best":
        return max(results, key=lambda r: r.quality_score)
    elif merge_strategy == "first_success":
        return next(r for r in results if r.success)
    elif merge_strategy == "vote":
        return majority_vote(results)
    elif merge_strategy == "consensus":
        return consensus_merge(results)
```

### 6.4 `verify` 的双层执行语义

```python
# verify 的内部实现（概念性）
def nexa_verify(result, target_type, context):
    # Level 0: 编译期已验证类型存在性
    
    # Level 1: 运行期类型合规性
    if isinstance(target_type, Protocol):
        type_result = type_checker.check_protocol_compliance(result, target_type)
        if not type_result.passed:
            raise TypeViolation(...)
    
    # Level 2: 语义验收（如果 verify 使用自然语言）
    if isinstance(target_type, str):
        semantic_result = semantic_eval(target_type, result)
        if not semantic_result:
            # 不抛异常，而是注入到 Harness 纠错循环
            reflect(f"Verification failed: {target_type}")
```

---

## 7. 关键字扩展清单

v2.0 新增的 exclusion keyword（避免与 IDENTIFIER 冲突）：

| 关键字 | 用途 | 优先级 |
|--------|------|--------|
| `autoloop` | 自主执行循环 | **P0** |
| `with_context` | 上下文作用域 | **P0** |
| `try_agent` | AI 专属容错 | **P0** |
| `catch_correction` | AI 错误自纠错 | **P0** |
| `step` | autoloop 推进 | **P0** |
| `reflect` | 反思注入 | **P0** |
| `snapshot` | 状态快照 | **P1** |
| `restore` | 状态回溯 | **P1** |
| `fork` | 并行探索 | **P1** |
| `merge` | 结果合并 | **P1** |
| `verify` | Harness 验收 | **P0** |
| `unharnessed` | 显式约束绕过 | **P0** |
| `spawn` | Actor 创建 | **P2** |
| `pass` | Actor 消息发送 | **P2** |
| `await` | Actor 结果等待 | **P2** |
| `receive` | Actor 消息接收 | **P2** |
| `before_step` | 生命周期钩子 | **P1** |
| `after_step` | 生命周期钩子 | **P1** |
| `on_error` | 生命周期钩子 | **P1** |
| `before_tool` | 生命周期钩子 | **P2** |
| `after_tool` | 生命周期钩子 | **P2** |
| `context_policy` | 上下文策略声明 | **P0** |
| `Option` | 类型构造 | **P1** |
| `Result` | 类型构造 | **P1** |
| `Actor` | 类型构造 | **P2** |
| `Some` | Option 变体 | **P1** |
| `None` | Option 变体 | **P1** |
| `Ok` | Result 变体 | **P1** |
| `Err` | Result 变体 | **P1** |

---

## 8. 语法设计决策记录

### 8.1 为什么 `autoloop` 而不是 `agent_loop`？

- `autoloop` 强调"自主"（autonomous），与"自主智能体"目标一致
- `agent_loop` 暗示"Agent 的循环"，但 Harness 的循环是框架控制的，不是 Agent 自身的
- `autoloop` 更短，更易读

### 8.2 为什么 `try_agent` 而不是 `try_llm`？

- `try_agent` 捕获的是整个 Agent step 的错误（包括 Tool 执行、格式解析、超时）
- `try_llm` 暗示只捕获 LLM 调用错误，范围太窄
- Agent 是 Harness 的执行单元，错误发生在 Agent 层面

### 8.3 为什么 `catch_correction` 而不是 `catch`？

- 传统 `catch` 走向失败逻辑
- `catch_correction` 走向纠错逻辑——将错误反馈给 LLM
- 语义完全不同，必须用不同的关键字

### 8.4 为什么 `unharnessed` 而不是 `unsafe`？

- `unsafe` 是 Rust 的概念，语义是"内存安全不保证"
- `unharnessed` 是 Nexa 的概念，语义是"Harness 保护不生效"
- 两者类比但领域不同，不应混用关键字

### 8.5 为什么 `verify` 而不是 `assert`？

- `assert` 是 v1.x 的测试断言，仅在 `test` 块内有效
- `verify` 是 v2.0 的 Harness 验收，在任何执行流内有效
- `verify` 有编译期 + 运行期双层语义，`assert` 仅运行期
- 保留 `assert` 用于测试，`verify` 用于 Harness 验收