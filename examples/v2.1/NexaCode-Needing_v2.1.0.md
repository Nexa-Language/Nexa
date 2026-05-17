# Nexa 语言待支持特性（Feature Wishlist）

> 这些特性目前 Nexa v2.0 编译器不支持，Nexa Code 通过 `python!` escape hatch 或混合方案实现。
> 一旦 Nexa 编译器支持后，可在此处标记"已支持"并迁移为纯 Nexa 语法。
> **v2.1.0 更新**: P0 四特性已于 2026-05-17 实现，标记为 ✅。

---

## P0 — 核心缺失（当前严重依赖 python! escape）

### 1. `spawn` — 子 Agent 调用

**当前状态**：✅ 已支持 (v2.1.0)
**语法**：
```nexa
// spawn pipeline
results = task |>> spawn [Agent1, Agent2, Agent3];

// 传统 spawn/pass/await
worker = spawn Agent("task");
result = await worker;
```

**迁移方案**：将 Pipeline flow 中的链式赋值改为 `|>> spawn` 或管道语法。

---

### 2. Streaming 流式输出

**当前状态**：✅ 已支持 (v2.1.0)
**语法**：
```nexa
agent Coder {
    prompt: "..."
    stream: true  // 启用流式输出
}
```

**迁移方案**：在 `Nexa-Code/src/agents/coder.nx` 中添加 `stream: true`。

---

### 3. Structured Output / JSON Mode

**当前状态**：✅ 已支持 (v2.1.0)
**语法**：
```nexa
agent Planner {
    prompt: "..."
    output_format: "json"
    output_schema: {
        steps: [{title: "string", description: "string"}],
        estimated_time: "string"
    }
}
```

**迁移方案**：在 `Nexa-Code/src/agents/planner.nx` 中添加 `output_format` + `output_schema`，编译器自动生成 `response_format`。

---

### 4. 多轮工具调用 (ReAct Loop)

**当前状态**：✅ 已支持 (v2.1.0)
**语法**：
```nexa
agent Coder {
    prompt: "..."
    max_tool_calls: 10
    tool_call_strategy: "auto"  // "auto" | "required" | "none"
}
```

**迁移方案**：在 agent 声明中添加 `max_tool_calls` 和 `tool_call_strategy` 参数。

---

## P1 — 重要增强

### 5. Agent 间结构化通信

**当前状态**：❌ 不支持  
**影响范围**：Agent 间只能传递字符串，无法传递类型化消息  
**当前替代方案**：字符串拼接 + JSON 序列化/反序列化

**期望语法**：
```nexa
message PlanResult {
    steps: [Step];
    summary: string;
}

flow pipeline {
    plan: PlanResult = Planner.run(task);
    code = Coder.run(plan.summary, context: plan.steps);
}
```

**迁移方案**：定义 `message` 类型，Agent 间传递结构化对象。

---

### 6. 条件中断增强

**当前状态**：⚠️ `exit_when` 仅支持简单字符串匹配  
**影响范围**：REPL 循环的灵活退出条件  
**当前替代方案**：在 autoloop 内部用 `if` + `exit(0)` 手动处理

**期望语法**：
```nexa
autoloop {
    exit_when: fn(state) -> bool {
        // 任意复杂的中断条件
        return state.iterations > 100 or state.user_exit;
    }
}
```

**迁移方案**：将 REPL 中的 `if (user_input == "/exit")` 逻辑迁移到 `exit_when` 回调。

---

### 7. 并行 Agent 执行

**当前状态**：❌ 不支持  
**影响范围**：Pipeline 中 Planner/Reviewer/Tester 可并行  
**当前替代方案**：串行调用，无法加速

**期望语法**：
```nexa
parallel {
    review = Reviewer.run(diff);
    tests = Tester.run(".");
}
// 两个 Agent 并发执行
```

**迁移方案**：Pipeline 中将独立的审查和测试阶段用 `parallel` 包裹。

