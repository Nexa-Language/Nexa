<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa Language</h1>
  <p><b><i>The Dawn of Agent-Native Programming. Write flows, not glue code.</i></b></p>
  <p>
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"/>
    <img src="https://img.shields.io/badge/Version-v1.0--alpha-brightgreen.svg?style=for-the-badge" alt="Version"/>
    <img src="https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg?style=for-the-badge" alt="Python"/>
    <img src="https://img.shields.io/badge/Status-Experimental-orange.svg?style=for-the-badge" alt="Status"/>
  </p>
  
  **[中文版](README.md)** | **English**
  
  📚 **Docs**: [中文](https://ouyangyipeng.github.io/Nexa-docs/) | [English](https://ouyangyipeng.github.io/Nexa-docs/en/)
</div>

---

## ⚡ What is Nexa?

**Nexa** is an **Agent-Native programming language** designed specifically for Large Language Models (LLMs) and Agentic Systems.

Modern AI application development is plagued by massive Prompt concatenation, bloated JSON parsing suites, unreliable regex belts, and complex frameworks. Nexa elevates high-level intent routing, multi-agent concurrent assembly, pipeline streaming, and tool execution sandboxing as first-class syntax citizens. Through the underlying `Transpiler`, it transforms into stable, reliable Python Runtime, allowing you to define the most hardcore LLM computation graphs (DAGs) with the most elegant syntax.

---

## 🔥 **v1.0-alpha AVM RELEASE**: The Agent Virtual Machine Era

Nexa v1.0-alpha introduces the revolutionary **Agent Virtual Machine (AVM)** - a high-performance, securely isolated agent execution engine written in Rust:

### 🦀 Rust AVM Foundation
Evolved from Python script interpretation to a standalone compiled Agent Virtual Machine written in Rust:
- **High-performance bytecode interpreter** - Natively executes compiled Nexa bytecode
- **Complete compiler frontend** - Lexer → Parser → AST → Bytecode
- **110+ test coverage** - Full-chain testing ensures stability

### 🔒 WASM Security Sandbox
Introduced WebAssembly in AVM, providing strong isolation for external `tool` execution:
- **wasmtime integration** - High-performance WASM runtime
- **Permission levels** - None/Standard/Elevated/Full four-level permission model
- **Resource limits** - Memory, CPU, execution time constraints
- **Audit logs** - Complete operation audit trail

### ⚡ Smart Scheduler
Dynamically allocates concurrent resources at the AVM level based on system load:
- **Priority queue** - Task scheduling based on Agent priority
- **Load balancing** - RoundRobin/LeastLoaded/Adaptive strategies
- **DAG topological sort** - Automatic dependency resolution and parallelism analysis
- **Resource allocation** - Memory, CPU core allocation optimization

### 📄 Vector Virtual Memory Paging
AVM manages memory, automatically performing vectorized swapping of conversation history:
- **LRU/LFU/Hybrid eviction policies** - Intelligent page replacement
- **Embedding similarity search** - Semantic relevance loading
- **Transparent page loading** - Imperceptible memory management
- **Auto compression** - Old page summary compression

---

## 📚 v0.9.7-rc Enterprise Features Recap

### 1. Complex Topology DAG Support
Powerful DAG operators supporting fork, merge, and conditional branching:
```nexa
// Fork: Parallel send to multiple Agents
results = input |>> [Researcher, Analyst, Writer];

// Merge: Combine multiple results
report = [Researcher, Analyst] &>> Reviewer;

// Conditional branch: Select path based on input
result = input ?? UrgentHandler : NormalHandler;
```

### 2. Intelligent Caching System
Multi-level caching + semantic caching, significantly reducing Token consumption:
```nexa
agent CachedBot {
    prompt: "...",
    model: "deepseek/deepseek-chat",
    cache: true  // Enable smart caching
}
```

### 3. Knowledge Graph Memory
Structured knowledge storage and reasoning capabilities:
```python
from src.runtime.knowledge_graph import get_knowledge_graph
kg = get_knowledge_graph()
kg.add_relation("Nexa", "is_a", "Agent Language")
```

### 4. RBAC Permission Control
Role-based access control, ensuring least privilege principle:
```python
from src.runtime.rbac import get_rbac_manager, Permission
rbac = get_rbac_manager()
rbac.assign_role("DataBot", "agent_readonly")
```

### 5. Long-term Memory System
CLAUDE.md style persistent memory, supporting experience and knowledge accumulation:
```nexa
agent SmartBot {
    prompt: "...",
    experience: "bot_memory.md"  // Load long-term memory
}
```

### 6. Open-CLI Deep Integration
Native interactive command line support, rich text output:
```bash
nexa > run script.nx --debug
nexa > cache stats
nexa > agent list
```

---

## 📖 v0.9-alpha Features Recap

### Native Testing & Assertions (`test` & `assert`)
```nexa
test "login_agent" {
    result = LoginBot.run("user: admin");
    assert "contains success confirmation" against result;
}
```

### MCP Support (`mcp: "..."`)
```nexa
tool SearchGlobal {
    mcp: "github.com/nexa-ai/search-mcp"
}
```

### High-speed Heuristic Evaluation (`fast_match`)
```nexa
semantic_if "is a date hint" fast_match r"\d{4}-\d{2}" against req { ... }
```

---

## 🚀 Quick Start

### 1. Global Installation
```bash
git clone https://github.com/your-org/nexa.git
cd nexa
pip install -e .
```

### 2. Execute and Test Workflow
```bash
# Run flow
nexa run examples/09_cognitive_architecture.nx

# Run semantic assertion tests (v0.9+)
nexa test examples/v0.9_test_suite.nx

# Audit generated pure Python code stack
nexa build examples/09_cognitive_architecture.nx
```

---

## ✅ Documentation Validation

All documentation example code has been validated through compilation:
- **Python Tests**: 42/42 examples passed (100%)
- **Rust AVM Tests**: 110/110 tests passed (100%)

New syntax support:
- **Agent Decorators**: `@limit`, `@timeout`, `@retry`, `@temperature`
- **MCP/Python Tool Body**: `mcp: "..."`, `python: "..."`
- **DAG Parallel Operators**: `||` (fire-forget), `&&` (consensus)
- **Literal Types**: `Regex`, `Float`

---

## 📖 Documentation
- [x] [Nexa v0.9 Syntax Reference](docs/01_nexa_syntax_reference.md)
- [x] [Compiler Architecture](docs/02_compiler_architecture.md)
- [x] [Vision & Roadmap](docs/03_roadmap_and_vision.md)
- [x] [Memory Bank](MEMORY_BANK.md) - Architecture design and version history

<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>