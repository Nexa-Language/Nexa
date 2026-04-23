# Nexa 编译器与运行时架构 (v1.3)

> 本文档记录 Nexa 语言从源代码到可执行 Python 代码的完整编译链路，以及 v1.1-v1.3 引入的核心架构模式。

## 1. 编译管线总览

Nexa 的编译管线遵循经典的三阶段架构，但在每个阶段都引入了 Agent-Native 特有的设计决策：

```
┌─────────────────────────────────────────────────────────────────┐
│                     Nexa 编译管线 (v1.3)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────┐    ┌───────────────────┐    ┌──────────────────┐ │
│  │ .nx 源码   │───→│ 1. Lexer + Parser │───→│ 2. AST Transformer│ │
│  │ (Lark)    │    │ (Lark Earley)      │    │ (_ambig scoring)  │ │
│  └───────────┘    └───────────────────┘    └──────────────────┘ │
│                                               │                 │
│                                               ↓                 │
│                                      ┌──────────────────┐      │
│                                      │ 3. Code Generator │      │
│                                      │ (BOILERPLATE +    │      │
│                                      │  resolve_expr)    │      │
│                                      └──────────────────┘      │
│                                               │                 │
│                                               ↓                 │
│                                      ┌──────────────────┐      │
│                                      │ 纯 Python 代码     │      │
│                                      │ (NexaRuntime SDK) │      │
│                                      └──────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 前端阶段 (Lexer + Parser)

### 2.1 Lark Earley 解析器

Nexa 前端基于 `Lark` 框架，使用 Earley 算法解析词法与语法。Earley 算法的优势在于支持任意上下文无关文法 (CFG)，不要求文法是 LR(1) 或 LALR(1) 兼容的。

这对 Nexa 尤为关键——因为 Nexa 的语法定义了大量互不排斥的表达式层级（管道、DAG、语义条件、类型注解、模式匹配、ADT 等），严格的自底向上解析策略无法处理这些歧义。

### 2.2 `_ambig()` 消歧策略

Earley 解析器在遇到歧义时会产生多个候选解析树。Nexa 通过 AST Transformer 的 `_score_ast_node()` 方法解决歧义：

```python
# ast_transformer.py — 评分表
_SCORE_TABLE = {
    "MatchExpression": 50,    # P3-3 模式匹配
    "MatchArm": 45,
    "StructDeclaration": 60,  # P3-4 ADT
    "EnumDeclaration": 60,
    "TraitDeclaration": 60,
    "ImplDeclaration": 60,
    "VariantCallExpression": 55,
    "FieldInitExpression": 45,
    "PipelineExpression": 30,
    "DAGForkExpression": 35,
    "ContractSpec": 40,       # P0-2 DbC
    "Literal": 38,
    "Variable": 35,
}
```

**设计原则**：越具体的语法结构评分越高，越通用的评分越低。当 Earley 解析器产生歧义森林时，Transformer 选择总评分最高的分支。

### 2.3 语法扩展 (v1.1-v1.3)

每个新特性都在 `src/nexa_parser.py` 中添加了对应的语法规则：

| 版本 | 特性 | 新增语法规则 |
|------|------|-------------|
| v1.1.0 | IDD | `@implements`/`@supports` 注解解析 |
| v1.2.0 | DbC | `requires`/`ensures`/`invariant` 语句 |
| v1.3.0 | Tooling | CLI 命令扩展 |
| v1.3.1 | Type System | 类型注解表达式 |
| v1.3.2 | Error Propagation | `?` operator, `otherwise` |
| v1.3.3 | Job System | `job` 声明 |
| v1.3.4 | HTTP Server | `server` 声明 |
| v1.3.5 | Database | `db` 声明 |
| v1.3.6 | Auth/Conc/KV/Tmpl | `auth_decl`/`concurrent_decl`/`kv_decl`/`template_expr` |
| v1.3.7 | Pipe/Defer/??/Interp/Pattern/ADT | `pipe_expr`/`defer_stmt`/`null_coalesce_expr`/string interpolation/`match_expr`/7 pattern rules/`struct_decl`/`enum_decl`/`trait_decl`/`impl_decl` |

**排除关键字机制**：新增语法关键字通过 Lark 的 `%declare` 声明为 exclusion keyword，避免与已有的 IDENTIFIER 产生歧义。例如 `defer`、`match`、`struct`、`enum`、`trait`、`impl`、`template` 都被声明为 exclusion keyword。

## 3. AST Transformer (中间层)

### 3.1 智能脱糖 (Desugaring)

AST Transformer 不仅负责将 Lark 的原始解析树转换为内部 AST 表示，还执行关键的脱糖操作：

**管道操作符脱糖** (`|>`):
```nexa
result |> format_output |> extract_answer
# 脱糖为:
extract_answer(format_output(result))
```

**带参数的管道脱糖**:
```nexa
data |> std.text.upper |> process(delimiter=",")
# 脱糖为:
process(std.text.upper(data), delimiter=",")
```

**Null Coalescing 脱糖** (`??`):
```nexa
a ?? b ?? c
# 脱糖为:
_nexa_null_coalesce(a, _nexa_null_coalesce(b, c))
```

**字符串插值脱糖** (`#{expr}`):
```nexa
"Hello #{user.name}, age #{age}"
# 脱糖为:
_nexa_interp_str([("Hello ", None), ("", "user['name']"), (", age ", None), ("", "age")])
```

