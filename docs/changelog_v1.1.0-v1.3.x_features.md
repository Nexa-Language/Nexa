# Nexa v1.1.0-v1.3.x Feature Changelog

## Overview

This document records all feature implementations for the Nexa Agent-Native language platform, covering 16 major features across 4 priority tiers (P0–P3), totaling ~1500+ tests.

---

## P0: Core Differentiation Features

### P0-1: Intent-Driven Development (IDD) v1.1.0

**Status**: Completed (104 tests)

Nexa's Intent-Driven Development system provides a structured way to define, track, and verify agent behavioral intents. The IDD system enables developers to specify what an agent *should do* declaratively, then verify implementation correctness against those specifications.

**New files**:
- `src/ial/primitives.py` — Intent primitive definitions (action, goal, constraint, preference)
- `src/ial/vocabulary.py` — Intent vocabulary and term management
- `src/ial/standard.py` — Standard intent vocabulary (40+ built-in intents)
- `src/ial/resolve.py` — Intent resolution engine (fuzzy matching, semantic grouping)
- `src/ial/execute.py` — Intent execution and validation engine
- `src/ial/__init__.py` — Module exports

**CLI commands**: `nexa intent-check`, `nexa intent-coverage`, `nexa inspect`
**File format**: `.nxintent` — Intent specification files alongside `.nx` source files

**Key capabilities**:
- Intent declaration: `intent Bot shall "respond politely to user questions"`
- Intent coverage measurement: percentage of code paths covered by intents
- Intent validation: runtime checking of intent satisfaction
- Fuzzy intent matching: near-match resolution for partial intent specifications

---

### P0-2: Design by Contract v1.2.0

**Status**: Completed (47 tests)

Nexa's Contract system brings Design by Contract (DbC) to agent programming. Developers specify `requires` (preconditions), `ensures` (postconditions), and `invariant` (always-true conditions) that are checked at runtime.

**New files**:
- `src/runtime/contracts.py` — ContractSpec, ContractClause, ContractViolation, check_requires, check_ensures, capture_old_values

**Contract syntax**:
```nexa
requires: input != None
ensures: result.length > 0
invariant: self.state in ["idle", "running"]
```

**ContractViolation** integrates with HTTP server (401→requires, 403→ensures), KV store, and concurrent operations.

---

### P0-3: Agent-Native Tooling v1.3.0

**Status**: Completed (41 tests)

Built-in CLI tools for inspecting, validating, and linting Nexa code with agent-aware semantics.

**CLI commands**:
- `nexa inspect` — Structural analysis of agents, tools, flows
- `nexa validate` — Semantic validation of Nexa programs
- `nexa lint` — Style and best-practice checking
- `nexa intent-check` — Intent coverage verification
- `nexa intent-coverage` — Coverage percentage reporting

---

## P1: Essential Features v1.3.x

### P1-1: Gradual Type System v1.3.1

**Status**: Completed (79 tests)

Nexa's gradual type system allows optional type annotations that are enforced based on `NTNT_TYPE_MODE` (strict/warn/forgiving). Type violations produce TypeViolation or TypeWarning depending on mode.

**New files**:
- `src/runtime/type_system.py` — TypeChecker, TypeInferrer, TypeViolation, TypeWarning, TypeCheckResult, TypeMode, LintMode, PrimitiveTypeExpr, GenericTypeExpr, UnionTypeExpr, OptionTypeExpr, ResultTypeExpr, AliasTypeExpr, FuncTypeExpr, SemanticTypeExpr

**Type annotations**: `Int`, `String`, `Bool`, `Float`, `List[Int]`, `Map[String, Int]`, `Option[T]`, `Result[T, E]`
**Type modes**: strict (enforce), warn (log), forgiving (skip)

---

### P1-2: Error Propagation (? + otherwise) v1.3.2

**Status**: Completed (82 tests)

Nexa's error propagation operators enable clean, Rust-inspired error handling:

