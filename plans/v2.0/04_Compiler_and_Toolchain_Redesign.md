# Nexa v2.0 — Compiler and Toolchain Redesign

> 本文档定义 Nexa v2.0 编译器与工具链的完整重构方案，包括 Harness Validator（编译期验证）、多后端 Code Generation（Python + AVM Bytecode + WASM）、AVM 字节码指令集扩展、以及 CLI/Debugger/Inspector 工具链增强。

---

## 1. 编译器架构总览

### 1.1 v1.x 编译器架构回顾

v1.x 编译器是经典的三阶段架构：

```
.nx 源码 → Lark Parser → AST Transformer → Code Generator → Python 代码
```

关键特征：
- **单后端**: 只生成 Python 代码
- **无验证**: 没有 AST 级的约束检查
- **BOILERPLATE 模式**: 生成的 Python 代码头部注入大量固定导入
- **Handle-as-dict**: 所有运行时 handle 用 Python dict 表示

### 1.2 v2.0 编译器架构

v2.0 编译器在 v1.x 三阶段架构基础上增加两个新阶段：

```
.nx 源码 → Lark Parser → AST Transformer → Harness Validator → Code Generator → 多后端输出
```

新增阶段：
- **Harness Validator**: 在 AST Transformer 之后，对增强 AST 执行编译期 Harness 约束检查
- **多后端 Code Generator**: 支持 Python / AVM Bytecode / WASM 三种输出

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Nexa v2.0 Compiler Pipeline                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────┐    ┌───────────────────┐    ┌──────────────────┐         │
│  │ .nx 源码   │───→│ 1. Lexer + Parser │───→│ 2. AST Transformer│         │
│  │           │    │ (Lark Earley)      │    │ (v1.x + v2.0     │         │
│  │           │    │                    │    │  Harness nodes)   │         │
│  └───────────┘    └───────────────────┘    └──────────────────┘         │
│                                               │                         │
│                                               ↓                         │
│                                      ┌──────────────────┐              │
│                                      │ 3. Harness Validator│ ← NEW      │
│                                      │ (编译期约束检查)     │              │
│                                      │ E/T/C/S/L/V 规则   │              │
│                                      └──────────────────┘              │
│                                               │                         │
│                               ┌───────────────┼───────────────┐        │
│                               ↓               ↓               ↓        │
│                      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
│                      │ 4a. Python   │ │ 4b. AVM      │ │ 4c. WASM     ││
│                      │ Code Gen     │ │ Bytecode Gen │ │ Tool Gen     ││
│                      │ (兼容 v1.x)  │ │ (主目标)     │ │ (Tool 沙箱)  ││
│                      └──────────────┘ └──────────────┘ └──────────────┘│
│                               │               │               │        │
│                               ↓               ↓               ↓        │
│                      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
│                      │ Python 代码   │ │ AVM 字节码    │ │ WASM 模块    ││
│                      │ + Harness    │ │ + Metadata   │ │ + Schema     ││
│                      │ Runtime      │ │              │ │              ││
│                      └──────────────┘ └──────────────┘ └──────────────┘│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Parser 扩展

### 2.1 新增语法规则

v2.0 在 [`nexa_parser.py`](src/nexa_parser.py) 的 Lark grammar 中新增以下规则：

```python
# ═══════════════════════════════════════════════════════════
# Nexa v2.0 — Harness Native 新增 Lark 语法规则
# ═══════════════════════════════════════════════════════════

# 新增 exclusion keywords
%declare AUTOLOOP WITH_CONTEXT TRY_AGENT CATCH_CORRECTION STEP
%declare REFLECT SNAPSHOT RESTORE FORK MERGE VERIFY UNHARNESSED
%declare SPAWN PASS AWAIT RECEIVE BEFORE_STEP AFTER_STEP ON_ERROR
%declare BEFORE_TOOL AFTER_TOOL CONTEXT_POLICY
%declare OPTION RESULT ACTOR SOME OK ERR

// ─── @tool 注解式工具声明 ───
tool_annotation: "@tool" "(" STRING_LITERAL ["," tool_config_list] ")" tool_fn_def

tool_config_list: tool_config_item ("," tool_config_item)*
tool_config_item: IDENTIFIER ":" tool_config_value
tool_config_value: STRING_LITERAL -> tool_config_string
                | IDENTIFIER -> tool_config_id

tool_fn_def: "fn" IDENTIFIER "(" [tool_param_list] ")" [":" type_expr] block
tool_param_list: tool_param ("," tool_param)*
tool_param: IDENTIFIER ":" type_expr ["=" default_value]
default_value: STRING_LITERAL | INT | FLOAT | BOOL

// ─── Harness 增强型 agent 声明 ───
harness_agent_decl: "agent" IDENTIFIER "(" [param_list] ")" "{" harness_agent_body "}"
harness_agent_body: (agent_body_item | context_policy_decl | lifecycle_hook | autoloop_stmt)*

// ─── autoloop — 自主执行循环 ───
autoloop_stmt: "autoloop" autoloop_config "{" autoloop_body "}"
autoloop_config: ["max_steps:" INT] ["exit_when:" STRING_LITERAL] ["timeout:" INT]
autoloop_body: (try_agent_stmt | lifecycle_hook_stmt | flow_stmt)*

// ─── with_context — 上下文作用域 ───
with_context_stmt: "with_context" context_config "{" flow_stmt* "}"
context_config: context_param ("," context_param)*
context_param: IDENTIFIER ":" (INT | IDENTIFIER | STRING_LITERAL)

// ─── try_agent / catch_correction ───
try_agent_stmt: "try_agent" "{" flow_stmt* "}"
                ("catch_correction" "(" error_binding ")" "{" correction_body "}")+

error_binding: IDENTIFIER ":" IDENTIFIER
correction_body: reflect_stmt | flow_stmt*

// ─── snapshot / restore / fork ───
snapshot_stmt: [IDENTIFIER "="] "snapshot" ";"
restore_stmt: "restore" "(" IDENTIFIER ")" ["if" expression] ";"
fork_stmt: "fork" "[" fork_branch ("," fork_branch)* "]" "merge" merge_strategy ";"
fork_branch: [IDENTIFIER "="] expression
merge_strategy: IDENTIFIER

// ─── verify — Harness 验收 ───
verify_stmt: "verify" expression "satisfies" type_expr ";"
            | "verify" expression "." IDENTIFIER "(" ")" ";"
            | "verify" STRING_LITERAL "against" expression ";"

// ─── reflect — 反思注入 ───
reflect_stmt: "reflect" STRING_LITERAL ";"

// ─── unharnessed — 显式约束绕过 ───
unharnessed_stmt: "unharnessed" ["(" STRING_LITERAL ")"] "{" flow_stmt* "}"

// ─── spawn / pass / await / receive ───
spawn_stmt: [IDENTIFIER "="] "spawn" IDENTIFIER "(" [argument_list] ")" ";"
pass_stmt: "pass" expression "to" IDENTIFIER ";"
await_stmt: "await" IDENTIFIER ";"
receive_stmt: "receive" "(" ")" [":" type_expr] ";"

// ─── context_policy ───
context_policy_decl: "context_policy" "{" context_param* "}"

// ─── lifecycle hooks ───
lifecycle_hook: "before_step" "{" flow_stmt* "}"
               | "after_step" "{" flow_stmt* "}"
               | "on_error" "(" error_binding ")" "{" flow_stmt* "}"
               | "before_tool" "(" IDENTIFIER ")" "{" flow_stmt* "}"
               | "after_tool" "(" IDENTIFIER ")" "{" flow_stmt* "}"

// ─── 类型系统扩展 ───
option_type: "Option" "<" type_expr ">"
result_type: "Result" "<" type_expr "," type_expr ">"
actor_type: "Actor" "<" type_expr ">"
```

