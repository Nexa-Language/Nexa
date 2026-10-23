# Nexa 2.4.0 安装与第一个程序

需要 Python 3.10+。使用 uv 创建独立环境并安装官方发行物：

```sh
uv venv --python 3.12
uv pip install "nexa-lang[anthropic,terminal,mcp] @ https://github.com/Nexa-Language/Nexa/releases/download/v2.4.0/nexa_lang-2.4.0-py3-none-any.whl"
source .venv/bin/activate
nexa --version
```

Windows PowerShell 使用 `.venv\Scripts\Activate.ps1` 激活。已有虚拟环境也可通过 `python -m pip install` 安装同一 wheel URL。PyPI 的 `nexa-lang` 属于另一项目，安装时使用完整发行物地址。版本应显示 `Nexa v2.4.0`。

将以下内容保存为 `hello.nx`：

```nexa
flow main {
    result = 23 + 19;
    print(result);
}
```

```sh
nexa build hello.nx
nexa run hello.nx
nexa inspect hello.nx --format json
```

程序输出 `42`。编译与纯计算程序无需模型凭据。构建会在源文件旁生成
`hello.py`；`run` 编译并执行源文件。项目外使用安装后的 `nexa` 命令，或以
`.venv/bin/nexa` 的绝对路径启动。

需要模型时先按 [首次模型配置](../docs/development.md#configure-your-first-model) 设置 endpoint、model ID 和凭据，再按照 [编写指南](AGENT_GUIDE.md)
声明 Agent。Chat/Responses 使用现有 provider 配置；原生 Anthropic 使用
`ANTHROPIC_API_KEY` 和可选 `ANTHROPIC_BASE_URL`。凭据保存在本地配置或环境中。

带审批的文件修改任务从 [Nexa Code](../examples/Nexa-Code/README.md) 开始，
使用 `nexa agent FILE NAME TASK` 保存 checkpoint，并检查每个待审批调用。
恢复时保持原工作目录和程序配置，总超时包含等待审批时间。

需要完整示例或 Rust AVM 时，检出源码 tag 并建立锁定开发环境：

```sh
git clone --branch v2.4.0 --depth 1 https://github.com/Nexa-Language/Nexa.git
cd Nexa
uv sync --locked --all-extras
uv run nexa --version
```

[开发与分发](../docs/development.md) 说明支持矩阵和测试方式；
[运行契约与迁移](../docs/runtime-v2.4.md) 说明预算、错误、恢复和能力范围。