### 3.2 新增 Handler 方法 (v1.1-v1.3)

| 版本 | 新增 Handler | 数量 |
|------|-------------|------|
| v1.1.0 | IDD 相关注解 | ~3 |
| v1.2.0 | Contract 语句 | ~3 |
| v1.3.1 | Type 注解 | ~5 |
| v1.3.2 | Error propagation | ~3 |
| v1.3.6 | Template | NexaTemplateParser, TemplatePart, TemplateFilter |
| v1.3.7 | Pattern + ADT | 18 pattern/destructure handlers + 10 ADT handlers |

## 4. Code Generator (后端)

### 4.1 BOILERPLATE Code Generation Pattern

Code Generator 生成 Python 代码时，在文件头部注入一组标准导入和辅助函数（BOILERPLATE）。每个 v1.1-v1.3 的新特性都扩展了 BOILERPLATE：

```python
# code_generator.py — BOILERPLATE 组成部分
BOILERPLATE = """
# Nexa Runtime imports
from src.runtime import (
    NexaRuntime, NexaAgent, NexaFlow,
    # v1.1.0 — IDD
    _nexa_intent_check, _nexa_intent_coverage,
    # v1.2.0 — DbC
    _nexa_contract_check_requires, _nexa_contract_check_ensures,
    _nexa_contract_capture_old, ContractViolation,
    # v1.3.2 — Error Propagation
    NexaResult, NexaOption, ErrorPropagation,
    propagate_or_else, try_propagate, wrap_agent_result,
    # v1.3.3 — Job System
    JobSpec, JobPriority, JobStatus, JobRegistry, JobQueue, JobScheduler,
    # v1.3.7 — Language Expressiveness
    _nexa_null_coalesce, _nexa_interp_str, _nexa_defer_execute,
    nexa_match_pattern, nexa_destructure, nexa_make_variant,
    # v1.3.7 — ADT
    register_struct, make_struct_instance, register_enum, make_variant,
    register_trait, register_impl, call_trait_method,
)
"""
```

### 4.2 Handle-as-dict Pattern

所有运行时 handle 都使用带 `_nexa_*` 前缀键的 Python dict 表示，确保 JSON 兼容性和可序列化：

**Struct instance**:
```python
{
    "_nexa_struct": "Point",
    "_nexa_struct_id": 1,
    "x": 1,
    "y": 2
}
```

**Enum variant**:
```python
{
    "_nexa_variant": "Some",
    "_nexa_enum": "Option",
    "_nexa_variant_id": 1,
    "value": 42
}
```

**Unit variant**:
```python
{
    "_nexa_variant": "None",
    "_nexa_enum": "Option"
}
```

其他 handle-as-dict 应用：

| Handle 类型 | `_nexa_*` 键 | 模块 |
|------------|---------------|------|
| DB 连接 | `_nexa_db`, `_nexa_db_id` | database.py |
| KV Store | `_nexa_kv`, `_nexa_kv_id` | kv_store.py |
| Auth Session | `_nexa_session`, `_nexa_session_id` | auth.py |
| Compiled Template | `_nexa_template`, `_nexa_template_id` | template.py |
| HTTP Server | `_nexa_server`, `_nexa_server_id` | http_server.py |
| Job | `_nexa_job`, `_nexa_job_id` | jobs.py |

### 4.3 表达式解析链 (`_resolve_expression`)

Code Generator 使用 `_resolve_expression()` 方法将 AST 表达式节点转换为 Python 代码字符串。该方法通过表达式类型的 `if/elif` 链处理所有已知表达式类型：