### 2.2 Exclusion Keyword 管理

v2.0 新增 28 个 exclusion keyword。为了避免与 v1.x IDENTIFIER 冲突，需要在 Lark grammar 的 `%declare` 区域声明所有新关键字。

关键字冲突风险分析：

| 关键字 | 与 v1.x 冲突风险 | 处理策略 |
|--------|-----------------|---------|
| `step` | **高** — v1.x 中 `step` 可能作为变量名 | 声明为 exclusion keyword，仅在 `autoloop` 内有效 |
| `merge` | **中** — v1.x DAG 操作符已使用 | 在 `fork` 语句内作为关键字，其他位置作为 IDENTIFIER |
| `pass` | **高** — Python 关键字，v1.x 可能使用 | 声明为 exclusion keyword |
| `await` | **高** — Python 关键字 | 声明为 exclusion keyword |
| `receive` | **低** | 声明为 exclusion keyword |
| `Some`/`None`/`Ok`/`Err` | **高** — 常见变量名 | 声明为 exclusion keyword，仅在类型表达式内有效 |
| `restore` | **低** | 声明为 exclusion keyword |
| `reflect` | **低** | 声明为 exclusion keyword |

**关键设计决策**: `step`、`pass`、`await` 等高频词采用**上下文敏感解析**——仅在特定语法结构（autoloop 内、Actor 语句内）中作为关键字，其他位置作为 IDENTIFIER。这通过 Lark 的优先级规则实现。

### 2.3 Parser 扩展实现步骤

```
Step 1: 在 nexa_grammar 字符串中添加 %declare 行
Step 2: 添加新语法规则到 nexa_grammar
Step 3: 更新 script_stmt 规则，包含新的声明类型
Step 4: 测试新语法规则的解析正确性
Step 5: 处理上下文敏感关键字的歧义
```

---

## 3. AST Transformer 扩展

### 3.1 新增 AST 节点类型

v2.0 在 [`ast_transformer.py`](src/ast_transformer.py) 中新增以下 AST 节点类：

```python
# ═══════════════════════════════════════════════════════════
# Nexa v2.0 — Harness Native 新增 AST 节点
# ═══════════════════════════════════════════════════════════

@dataclass
class ToolAnnotation:
    """@tool 注解式工具声明"""
    description: str
    fn_name: str
    params: List[Tuple[str, str, Any]]  # (name, type, default)
    return_type: Optional[str]
    body: List[Any]  # block 内的语句
    risk_level: str = "low"
    requires_approval: bool = False
    sandbox: bool = False

@dataclass
class HarnessAgentDecl:
    """Harness 增强型 agent 声明"""
    name: str
    params: List[Tuple[str, str]]  # (name, type)
    system_prompt: Optional[str]
    context_policy: Optional[ContextPolicyDecl]
    lifecycle_hooks: List[LifecycleHook]
    autoloop: Optional[AutoLoopStmt]
    traditional_body: List[Any]  # v1.x agent body items

@dataclass
class AutoLoopStmt:
    """autoloop 自主执行循环"""
    max_steps: Optional[int]
    exit_when: Optional[str]
    timeout: Optional[int]
    body: List[Any]  # try_agent / lifecycle_hook / flow_stmt

@dataclass
class WithContextStmt:
    """with_context 上下文作用域"""
    config: Dict[str, Any]  # max_tokens, strategy, etc.
    body: List[Any]

@dataclass
class TryAgentStmt:
    """try_agent AI 专属容错"""
    try_body: List[Any]
    catch_branches: List[CatchCorrectionBranch]

@dataclass
class CatchCorrectionBranch:
    """catch_correction 分支"""
    error_var: str
    error_type: str
    correction_body: List[Any]  # reflect_stmt or flow_stmts

@dataclass
class SnapshotStmt:
    """snapshot 状态快照"""
    var_name: Optional[str]  # 如果赋值给变量

@dataclass
class RestoreStmt:
    """restore 状态回溯"""
    target_var: str
    condition: Optional[Any]  # if expression

@dataclass
class ForkStmt:
    """fork 并行探索"""
    branches: List[Tuple[Optional[str], Any]]  # (var_name, expression)
    merge_strategy: str

@dataclass
class VerifyStmt:
    """verify Harness 验收"""
    target: Any
    check_type: str  # "satisfies" | "method" | "semantic"
    check_value: Any  # type_expr | method_name | string_literal

@dataclass
class ReflectStmt:
    """reflect 反思注入"""
    text: str

@dataclass
class UnharnessedStmt:
    """unharnessed 显式约束绕过"""
    reason: Optional[str]
    body: List[Any]

@dataclass
class SpawnStmt:
    """spawn Actor 创建"""
    var_name: Optional[str]
    agent_name: str
    args: List[Any]

@dataclass
class PassStmt:
    """pass Actor 消息发送"""
    message: Any
    target_actor: str

@dataclass
class AwaitStmt:
    """await Actor 结果等待"""
    actor_var: str

@dataclass
class ReceiveStmt:
    """receive Actor 消息接收"""
    type_expr: Optional[str]

@dataclass
class ContextPolicyDecl:
    """context_policy 上下文策略声明"""
    params: Dict[str, Any]

@dataclass
class LifecycleHook:
    """生命周期钩子"""
    hook_type: str  # before_step | after_step | on_error | before_tool | after_tool
    tool_name: Optional[str]  # for before_tool/after_tool
    error_binding: Optional[Tuple[str, str]]  # for on_error
    body: List[Any]
```

### 3.2 AST Transformer Handler 扩展

v1.x 的 AST Transformer 使用 Lark 的 `Transformer` 类，每个语法规则对应一个 handler 方法。v2.0 需要新增约 15 个 handler：