- `try` — attempt operation, catch errors
- `?` operator — propagate error upward (like Rust's `?`)
- `otherwise` — provide fallback on error

**Syntax**:
```nexa
let result = risky_operation() otherwise "fallback"
let value = parse(input) ? 
```

**New files**:
- `src/runtime/result_types.py` — NexaResult, NexaOption, ErrorPropagation, propagate_or_else, try_propagate, wrap_agent_result

---

### P1-3: Background Job System v1.3.3

**Status**: Completed (73 tests)

Nexa's Job System provides a DSL for background task processing with priority queues, cron scheduling, and retry logic.

**New files**:
- `src/runtime/jobs.py` — JobSpec, JobPriority, JobStatus, BackoffStrategy, JobRegistry, JobQueue, JobWorker, JobScheduler

**Job DSL syntax**:
```nexa
job SendEmail on "emails" (retry: 2, timeout: 120) {
  perform(user_id) { ... }
  on_failure(error, attempt) { ... }
}
```

---

### P1-4: Built-In HTTP Server v1.3.4

**Status**: Completed (94 tests)

Nexa's built-in HTTP server provides a declarative DSL for defining web servers with CORS, CSP, static file serving, middleware, and route definitions.

**New files**:
- `src/runtime/http_server.py` (~1481 lines) — NexaHttpServer, ServerState, CorsConfig, CspConfig, SecurityConfig, NexaRequest, RouteSegment, Route, ContractViolation integration

**Server DSL syntax**:
```nexa
server 8080 {
  static "/assets" from "./public"
  cors { origins: ["*"], methods: ["GET", "POST"] }
  route GET "/chat" => ChatBot
  route POST "/analyze" => DataExtractor |>> Analyzer
}
```

**Key features**: Hot reload, security headers, contract-based route guards, semantic routing, multipart parsing

---

### P1-5: Database Integration v1.3.5

**Status**: Completed (79+5skipped tests)

Nexa's built-in database module provides SQLite and PostgreSQL integration with connection pooling, transactions, and agent-specific memory queries.

**New files**:
- `src/runtime/database.py` (~600 lines) — NexaDatabase, NexaSQLite, NexaPostgres, connection registry, transaction management

**Database DSL syntax**:
```nexa
db connect "sqlite://data.db" {
  query "SELECT * FROM users WHERE id = ?" [user_id]
  execute "INSERT INTO logs (msg) VALUES (?)" [message]
}
```

**Agent-Native extensions**: `agent_memory_query`, `agent_memory_store`, `agent_memory_delete`, `agent_memory_list`

---

## P2: Advanced Features v1.3.6

### P2-1: Built-In Auth & OAuth

**Status**: Completed (79+5skipped tests)

Nexa's 3-layer authentication system: API Key + JWT (HS256) + OAuth 2.0 (PKCE flow). Built-in providers for Google and GitHub.

**New files**:
- `src/runtime/auth.py` (~1500 lines) — NexaAuth, ProviderConfig, AuthConfig, Session, Memory+SQLite SessionStore, CSRF protection, HMAC Cookie signing, BUILTIN_PROVIDERS, require_auth middleware, agent_api_key_generate (format: `nexa-ak-{random32hex}`), agent_auth_context

**Auth DSL syntax**:
```nexa
auth_decl {
  providers: [google(client_id, client_secret), github(client_id, client_secret)]
  session_store: memory
  require_auth: ["/admin", "/api"]
}
```

**Agent-Native**: API Key generation with `nexa-ak-` prefix, auth context injection for agent operations

---

### P2-2: Structured Concurrency

**Status**: Completed (172 tests)

Nexa's structured concurrency module provides safe, scoped concurrent operations with channels, task spawning, parallel execution, and race conditions.

**New files**:
- `src/runtime/concurrent.py` — NexaChannel (queue.Queue), NexaTask (ThreadPoolExecutor + cooperative cancel via threading.Event), NexaSchedule (periodic with panic-catching), NexaConcurrencyRuntime global singleton. 18 API functions.

**Concurrency DSL syntax**:
```nexa
concurrent_decl {
  spawn my_task { ... }
  parallel [task_a, task_b, task_c]
  race [fast_task, slow_task]
  channel ch = channel()
  after 500ms { cleanup() }
  schedule every 30s { health_check() }
}
```

**18 API functions**: channel/send/recv/recv_timeout/try_recv/close/select/spawn/await_task/try_await/cancel_task/parallel/race/after/schedule/cancel_schedule/sleep_ms/thread_count + parse_interval

**Agent-Native**: `spawn` accepts NexaAgent → `agent.run(context)`

---

### P2-3: KV Store

**Status**: Completed (81 tests)

Nexa's built-in Key-Value store with SQLite backend, type-preserving serialization, TTL expiration, and agent-specific query/storage operations.

**New files**:
- `src/runtime/kv_store.py` (~780 lines) — NexaKVStore with SQLite backend, `_nexa_kv` table (key TEXT PK, value TEXT, type TEXT, expires_at INTEGER). Thread-safe registry with `_kv_registry` + `_kv_id_counter` + `_registry_lock`.

**15 generic KV API**: open/get/set/del/has/list/expire/ttl/flush/set_nx/incr + typed get_int/get_str/get_json
**3 Agent-Native API**: agent_kv_query (semantic query), agent_kv_store (agent memory), agent_kv_context (context-aware retrieval)

**KV DSL syntax**:
```nexa
kv_decl {
  open "sqlite://cache.db"
}
```

---

### P2-4: Template System

**Status**: Completed (209 tests)

Nexa's template system provides a full-featured template engine with `template"""..."""` syntax, 30+ filters, for-loops with metadata, if/elif/else blocks, partials, and agent-specific prompt templating.

**New files**:
- `src/runtime/template.py` (~1594 lines) — NexaTemplateRenderer, TemplateContentParser, 30+ filter functions, FILTER_REGISTRY, CompiledTemplate (mtime-based cache auto-reload), external template API, Agent-Native extensions

**Modified files**:
- `src/nexa_parser.py` — `template_expr` grammar rule, `TEMPLATE_STRING` token, `template` exclusion keyword
- `src/ast_transformer.py` — NexaTemplateParser class, TemplatePart/TemplateFilter dataclasses, `template_string_expr` handler
- `src/code_generator.py` — TEMPLATE_BOILERPLATE, template code generation with ForLoop/IfBlock/Partial
- `src/runtime/__init__.py` — Template module exports
- `src/runtime/stdlib.py` — 18 StdTool `std.template` namespace

**Template syntax**:
```nexa
template"""Hello {{name | upper}}!"""
template"""{{#for item in items}}{{@index}}:{{item}}{{/for}}"""
template"""{{#if is_admin}}Admin{{#elif is_mod}}Mod{{#else}}User{{/if}}"""
template"""{{> card user_data}}"""
```

**30+ Filters**: upper/lower/capitalize/trim/truncate(n)/replace(from,to)/escape/raw/safe/default(val)/length/first/last/reverse/join(sep)/slice(start,end)/json/number(n)/url_encode/strip_tags/word_count/line_count/indent/date/sort/unique/abs/ceil/floor

**ForLoop metadata**: `@index`, `@index1`, `@first`, `@last`, `@length`, `@even`, `@odd`

**External template API**: `template(path, data)`, `compile(path)`, `render(compiled, data)` — mtime-based cache invalidation

**Agent-Native extensions**:
- `agent_template_prompt(agent, template_str, context)` — auto-inject agent context (name, description, tools) into template variables
- `agent_template_slot_fill(agent, template_str, slot_sources)` — multi-source slot filling with priority: explicit_data > auth_context > kv_data > memory > agent_attrs
- `agent_template_register(agent, name, template_str)` — register agent-specific templates
- `agent_template_list()` — list all registered agent templates

---

## P3: Language Expressiveness

### P3-2: Pipe Operator `|>`

**Status**: Completed (84 tests, part of Batch A)

Nexa's pipe operator enables left-to-right data flow: `x |> f` desugars to `f(x)`, `x |> f(a,b)` desugars to `f(x, a, b)`. The LHS is inserted as the **first argument** of the RHS function call.

**Modified files**:
- `src/nexa_parser.py` — `pipe_expr` grammar rule with `"|>"` anonymous terminal
- `src/ast_transformer.py` — `pipe_chain_expr` handler with intelligent desugaring (std_call, method_call, property_access)
- `src/code_generator.py` — No changes needed (desugared at AST level)

**Syntax examples**:
```nexa
result |> format_output
data |> std.text.upper
prompt |> agent.run |> extract_answer
```

**Agent-Native**: `agent.run(prompt) |> extract_answer |> format_output`

---

### P3-5: Defer Statement

**Status**: Completed (84 tests, part of Batch A)

Nexa's defer statement ensures cleanup operations execute when scope exits, in LIFO order, even if errors occur (similar to Go's defer).