---

### 8. MCP 协议集成

**当前状态**：❌ 不支持  
**影响范围**：外部工具注册（MCP servers）  
**当前替代方案**：`python!` 手动实现 MCP 客户端

**期望语法**：
```nexa
@mcp_tool("my-mcp-server")
fn external_search(query: string): string {
    // MCP 协议自动处理通信
}
```

**迁移方案**：将手动实现的 MCP 客户端替换为 `@mcp_tool` 注解。

---

## P2 — 锦上添花

### 9. Vision / 图片输入

**期望语法**：
```nexa
agent Analyst {
    prompt: "..."
    supports_vision: true
}

// 调用时传入图片
result = Analyst.run("分析这张截图", images: ["screenshot.png"]);
```

---

### 10. 文件监听 (Watch Mode)

**期望语法**：
```nexa
flow watch_mode {
    watch "src/**/*.py" {
        on_change: fn(files) {
            result = Reviewer.run("Review changes in: " + files);
        }
    }
}
```

---

### 11. Agent 生命周期钩子

**期望语法**：
```nexa
agent Coder {
    prompt: "..."
    on_start: fn() { print("Coder starting..."); }
    on_complete: fn(result) { print("Coder done: " + result[:50]); }
    on_error: fn(error) { print("Coder error: " + error); }
}
```

---

### 12. 工具权限控制

**期望语法**：
```nexa
@tool("Execute shell command", permissions: ["shell", "network"])
fn shell_exec(command: string): string { ... }

agent Coder {
    allowed_permissions: ["file_write", "shell"]
    denied_permissions: ["network"]
}
```

---

### 13. Agent 模板/继承

**期望语法**：
```nexa
agent BaseAgent {
    model: "glm-5"
    temperature: 0.7
}

agent Coder extends BaseAgent {
    prompt: "You are a coder..."
}

agent Reviewer extends BaseAgent {
    prompt: "You are a reviewer..."
    temperature: 0.3
}
```

---

### 14. 内置记忆/向量存储

**期望语法**：
```nexa
memory = vector_store("project_context");
memory.embed("This project uses FastAPI with SQLAlchemy");

// Agent 自动从向量存储检索相关上下文
agent Coder {
    prompt: "..."
    memory: vector_store("project_context")
}
```

---

## 迁移优先级路线图

```
P0 (必须)          P1 (重要)              P2 (增强)
─────              ─────                  ─────
spawn ──────────► Agent通信 ──────────► Vision
streaming ──────► 条件中断 ────────────► Watch mode
json_mode ──────► 并行执行 ────────────► 生命周期钩子
tool_loop ──────► MCP集成 ────────────► 权限控制
                                         模板/继承
                                         向量存储
```

---

## 迁移检查清单

当 Nexa 编译器支持相应特性后，按以下清单逐一迁移：

- [ ] `spawn` → 替换 `src/flows/pipeline.nx` 中的链式赋值
- [ ] `streaming` → 在 `src/agents/*.nx` 中启用流式输出
- [ ] `json_mode` → Planner/Reviewer/Tester 使用强制 JSON 输出
- [ ] `tool_loop` → 在 agent 声明中添加 `max_tool_calls` 控制
- [ ] `Agent通信` → 用 `message` 类型替换字符串拼接
- [ ] `条件中断` → REPL 退出逻辑迁移到 `exit_when`
- [ ] `并行执行` → Pipeline 中独立阶段并行化
- [ ] `MCP集成` → 外部工具使用 `@mcp_tool`
- [ ] `Vision` → 截图分析等场景
- [ ] `Watch mode` → 新增文件监听 flow
- [ ] `生命周期` → 添加 on_start/on_complete/on_error 钩子
- [ ] `权限控制` → 细粒度工具权限
- [ ] `模板` → BaseAgent 提取公共配置
- [ ] `向量存储` → 跨会话上下文记忆