```python
class NexaASTTransformer(Transformer):
    # ═══ v1.x 已有 handlers (保留) ═══
    # tool_decl, agent_decl, flow_decl, protocol_decl, ...
    # pipeline_expr, dag_fork_expr, semantic_if, loop_until, ...
    # contract_spec, type_decl, job_decl, server_decl, ...
    # pattern_matching, adt, template, ...
    
    # ═══ v2.0 新增 handlers ═══
    
    def tool_annotation(self, items):
        """@tool 注解 → ToolAnnotation AST 节点"""
        description = items[0]
        config = items[1] if len(items) > 2 else {}
        fn_def = items[-1]
        return ToolAnnotation(
            description=description,
            fn_name=fn_def.name,
            params=fn_def.params,
            return_type=fn_def.return_type,
            body=fn_def.body,
            risk_level=config.get("risk_level", "low"),
            requires_approval=config.get("requires_approval", False),
        )
    
    def harness_agent_decl(self, items):
        """Harness agent → HarnessAgentDecl AST 节点"""
        name = items[0]
        params = items[1] if items[1] else []
        body_items = items[2:]
        
        # 分类 body items
        system_prompt = None
        context_policy = None
        lifecycle_hooks = []
        autoloop = None
        traditional_body = []
        
        for item in body_items:
            if isinstance(item, ContextPolicyDecl):
                context_policy = item
            elif isinstance(item, LifecycleHook):
                lifecycle_hooks.append(item)
            elif isinstance(item, AutoLoopStmt):
                autoloop = item
            else:
                traditional_body.append(item)
        
        return HarnessAgentDecl(
            name=name, params=params,
            system_prompt=system_prompt,
            context_policy=context_policy,
            lifecycle_hooks=lifecycle_hooks,
            autoloop=autoloop,
            traditional_body=traditional_body
        )
    
    def autoloop_stmt(self, items):
        """autoloop → AutoLoopStmt AST 节点"""
        config = items[0]
        body = items[1:]
        return AutoLoopStmt(
            max_steps=config.get("max_steps"),
            exit_when=config.get("exit_when"),
            timeout=config.get("timeout"),
            body=body
        )
    
    def with_context_stmt(self, items):
        """with_context → WithContextStmt AST 节点"""
        config = items[0]
        body = items[1:]
        return WithContextStmt(config=config, body=body)
    
    def try_agent_stmt(self, items):
        """try_agent → TryAgentStmt AST 节点"""
        try_body = items[0]
        catch_branches = items[1:]
        return TryAgentStmt(try_body=try_body, catch_branches=catch_branches)
    
    def catch_correction(self, items):
        """catch_correction → CatchCorrectionBranch"""
        error_var, error_type = items[0]
        body = items[1:]
        return CatchCorrectionBranch(
            error_var=error_var, error_type=error_type, correction_body=body
        )
    
    def snapshot_stmt(self, items):
        """snapshot → SnapshotStmt"""
        var_name = items[0] if items else None
        return SnapshotStmt(var_name=var_name)
    
    def restore_stmt(self, items):
        """restore → RestoreStmt"""
        target_var = items[0]
        condition = items[1] if len(items) > 1 else None
        return RestoreStmt(target_var=target_var, condition=condition)
    
    def fork_stmt(self, items):
        """fork → ForkStmt"""
        branches = items[0]
        merge_strategy = items[1]
        return ForkStmt(branches=branches, merge_strategy=merge_strategy)
    
    def verify_stmt(self, items):
        """verify → VerifyStmt"""
        # 三种形式: satisfies / method / semantic
        ...
    
    def reflect_stmt(self, items):
        """reflect → ReflectStmt"""
        return ReflectStmt(text=items[0])
    
    def unharnessed_stmt(self, items):
        """unharnessed → UnharnessedStmt"""
        reason = items[0] if items[0] else None
        body = items[1:]
        return UnharnessedStmt(reason=reason, body=body)
    
    def spawn_stmt(self, items):
        """spawn → SpawnStmt"""
        ...
    
    def pass_stmt(self, items):
        """pass → PassStmt"""
        ...
    
    def await_stmt(self, items):
        """await → AwaitStmt"""
        ...
```

### 3.3 _ambig() 消歧评分表扩展

v2.0 新增 AST 节点需要在 [`_SCORE_TABLE`](src/ast_transformer.py) 中添加评分：

```python
_SCORE_TABLE = {
    # ═══ v1.x 已有评分 (保留) ═══
    "MatchExpression": 50,
    "MatchArm": 45,
    "StructDeclaration": 60,
    "EnumDeclaration": 60,
    "TraitDeclaration": 60,
    "ImplDeclaration": 60,
    "VariantCallExpression": 55,
    "FieldInitExpression": 45,
    "PipelineExpression": 30,
    "DAGForkExpression": 35,
    "ContractSpec": 40,
    "Literal": 38,
    "Variable": 35,
    
    # ═══ v2.0 新增评分 ═══
    "AutoLoopStmt": 70,          # 最高优先级 — Harness 核心原语
    "TryAgentStmt": 65,          # 高优先级 — AI 容错
    "WithContextStmt": 60,       # 高优先级 — 上下文管理
    "ToolAnnotation": 55,        # 中高优先级 — @tool
    "ForkStmt": 50,              # 中优先级 — 并行探索
    "VerifyStmt": 48,            # 中优先级 — 验收
    "SnapshotStmt": 45,          # 中优先级 — 快照
    "RestoreStmt": 45,           # 中优先级 — 回溯
    "ReflectStmt": 40,           # 中低优先级 — 反思
    "SpawnStmt": 42,             # 中低优先级 — Actor
    "PassStmt": 38,              # 低优先级 — Actor 消息
    "AwaitStmt": 38,             # 低优先级 — Actor 等待
    "UnharnessedStmt": 35,       # 低优先级 — 约束绕过
    "LifecycleHook": 30,         # 低优先级 — 钩子
    "ContextPolicyDecl": 30,     # 低优先级 — 配置
}
```

---

## 4. Harness Validator (新增编译期检查)

### 4.1 设计目标

Harness Validator 是 v2.0 编译器新增的核心阶段，负责在编译期强制检查 Harness 约束的完整性。这是 Nexa v2.0 "Harness Native" 定位的编译期体现——正如 Rust 的 borrow checker 在编译期消灭内存错误，Harness Validator 在编译期消灭 Agent 不确定性失控。

### 4.2 Validator 架构