**Modified files**:
- `src/nexa_parser.py` — `defer_stmt: "defer" expression ";"` grammar rule, `defer` exclusion keyword
- `src/ast_transformer.py` — `defer_stmt` handler
- `src/code_generator.py` — `_nexa_defer_stack` / `_nexa_defer_execute` BOILERPLATE helpers, try/finally wrapping in `_generate_flows()`
- `src/runtime/__init__.py` — `_nexa_defer_execute` export

**Syntax examples**:
```nexa
defer cleanup(db)
defer log("operation complete")
```

**Agent-Native**: `defer agent_cleanup(agent)` — automatic agent resource cleanup

---

### P3-6: Null Coalescing `??`

**Status**: Completed (84 tests, part of Batch A)

Nexa's null coalescing operator provides safe fallback values: `expr ?? fallback` returns the fallback if expr is None/Option::None/empty dict, otherwise returns expr.

**Modified files**:
- `src/nexa_parser.py` — `null_coalesce_expr` grammar rule with `"??"` anonymous terminal
- `src/ast_transformer.py` — `null_coalesce_expr` handler with part flattening
- `src/code_generator.py` — `_nexa_null_coalesce` BOILERPLATE helper, nested call generation for chained `a ?? b ?? c`
- `src/runtime/__init__.py` — `_nexa_null_coalesce` export

