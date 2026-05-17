# Nexa 语言安装与 Hello World 指南

> **给 AI Agent 的指令**: 按照本文档的步骤，在你的环境中安装 Nexa v2.1.0 并运行第一个程序。

---

## 📋 前置条件检查

在开始安装之前，请检查以下条件：

| 条件 | 要求 | 检查命令 |
|------|------|---------|
| Python 版本 | >= 3.10 | `python3 --version` |
| pip | 最新版 | `pip --version` |
| Git | 任意版本 | `git --version` |

**如果条件不满足**：
- Python < 3.10: 请先升级 Python 或使用 `pyenv` 安装 3.10+
- pip 未安装: 运行 `python3 -m ensurepip --upgrade`

---

## 🚀 安装步骤

### 步骤 1: 克隆仓库

```bash
git clone https://github.com/ouyangyipeng/Nexa.git
cd Nexa
```

### 步骤 2: 创建虚拟环境（推荐）

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 步骤 3: 安装 Nexa

```bash
pip install -e .
```

这会安装 `nexa` 命令行工具（通过 setup.py entry_points 注册），同时安装所有核心依赖（lark、openai、pydantic、tenacity 等）。

### 步骤 4: 验证安装

```bash
nexa --version
# 输出: Nexa v2.1.0.0

python3 -c "from src import parse; print('Nexa 安装成功!')"
```

如果输出 `Nexa v2.1.0.0` 和 `Nexa 安装成功!`，则安装完成。

---

## 🔑 配置 API 密钥

Nexa 需要 LLM API 密钥才能运行。选择以下方式之一配置：

### 方式 1: 环境变量（推荐）

```bash
# OpenAI 兼容 API (通用)
export OPENAI_API_KEY="sk-your-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 或用国内代理

# DeepSeek
export DEEPSEEK_API_KEY="sk-your-api-key"

# 其他兼容服务 (如 GLM、Qwen 等)
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.your-service.com/v1"
```

### 方式 2: secrets.nxs 文件

在项目根目录创建 `secrets.nxs` 文件（已在 .gitignore 中）：

```
config default {
    OPENAI_API_KEY = "sk-your-api-key"
    OPENAI_BASE_URL = "https://api.openai.com/v1"
}
```

---

## 👋 运行 Hello World

### 最小 Hello World

创建文件 `hello.nx`：

```nexa
agent Greeter {
    role: "Friendly Assistant",
    model: "gpt-4o-mini",
    prompt: "You are a friendly greeter. Greet the user warmly and briefly."
}

flow main {
    result = Greeter.run("Hello, Nexa!");
    print(result);
}
```

### 运行程序

```bash
# 方式 1: nexa 命令（推荐）
nexa run hello.nx

# 方式 2: 含 v2.0 Harness 验证
nexa run hello.nx --harness=warn

# 方式 3: 只编译，查看生成的 Python
nexa build hello.nx
# 生成 hello.py，可直接查看编译结果
```

### 预期输出

```
Hello! Welcome to Nexa! I'm here to help you with anything you need.
```

（实际输出由 LLM 生成，内容可能略有不同）

---

## 🦾 v2.0 Harness 风味 Hello World

以下示例展示 v2.0 的 Harness Native 特性：

```nexa
@tool("获取当前时间")
fn get_time(): string {
    python! """
import datetime
return datetime.datetime.now().isoformat()
"""
}

agent HarnessBot {
    role: "智能助手",
    model: "gpt-4o-mini",
    prompt: "你是一个展示 Nexa v2.1.0 Harness 能力的助手"
}

flow main {
    print("=== Nexa v2.1.0 Harness Demo ===");

    // E: autoloop — 自主执行循环
    autoloop max_steps: 3, exit_when: "打招呼完成" {

        // C: with_context — 上下文管理
        with_context max_tokens: 30000 {

            // S: snapshot — 状态快照
            snap = snapshot();

            // E+L: try_agent — 容错执行
            try_agent {
                result = HarnessBot.run("Say hello and tell me the time");
                print(result);

                // V: verify — 验证输出
                verify result satisfies string;
            } catch_correction(e: ToolError) {
                restore(snap);
                reflect "Error occurred, retrying...";
            }
        }
    }
}
```

保存为 `hello_harness.nx` 并运行：

```bash
nexa run hello_harness.nx --harness=warn
```

---

## 📁 运行官方示例

```bash
# v0.1 基础示例
nexa run examples/v0.1/01_hello_world.nx
nexa run examples/v0.1/02_pipeline_and_routing.nx
nexa run examples/v0.1/03_critic_loop.nx

# v1.0 高级特性
nexa run examples/v1.0/13_try_catch_and_reflection.nx
nexa run examples/v1.0/15_dag_topology.nx

# v2.0 Harness Native 示例 (12 个)
nexa run examples/v2.0/01_autoloop.nx --harness=warn
nexa run examples/v2.0/04_tool_annotation.nx --harness=warn
nexa run examples/v2.0/07_verify.nx --harness=warn
nexa run examples/v2.0/10_actor_system.nx --harness=warn
nexa run examples/v2.0/11_well_harnessed.nx --harness=warn

# Nexa Code — 用 Nexa 写的 AI 编程助手
nexa run examples/Nexa-Code/main.nx --harness=warn
```

