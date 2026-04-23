<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa Language</h1>
  <p><b><i>The Dawn of Agent-Native Programming. Write flows, not glue code.</i></b></p>
  <p>
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"/>
    <img src="https://img.shields.io/badge/Version-v1.3.7-brightgreen.svg?style=for-the-badge" alt="Version"/>
    <img src="https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg?style=for-the-badge" alt="Python"/>
    <img src="https://img.shields.io/badge/Tests-1500+-orange.svg?style=for-the-badge" alt="Tests"/>
  </p>
  
  **[中文版](README.md)** | **English**
  
  📚 **Docs**: [中文](https://ouyangyipeng.github.io/Nexa-docs/) | [English](https://ouyangyipeng.github.io/Nexa-docs/en/)
</div>

---

## ⚡ What is Nexa?

**Nexa** is an **Agent-Native programming language** designed specifically for Large Language Models (LLMs) and Agentic Systems.

Modern AI application development is plagued by massive Prompt concatenation, bloated JSON parsing suites, unreliable regex belts, and complex frameworks. Nexa elevates high-level intent routing, multi-agent concurrent assembly, pipeline streaming, and tool execution sandboxing as first-class syntax citizens. Through the underlying `Transpiler`, it transforms into stable, reliable Python Runtime, allowing you to define the most hardcore LLM computation graphs (DAGs) with the most elegant syntax.

---

## 🔥 v1.1-v1.3.7 Feature Overview

Nexa released **16 core features** from v1.1.0 to v1.3.7, covering 4 priority tiers (P0-P3), with **1500+ tests** total.

### 🏆 P0: Core Differentiation Features

| Version | Feature | Tests | Highlights |
|---------|---------|-------|------------|
| **v1.1.0** | Intent-Driven Development (IDD) | 104 | `.nxintent` files + IAL term rewriting engine + `@implements` annotations |
| **v1.2.0** | Design by Contract (DbC) | 47 | `requires`/`ensures`/`invariant` + ContractViolation cross-module integration |
| **v1.3.0** | Agent-Native Tooling | 41 | `nexa inspect`/`validate`/`lint` CLI commands |

### 📦 P1: Essential Features

| Version | Feature | Tests | Highlights |
|---------|---------|-------|------------|
| **v1.3.1** | Gradual Type System | 79 | `Int`/`String`/`Bool`/`List[T]`/`Option[T]`/`Result[T,E]` + 3-level mode |
| **v1.3.2** | Error Propagation | 82 | `?` operator + `otherwise` + `NexaResult`/`NexaOption` |
| **v1.3.3** | Background Job System | 73 | `job` DSL + priority queues + cron + backoff strategies |
| **v1.3.4** | Built-In HTTP Server | 94 | `server` DSL + CORS/CSP + route guards + hot reload |
| **v1.3.5** | Database Integration | 79+5 | `db` DSL + SQLite/PostgreSQL + Agent memory API |

### 🎯 P2: Advanced Features

| Version | Feature | Tests | Highlights |
|---------|---------|-------|------------|
| **v1.3.6** | Auth & OAuth | 79+5 | 3-layer auth (API Key + JWT + OAuth PKCE) |
| **v1.3.6** | Structured Concurrency | 172 | `spawn`/`parallel`/`race`/`channel` + 18 API functions |
| **v1.3.6** | KV Store | 81 | SQLite backend + TTL + Agent semantic queries |
| **v1.3.6** | Template System | 209 | `template"""..."""` + 30+ filters + Agent templates |

### ✨ P3: Language Expressiveness

| Version | Feature | Tests | Highlights |
|---------|---------|-------|------------|
| **v1.3.7** | Pipe Operator `|>` | 84 | `x |> f` → `f(x)` left-to-right data flow |
| **v1.3.7** | defer Statement | 84 | LIFO cleanup on scope exit |
| **v1.3.7** | Null Coalescing `??` | 84 | `expr ?? fallback` safe fallback |
| **v1.3.7** | String Interpolation `#{}` | 100 | Ruby-style string interpolation |
| **v1.3.7** | Pattern Matching | 91 | 7 pattern types + `match`/`let`/`for` destructuring |
| **v1.3.7** | ADT (Struct/Enum/Trait) | 100 | Algebraic data types + handle-as-dict pattern |

---

## 🦀 Rust AVM Foundation (v1.0-alpha)

Nexa v1.0-alpha introduced the revolutionary **Agent Virtual Machine (AVM)** — a high-performance, securely isolated agent execution engine written in Rust:

- **High-performance bytecode interpreter** — Natively executes compiled Nexa bytecode
- **WASM Security Sandbox** — wasmtime integration + 4-level permission model
- **Smart Scheduler** — DAG topological sort + automatic dependency resolution
- **Vector Virtual Memory Paging** — LRU/LFU/Hybrid eviction + semantic relevance loading

---

## 🚀 Quick Start

### 1. Global Installation
```bash
git clone https://github.com/ouyangyipeng/Nexa.git
cd Nexa
pip install -e .
```

### 2. Agent Tool Installation 🤖
If you're using AI Agent tools (Claude Code, Cursor, Copilot, etc.), simply enter:

```
Follow the instructions at https://github.com/ouyangyipeng/Nexa/AGENT_LEARN to install and try this language
```

Your Agent will automatically access `AGENT_LEARN/` to complete installation and learn Nexa syntax.

**Agent-specific docs**:
- [`AGENT_LEARN/INSTALL_AND_HELLO_WORLD.md`](AGENT_LEARN/INSTALL_AND_HELLO_WORLD.md)
- [`AGENT_LEARN/AGENT_GUIDE.md`](AGENT_LEARN/AGENT_GUIDE.md)

### 3. Execute and Test Workflow
```bash
# Run flow
python -m src.cli run examples/01_hello_world.nx

# Semantic assertion tests
python -m src.cli test examples/12_v0.9_features.nx

# Audit generated Python code stack
python -m src.cli build examples/01_hello_world.nx

# Agent-Native tooling (v1.3+)
python -m src.cli inspect examples/01_hello_world.nx
python -m src.cli validate examples/01_hello_world.nx
python -m src.cli lint examples/01_hello_world.nx
```

---

## 📖 Syntax Examples

### Agent Declaration + Pipeline
```nexa
agent ChatBot {
    role: "Helpful Assistant",
    model: "gpt-4o-mini",
    prompt: "Answer user questions concisely"
}

flow main {
    result = user_input |> ChatBot |> format_output;
}
```

### Design by Contract (v1.2)
```nexa
agent SecureBot {
    requires: input != None and input.length < 1000
    ensures: "response is helpful and accurate"
}
```

### Type Annotations + Error Propagation (v1.3.1-v1.3.2)
```nexa
let count: Int = parse(input) ?
let result = risky_operation() otherwise 0
```

### HTTP Server (v1.3.4)
```nexa
server 8080 {
    cors { origins: ["*"], methods: ["GET", "POST"] }
    route GET "/chat" => ChatBot
    route POST "/analyze" => Analyzer
}
```

### Pattern Matching + ADT (v1.3.7)
```nexa
enum Option { Some(value), None }
struct Point { x: Int, y: Int }

match result {
    Option::Some(answer) => answer
    Option::None => "no response"
}
```

---

## ✅ Documentation & Test Validation

- **Python Tests**: 1500+ tests passed (16 features fully covered)
- **Rust AVM Tests**: 110+ tests passed (100%)

---

## 📖 Documentation

- [x] [Nexa Syntax Reference v1.3.7](docs/01_nexa_syntax_reference.md) — 25 chapters full syntax coverage
- [x] [Compiler & Runtime Architecture v1.3](docs/02_compiler_architecture.md) — AST scoring, BOILERPLATE, handle-as-dict
- [x] [Roadmap & Vision](docs/03_roadmap_and_vision.md) — v0.1 to v1.3.7 complete milestones
- [x] [Architecture Evolution Plan](docs/05_architecture_evolution.md) — Rust AVM design blueprint
- [x] [Quick Start Guide](docs/06_quick_start_guide.md) — 5-minute introduction
- [x] [IDD Complete Reference](docs/idd_reference.md) — Intent-Driven Development deep dive
- [x] [Feature Changelog v1.1-v1.3.x](docs/changelog_v1.1.0-v1.3.x_features.md) — 16 feature change records
- [x] [Release Notes](docs/release_notes/) — Per-version release announcements

<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>