```python
class HarnessValidator:
    """
    Harness 编译期验证器
    
    验证规则来源:
    ├── 02_Language_Design_Specification.md 中定义的 E/T/C/S/L/V 规则
    ├── 每个规则有唯一 ID (如 E-001, T-001, C-001)
    ├── 每个规则有错误级别 (ERROR / WARN / INFO)
    ├── 验证结果汇总为 HarnessValidationReport
    """
    
    def __init__(self, mode: HarnessMode = HarnessMode.WARN):
        self._mode = mode
        self._rules: List[HarnessRule] = self._load_rules()
        self._violations: List[HarnessViolation] = []
    
    def validate(self, ast: List[Any]) -> HarnessValidationReport:
        """对完整 AST 执行 Harness 验证"""
        for node in ast:
            self._validate_node(node)
        
        return HarnessValidationReport(
            violations=self._violations,
            mode=self._mode,
            total_rules=len(self._rules),
            passed=len(self._violations) == 0 or (
                self._mode == HarnessMode.WARN and 
                not any(v.level == "ERROR" for v in self._violations)
            )
        )
    
    def _validate_node(self, node: Any):
        """递归验证 AST 节点"""
        if isinstance(node, AutoLoopStmt):
            self._validate_autoloop(node)
        elif isinstance(node, ToolAnnotation):
            self._validate_tool_annotation(node)
        elif isinstance(node, WithContextStmt):
            self._validate_with_context(node)
        elif isinstance(node, TryAgentStmt):
            self._validate_try_agent(node)
        elif isinstance(node, UnharnessedStmt):
            self._validate_unharnessed(node)
        elif isinstance(node, HarnessAgentDecl):
            self._validate_harness_agent(node)
        elif isinstance(node, VerifyStmt):
            self._validate_verify(node)
        elif isinstance(node, ForkStmt):
            self._validate_fork(node)
        # ... 递归验证子节点
    
    def _validate_autoloop(self, node: AutoLoopStmt):
        """验证 autoloop 约束"""
        # E-001: autoloop 必须有 max_steps 或 exit_when
        if not node.max_steps and not node.exit_when:
            self._add_violation(
                rule_id="E-001",
                level="ERROR",
                message=f"autoloop must have 'max_steps' or 'exit_when'",
                node=node
            )
        
        # E-002: autoloop 循环体内必须有 step() 调用
        has_step = any(
            isinstance(stmt, str) and stmt == "step()" 
            for stmt in node.body
        )
        if not has_step:
            self._add_violation(
                rule_id="E-002",
                level="ERROR",
                message=f"autoloop body must contain 'step()' call",
                node=node
            )
        
        # E-005: max_steps 上限建议不超过 200
        if node.max_steps and node.max_steps > 200:
            self._add_violation(
                rule_id="E-005",
                level="WARN",
                message=f"autoloop max_steps={node.max_steps} exceeds recommended limit of 200",
                node=node
            )
    
    def _validate_tool_annotation(self, node: ToolAnnotation):
        """验证 @tool 约束"""
        # T-001: @tool 函数必须有 description
        if not node.description or node.description.strip() == "":
            self._add_violation(
                rule_id="T-001",
                level="ERROR",
                message=f"@tool '{node.fn_name}' must have a description",
                node=node
            )
        
        # T-002: @tool 函数参数必须有类型标注
        for param_name, param_type, _ in node.params:
            if param_type is None or param_type == "":
                self._add_violation(
                    rule_id="T-002",
                    level="WARN",
                    message=f"@tool '{node.fn_name}' parameter '{param_name}' lacks type annotation",
                    node=node
                )
        
        # T-003: risk_level=high 的 tool 必须标注 requires_approval
        if node.risk_level == "high" and not node.requires_approval:
            self._add_violation(
                rule_id="T-003",
                level="ERROR",
                message=f"@tool '{node.fn_name}' with risk_level='high' must have requires_approval=true",
                node=node
            )
    
    def _validate_with_context(self, node: WithContextStmt):
        """验证 with_context 约束"""
        # C-001: with_context 必须指定 max_tokens
        if "max_tokens" not in node.config:
            self._add_violation(
                rule_id="C-001",
                level="ERROR",
                message=f"with_context must specify 'max_tokens'",
                node=node
            )
        
        # C-002: with_context 必须指定 strategy 或 on_overflow
        if "strategy" not in node.config and "on_overflow" not in node.config:
            self._add_violation(
                rule_id="C-002",
                level="ERROR",
                message=f"with_context must specify 'strategy' or 'on_overflow'",
                node=node
            )
    
    def _validate_try_agent(self, node: TryAgentStmt):
        """验证 try_agent 约束"""
        # EC-001: try_agent 必须有至少一个 catch_correction 分支
        if not node.catch_branches:
            self._add_violation(
                rule_id="EC-001",
                level="ERROR",
                message=f"try_agent must have at least one catch_correction branch",
                node=node
            )
    
    def _validate_unharnessed(self, node: UnharnessedStmt):
        """验证 unharnessed 约束"""
        # U-001: unharnessed 必须有 reason 说明
        if not node.reason:
            self._add_violation(
                rule_id="U-001",
                level="WARN",
                message=f"unharnessed block should have a reason string",
                node=node
            )
        
        # U-002: unharnessed 块内不能有 snapshot/restore
        for stmt in node.body:
            if isinstance(stmt, (SnapshotStmt, RestoreStmt)):
                self._add_violation(
                    rule_id="U-002",
                    level="ERROR",
                    message=f"unharnessed block cannot contain snapshot/restore operations",
                    node=node
                )
    
    def _validate_harness_agent(self, node: HarnessAgentDecl):
        """验证 Harness agent 整体约束"""
        # 如果有 autoloop，检查是否在 agent 内
        # E-003 已在 autoloop 验证中覆盖
        
        # 如果 agent 有 autoloop 但没有 context_policy
        if node.autoloop and not node.context_policy:
            self._add_violation(
                rule_id="H-001",
                level="WARN",
                message=f"Agent '{node.name}' has autoloop but no context_policy — risk of context overflow",
                node=node
            )
        
        # 如果 agent 有 autoloop 但没有 lifecycle hooks
        if node.autoloop and not node.lifecycle_hooks:
            self._add_violation(
                rule_id="H-002",
                level="INFO",
                message=f"Agent '{node.name}' has autoloop but no lifecycle hooks — consider adding before_step/after_step",
                node=node
            )
    
    def _add_violation(self, rule_id: str, level: str, message: str, node: Any):
        """添加验证违规"""
        # 根据 mode 调整级别
        effective_level = level
        if self._mode == HarnessMode.OFF:
            return  # 不执行任何验证
        elif self._mode == HarnessMode.WARN:
            if level == "ERROR":
                effective_level = "WARN"  # 降级为警告
        elif self._mode == HarnessMode.STRICT:
            effective_level = level  # 保持原级别
        
        self._violations.append(HarnessViolation(
            rule_id=rule_id,
            level=effective_level,
            message=message,
            node_type=type(node).__name__
        ))

@dataclass
class HarnessViolation:
    """验证违规"""
    rule_id: str
    level: str       # ERROR | WARN | INFO
    message: str
    node_type: str

@dataclass
class HarnessValidationReport:
    """验证报告"""
    violations: List[HarnessViolation]
    mode: HarnessMode
    total_rules: int
    passed: bool
    
    def format_report(self) -> str:
        """格式化验证报告"""
        lines = [f"Harness Validation Report (mode={self._mode.value})"]
        lines.append(f"Total rules: {self.total_rules}")
        lines.append(f"Violations: {len(self.violations)}")
        lines.append(f"Passed: {self.passed}")
        lines.append("")
        
        for v in self.violations:
            icon = "❌" if v.level == "ERROR" else "⚠️" if v.level == "WARN" else "ℹ️"
            lines.append(f"  {icon} [{v.rule_id}] {v.level}: {v.message} (in {v.node_type})")
        
        return "\n".join(lines)
```

### 4.3 Validator 在编译管线中的位置

```python
# cli.py 中的编译流程修改
def compile_nexa(source: str, harness_mode: str = "warn") -> Tuple[str, HarnessValidationReport]:
    """v2.0 编译流程"""
    
    # Step 1: Parse
    parse_tree = parser.parse(source)
    
    # Step 2: AST Transform
    ast = transformer.transform(parse_tree)
    
    # Step 3: Harness Validate (NEW)
    validator = HarnessValidator(mode=HarnessMode(harness_mode))
    report = validator.validate(ast)
    
    # 如果 strict 模式下有 ERROR，停止编译
    if harness_mode == "strict" and not report.passed:
        print(report.format_report())
        raise HarnessValidationError(report)
    
    # 打印验证报告（即使通过也显示 INFO/WARN）
    if report.violations:
        print(report.format_report())
    
    # Step 4: Code Generate
    code = code_generator.generate(ast, harness_report=report)
    
    return code, report
```

---

## 5. Code Generator 多后端重构

### 5.1 后端抽象层

v2.0 Code Generator 从单后端（Python）重构为多后端架构：

```python
class CodeGenerator:
    """
    多后端代码生成器
    
    后端选择:
    ├── PythonBackend: 生成 Python 代码 (兼容 v1.x)
    ├── AVMBackend: 生成 AVM 字节码 (主目标)
    ├── WASMBackend: 生成 WASM 模块 (Tool 沙箱)
    """
    
    def __init__(self, backend: str = "python"):
        self._backend = self._create_backend(backend)
    
    def _create_backend(self, backend: str) -> CodeGenBackend:
        if backend == "python":
            return PythonBackend()
        elif backend == "avm":
            return AVMBytecodeBackend()
        elif backend == "wasm":
            return WASMToolBackend()
        else:
            raise ValueError(f"Unknown backend: {backend}")
    
    def generate(self, ast: List[Any], harness_report: HarnessValidationReport) -> str:
        """生成目标代码"""
        return self._backend.generate(ast, harness_report)

class CodeGenBackend(ABC):
    """代码生成后端抽象基类"""
    
    @abstractmethod
    def generate(self, ast: List[Any], harness_report: HarnessValidationReport) -> str:
        """生成目标代码"""
        ...
```

### 5.2 Python Backend (兼容 v1.x)

Python Backend 是 v2.0 的首要实现目标，它生成与 v1.x 兼容的 Python 代码，但增加了 Harness Runtime 调用：