**Syntax examples**:
```nexa
result ?? "fallback"
config.timeout ?? 30
agent.run(prompt) ?? "I couldn't process that"
```

**Agent-Native**: Agent response safety net with graceful fallbacks

---

### P3-1: String Interpolation `#{expr}`

**Status**: Completed (100 tests)

Nexa's string interpolation uses Ruby-style `#{expr}` syntax inside double-quoted strings. No grammar changes required — interpolation is detected and parsed at the AST Transformer level.

**Modified files**:
- `src/ast_transformer.py` — `_parse_string_interpolation()` static method, `_INTERP_EXPR_PATTERN` regex, enhanced `string_expr` handlers
- `src/code_generator.py` — `_generate_interpolated_string()`, `_interp_expr_to_python()`, `_nexa_interp_str` BOILERPLATE helper
- `src/runtime/__init__.py` — `_nexa_interp_str` export
- `src/runtime/stdlib.py` — `std.string.interpolate` StdTool
- `src/runtime/inspector.py` — `InterpolatedString` handling in expression-to-string dispatch
- `src/runtime/type_system.py` — `InterpolatedString` in `infer_from_expression`

**Expression support inside `#{}`**:
- Simple identifiers: `#{name}`
- Dot access: `#{user.name}` → `user["name"]` in Python
- Bracket access: `#{arr[0]}` → `arr[0]` in Python
- Combined: `#{data.items[0].name}` → `data["items"][0]["name"]`

**Escape handling**: `\#{` → literal `#{`, invalid expressions → literal text

**Type conversion (`_nexa_interp_str`)**:
- `None` → `""` (empty string)
- `bool` → `"true"/"false"`
- `int/float` → `str(value)`
- `dict/list` → `json.dumps(value)`
- `Option::Some` → unwrap inner, `Option::None` → `""`