```
PropertyAccess → "obj['attr']"
MethodCall → "obj.method(args)"
PipelineExpression → desugared function call
BinaryExpression → "left op right"
MatchExpression → if/elif chain with isinstance checks
VariantCallExpression → make_variant(Enum, Variant, value)
FieldInitExpression → "key=value"
InterpolatedString → _nexa_interp_str([...])
NullCoalesceExpression → _nexa_null_coalesce(expr, fallback)
PipeExpression → desugared f(x) or f(x, *args)
```

## 5. Runtime Architecture

### 5.1 Thread-safe Registry Pattern

所有需要全局状态的运行时模块都使用统一的线程安全注册表模式：

```python
# 通用模式
_registry_lock = threading.Lock()
_registry = {}
_id_counter = 0

def register_item(name, spec):
    with _registry_lock:
        _id_counter += 1
        _registry[name] = {"_nexa_*_id": _id_counter, ...}
```

应用此模式的模块：

| 模块 | 注册表 | ID 计数器 |
|------|--------|----------|
| `adt.py` | `_struct_registry`, `_enum_registry`, `_trait_registry`, `_impl_registry` | 各自独立的 ID counter |
| `database.py` | `_db_registry` | `_db_id_counter` |
| `kv_store.py` | `_kv_registry` | `_kv_id_counter` |
| `auth.py` | session stores (Memory + SQLite) | session ID |
| `http_server.py` | route registry | server ID |
| `jobs.py` | `JobRegistry` | job ID |
| `template.py` | compiled template cache | template ID |

### 5.2 StdTool Namespace Pattern

`src/runtime/stdlib.py` 提供标准库工具的命名空间注册机制。每个新功能模块通过 `StdTool` 注册到对应的 `std.*` 命名空间：

```python
STD_NAMESPACE_MAP = {
    "std.fs": ["file_read", "file_write", ...],
    "std.http": ["http_get", "http_post", ...],
    "std.db": ["db_query", "db_execute", ...],       # v1.3.5
    "std.auth": ["auth_check", "auth_login", ...],   # v1.3.6
    "std.kv": ["kv_get", "kv_set", ...],             # v1.3.6
    "std.concurrent": ["spawn", "channel", ...],     # v1.3.6
    "std.template": ["template_render", ...],         # v1.3.6
    "std.match": ["match_pattern", ...],             # v1.3.7
    "std.struct": ["struct_create", ...],             # v1.3.7
    "std.enum": ["enum_variant", ...],                # v1.3.7
    "std.trait": ["trait_impl", ...],                 # v1.3.7
}
```

### 5.3 ContractViolation 跨模块集成

ContractViolation 不仅是 DbC 的异常类型，更是跨模块的错误通信协议：

- **HTTP Server**: 路由前置条件违反 → HTTP 401 (requires), 后置条件违反 → HTTP 403 (ensures)
- **KV Store**: 操作失败 → ensures violation
- **Concurrent**: 任务执行失败 → contract violation
- **ADT**: 无效操作（如访问未注册的 struct 字段）→ ContractViolation

## 6. DSL 声明模式

v1.3.x 引入的多个运行时模块都遵循统一的 DSL 声明模式：

```nexa
# 通用 DSL 声明语法
module_type name [parameters] {
    declaration_1
    declaration_2
    ...
}
```

具体应用：

| DSL | 语法 | 版本 |
|-----|------|------|
| Job | `job SendEmail on "emails" (retry: 2) { ... }` | v1.3.3 |
| HTTP Server | `server 8080 { static/cors/route }` | v1.3.4 |
| Database | `db connect "sqlite://..." { query/execute }` | v1.3.5 |
| Auth | `auth_decl { providers/session_store }` | v1.3.6 |
| Concurrency | `concurrent_decl { spawn/parallel/race/channel }` | v1.3.6 |
| KV Store | `kv_decl { open }` | v1.3.6 |
| Template | `template"""..."""` | v1.3.6 |
| Struct | `struct Point { x: Int, y: Int }` | v1.3.7 |
| Enum | `enum Option { Some(value), None }` | v1.3.7 |
| Trait | `trait Printable { fn format() }` | v1.3.7 |
| Impl | `impl Printable for Point { ... }` | v1.3.7 |

## 7. 模块依赖关系