```python
class PythonBackend(CodeGenBackend):
    """
    Python 代码生成后端
    
    与 v1.x 的区别:
    ├── BOILERPLATE 增加 Harness Runtime 导入
    ├── @tool 函数生成自动 Schema + 注册逻辑
    ├── autoloop 生成 HarnessKernel.run_autoloop() 调用
    ├── with_context 生成 ContextManager.enter_scope/exit_scope 调用
    ├── try_agent 生成 try_agent/catch_correction 运行时逻辑
    ├── snapshot/restore 生成 StateStore 操作
    ├── verify 生成 EvaluationInterface 调用
    ├── reflect 生成 nexa_reflect() 调用
    ├── fork 生成 ActorSystem.fork_execution() 调用
    ├── unharnessed 生成带 trace 标记的代码块
    └── lifecycle hooks 生成 LifecycleHookManager.register() 调用
    """
    
    def generate(self, ast: List[Any], harness_report: HarnessValidationReport) -> str:
        """生成 Python 代码"""
        parts = []
        
        # 1. BOILERPLATE (增强版)
        parts.append(self._generate_harness_boilerplate())
        
        # 2. 逐节点生成
        for node in ast:
            if isinstance(node, ToolAnnotation):
                parts.append(self._gen_tool_annotation(node))
            elif isinstance(node, HarnessAgentDecl):
                parts.append(self._gen_harness_agent(node))
            elif isinstance(node, AutoLoopStmt):
                parts.append(self._gen_autoloop(node))
            elif isinstance(node, WithContextStmt):
                parts.append(self._gen_with_context(node))
            elif isinstance(node, TryAgentStmt):
                parts.append(self._gen_try_agent(node))
            # ... v1.x 节点生成逻辑保留
            else:
                parts.append(self._gen_v1x_node(node))
        
        return "\n".join(parts)
    
    def _generate_harness_boilerplate(self) -> str:
        """v2.0 增强 BOILERPLATE"""
        return """
# Nexa v2.0 Harness Runtime imports
from src.runtime.harness_kernel import HarnessKernel, HarnessConfig, HarnessMode
from src.runtime.execution_engine import ExecutionEngine, AutoLoopConfig, AutoLoopResult
from src.runtime.context_manager import ContextManager, ContextConfig, EvictionStrategy
from src.runtime.tool_registry import ToolRegistry, ToolSpec
from src.runtime.state_store import StateStore, SnapshotHandle
from src.runtime.lifecycle_hooks import LifecycleHookManager, HookDecision
from src.runtime.evaluation_interface import EvaluationInterface, VerifyResult
from src.runtime.llm_router import LLMRouter, ModelRequirement
from src.runtime.actor_system import ActorSystem, ActorHandle
from src.runtime.trace_system import TraceSystem, TraceLog
from src.runtime.sandbox_pool import SandboxPool, WasmSandbox

# v1.x Runtime imports (保留兼容)
from src.runtime.agent import NexaAgent
from src.runtime.orchestrator import join_agents, nexa_pipeline
from src.runtime.dag_orchestrator import dag_fanout, dag_merge, SmartRouter
from src.runtime.memory import global_memory
from src.runtime.stdlib import STD_TOOLS_SCHEMA, STD_NAMESPACE_MAP
from src.runtime.secrets import nexa_secrets
from src.runtime.core import nexa_fallback, nexa_img_loader
from src.runtime.compactor import ContextCompactor
from src.runtime.cow_state import CowAgentState
from src.runtime.reason import reason, reason_float, reason_int, reason_bool
from src.runtime.hitl import wait_for_human, ApprovalStatus
from src.runtime.contracts import ContractSpec, ContractClause, ContractViolation
from src.runtime.result_types import NexaResult, NexaOption, ErrorPropagation
from src.runtime.type_system import TypeChecker, TypeViolation
from src.runtime.pattern_matching import nexa_match_pattern, nexa_destructure
from src.runtime.adt import register_struct, make_struct_instance, register_enum, make_variant
"""
    
    def _gen_tool_annotation(self, node: ToolAnnotation) -> str:
        """生成 @tool 函数 + 自动 Schema 注册"""
        # 1. 生成函数定义
        fn_code = f"def {node.fn_name}({self._gen_params(node.params)}):"
        if node.return_type:
            fn_code += f" -> {node.return_type}"
        fn_code += "\n"
        for stmt in node.body:
            fn_code += f"    {self._gen_stmt(stmt)}\n"
        
        # 2. 生成 Schema 注册
        schema_code = f"""
# @tool auto-registration
_tool_registry.register_from_annotation(
    fn={node.fn_name},
    description="{node.description}",
    risk_level="{node.risk_level}",
    requires_approval={node.requires_approval}
)
"""
        return fn_code + schema_code
    
    def _gen_harness_agent(self, node: HarnessAgentDecl) -> str:
        """生成 Harness agent"""
        # 生成 agent 创建 + Harness 配置
        agent_code = f"""
# Harness Agent: {node.name}
_{node.name}_config = HarnessConfig(
    execution=AutoLoopConfig(
        max_steps={node.autoloop.max_steps if node.autoloop else 50},
        exit_when={repr(node.autoloop.exit_when) if node.autoloop else None},
    ),
    context=ContextConfig(
        max_tokens={node.context_policy.params.get('max_tokens', 100000) if node.context_policy else 100000},
        strategy=EvictionStrategy.{node.context_policy.params.get('strategy', 'IMPORTANCE_WEIGHTED').upper() if node.context_policy else 'IMPORTANCE_WEIGHTED'},
    ),
)
_{node.name}_kernel = HarnessKernel(_{node.name}_config)
"""
        
        # 生成 lifecycle hooks 注册
        for hook in node.lifecycle_hooks:
            agent_code += self._gen_lifecycle_hook(node.name, hook)
        
        return agent_code
    
    def _gen_autoloop(self, node: AutoLoopStmt) -> str:
        """生成 autoloop 调用"""
        return f"""
# autoloop execution
_result = _kernel.run_autoloop(
    context=_harness_context,
    config=AutoLoopConfig(
        max_steps={node.max_steps or 50},
        exit_when={repr(node.exit_when)},
        timeout_seconds={node.timeout or 300},
    )
)
"""
    
    def _gen_with_context(self, node: WithContextStmt) -> str:
        """生成 with_context 作用域"""
        return f"""
# with_context scope
_scope = _context_manager.enter_scope(ContextConfig(
    max_tokens={node.config.get('max_tokens', 100000)},
    strategy=EvictionStrategy.{node.config.get('strategy', 'SLIDING_WINDOW').upper()},
))
try:
    {self._gen_body(node.body)}
finally:
    _context_manager.exit_scope(_scope)
"""
    
    def _gen_try_agent(self, node: TryAgentStmt) -> str:
        """生成 try_agent/catch_correction"""
        code = "try:\n"
        for stmt in node.try_body:
            code += f"    {self._gen_stmt(stmt)}\n"
        
        for branch in node.catch_branches:
            code += f"except {branch.error_type} as {branch.error_var}:\n"
            for stmt in branch.correction_body:
                if isinstance(stmt, ReflectStmt):
                    code += f"    nexa_reflect(_agent, {repr(stmt.text)})\n"
                else:
                    code += f"    {self._gen_stmt(stmt)}\n"
        
        return code
```

### 5.3 AVM Bytecode Backend

AVM Bytecode Backend 是 v2.0 的主目标后端，生成 Rust AVM 可执行的字节码：