**Syntax examples**:
```nexa
"Hello #{name}, you are #{age} years old!"
"Status: #{result ?? 'pending'}"
"Agent #{agent.name} responding"
```

---

### P3-3: Pattern Matching + Destructuring

**Status**: Completed (91 tests)

Nexa's pattern matching system provides 7 pattern types for `match` expressions, `let` destructuring, and `for` destructuring.

**New files**:
- `src/runtime/pattern_matching.py` — `nexa_match_pattern()`, `nexa_destructure()`, `nexa_make_variant()`, helper functions (`_nexa_is_tuple_like`, `_nexa_is_list_like`, `_nexa_is_dict_with_keys`, `_nexa_is_variant`, `_nexa_list_rest`, `_nexa_dict_rest`)

**Modified files**:
- `src/nexa_parser.py` — `match_expr`, `match_arm`, 7 pattern grammar rules (`wildcard_pattern`, `literal_pattern`, `variable_pattern`, `tuple_pattern`, `array_pattern`, `map_pattern`, `variant_pattern`), `let_pattern_stmt`, `for_pattern_stmt`, `match`/`let` exclusion keywords
- `src/ast_transformer.py` — 18 new handler methods, `_score_ast_node` scoring updates (MatchExpression=50, MatchArm=45, Pattern literal=38>variable=35)
- `src/code_generator.py` — `_generate_match_expr`, `_generate_pattern_condition`, `_generate_pattern_bindings`, `_generate_let_pattern`, `_generate_for_pattern`, BOILERPLATE pattern_matching imports
- `src/runtime/__init__.py` — Pattern matching exports
- `src/runtime/stdlib.py` — `std.match` StdTool namespace

**7 Pattern types**:
1. **Wildcard**: `_` — matches anything, no binding
2. **Variable**: `name` — matches anything, binds variable
3. **Literal**: `42`, `"hello"`, `true`, `false` — matches exact value
4. **Tuple**: `(a, b)` — matches tuple/array of specific length
5. **Array**: `[a, b, ..rest]` — matches array with rest collector
6. **Map**: `{ name, age: a, ..other }` — matches dict with rest collector
7. **Variant**: `Option::Some(v)` — matches enum variant

**Syntax examples**:
```nexa
match result {
  Option::Some(answer) => answer
  Option::None => "no response"
}

let (key, value) = entry
for (name, score) in rankings { ... }

match status {
  200 => "success"
  404 => "not found"
  _ => "unknown"
}
```

**Code generation**: Python if/elif chains with `isinstance()` checks and variable binding

---

### P3-4: ADT (Struct/Trait/Enum)

**Status**: Completed (100 tests)

Nexa's Algebraic Data Types system provides struct, enum, trait, and impl declarations with Python dataclass/class-based code generation and handle-as-dict pattern for JSON compatibility.

**New files**:
- `src/runtime/adt.py` — Thread-safe registries (`_struct_registry`, `_enum_registry`, `_trait_registry`, `_impl_registry`) with `_registry_lock` + ID counters. Helper functions: `register_struct`, `make_struct_instance`, `struct_get_field`, `struct_set_field`, `register_enum`, `make_variant`, `make_unit_variant`, `register_trait`, `register_impl`, `call_trait_method`, lookup functions, `adt_reset_registries`, `adt_get_registry_summary`, ContractViolation integration.

**Modified files**:
- `src/nexa_parser.py` — `struct_decl`, `struct_field`, `enum_decl`, `enum_variant`, `trait_decl`, `trait_method`, `impl_decl`, `impl_method`, `variant_call_expr`, `field_init` grammar rules. `struct`, `enum`, `trait`, `impl`, `fn` exclusion keywords
- `src/ast_transformer.py` — 10 new handler methods, ADT AST node scoring (StructDeclaration=60, EnumDeclaration=60, TraitDeclaration=60, ImplDeclaration=60, VariantCallExpression=55, FieldInitExpression=45)
- `src/code_generator.py` — ADT imports in BOILERPLATE, `self.structs`/`self.enums`/`self.trait_decls`/`self.impl_decls` collections, `_generate_adt`, `_generate_structs`, `_generate_enums`, `_generate_traits`, `_generate_impls`, `_generate_impl_method_body` methods, VariantCallExpression/FieldInitExpression handling
- `src/runtime/__init__.py` — ADT function exports
- `src/runtime/stdlib.py` — 9 StdTools (`std.struct`, `std.enum`, `std.trait` namespaces)

