# Nexa 语言安装与 Hello World 指南

> **给 AI Agent 的指令**: 按照本文档的步骤，在你的环境中安装 Nexa 语言并运行第一个 Hello World 程序。

---

## 📋 前置条件检查

在开始安装之前，请检查以下条件：

| 条件 | 要求 | 检查命令 |
|------|------|---------|
| Python 版本 | >= 3.10 | `python --version` 或 `python3 --version` |
| pip | 最新版 | `pip --version` |
| Git | 任意版本 | `git --version` |

**如果条件不满足**：
- Python < 3.10: 请先升级 Python 或使用 `pyenv` 安装 3.10+
- pip 未安装: 运行 `python -m ensurepip --upgrade`

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
python -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 步骤 3: 安装依赖

```bash
pip install -e .
```

或者手动安装核心依赖：

```bash
pip install lark openai pydantic tenacity python-dotenv
```

### 步骤 4: 验证安装

```bash
python -c "from src import parse; print('Nexa 安装成功!')"
```

如果输出 `Nexa 安装成功!`，则安装完成。

---

## 🔑 配置 API 密钥

Nexa 需要 LLM API 密钥才能运行。选择以下方式之一配置：

### 方式 1: 环境变量（推荐）

```bash
# OpenAI
export OPENAI_API_KEY="sk-your-api-key"

# 或 DeepSeek
export DEEPSEEK_API_KEY="sk-your-api-key"

# 或其他兼容服务
export OPENAI_API_KEY="sk-your-key"
export OPENAI_BASE_URL="https://api.your-service.com/v1"
```

### 方式 2: secrets.nxs 文件

在项目根目录创建 `secrets.nxs` 文件：

```
OPENAI_API_KEY = "sk-your-api-key"
```

---

## 👋 运行 Hello World

### 创建 Hello World 程序

创建文件 `hello.nx`：

```nexa
agent Greeter {
    role: "Friendly Assistant",
    model: "gpt-4o-mini",
    prompt: "You are a friendly greeter. Greet the user warmly and briefly."
}

flow main() {
    result = Greeter.run("Hello, Nexa!");
    print(result);
}
```

### 运行程序

**方式 1: 使用 nexa 命令**

```bash
python -m src.cli run hello.nx
```

**方式 2: 使用 Python 直接运行**

```python
from src.nexa_parser import parse
from src.code_generator import CodeGenerator
from src.runtime.agent import NexaAgent

# 解析和编译
with open("hello.nx") as f:
    source = f.read()
    
ast = parse(source)
generator = CodeGenerator(ast)
python_code = generator.generate()

# 执行生成的代码
exec(python_code)
main()
```

**方式 3: 使用 SDK**

```python
import nexa

result = nexa.run("""
agent Greeter {
    role: "Friendly Assistant",
    model: "gpt-4o-mini",
    prompt: "Greet the user warmly."
}

flow main() {
    result = Greeter.run("Hello!");
    print(result);
}
""")
```

### 预期输出

```
Hello! Welcome to Nexa! I'm here to help you with anything you need.
```

（实际输出由 LLM 生成，内容可能略有不同）

---

## 📁 运行官方示例

项目 `examples/` 目录包含多个示例：

```bash
# Hello World
python -m src.cli run examples/01_hello_world.nx

# 管道与路由
python -m src.cli run examples/02_pipeline_and_routing.nx

# 批评循环
python -m src.cli run examples/03_critic_loop.nx

# DAG 拓扑
python -m src.cli run examples/15_dag_topology.nx
```

---

## ✅ 安装验证清单

完成以下检查确认安装成功：

- [ ] `python -c "from src import parse"` 无报错
- [ ] API 密钥已配置
- [ ] `hello.nx` 运行成功并输出问候语
- [ ] 至少一个 examples 示例运行成功

---

## 🐛 常见问题

### Q1: ModuleNotFoundError: No module named 'src'

**解决方案**: 确保在项目根目录运行命令，或使用 `pip install -e .` 安装。

### Q2: API key not found

**解决方案**: 检查环境变量是否正确设置：
```bash
echo $OPENAI_API_KEY  # Linux/macOS
echo %OPENAI_API_KEY%  # Windows
```

### Q3: Connection error / timeout

**解决方案**: 
- 检查网络连接
- 如果使用代理，设置 `HTTP_PROXY` 和 `HTTPS_PROXY`
- 如果使用国内服务，确保 `OPENAI_BASE_URL` 正确

### Q4: Python version mismatch

**解决方案**: 使用 pyenv 或 conda 创建 Python 3.10+ 环境：
```bash
# 使用 conda
conda create -n nexa python=3.10
conda activate nexa

# 使用 pyenv
pyenv install 3.10.0
pyenv local 3.10.0
```

---

## 📚 下一步

安装完成后，建议：

1. **阅读 Agent 指南**: 查看 [`AGENT_GUIDE.md`](AGENT_GUIDE.md) 学习 Nexa 语法
2. **运行更多示例**: 探索 `examples/` 目录中的示例代码
3. **编写自己的程序**: 使用 Agent Guide 中的模板创建新程序

---

## 🔗 有用的链接

- **GitHub 仓库**: https://github.com/ouyangyipeng/Nexa
- **在线文档（中文）**: https://ouyangyipeng.github.io/Nexa-docs/
- **在线文档（英文）**: https://ouyangyipeng.github.io/Nexa-docs/en/

---

*本文档专为 AI Agent 设计，帮助快速安装和验证 Nexa 语言。*