```python
class AVMBytecodeBackend(CodeGenBackend):
    """
    AVM 字节码生成后端
    
    生成流程:
    .nx → AST → Harness Validator → AVM Bytecode Module
    
    字节码格式:
    ├── Header: 版本号 + 模块名 + 常量池大小
    ├── Constant Pool: 字符串/数字/类型常量
    ├── Symbol Table: 变量/函数/agent/tool 符号
    ├── Code Section: 字节码指令序列
    ├── Metadata: Harness 配置 + Trace 配置
    """
    
    def generate(self, ast: List[Any], harness_report: HarnessValidationReport) -> str:
        """生成 AVM 字节码 (二进制格式)"""
        module = BytecodeModule(name="nexa_main")
        
        # 1. 注册常量
        self._register_constants(module, ast)
        
        # 2. 注册符号
        self._register_symbols(module, ast)
        
        # 3. 生成指令
        for node in ast:
            self._gen_node_instructions(module, node)
        
        # 4. 添加 Harness Metadata
        module.metadata = self._gen_harness_metadata(harness_report)
        
        # 5. 序列化
        return module.to_bytes()
```

---

## 6. AVM 字节码指令集扩展

### 6.1 v1.x AVM 指令集回顾

v1.x AVM（[`avm/src/bytecode/instructions.rs`](avm/src/bytecode/instructions.rs)）定义了约 30 条基础指令：

```rust
pub enum OpCode {
    // 基础操作
    Nop, Push, Pop, Dup, Swap,
    // 变量操作
    Load, Store, LoadGlobal, StoreGlobal,
    // 算术运算
    Add, Sub, Mul, Div, Mod,
    // 比较运算
    Eq, Ne, Lt, Gt, Le, Ge,
    // 控制流
    Jump, JumpIf, JumpIfNot, Call, Return,
    // Agent 操作
    AgentCreate, AgentRun, AgentClone,
    // 流程编排
    Pipeline, Fork, Merge,
    // LLM 操作
    LLMCall, LLMStream,
    // 工具操作
    ToolCall, ToolReturn,
    // 记忆操作
    MemStore, MemLoad,
}
```

### 6.2 v2.0 新增 Harness 指令

v2.0 在 OpCode enum 中新增约 50 条 Harness 指令：

```rust
pub enum OpCode {
    // ═══ v1.x 基础指令 (保留) ═══
    Nop, Push, Pop, Dup, Swap,
    Load, Store, LoadGlobal, StoreGlobal,
    Add, Sub, Mul, Div, Mod,
    Eq, Ne, Lt, Gt, Le, Ge,
    Jump, JumpIf, JumpIfNot, Call, Return,
    AgentCreate, AgentRun, AgentClone,
    Pipeline, Fork, Merge,
    LLMCall, LLMStream,
    ToolCall, ToolReturn,
    MemStore, MemLoad,
    
    // ═══ v2.0 Harness 指令 (新增) ═══
    
    // ─── E: Execution Loop ───
    AutoLoopStart { max_steps: u32, exit_when: Option<StringId>, timeout: u32 },
    AutoLoopStep,                              // 执行一个 ReAct step
    AutoLoopCheckExit,                         // 检查退出条件
    AutoLoopEnd,                               // 结束 autoloop
    
    // ─── T: Tool Registry ───
    ToolRegister { name: StringId, description: StringId, risk_level: u8 },
    ToolRegisterSchema,                        // 自动生成 JSON Schema
    ToolExecuteSandboxed { tool_id: u32 },     // 在沙箱中执行 tool
    ToolRequestApproval { tool_id: u32 },      // HITL 请求审批
    
    // ─── C: Context Manager ───
    ContextEnterScope { max_tokens: u32, strategy: u8 },  // with_context 进入
    ContextExitScope,                          // with_context 退出
    ContextAddMessage { role: u8 },            // 添加消息到上下文
    ContextAddToolResult,                      // 添加工具结果（可能卸载）
    ContextCheckEviction,                      // 检查 Token 溢出
    ContextEvict { strategy: u8 },             // 执行 eviction
    
    // ─── S: State Store ───
    StateSnapshot,                             // 创建 COW 快照
    StateRestore { snapshot_id: u32 },         // 恢复快照
    StateFork { branch_count: u32 },           // 创建多个 COW 分支
    StateMergeBranches { strategy: u8 },       // 合并分支结果
    StateStoreKV { key: StringId },            // 存储到 KV
    StateLoadKV { key: StringId },             // 从 KV 加载
    StateStoreVector { key: StringId },        // 存储到 Vector Store
    StateSearchVector { top_k: u32 },          // 从 Vector Store 搜索
    
    // ─── L: Lifecycle Hooks ───
    HookRegisterBeforeStep { hook_id: u32 },   // 注册 before_step 钩子
    HookRegisterAfterStep { hook_id: u32 },    // 注册 after_step 钩子
    HookRegisterOnError { hook_id: u32 },      // 注册 on_error 钩子
    HookRegisterBeforeTool { tool_name: StringId, hook_id: u32 },
    HookRegisterAfterTool { tool_name: StringId, hook_id: u32 },
    HookFireBeforeStep,                        // 触发 before_step
    HookFireAfterStep,                         // 触发 after_step
    HookFireOnError,                           // 触发 on_error
    HookFireBeforeTool { tool_name: StringId },// 触发 before_tool
    HookFireAfterTool { tool_name: StringId }, // 触发 after_tool
    
    // ─── V: Evaluation Interface ───
    VerifySatisfies { type_id: StringId },     // verify result satisfies Type
    VerifyMethod { method_id: StringId },      // verify result.method()
    VerifySemantic { condition: StringId },    // verify "condition" against result
    
    // ─── AI 专属容错 ───
    TryAgentStart,                             // try_agent 开始
    TryAgentEnd,                               // try_agent 结束
    CatchCorrection { error_type: u8 },        // catch_correction 分支
    Reflect { text: StringId },                // reflect 注入
    
    // ─── Actor System ───
    ActorSpawn { agent_id: StringId },         // spawn 子 Agent
    ActorPass { actor_id: u32 },               // pass 消息
    ActorAwait { actor_id: u32 },              // await 结果
    ActorReceive,                              // receive 消息
    
    // ─── Trace System ───
    TraceRecordStep { step_number: u32 },      // 记录 step
    TraceRecordThought,                        // 记录 thought
    TraceRecordAction { tool_name: StringId }, // 记录 action
    TraceRecordObservation,                    // 记录 observation
    TraceRecordReflection,                     // 记录 reflection
    TraceRecordError,                          // 记录 error
    TraceExport,                               // 导出 trace
    
    // ─── LLM Router ───
    LLMRoute { requirement: u8 },              // 动态路由模型
    LLMCallRouted,                             // 使用路由后的模型调用
    
    // ─── Unharnessed ───
    UnharnessedStart { reason: Option<StringId> },  // unharnessed 块开始
    UnharnessedEnd,                            // unharnessed 块结束
}
```

### 6.3 BytecodeModule Metadata 扩展

v2.0 的 [`BytecodeModule`](avm/src/bytecode/instructions.rs) 需要扩展 Metadata 以包含 Harness 配置：

```rust
pub struct BytecodeMetadata {
    // v1.x 已有
    pub version: String,
    pub module_name: String,
    pub compile_time: u64,
    
    // v2.0 新增: Harness 配置
    pub harness_mode: HarnessMode,       // Strict | Warn | Off
    pub harness_rules_applied: Vec<String>,  // 应用的验证规则 ID
    pub harness_violations: Vec<HarnessViolationInfo>,
    
    // v2.0 新增: 上下文配置
    pub default_max_tokens: u32,
    pub default_eviction_strategy: EvictionStrategy,
    
    // v2.0 新增: Trace 配置
    pub trace_enabled: bool,
    pub trace_output_format: TraceOutputFormat,
}

pub enum HarnessMode {
    Strict,
    Warn,
    Off,
}

pub enum EvictionStrategy {
    SlidingWindow,
    Lru,
    ImportanceWeighted,
    Custom,
}

pub enum TraceOutputFormat {
    DecisionTree,
    Timeline,
    Json,
}
```

---

## 7. WASM Tool Backend

### 7.1 设计目标