**Handle-as-dict pattern**:
- Struct instance: `{"_nexa_struct": "Point", "_nexa_struct_id": 1, "x": 1, "y": 2}`
- Enum variant: `{"_nexa_variant": "Some", "_nexa_enum": "Option", "_nexa_variant_id": 1, "value": 42}`
- Unit variant: `{"_nexa_variant": "None", "_nexa_enum": "Option"}`

**Syntax examples**:
```nexa
struct Point { x: Int, y: Int }
enum Option { Some(value), None }
enum Result { Ok(value), Err(error) }
trait Printable { fn format() -> String }
impl Printable for Point { fn format() -> String { ... } }

let p = Point(x: 1, y: 2)
let opt = Option::Some(42)
match opt {
  Option::Some(v) => v
  Option::None => 0
}
```

**Agent-Native**: Agent state enums (`enum AgentState { Idle, Running, Error(message) }`), Agent result structs (`struct AgentResult { answer, confidence, tokens }`), trait implementations for agent behavior

---

## Test Summary

| Feature | Test Count | Test File |
|---------|-----------|-----------|
| P0-1 IDD | 104 | `tests/test_ial.py` |
| P0-2 Contracts | 47 | `tests/test_contracts.py` |
| P0-3 Tooling | 41 | `tests/test_inspector.py` |
| P1-1 Type System | 79 | `tests/test_type_system.py` (via test_doc_examples) |
| P1-2 Error Propagation | 82 | `tests/test_error_propagation.py` |
| P1-3 Job System | 73 | `tests/test_jobs.py` |
| P1-4 HTTP Server | 94 | `tests/test_http_server.py` |
| P1-5 Database | 79+5skip | `tests/test_database.py` |
| P2-1 Auth | 79+5skip | `tests/test_auth.py` |
| P2-2 Concurrency | 172 | `tests/test_concurrent.py` |
| P2-3 KV Store | 81 | `tests/test_kv_store.py` |
| P2-4 Template | 209 | `tests/test_template.py` |
| P3 Batch A (Pipe+Defer+??) | 84 | `tests/test_batch_a.py` |
| P3-1 String Interpolation | 100 | `tests/test_string_interpolation.py` |
| P3-3 Pattern Matching | 91 | `tests/test_pattern_matching.py` |
| P3-4 ADT | 100 | `tests/test_adt.py` |
| **Total** | **~1500+** | |

---

## Architecture Patterns Used Consistently

1. **Handle-as-dict Pattern**: All runtime handles (DB connections, KV stores, auth sessions, compiled templates, struct instances, enum variants) are plain Python dicts with `_nexa_*` prefixed keys for JSON compatibility
2. **Thread-safe Registry Pattern**: Global registries with `_registry_lock` (threading.Lock) + `_id_counter` for all runtime modules
3. **StdTool Namespace Pattern**: `std.db`, `std.auth`, `std.kv`, `std.concurrent`, `std.template`, `std.match`, `std.struct`, `std.enum`, `std.trait` registered via StdTool in stdlib.py
4. **BOILERPLATE Code Generation**: Each feature adds imports and helper functions to the code generator's BOILERPLATE section
5. **ContractViolation Integration**: Auth 401→requires, 403→ensures; KV failures→ensures; Concurrent task failures→contract; ADT invalid operations→ContractViolation
5. **_ambig() Scoring**: AST transformer uses intelligent scoring to resolve Lark Earley parser ambiguities, with per-feature priority scores