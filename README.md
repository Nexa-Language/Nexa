<div align="center">
  <img src="docs/img/nexa-logo-noframe.png" alt="Nexa Logo" width="100" />
  <h1>Nexa Language</h1>
  <p><b><i>The Dawn of Agent-Native Programming. Write flows, not glue code.</i></b></p>
  <p>
    <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"/>
    <img src="https://img.shields.io/badge/Version-v0.9--alpha-brightgreen.svg?style=for-the-badge" alt="Version"/>
    <img src="https://img.shields.io/badge/Python-%3E%3D3.10-blue.svg?style=for-the-badge" alt="Python"/>
    <img src="https://img.shields.io/badge/Status-Experimental-orange.svg?style=for-the-badge" alt="Status"/>
  </p>
</div>

---

## ⚡ What is Nexa?

**Nexa** 是一门为大语言模型（LLM）与智能体系统（Agentic Systems）量身定制的**智能体原生 (Agent-Native) 编程语言**。
当代 AI 应用开发充斥着大量的 Prompt 拼接、臃肿的 JSON 解析套件、不可靠的正则皮带，以及复杂的框架。Nexa 将高层级的意图路由、多智能体并发组装、管道流传输以及工具执行沙盒提权为核心语法一等公民，直接通过底层的 `Transpiler` 转换为稳定可靠的 Python Runtime，让你能够用最优雅的语法定义最硬核的 LLM 计算图（DAG）。

---

## 🔥 **v0.9.7-rc ENTERPRISE RELEASE**: Cognitive & Security Era

Nexa v0.9.7-rc 引入了企业级认知架构和安全增强，包括复杂 DAG 拓扑、智能缓存、知识图谱和 RBAC 权限控制：

### 1. 复杂拓扑 DAG 支持
新增强大的 DAG 操作符，支持分叉、合流、条件分支：
```nexa
// 分叉：并行发送到多个 Agent
results = input |>> [Researcher, Analyst, Writer];

// 合流：合并多个结果
report = [Researcher, Analyst] &>> Reviewer;

// 条件分支：根据输入选择路径
result = input ?? UrgentHandler : NormalHandler;
```

### 2. 智能缓存系统
多级缓存 + 语义缓存，大幅减少 Token 消耗：
```nexa
agent CachedBot {
    prompt: "...",
    model: "deepseek/deepseek-chat",
    cache: true  // 启用智能缓存
}
```

### 3. 知识图谱记忆
结构化知识存储和推理能力：
```python
from src.runtime.knowledge_graph import get_knowledge_graph
kg = get_knowledge_graph()
kg.add_relation("Nexa", "is_a", "Agent Language")
```

### 4. RBAC 权限控制
角色基础的访问控制，确保最小权限原则：
```python
from src.runtime.rbac import get_rbac_manager, Permission
rbac = get_rbac_manager()
rbac.assign_role("DataBot", "agent_readonly")
```

### 5. 长期记忆系统
CLAUDE.md 风格的持久化记忆，支持经验和知识积累：
```nexa
agent SmartBot {
    prompt: "...",
    experience: "bot_memory.md"  // 加载长期记忆
}
```

### 6. Open-CLI 深度接入
原生交互式命令行支持，富文本输出：
```bash
nexa > run script.nx --debug
nexa > cache stats
nexa > agent list
```

---

## 📖 v0.9-alpha 特性回顾

### 原生测试与断言 (`test` & `assert`)
```nexa
test "login_agent" {
    result = LoginBot.run("user: admin");
    assert "包含成功确认信息" against result;
}
```

### MCP 支持 (`mcp: "..."`)
```nexa
tool SearchGlobal {
    mcp: "github.com/nexa-ai/search-mcp"
}
```

### 高速启发式评估 (`fast_match`)
```nexa
semantic_if "是一句日期提示" fast_match r"\d{4}-\d{2}" against req { ... }
```

---

## 🚀 Quick Start

### 1. 全局安装
```bash
git clone https://github.com/your-org/nexa.git
cd nexa
pip install -e .
```

### 2. 执行与测试工作流
```bash
# 执行流
nexa run examples/09_cognitive_architecture.nx

# 进行语义断言测试 (v0.9+)
nexa test examples/v0.9_test_suite.nx

# 审计生成的纯净 Python 代码栈
nexa build examples/09_cognitive_architecture.nx
```

---

## 📖 Documentation
- [x] [Nexa v0.9 Syntax Reference](docs/01_nexa_syntax_reference.md)
- [x] [Compiler Architecture](docs/02_compiler_architecture.md)
- [x] [Vision & Roadmap](docs/03_roadmap_and_vision.md)

<div align="center">
  <sub>Built with ❤️ by the Nexa Genesis Team for the next era of automation.</sub>
</div>