`@tool` 注解的函数可以被编译为 WASM 模块，在 AVM 的 WASM 沙箱中安全执行：

- 高风险 Tool（`risk_level=high`）强制 WASM 编译
- WASM 模块有资源限制（CPU/内存/文件系统/网络）
- WASM 模块通过 Host FFI 与 AVM 通信

### 7.2 WASM Tool 编译流程

```
@tool fn grep(pattern: string): string { ... }
                    │
                    ↓ Python Backend: 生成 Python 函数
                    ↓ AVM Backend: 生成 AVM 字节码指令
                    ↓ WASM Backend: 生成 WASM 模块
                    
WASM Tool 编译流程:
.nx @tool 函数 → AST → Rust 代码生成 → wasm-pack build → .wasm 模块
```

### 7.3 WASM Tool SDK

```rust
// avm/src/wasm/sdk.rs — WASM Tool 开发 SDK

use nexa_wasm_sdk::*;

#[nexa_tool(
    name = "grep",
    description = "Search for a pattern in the codebase",
    risk_level = "low"
)]
fn grep(pattern: String, path: String) -> Result<String, ToolError> {
    // 通过 Host FFI 执行 shell 命令
    let output = host_shell_exec(format!("grep -rn {} {}", pattern, path))?;
    Ok(output)
}

#[nexa_tool(
    name = "shell_exec",
    description = "Execute a shell command",
    risk_level = "high",
    requires_approval = true
)]
fn shell_exec(command: String) -> Result<String, ToolError> {
    // 高风险操作 — 需要 HITL 审批
    let approval = host_request_approval("shell_exec", &command)?;
    if !approval.approved {
        return Err(ToolError::Denied(approval.reason));
    }
    let output = host_shell_exec(command)?;
    Ok(output)
}
```

---

## 8. CLI 工具链增强

### 8.1 新增 CLI 命令

v2.0 在 [`cli.py`](src/cli.py) 中新增以下命令：

| 命令 | 用途 | 示例 |
|------|------|------|
| `nexa run --harness=strict` | 以 strict Harness 模式运行 | `nexa run agent.nx --harness=strict` |
| `nexa run --harness=warn` | 以 warn Harness 模式运行（默认） | `nexa run agent.nx` |
| `nexa run --harness=off` | 以 v1.x 兼容模式运行 | `nexa run agent.nx --harness=off` |
| `nexa run --trace=decision_tree.json` | 运行并导出 Trace | `nexa run agent.nx --trace=out.json` |
| `nexa run --context-max-tokens=100000` | 运行时覆盖上下文配置 | `nexa run agent.nx --context-max-tokens=50k` |
| `nexa run --sandbox=enabled` | 启用 WASM 沙箱 | `nexa run agent.nx --sandbox=enabled` |
| `nexa harness-check` | 仅执行 Harness 验证（不运行） | `nexa harness-check agent.nx` |
| `nexa compile --backend=avm` | 编译为 AVM 字节码 | `nexa compile agent.nx --backend=avm` |
| `nexa trace-view` | 可视化 Trace 输出 | `nexa trace-view out.json` |

### 8.2 CLI 命令实现

```python
# cli.py 新增命令处理

def harness_check_file(nx_file_path: str, harness_mode: str = "strict", 
                        json_output: bool = False):
    """仅执行 Harness 验证，不运行代码"""
    source = read_file(nx_file_path)
    parse_tree = parser.parse(source)
    ast = transformer.transform(parse_tree)
    
    validator = HarnessValidator(mode=HarnessMode(harness_mode))
    report = validator.validate(ast)
    
    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.format_report())
    
    if not report.passed and harness_mode == "strict":
        sys.exit(1)

def compile_file(nx_file_path: str, backend: str = "python", 
                  harness_mode: str = "warn", output_path: str = None):
    """编译 .nx 文件到目标后端"""
    source = read_file(nx_file_path)
    parse_tree = parser.parse(source)
    ast = transformer.transform(parse_tree)
    
    validator = HarnessValidator(mode=HarnessMode(harness_mode))
    report = validator.validate(ast)
    
    if not report.passed and harness_mode == "strict":
        print(report.format_report())
        sys.exit(1)
    
    codegen = CodeGenerator(backend=backend)
    output = codegen.generate(ast, harness_report=report)
    
    if output_path:
        with open(output_path, "w") as f:
            f.write(output)
    else:
        print(output)

def trace_view(trace_file: str):
    """可视化 Trace 输出"""
    with open(trace_file) as f:
        trace_data = json.load(f)
    
    # 生成 ASCII 决策树
    tree = generate_decision_tree(trace_data)
    print(tree)
```

### 8.3 argparse 扩展

```python
# main() 中新增 argparse 参数

parser.add_argument("--harness", choices=["strict", "warn", "off"], default="warn",
                    help="Harness validation mode (default: warn)")
parser.add_argument("--backend", choices=["python", "avm", "wasm"], default="python",
                    help="Compilation backend (default: python)")
parser.add_argument("--trace-output", type=str, default=None,
                    help="Export trace to file (decision_tree.json or timeline.json)")
parser.add_argument("--context-max-tokens", type=int, default=None,
                    help="Override context max_tokens at runtime")
parser.add_argument("--sandbox", choices=["enabled", "disabled"], default="disabled",
                    help="Enable WASM sandbox for tool execution")
parser.add_argument("--sandbox-pool-size", type=int, default=5,
                    help="WASM sandbox pool size")
```

---

## 9. Debugger & Inspector 增强

### 9.1 Harness-aware Debugger

v2.0 的 [`debugger.py`](src/runtime/debugger.py) 需要增强为 Harness-aware：

```python
class HarnessDebugger:
    """
    Harness-aware 调试器
    
    新增功能:
    ├── step-by-step autoloop 调试 (类似 Python pdb)
    ├── 上下文状态实时查看
    ├── COW 快照树可视化
    ├── Lifecycle hooks 执行追踪
    ├── Trace 决策树交互式浏览
    """
    
    def break_at_step(self, step_number: int):
        """在指定 step 处设置断点"""
        ...
    
    def inspect_context(self):
        """查看当前上下文状态"""
        ...
    
    def inspect_cow_tree(self):
        """查看 COW 快照树"""
        ...
    
    def step_over(self):
        """跳过当前 step"""
        ...
    
    def step_into_tool(self):
        """进入 tool 执行"""
        ...
    
    def continue_execution(self):
        """继续执行到下一个断点"""
        ...
```

### 9.2 Inspector 增强

v2.0 的 [`inspector.py`](src/runtime/inspector.py) 增加 Harness 信息输出：

```python
def inspect_harness(nx_file_path: str):
    """输出 Harness 结构分析"""
    # 1. 列出所有 @tool 函数及其 Schema
    # 2. 列出所有 agent 的 Harness 配置
    # 3. 列出所有 autoloop 的退出条件
    # 4. 列出所有 with_context 的 eviction 策略
    # 5. 列出所有 lifecycle hooks
    # 6. 列出所有 verify 语句
    # 7. 列出所有 unharnessed 块
    # 8. 输出 Harness 验证报告
```

---

## 10. 编译器实现步骤

### 10.1 实现顺序