---

## 🐍 Python SDK 使用

安装后可直接在 Python 中使用 Nexa：

```python
import nexa

# 运行脚本
result = nexa.run("hello.nx")

# 动态创建 Agent
bot = nexa.Agent(
    name="MyBot",
    prompt="你是一个有用的助手",
    model="gpt-4o-mini"
)
response = bot.run("Hello from Python!")
print(response)

# 编译代码字符串
result = nexa.compile("""
agent TestBot {
    prompt: "你是一个测试助手"
}
""")
print(result.python_code)
```

SDK 还支持 `nexa.build()`、`nexa.test()`、`nexa.batch_run()` 等 API。详见 [`src/nexa_sdk.py`](src/nexa_sdk.py)。

---

## ✅ 安装验证清单

完成以下检查确认安装成功：

- [ ] `nexa --version` 输出 `Nexa v2.1.0.0`
- [ ] `python3 -c "from src import parse"` 无报错
- [ ] API 密钥已配置（`echo $OPENAI_API_KEY` 有输出）
- [ ] `nexa run hello.nx` 运行成功并输出问候语
- [ ] 至少一个 v2.0 示例运行成功：`nexa run examples/v2.0/01_autoloop.nx --harness=warn`

---

## 🐛 常见问题

### Q1: `nexa: command not found`

**解决方案**: 确保 `pip install -e .` 执行成功。或者用：
```bash
python3 -m src.cli run hello.nx
```

### Q2: ModuleNotFoundError: No module named 'src'

**解决方案**: 确保在项目根目录运行命令，或使用 `pip install -e .` 以开发模式安装。

### Q3: API key not found

**解决方案**: 检查环境变量：
```bash
echo $OPENAI_API_KEY
# 如为空，重新 export 或检查 secrets.nxs
```

### Q4: Connection error / timeout

**解决方案**:
- 检查网络连接
- 如使用代理，设置 `HTTP_PROXY` 和 `HTTPS_PROXY`
- 如使用国内 API 服务，确保 `OPENAI_BASE_URL` 正确指向

### Q5: Python version mismatch

**解决方案**: 使用 pyenv 创建 Python 3.10+ 环境：
```bash
pyenv install 3.10.0
pyenv local 3.10.0
```

### Q6: Harness validation warnings

运行 v2.0 示例时可能出现 Harness 警告，这是正常的。使用 `--harness=warn` 模式编译通过即可。严格模式用 `--harness=strict`。

---

## 📚 下一步

安装完成后，建议：

1. **阅读 Agent 指南**: 查看 [`AGENT_GUIDE.md`](AGENT_GUIDE.md) 学习 Nexa v2.1.0 完整语法
2. **运行 v2.0 示例**: 探索 `examples/v2.0/` 目录中的 12 个 Harness Native 示例
3. **学习 Nexa Code**: 查看 `examples/Nexa-Code/` — 用 Nexa 写的 AI 编程助手
4. **编写自己的程序**: 使用 Agent Guide 中的模板创建新程序

### v2.0 示例概览

| 示例 | 维度 | 说明 |
|------|------|------|
| `01_autoloop.nx` | E | 自主 ReAct 循环 |
| `02_with_context.nx` | C | 上下文自动管理 |
| `03_try_agent.nx` | E+L | 容错执行 + 反思注入 |
| `04_tool_annotation.nx` | T | @tool 零成本工具绑定 |
| `05_snapshot_restore.nx` | S | 状态快照与回溯 |
| `06_fork_merge.nx` | S | 分支探索与合并 |
| `07_verify.nx` | V | 输出验证 |
| `08_reflect.nx` | L | 反思注入 |
| `09_lifecycle_hooks.nx` | L | 生命周期拦截 |
| `10_actor_system.nx` | Actor | 多 Agent 编排 |
| `11_well_harnessed.nx` | 全部 | 全维度综合示例 |
| `12_harness_cli.nx` | 全部 | 类 Claude Code CLI 框架 |

---

## 🔗 有用的链接

- **GitHub 仓库**: https://github.com/ouyangyipeng/Nexa
- **在线文档（中文）**: https://docs.nexa-lang.com/
- **在线文档（英文）**: https://docs.nexa-lang.com/en/
- **v2.0.0 Release Notes**: [`docs/release_notes/v2.0.0.md`](../docs/release_notes/v2.0.0.md)

---

*本文档专为 AI Agent 设计，帮助快速安装和验证 Nexa v2.1.0 语言。*