```
src/runtime/__init__.py ← 所有模块的导出枢纽
    ├── core.py          ← NexaRuntime 核心
    ├── agent.py         ← NexaAgent (uses: contracts, type_system, secrets)
    ├── contracts.py     ← ContractSpec, ContractViolation
    ├── type_system.py   ← TypeChecker, TypeInferrer
    ├── result_types.py  ← NexaResult, NexaOption, ErrorPropagation
    ├── jobs.py          ← JobSpec, JobRegistry, JobScheduler
    ├── http_server.py   ← NexaHttpServer (uses: contracts)
    ├── database.py      ← NexaDatabase, NexaSQLite, NexaPostgres
    ├── auth.py          ← NexaAuth (uses: contracts)
    ├── concurrent.py    ← NexaConcurrencyRuntime
    ├── kv_store.py      ← NexaKVStore (uses: contracts)
    ├── template.py      ← NexaTemplateRenderer
    ├── pattern_matching.py ← nexa_match_pattern, nexa_destructure
    ├── adt.py           ← ADT registries (uses: contracts)
    ├── inspector.py     ← structural analysis
    ├── validator.py     ← semantic validation
    ├── stdlib.py        ← StdTool namespace registry
    └─────────── ...

src/ial/
    ├── primitives.py    ← Intent 原语
    ├── vocabulary.py    ← 术语词汇
    ├── standard.py      ← 40+ 标准术语
    ├── resolve.py       ← 模糊匹配引擎
    └── execute.py       ← 执行验证引擎
```

## 8. Rust AVM 架构 (v1.0 基础)

Rust AVM 作为高性能执行引擎，与 Python 编译管线并行发展：

```
avm/src/
    ├── compiler/        ← Lexer (logos) → Parser (lalrpop) → AST → Type Checker
    ├── bytecode/        ← Compiler → Instructions → Bytecode
    ├── vm/              ← Interpreter + Stack + Scheduler + ContextPager + CowMemory
    ├── runtime/         ← agent.rs + llm.rs + tool.rs + contracts.rs + jobs.rs + result_types.rs
    ├── ffi/             ← python.rs (Python FFI) + c_api.rs (C API)
    ├── wasm/            ← sandbox.rs (wasmtime) + runtime.rs
    └─────────── utils/  ← error.rs
```

**Python ↔ Rust 同步策略**：Python 编译器与 Rust AVM Lexer 保持一致的 token 定义，确保两个编译前端的语法覆盖范围同步。

## 9. 测试架构

| 测试类型 | 文件位置 | 覆盖范围 |
|---------|---------|---------|
| IAL 测试 | `tests/test_ial.py` | 104 tests |
| Contract 测试 | `tests/test_contracts.py` | 47 tests |
| Inspector 测试 | `tests/test_inspector.py` | 41 tests |
| Type System 测试 | `tests/test_type_system.py` | 79 tests |
| Error Propagation 测试 | `tests/test_error_propagation.py` | 82 tests |
| Job System 测试 | `tests/test_jobs.py` | 73 tests |
| HTTP Server 测试 | `tests/test_http_server.py` | 94 tests |
| Database 测试 | `tests/test_database.py` | 79+5 tests |
| Auth 测试 | `tests/test_auth.py` | 79+5 tests |
| Concurrency 测试 | `tests/test_concurrent.py` | 172 tests |
| KV Store 测试 | `tests/test_kv_store.py` | 81 tests |
| Template 测试 | `tests/test_template.py` | 209 tests |
| Batch A (Pipe+Defer+??) | `tests/test_batch_a.py` | 84 tests |
| String Interpolation | `tests/test_string_interpolation.py` | 100 tests |
| Pattern Matching | `tests/test_pattern_matching.py` | 91 tests |
| ADT | `tests/test_adt.py` | 100 tests |
| **Total** | | **~1500+** |

## 10. 架构演进历史

| 版本 | 架构变化 |
|------|---------|
| v0.1-v0.8 | 基础 MVP 转译器，Boilerplate Injection 模式 |
| v0.9-alpha | SDK Interop 模式，废弃 Boilerplate Injection，引入 Fast-Path 和 MCP |
| v1.0-alpha | Rust AVM 底座，WASM 沙盒，Smart Scheduler，Context Paging |
| v1.1.0 | IAL 引擎，Intent 术语重写，.nxintent 文件格式 |
| v1.2.0 | Contract 系统，ContractViolation 跨模块集成 |
| v1.3.0 | Agent-Native Tooling，AST scoring 消歧 |
| v1.3.1-v1.3.7 | 14 个新特性模块，Handle-as-dict Pattern，线程安全注册表 Pattern，StdTool namespace Pattern |