```
Phase 1: Parser + AST Transformer 扩展
  ├── Step 1.1: 添加 %declare exclusion keywords
  ├── Step 1.2: 添加新语法规则到 nexa_grammar
  ├── Step 1.3: 新增 AST 节点 dataclass
  ├── Step 1.4: 新增 AST Transformer handler 方法
  ├── Step 1.5: 更新 _SCORE_TABLE 消歧评分
  ├── Step 1.6: 测试新语法解析正确性

Phase 2: Harness Validator
  ├── Step 2.1: 定义 HarnessRule 和 HarnessViolation 数据结构
  ├── Step 2.2: 实现 HarnessValidator 类
  ├── Step 2.3: 实现 E/T/C/S/L/V 各类验证规则
  ├── Step 2.4: 实现 HarnessValidationReport 格式化
  ├── Step 2.5: 集成到编译管线
  ├── Step 2.6: 测试验证规则正确性

Phase 3: Python Backend Code Generator
  ├── Step 3.1: 定义 CodeGenBackend 抽象基类
  ├── Step 3.2: 实现 PythonBackend 类
  ├── Step 3.3: 增强 BOILERPLATE (Harness Runtime 导入)
  ├── Step 3.4: 实现 @tool 代码生成
  ├── Step 3.5: 实现 autoloop 代码生成
  ├── Step 3.6: 实现 with_context 代码生成
  ├── Step 3.7: 实现 try_agent/catch_correction 代码生成
  ├── Step 3.8: 实现 snapshot/restore/fork 代码生成
  ├── Step 3.9: 实现 verify 代码生成
  ├── Step 3.10: 实现 reflect 代码生成
  ├── Step 3.11: 实现 unharnessed 代码生成
  ├── Step 3.12: 实现 lifecycle hooks 代码生成
  ├── Step 3.13: 测试 Python 代码生成正确性

Phase 4: AVM Bytecode Backend (后续)
  ├── Step 4.1: 扩展 OpCode enum (新增 ~50 条指令)
  ├── Step 4.2: 扩展 BytecodeMetadata (Harness 配置)
  ├── Step 4.3: 实现 AVMBytecodeBackend 类
  ├── Step 4.4: 实现 Harness 指令的字节码生成
  ├── Step 4.5: 更新 AVM Interpreter 支持 Harness 指令
  ├── Step 4.6: 测试 AVM 字节码执行正确性

Phase 5: WASM Tool Backend (后续)
  ├── Step 5.1: 实现 WASMToolBackend 类
  ├── Step 5.2: 实现 @tool → Rust → WASM 编译流程
  ├── Step 5.3: 实现 Host FFI 接口
  ├── Step 5.4: 测试 WASM Tool 执行正确性

Phase 6: CLI 工具链增强
  ├── Step 6.1: 新增 --harness/--backend/--trace-output CLI 参数
  ├── Step 6.2: 实现 harness-check 命令
  ├── Step 6.3: 实现 compile --backend 命令
  ├── Step 6.4: 实现 trace-view 命令
  ├── Step 6.5: 增强 debugger/inspector
```

### 10.2 关键依赖关系

```
Parser 扩展 ──→ AST Transformer 扩展 ──→ Harness Validator
                                              │
                                              ↓
                                    Python Backend Code Gen
                                              │
                                              ↓
                                    AVM Bytecode Backend (后续)
                                              │
                                              ↓
                                    WASM Tool Backend (后续)
```

Python Backend 是所有后端的基础——它验证了 Harness 语义的正确性，其他后端只是将同一语义映射到不同的执行环境。

---

## 11. 测试策略

### 11.1 编译器测试层次

| 测试层次 | 测试内容 | 工具 |
|----------|---------|------|
| **L1 — 语法解析** | 新增语法规则能否正确解析 | `pytest` + Lark parse tree 检查 |
| **L2 — AST 转换** | 新增 handler 能否正确生成 AST 节点 | `pytest` + AST 节点类型检查 |
| **L3 — Harness 验证** | 验证规则能否正确检测违规 | `pytest` + HarnessValidationReport 检查 |
| **L4 — 代码生成** | 生成的 Python 代码能否正确执行 | `pytest` + 运行生成代码 |
| **L5 — 集成测试** | 完整 .nx → Python → 运行流程 | `pytest` + end-to-end |
| **L6 — AVM 测试** | 字节码能否在 AVM 中正确执行 | `cargo test` + AVM integration |

### 11.2 Harness Validator 测试矩阵

```python
# 每个 Harness 规则需要至少 2 个测试: 1 个违规 + 1 个合规

class TestHarnessValidator:
    def test_E001_autoloop_without_exit_condition(self):
        """E-001: autoloop 必须有 max_steps 或 exit_when"""
        ast = [AutoLoopStmt(max_steps=None, exit_when=None, timeout=None, body=[...])]
        validator = HarnessValidator(mode=HarnessMode.STRICT)
        report = validator.validate(ast)
        assert not report.passed
        assert any(v.rule_id == "E-001" for v in report.violations)
    
    def test_E001_autoloop_with_max_steps(self):
        """E-001: autoloop 有 max_steps — 合规"""
        ast = [AutoLoopStmt(max_steps=50, exit_when=None, timeout=None, body=[...])]
        validator = HarnessValidator(mode=HarnessMode.STRICT)
        report = validator.validate(ast)
        assert not any(v.rule_id == "E-001" for v in report.violations)
    
    # ... 类似测试覆盖所有 E/T/C/S/L/V 规则
```

### 11.3 代码生成测试策略

```python
class TestPythonBackend:
    def test_tool_annotation_generates_schema(self):
        """@tool 生成自动 Schema 注册"""
        ast = [ToolAnnotation(
            description="Search codebase",
            fn_name="grep",
            params=[("pattern", "string", None), ("path", "string", ".")],
            return_type="string",
            body=[...],
        )]
        codegen = PythonBackend()
        code = codegen.generate(ast, HarnessValidationReport(passed=True, ...))
        assert "_tool_registry.register_from_annotation" in code
        assert "fn=grep" in code
    
    def test_autoloop_generates_kernel_call(self):
        """autoloop 生成 HarnessKernel.run_autoloop() 调用"""
        ast = [AutoLoopStmt(max_steps=50, exit_when="resolved", ...)]
        codegen = PythonBackend()
        code = codegen.generate(ast, ...)
        assert "_kernel.run_autoloop" in code
        assert "max_steps=50" in code
```

---

## 12. 编译器设计决策记录

### 12.1 为什么 Harness Validator 是独立阶段而非 AST Transformer 内的检查？

- **关注点分离**: AST Transformer 负责语法→语义映射，Validator 负责语义→约束验证
- **可配置性**: Validator 的 mode (strict/warn/off) 不影响 AST 转换逻辑
- **可扩展性**: 新增验证规则只需修改 Validator，不需要修改 Transformer
- **报告质量**: 独立 Validator 可以生成结构化的验证报告

### 12.2 为什么 Python Backend 先于 AVM Backend？

- **验证优先**: Python Backend 可以最快验证 Harness 语义的正确性
- **兼容性**: Python Backend 保证 v1.x 代码可以继续运行
- **调试便利**: Python 代码可以直接调试，AVM 字节码调试困难
- **渐进迁移**: 先用 Python 验证设计，再用 AVM 追求性能

### 12.3 为什么 @tool 生成 Python 函数而非仅生成 Schema？

- **可执行性**: 生成的 Python 函数可以直接在 Python Runtime 中执行
- **调试性**: 函数体是可读的 Python 代码，便于调试
- **Schema 自动化**: 函数签名自动生成 Schema，不需要手动维护两份代码
- **AVM 兼容**: 函数体可以被 AVM Backend 映射为 ToolCall 指令

### 12.4 为什么 `step`/`pass`/`await` 采用上下文敏感解析？

- **减少冲突**: 这些词在 v1.x 中可能作为变量名使用
- **渐进迁移**: 不需要一次性修改所有 v1.x 代码
- **语义清晰**: 在 autoloop 内 `step()` 是关键字，在 flow 内 `step` 是变量名
- **Lark 支持**: Earley 解析器天然支持上下文敏感的歧义消解